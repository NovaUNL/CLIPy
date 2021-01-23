import hashlib
import logging
import os
import pathlib
import traceback
from datetime import datetime
from queue import Queue
from threading import Thread, Lock
from time import sleep

import re

from sqlalchemy.exc import IntegrityError

from . import parser
from . import database as db
from .config import INSTITUTION_FIRST_YEAR, INSTITUTION_ID, FILE_SAVE_DIR
from .database import exceptions
from .session import Session as WebSession
from . import urls

log = logging.getLogger(__name__)


class PageCrawler(Thread):
    def __init__(self, name, clip_session: WebSession, db_registry: db.SessionRegistry, work_queue: Queue,
                 queue_lock: Lock, crawl_function):
        Thread.__init__(self)
        self.name = name
        self.web_session: WebSession = clip_session
        self.db_registry = db_registry
        self.work_queue = work_queue
        self.queue_lock = queue_lock
        self.crawl_function = crawl_function

    def run(self):
        db_session = self.db_registry.get_session()
        db_controller = db.Controller(self.db_registry)
        while True:
            self.queue_lock.acquire()
            if not self.work_queue.empty():
                work_unit = self.work_queue.get()
                self.queue_lock.release()
                exception_count = 0
                while True:
                    try:
                        self.crawl_function(self.web_session, db_controller, work_unit)
                        exception_count = 0
                        break
                    except Exception:
                        db_session.rollback()
                        exception_count += 1
                        log.error(f'Failed to complete the job for the work unit with the ID {work_unit.id}.'
                                  f'Error: \n{traceback.format_exc()}\n'
                                  f'Retrying in {5 + min(exception_count, 55)} seconds...')

                    if exception_count > 10:
                        log.critical(f"Thread failed for more than 10 times. Skipping work unit {work_unit.id}")
                        break
                    sleep(5 + min(exception_count, 55))
            else:
                self.queue_lock.release()
                break

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_registry.remove()


def crawl_departments(session: WebSession, database: db.Controller):
    """
    Finds new departments and adds them to the database. *NOT* thread-safe.

    :param session: Web session
    :param database: Database controller
    """
    found = {}  # id -> Department

    # Find the departments which existed each year
    for year in range(INSTITUTION_FIRST_YEAR, datetime.now().year + 2):
        log.info(f"Crawling departments of institution. Year:{year}")
        hierarchy = session.get_simplified_soup(urls.DEPARTMENTS.format(institution=INSTITUTION_ID, year=year))
        for department_id, name in parser.get_departments(hierarchy):
            if department_id in found:  # update creation year
                found[department_id].add_year(year)
            else:  # insert new
                department = db.candidates.Department(department_id, name, year, year)
                found[department_id] = department
    database.add_departments(found.values())


def crawl_buildings(session: WebSession, database: db.Controller):
    """
    Finds new buildings and adds them to the database. *NOT* thread-safe.

    :param session: Web session
    :param database: Database controller
    """

    buildings = {}  # id -> Candidate
    for year in range(INSTITUTION_FIRST_YEAR, datetime.now().year + 1):
        for period in database.get_period_set():
            log.info(f"Crawling buildings. Year:{year}. Period: {period}")
            page = session.get_simplified_soup(
                urls.BUILDINGS.format(
                    institution=INSTITUTION_ID,
                    year=year,
                    period=period['part'],
                    period_type=period['letter']))
            page_buildings = parser.get_buildings(page)
            for identifier, name in page_buildings:
                candidate = db.candidates.Building(identifier=identifier, name=name, first_year=year, last_year=year)
                if identifier in buildings:
                    other = buildings[identifier]
                    if other != candidate:
                        raise Exception("Found two different buildings going by the same ID")
                    other.add_year(year)
                else:
                    buildings[identifier] = candidate

    for building in buildings.values():
        log.debug(f"Adding building {building} to the database.")
        database.add_building(building)

integrated_master_name_exp = re.compile("Mestrado Integrado.*")

def crawl_courses(session: WebSession, database: db.Controller):
    """
    Finds new courses and adds them to the database. *NOT* thread-safe.

    :param session: Web session
    :param database: Database controller
    """
    courses = {}  # identifier -> Candidate pairs

    # Obtain course id-name pairs from the course list page
    page = session.get_simplified_soup(urls.COURSES.format(institution=INSTITUTION_ID))
    for identifier, name in parser.get_course_names(page):
        # Fetch the course curricular plan to find the activity years
        page = session.get_simplified_soup(urls.CURRICULAR_PLANS.format(institution=INSTITUTION_ID, course=identifier))
        first, last = parser.get_course_activity_years(page)
        candidate = db.candidates.Course(identifier, name, first_year=first, last_year=last)
        courses[identifier] = candidate

    # fetch course abbreviation from the statistics page
    # TODO redo degrees, make them a static entity
    integrated_master_degree = list(filter(lambda deg: deg.id == 4, database.get_degree_set()))[0]
    for degree in database.get_degree_set():
        if degree.id == 4:  # Skip integrated masters
            continue
        page = session.get_simplified_soup(urls.STATISTICS.format(institution=INSTITUTION_ID, degree=degree.iid))
        for identifier, abbreviation in parser.get_course_abbreviations(page):
            if identifier in courses:
                course = courses[identifier]
                courses[identifier].abbreviation = abbreviation
                if degree.id == 2 and abbreviation.startswith('MI'):  # Distinguish masters from integrated masters
                    course_page = session.get_simplified_soup(
                        urls.COURSE.format(institution=INSTITUTION_ID, course=course.id))
                    if course_page.find(text=integrated_master_name_exp):
                        courses[identifier].degree = integrated_master_degree
                    else:
                        courses[identifier].degree = degree
                else:
                    courses[identifier].degree = degree
            else:
                raise Exception(
                    "{}({}) was listed in the abbreviation list but a corresponding course wasn't found".format(
                        abbreviation, identifier))

    database.add_courses(courses.values())


def crawl_rooms(session: WebSession, database: db.Controller, building: db.models.Building):
    building = database.session.merge(building)
    rooms = {}  # id -> Candidate

    for year in range(building.first_year, building.last_year + 1):
        page = session.get_simplified_soup(urls.BUILDING_SCHEDULE.format(
            institution=INSTITUTION_ID,
            building=building.id,
            year=year,
            period=1,
            period_type='s',
            weekday=2))  # 2 is monday
        candidates = parser.get_places(page)
        if len(candidates) > 0:
            log.debug(f'Found the following rooms in {building}, {year}:\n{candidates}')
        for identifier, room_type, name in candidates:
            candidate = db.candidates.Room(identifier=identifier, room_type=room_type, name=name, building=building)
            if identifier in rooms:
                if rooms[identifier] != candidate:
                    raise Exception("Found two different rooms going by the same ID")
            else:
                rooms[identifier] = candidate
    for room in rooms.values():
        database.add_room(room)


def crawl_teachers(session: WebSession, database: db.Controller, department: db.models.Department):
    department = database.session.merge(department)
    periods = database.get_period_set()
    classes_instances_cache = dict()  # cache to avoid queries

    # for each year this institution operated (knowing that the first building was recorded in 2001)
    for year in range(department.first_year, department.last_year + 1):
        teachers = {}  # id -> Candidate
        for period in periods:
            page = session.get_simplified_soup(urls.DEPARTMENT_TEACHERS.format(
                institution=INSTITUTION_ID,
                department=department.id,
                year=year,
                period=period['part'],
                period_type=period['letter']))
            candidates = parser.get_teachers(page)
            for identifier, name in candidates:
                # If there's a single teacher for a given period, a page with his/her schedule is served instead.
                # In those pages only the first match is the teacher, the second and so on aren't relevant.
                if name == 'Ficheiro':
                    break

                if identifier in teachers:
                    teacher = teachers[identifier]
                    if teacher.name != name:
                        raise Exception(f'Found two teachers with the same id ({identifier}).\n'
                                        f'\tT1:"{teachers[identifier].name}"\n\tT2:{name}')
                    teacher.add_year(year)
                else:
                    teacher = db.candidates.Teacher(
                        identifier=identifier,
                        name=name,
                        department=department,
                        first_year=year,
                        last_year=year)
                    teachers[identifier] = teacher

                schedule_page = session.get_simplified_soup(urls.TEACHER_SCHEDULE.format(
                    teacher=identifier,
                    institution=INSTITUTION_ID,
                    department=department.id,
                    year=year,
                    period=period['part'],
                    period_type=period['letter']))

                while True:  # Cycle in case classes get added during the first iteration
                    for shift_link_tag in schedule_page.find_all(href=urls.SHIFT_LINK_EXP):
                        shift_link = shift_link_tag.attrs['href']
                        class_match = urls.CLASS_ALT_EXP.search(shift_link)
                        if class_match is None:
                            raise Exception(f"Failed to match a class identifier in {shift_link}")
                        class_id = int(class_match.group(1))
                        shift_match = urls.SHIFT_LINK_EXP.search(shift_link)
                        if class_match is None:
                            raise Exception(f"Failed to match a shift in {shift_link}")
                        shift_type = database.get_shift_type(shift_match.group('type'))
                        if shift_type is None:
                            logging.error("Unknown shift type %s" % shift_match.group('type'))
                            continue
                        shift_number = shift_match.group('number')
                        class_instance_key = (class_id, year, period['id'])
                        if class_instance_key in classes_instances_cache:
                            class_instance = classes_instances_cache[class_instance_key]
                        else:
                            class_instance = database.get_class_instance(class_id, year, period['id'])
                            if class_instance is None:
                                logging.error("Teacher schedule has unknown class")
                                crawl_class_instance(session, database, class_id, year, period)
                                continue
                            classes_instances_cache[class_instance_key] = class_instance
                        shift = database.get_shift(class_instance, shift_type, shift_number)
                        if shift is None:
                            logging.error(f"Unknown shift {class_instance} - {shift_type} {shift_number}")
                            crawl_class_shifts(session, database, class_instance)
                            continue
                        teacher.add_shift(shift)
                    break

        for candidate in teachers.values():
            database.add_teacher(candidate)


def _crawl_class(session: WebSession, database: db.Controller, class_id, year, period,
                 name=None, department=None):
    # Fetch abbreviation and number of ECTSs
    page = session.get_simplified_soup(urls.CLASS_IDENTITY.format(
        institution=INSTITUTION_ID,
        year=year,
        period=period['part'],
        period_type=period['letter'],
        class_id=class_id))
    instance_name, abbr, ects = parser.get_class_identity(page, class_id)

    # Alternative
    # page = session.get_simplified_soup(urls.CLASS.format(
    #     institution=INSTITUTION_ID,
    #     year=year,
    #     period=period['part'],
    #     period_type=period['letter'],
    #     class_id=class_id))
    # instance_name, abbr, ects = parser.get_class_instance(page, class_id)

    if name is not None and name != instance_name:
        log.error(f"Class name and instance name don't match {instance_name}/{name} ({class_id})")
        if instance_name is None:
            instance_name = name

    return database.add_class(
        db.candidates.Class(
            identifier=class_id,
            name=instance_name,
            department=department,
            abbreviation=abbr,
            ects=ects))


def crawl_class_instance(session: WebSession, database: db.Controller, class_id: int, year: int, period):
    klass = _crawl_class(session, database, class_id, year, period)
    new_class_instances = database.add_class_instances([db.candidates.ClassInstance(klass, period['id'], year)])
    if len(new_class_instances) > 0:
        _populate_new_class_instances(session, database, new_class_instances)


period_exp = re.compile('&tipo_de_per%EDodo_lectivo=(?P<type>\w)&per%EDodo_lectivo=(?P<stage>\d)$')


def crawl_classes(session: WebSession, database: db.Controller, department: db.models.Department):
    department = database.session.merge(department)
    log.debug("Crawling classes in department %s" % department.id)
    classes = {}
    class_instances = []

    # for each year this department operated
    for year in range(department.first_year, department.last_year + 1):
        page = session.get_simplified_soup(urls.DEPARTMENT_PERIODS.format(
            institution=INSTITUTION_ID,
            department=department.id,
            year=year))

        period_links = page.find_all(href=period_exp)

        # for each period this department teaches
        for period_link in period_links:
            match = period_exp.search(period_link.attrs['href'])
            period_type = match.group("type")
            part = int(match.group("stage"))
            if period_type == 'a':
                parts = 1
            elif period_type == 's':
                parts = 2
            elif period_type == 't':
                parts = 4
            else:
                parts = None

            period = database.get_period(part, parts)

            if period is None:
                raise Exception("Unknown period")

            page = session.get_simplified_soup(urls.DEPARTMENT_CLASSES.format(
                institution=INSTITUTION_ID,
                department=department.id,
                year=year,
                period=period['part'],
                period_type=period['letter']))

            class_links = page.find_all(href=urls.CLASS_EXP)

            # for each class in this period
            for class_link in class_links:
                class_id = int(urls.CLASS_EXP.findall(class_link.attrs['href'])[0])
                class_name = class_link.contents[0].strip()
                if class_id not in classes:
                    classes[class_id] = _crawl_class(
                        session, database, class_id, year, period,
                        name=class_name, department=department)

                if classes[class_id] is None:
                    raise Exception("Null class")
                class_instances.append(db.candidates.ClassInstance(classes[class_id], period['id'], year, department))
    new_class_instances = database.add_class_instances(class_instances)
    if len(new_class_instances) > 0:
        _populate_new_class_instances(session, database, new_class_instances)


def _populate_new_class_instances(session: WebSession, database: db.Controller, new_class_instances):
    for instance in new_class_instances:
        crawl_class_info(session, database, instance)
        crawl_class_shifts(session, database, instance)
        crawl_class_enrollments(session, database, instance)
        crawl_class_events(session, database, instance)
        crawl_grades(session, database, instance)
        crawl_files(session, database, instance)


def crawl_admissions(session: WebSession, database: db.Controller, year):
    admissions = []
    if year < 2006:
        return
    log.debug(f"Crawling admissions for the year {year}")
    course_ids = set()  # Courses found in this year's page
    page = session.get_simplified_soup(urls.ADMISSIONS.format(institution=INSTITUTION_ID, year=year))
    course_links = page.find_all(href=urls.COURSE_EXP)
    for course_link in course_links:  # For every found course
        course_id = int(urls.COURSE_EXP.findall(course_link.attrs['href'])[0])
        course_ids.add(course_id)

    for course_id in course_ids:
        course = database.get_course(identifier=course_id, year=year)
        if course is None:
            log.error(f"Unable to fetch the course with the internal identifier {course_id}. Skipping.")
            continue
        for phase in range(1, 4):  # For every of the three phases
            page = session.get_simplified_soup(urls.ADMITTED.format(
                institution=INSTITUTION_ID,
                year=year,
                course=course_id,
                phase=phase))
            candidates = parser.get_admissions(page)
            for name, option, student_id, state in candidates:
                student = None
                if student_id:  # if the student has an id add him/her to the database
                    student = database.add_student(
                        db.candidates.Student(
                            identifier=student_id,
                            name=name,
                            course=course,
                            first_year=year,
                            last_year=year))

                name = name if student is None else None
                admission = db.candidates.Admission(student, name, course, phase, year, option, state)
                admissions.append(admission)
    database.add_admissions(admissions)


def crawl_class_enrollments(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    log.debug("Crawling enrollments in class instance ID %s" % class_instance.id)
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    year = class_instance.year

    page = session.get_simplified_soup(urls.CLASS_ENROLLED.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.id))

    # Strip file header and split it into lines
    if len(page.find_all(string=re.compile("Pedido inválido"))) > 0:
        log.debug("Instance skipped")
        return

    enrollments = []
    for student_id, name, abbreviation, statutes, course_abbr, attempt, student_year in parser.get_enrollments(page):
        try:
            course = database.get_course(abbreviation=course_abbr, year=class_instance.year)
        except exceptions.MultipleMatches:
            # TODO propagate unresolvable course abbreviations
            # from students of the same course abbreviation with a known course.
            course = None
            log.error(f"Unable to determine which course is {course_abbr} in {class_instance.year}. "
                      "Got multiple matches.")
        # TODO consider sub-courses EG: MIEA/[Something]
        observation = course_abbr if course is not None else (course_abbr + "(Unknown)")
        # update student info and take id
        student_candidate = db.candidates.Student(
            identifier=student_id,
            name=name,
            abbreviation=abbreviation,
            course=course,
            first_year=year,
            last_year=year)
        try:
            student = database.add_student(student_candidate)
        except IntegrityError:
            # Quite likely that multiple threads found the student at the same time. Give it another chance
            sleep(3)
            student = database.add_student(student_candidate)
        except exceptions.IdCollision as e:
            log.error(str(e))
            continue

        enrollment = db.candidates.Enrollment(student, class_instance, attempt, student_year, statutes, observation)
        enrollments.append(enrollment)
    database.add_enrollments(enrollments)


def crawl_class_info(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    log.debug("Crawling info from class instance ID %s" % class_instance.id)
    class_instance = database.session.merge(class_instance)
    class_info = {}

    args = {
        'institution': INSTITUTION_ID,
        'year': class_instance.year,
        'period': class_instance.period.part,
        'period_type': class_instance.period.letter,
        'class_id': class_instance.parent.id
    }
    page = session.get_broken_simplified_soup(urls.CLASS_DESCRIPTION.format(**args))
    class_info['description'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_OBJECTIVES.format(**args))
    class_info['objectives'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_REQUIREMENTS.format(**args))
    class_info['requirements'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_COMPETENCES.format(**args))
    class_info['competences'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_PROGRAM.format(**args))
    class_info['program'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_BIBLIOGRAPHY.format(**args))
    class_info['bibliography'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_ASSISTANCE.format(**args))
    class_info['assistance'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_TEACHING_METHODS.format(**args))
    class_info['teaching_methods'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_EVALUATION_METHODS.format(**args))
    class_info['evaluation_methods'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_EXTRA.format(**args))
    class_info['extra_info'] = parser.get_bilingual_info(page)
    database.update_class_instance_info(class_instance, class_info)


def crawl_class_events(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    log.debug("Crawling events from class instance ID %s" % class_instance.id)
    class_instance = database.session.merge(class_instance)

    page = session.get_broken_simplified_soup(urls.CLASS_EVENTS.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        class_id=class_instance.parent.id,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))
    events = parser.get_class_events(page)
    database.update_class_instance_events(class_instance, events)


def crawl_class_shifts(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    """
    Updates information on shifts belonging to a given class instance.
    :param session: Browsing session
    :param database: Database controller
    :param class_instance: ClassInstance object to look after
    """
    log.debug("Crawling shifts class instance ID %s" % class_instance.id)
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    year = class_instance.year

    # --- Prepare the list of shifts to crawl ---
    page = session.get_simplified_soup(urls.CLASS_SHIFTS.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        class_id=class_instance.parent.id,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))
    try:
        page.find('td', class_="barra_de_escolhas").find('table').decompose()  # Delete block with other instances
    except AttributeError:
        print()

    # When there is only one shift, the received page is the shift itself. (CLASS_SHIFT instead of CLASS_SHIFTS)
    single_shift = False
    shift_count = 0  # consistency check

    shift_type = None
    shift_number = None

    shift_links = page.find_all(href=urls.SHIFT_LINK_EXP)
    for shift_link in shift_links:
        if "aux=ficheiro" in shift_link.attrs['href'].lower():
            # there are no file links in shift lists, but they do exist on shift pages
            single_shift = True
        else:
            shift_count += 1
            shift_link_matches = urls.SHIFT_LINK_EXP.search(shift_link.attrs['href'])
            shift_type = shift_link_matches.group("type")
            shift_number = int(shift_link_matches.group("number"))

    shift_pages = []  # pages for shift parsing
    if single_shift:  # if the loaded page is the only shift
        if shift_count > 1:
            raise Exception(
                f"Class instance {class_instance}, previously though to have one single shift now has many!")
        if shift_count == 0:
            log.info("Shift page without any shift. Skipping")
            return
        shift_pages.append((page, shift_type, shift_number))  # save it, avoid requesting it again
    else:  # if there are multiple shifts then request them
        for shift_link in shift_links:
            shift_page = session.get_simplified_soup(urls.ROOT + shift_link.attrs['href'])
            shift_link_matches = urls.SHIFT_LINK_EXP.search(shift_link.attrs['href'])
            shift_type = shift_link_matches.group("type")
            shift_number = int(shift_link_matches.group("number"))
            shift_pages.append((shift_page, shift_type, shift_number))  # and save them with their metadata

    # --- Crawl found shifts ---
    for page, shift_type, shift_number in shift_pages:  # for every shift in this class instance
        # Create shift
        instances, routes, teachers_names, restrictions, minutes, state, enrolled, capacity \
            = parser.get_shift_info(page)
        routes_str = None  # TODO get rid of this pseudo-array after the curricular plans are done.
        for route in routes:
            if routes_str is None:
                routes_str = route
            else:
                routes_str += (';' + route)

        shift_type = database.get_shift_type(shift_type)
        if shift_type is None:
            log.error(f"Unable to resolve shift type {shift_pages[1]}.\n\tWas crawling {class_instance}, skipping!")
            continue
        shift = database.add_shift(
            db.candidates.Shift(
                class_instance=class_instance,
                number=shift_number,
                shift_type=shift_type,
                enrolled=enrolled,
                capacity=capacity,
                minutes=minutes,
                routes=routes_str,
                restrictions=restrictions,
                state=state))

        # Create instances of this shift
        instances_aux = instances
        instances = []
        for weekday, start, end, building, room in instances_aux:
            if building:
                building = database.get_building(building)
                if room:
                    room = database.get_room(room[0], building, room_type=room[1])
                    if room is None:
                        log.warning(f"{shift_type}{shift_number} of {class_instance} "
                                    "couldn't be matched against a room.")
            instances.append(db.candidates.ShiftInstance(shift, start, end, weekday, room=room))
        del instances_aux
        database.add_shift_instances(instances)

        # Assign students to this shift
        students = []
        for name, student_id, abbreviation, course_abbreviation in parser.get_shift_students(page):
            course = database.get_course(abbreviation=course_abbreviation, year=year)
            student = database.add_student(
                db.candidates.Student(
                    identifier=student_id,
                    name=name,
                    course=course,
                    abbreviation=abbreviation,
                    first_year=year,
                    last_year=year))
            students.append(student)
        database.add_shift_students(shift, students)


def crawl_files(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    """
    Finds files uploaded to a class instance.
    :param session: Browsing session
    :param database: Database controller
    :param class_instance: ClassInstance object to look after
    """
    log.debug("Crawling class instance ID %s files" % class_instance.id)
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    department = class_instance.department
    known_file_ids = {file.id for file in class_instance.files}

    page = session.get_simplified_soup(urls.CLASS_FILE_TYPES.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        class_id=class_instance.parent.id,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))

    file_types = parser.get_file_types(page)

    for file_type, _ in file_types:
        page = session.get_simplified_soup(urls.CLASS_FILES.format(
            institution=INSTITUTION_ID,
            year=class_instance.year,
            class_id=class_instance.parent.id,
            period=class_instance.period.part,
            period_type=class_instance.period.letter,
            file_type=file_type.to_url_argument()))
        files = parser.get_files(page)
        for identifier, name, size, upload_datetime, uploader in files:
            if identifier not in known_file_ids:
                candidate = db.candidates.File(
                    identifier=identifier,
                    name=name,
                    size=size,
                    upload_datetime=upload_datetime,
                    uploader=uploader,
                    file_type=file_type)
                database.add_class_file(candidate=candidate, class_instance=class_instance)
    # TODO deletion


def download_files(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    class_files = class_instance.file_relations
    poked_file_types = set()

    for class_file in class_files:
        if not class_file.file.downloaded:
            file_type = class_file.file_type
            if file_type not in poked_file_types:
                poked_file_types.add(file_type)

                # poke the page, this is required to download, for some reason...
                session.get_simplified_soup(urls.CLASS_FILES.format(
                    institution=INSTITUTION_ID,
                    year=class_instance.year,
                    department=class_instance.department.id,
                    class_id=class_instance.parent.id,
                    period=class_instance.period.part,
                    period_type=class_instance.period.letter,
                    file_type=class_file.file_type.to_url_argument()))

            response = session.get_file(urls.FILE_URL.format(file_identifier=class_file.file.id))
            if response is None:
                raise Exception("Unable to download file")
            content, mime = response
            hasher = hashlib.sha1()
            hasher.update(content)
            sha1 = hasher.hexdigest()
            file: db.models.File

            dir_name = f"{FILE_SAVE_DIR}/{sha1[:2]}"
            dir_path = pathlib.Path(dir_name)
            if dir_path.exists():
                if not dir_path.is_dir():
                    raise Exception("File with illegal name")
            else:
                os.mkdir(dir_name)

            path = f"{dir_name}/{sha1[2:]}"
            if os.path.isfile(path):
                log.info(f"{class_file} was already saved ({sha1})")
            else:
                log.info(f"Saving {class_file} as {sha1}")
                with open(path, 'wb') as fd:
                    fd.write(content)

            database.update_downloaded_file(file=class_file.file, hash=sha1, mime=mime)


def crawl_grades(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)

    if len(class_instance.enrollments) == 0:
        return  # Class has no one enrolled, nothing to see here...

    # Grades
    page = session.get_simplified_soup(urls.CLASS_RESULTS.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        class_id=class_instance.parent.id,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))

    course_links = page.find_all(href=urls.COURSE_EXP)

    for link in course_links:
        page = session.get_simplified_soup(urls.ROOT + link.attrs['href'])
        results = parser.get_results(page)

        for student, evaluations, approved in results:
            student_number, student_name, gender = student
            db_student = database.get_student(identifier=student_number)

            if db_student is None:
                raise Exception("Student dodged the enrollment search.\n" + student)

            if db_student.gender is None and gender is not None:
                if gender == 'f':
                    gender = 0
                elif gender == 'm':
                    gender = 1
                else:
                    raise Exception("Impossible gender")
                database.update_student_gender(student=db_student, gender=gender)
            database.update_enrollment_results(
                student=db_student,
                class_instance=class_instance,
                results=evaluations,
                approved=approved)

    # Attendance
    page = session.get_simplified_soup(urls.CLASS_ATTENDANCE.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        class_id=class_instance.parent.id,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))
    course_links = page.find_all(href=urls.COURSE_EXP)

    for link in course_links:
        page = session.get_simplified_soup(urls.ROOT + link.attrs['href'])
        for student, attendance, date in parser.get_attendance(page):
            db_student = database.get_student(student[0])
            if db_student is None:
                raise Exception("Student dodged the enrollment search.\n" + student)
            database.update_enrollment_attendance(
                student=db_student,
                class_instance=class_instance,
                attendance=attendance,
                date=date)

    # Improvements
    page = session.get_simplified_soup(urls.CLASS_IMPROVEMENTS.format(
        institution=INSTITUTION_ID,
        year=class_instance.year,
        class_id=class_instance.parent.id,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))
    course_links = page.find_all(href=urls.COURSE_EXP)

    for link in course_links:
        page = session.get_simplified_soup(urls.ROOT + link.attrs['href'])
        for student, improved, grade, date in parser.get_improvements(page):
            db_student = database.get_student(student[0])
            if db_student is None:
                log.error("Student dodged the enrollment search.\n" + student)

            database.update_enrollment_improvement(
                student=db_student,
                class_instance=class_instance,
                improved=improved,
                grade=grade,
                date=date)


def crawl_library_individual_room_availability(session: WebSession, date: datetime.date):
    page = session.get_broken_simplified_soup(
        urls.LIBRARY_INDIVIDUAL_ROOMS,
        post_data={
            'submit:reservas:es': 'Ver+disponibilidade',
            'data': date.isoformat()})
    return parser.get_library_room_availability(page)


def crawl_library_group_room_availability(session: WebSession, date: datetime.date):
    page = session.get_broken_simplified_soup(
        urls.LIBRARY_GROUP_ROOMS,
        post_data={
            'submit:reservas:es': 'Ver+disponibilidade',
            'data': date.isoformat()})
    return parser.get_library_group_room_availability(page)

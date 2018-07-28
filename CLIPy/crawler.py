import hashlib
import logging
import os
import traceback
from queue import Queue
from threading import Thread, Lock
from time import sleep

import re

from sqlalchemy.exc import IntegrityError

from . import parser
from . import database as db
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
                        log.critical("Thread {} failed for more than 10 times. Skipping work unit " + work_unit)
                        break
                    sleep(5 + min(exception_count, 55))
            else:
                self.queue_lock.release()
                break

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_registry.remove()


def crawl_rooms(session: WebSession, database: db.Controller, institution: db.models.Institution):
    institution = database.session.merge(institution)
    rooms = {}  # id -> Candidate
    buildings = database.get_building_set()

    # for each year this institution operated (knowing that the first building was recorded in 2001)
    for year in range(max(2001, institution.first_year), institution.last_year + 1):
        for building in buildings:
            page = session.get_simplified_soup(urls.BUILDING_SCHEDULE.format(
                institution=institution.id,
                building=building.id,
                year=year,
                period=1,
                period_type='s',
                weekday=2))  # 2 is monday
            candidates = parser.get_places(page)
            if len(candidates) > 0:
                log.info(f'Found the following rooms in {building}, {year}:\n{candidates}')
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
    teachers = {}  # id -> Candidate
    periods = database.get_period_set()

    # for each year this institution operated (knowing that the first building was recorded in 2001)
    for year in range(department.first_year, department.last_year + 1):
        for period in periods:
            page = session.get_simplified_soup(urls.DEPARTMENT_TEACHERS.format(
                institution=department.institution.id,
                department=department.id,
                year=year,
                period=period.part,
                period_type=period.letter))
            candidates = parser.get_teachers(page)
            for identifier, name in candidates:
                # If there's a single teacher for a given period, a page with his/her schedule is served instead.
                # In those pages only the first match is the teacher, the second and so on aren't relevant.
                if name == 'Ficheiro':
                    break

                if identifier in teachers:
                    if teachers[identifier].name != name:
                        raise Exception(f'Found two teachers with the same id ({identifier}).\n'
                                        f'\tT1:"{teachers[identifier].name}"\n\tT2:{name}')
                    teachers[identifier].add_year(year)
                else:
                    teachers[identifier] = db.candidates.Teacher(
                        identifier=identifier,
                        name=name,
                        department=department,
                        first_year=year,
                        last_year=year)
    for candidate in teachers.values():
        database.add_teacher(candidate)


def crawl_classes(session: WebSession, database: db.Controller, department: db.models.Department):
    department = database.session.merge(department)
    classes = {}
    class_instances = []

    period_exp = re.compile('&tipo_de_per%EDodo_lectivo=(?P<type>\w)&per%EDodo_lectivo=(?P<stage>\d)$')
    abbr_exp = re.compile('\(.+\) .* \((?P<abbr>.+)\)$')
    ects_exp = re.compile('(?P<ects>\d|\d.\d)\s?ECTS.*')

    # for each year this department operated
    for year in range(department.first_year, department.last_year + 1):
        page = session.get_simplified_soup(urls.DEPARTMENT_PERIODS.format(
            institution=department.institution.id,
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

            period = database.get_period(part, parts)
            page = session.get_simplified_soup(urls.DEPARTMENT_CLASSES.format(
                institution=department.institution.id,
                department=department.id,
                year=year,
                period=part,
                period_type=period_type))

            class_links = page.find_all(href=urls.CLASS_EXP)

            # for each class in this period
            for class_link in class_links:
                class_id = int(urls.CLASS_EXP.findall(class_link.attrs['href'])[0])
                class_name = class_link.contents[0].strip()
                if class_id not in classes:
                    # Fetch abbreviation and number of ECTSs
                    page = session.get_simplified_soup(urls.CLASS.format(
                        institution=department.institution.id,
                        year=year,
                        department=department.id,
                        period=part,
                        period_type=period_type,
                        class_id=class_id))
                    elements = page.find_all('td', attrs={'class': 'subtitulo'})
                    abbr = None
                    ects = None
                    try:
                        abbr_matches = abbr_exp.search(elements[0].text)
                        abbr = str(abbr_matches.group('abbr')).strip()
                    except:
                        log.warning(f'Class {class_name}({class_id}) has no abbreviation')

                    try:
                        ects_matches = ects_exp.search(elements[1].text)
                        ects_s = str(ects_matches.group('ects')).strip()
                        # ECTSs are stored in halves. Someone decided it would be cool to award half ECTS...
                        ects = int(float(ects_s) * 2)
                    except:
                        log.warning(f'Class {class_name}({class_id}) has no ECTS information')

                    classes[class_id] = database.add_class(
                        db.candidates.Class(
                            identifier=class_id,
                            name=class_name,
                            department=department,
                            abbreviation=abbr,
                            ects=ects))

                if classes[class_id] is None:
                    raise Exception("Null class")
                class_instances.append(db.candidates.ClassInstance(classes[class_id], period, year))
    database.add_class_instances(class_instances)


def crawl_admissions(session: WebSession, database: db.Controller, institution: db.models.Institution):
    institution = database.session.merge(institution)
    admissions = []
    years = range(max(institution.first_year, 2006), institution.last_year + 1)  # TODO put that magic number in a conf
    for year in years:
        log.info(f"Crawling {institution} admissions for the year {year}")
        course_ids = set()  # Courses found in this year's page
        page = session.get_simplified_soup(urls.ADMISSIONS.format(institution=institution.id, year=year))
        course_links = page.find_all(href=urls.COURSE_EXP)
        for course_link in course_links:  # For every found course
            course_id = int(urls.COURSE_EXP.findall(course_link.attrs['href'])[0])
            course_ids.add(course_id)

        for course_id in course_ids:
            course = database.get_course(identifier=course_id, institution=institution)
            if course is None:
                log.error("Unable to fetch the course with the internal identifier {course_id}. Skipping.")
                continue
            for phase in range(1, 4):  # For every of the three phases
                page = session.get_simplified_soup(urls.ADMITTED.format(
                    institution=institution.id,
                    year=year,
                    course=course_id,
                    phase=phase))
                candidates = parser.get_admissions(page)
                for name, option, student_iid, state in candidates:
                    student = None
                    if student_iid:  # if the student has an id add him/her to the database
                        student = database.add_student(
                            db.candidates.Student(
                                identifier=student_iid,
                                name=name,
                                course=course,
                                institution=institution,
                                first_year=year,
                                last_year=year))

                    name = name if student is None else None
                    admission = db.candidates.Admission(student, name, course, phase, year, option, state)
                    admissions.append(admission)
    database.add_admissions(admissions)


def crawl_class_enrollments(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    log.info("Crawling class instance ID %s" % class_instance.id)
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    institution = class_instance.parent.department.institution
    year = class_instance.year

    page = session.get_simplified_soup(urls.CLASS_ENROLLED.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))

    # Strip file header and split it into lines
    if len(page.find_all(string=re.compile("Pedido inválido"))) > 0:
        log.debug("Instance skipped")
        return

    enrollments = []
    for student_id, name, abbreviation, statutes, course_abbr, attempt, student_year in parser.get_enrollments(page):
        course = database.get_course(abbreviation=course_abbr, year=class_instance.year, institution=institution)

        # TODO consider sub-courses EG: MIEA/[Something]
        observation = course_abbr if course is not None else (course_abbr + "(Unknown)")
        # update student info and take id
        student_candidate = db.candidates.Student(
            identifier=student_id,
            name=name,
            abbreviation=abbreviation,
            course=course,
            institution=institution,
            first_year=year,
            last_year=year)
        try:
            student = database.add_student(student_candidate)
        except IntegrityError:
            # Quite likely that multiple threads found the student at the same time. Give it another chance
            sleep(3)
            student = database.add_student(student_candidate)

        enrollment = db.candidates.Enrollment(student, class_instance, attempt, student_year, statutes, observation)
        enrollments.append(enrollment)

    database.add_enrollments(enrollments)


def crawl_class_info(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    log.info("Crawling class instance ID %s" % class_instance.id)
    class_instance = database.session.merge(class_instance)
    institution = class_instance.parent.department.institution
    class_info = {}

    page = session.get_broken_simplified_soup(urls.CLASS_DESCRIPTION.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['description'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_OBJECTIVES.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['objectives'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_REQUIREMENTS.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['requirements'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_COMPETENCES.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['competences'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_PROGRAM.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['program'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_BIBLIOGRAPHY.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['bibliography'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_ASSISTANCE.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['assistance'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_TEACHING_METHODS.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['teaching_methods'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_EVALUATION_METHODS.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['evaluation_methods'] = parser.get_bilingual_info(page)
    page = session.get_broken_simplified_soup(urls.CLASS_EXTRA.format(
        institution=institution.id,
        department=class_instance.parent.department.id,
        year=class_instance.year,
        period=class_instance.period.part,
        period_type=class_instance.period.letter,
        class_id=class_instance.parent.iid))
    class_info['extra_info'] = parser.get_bilingual_info(page)
    database.update_class_instance_info(class_instance, class_info)


def crawl_class_turns(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    """
    Updates information on turns belonging to a given class instance.
    :param session: Browsing session
    :param database: Database controller
    :param class_instance: ClassInstance object to look after
    """
    log.info("Crawling class instance ID %s" % class_instance.id)
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    department = class_instance.parent.department
    institution = department.institution
    year = class_instance.year

    # --- Prepare the list of turns to crawl ---
    page = session.get_simplified_soup(urls.CLASS_TURNS.format(
        institution=institution.id,
        year=class_instance.year,
        department=class_instance.parent.department.id,
        class_id=class_instance.parent.iid,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))

    # When there is only one turn, the received page is the turn itself. (CLASS_TURN instead of CLASS_TURNS)
    single_turn = False
    turn_count = 0  # consistency check

    turn_type = None
    turn_number = None

    turn_links = page.find_all(href=urls.TURN_LINK_EXP)
    for turn_link in turn_links:
        if "aux=ficheiro" in turn_link.attrs['href'].lower():
            # there are no file links in turn lists, but they do exist on turn pages
            single_turn = True
        else:
            turn_count += 1
            turn_link_matches = urls.TURN_LINK_EXP.search(turn_link.attrs['href'])
            turn_type = turn_link_matches.group("type")
            turn_number = int(turn_link_matches.group("number"))

    turn_pages = []  # pages for turn parsing
    if single_turn:  # if the loaded page is the only turn
        if turn_count > 1:
            raise Exception("Class instance though to have one single turn now has many!")
        if turn_count == 0:
            log.warning("Turn page without any turn. Skipping")
            return
        turn_pages.append((page, turn_type, turn_number))  # save it, avoid requesting it again
    else:  # if there are multiple turns then request them
        for turn_link in turn_links:
            turn_page = session.get_simplified_soup(urls.ROOT + turn_link.attrs['href'])
            turn_link_matches = urls.TURN_LINK_EXP.search(turn_link.attrs['href'])
            turn_type = turn_link_matches.group("type")
            turn_number = int(turn_link_matches.group("number"))
            turn_pages.append((turn_page, turn_type, turn_number))  # and save them with their metadata

    # --- Crawl found turns ---
    for page, turn_type, turn_number in turn_pages:  # for every turn in this class instance
        # Create turn
        instances, routes, teachers_names, restrictions, minutes, state, enrolled, capacity = parser.get_turn_info(page)
        routes_str = None  # TODO get rid of this pseudo-array after the curricular plans are done.
        for route in routes:
            if routes_str is None:
                routes_str = route
            else:
                routes_str += (';' + route)

        turn_type = database.get_turn_type(turn_type)
        teachers = []
        for name in teachers_names:
            teacher = database.get_teacher(name=name, department=department)
            if teacher is None:
                log.warning(f'Unknown teacher {name}')
            else:
                teachers.append(teacher)
        turn = database.add_turn(
            db.candidates.Turn(
                class_instance=class_instance,
                number=turn_number,
                turn_type=turn_type,
                enrolled=enrolled,
                capacity=capacity,
                minutes=minutes,
                routes=routes_str,
                restrictions=restrictions,
                state=state,
                teachers=teachers))

        # Create instances of this turn
        instances_aux = instances
        instances = []
        for weekday, start, end, building, room in instances_aux:
            if building:
                building = database.get_building(building)
                if room:
                    room = database.get_room(room[0], building, room_type=room[1])
                    if room is None:
                        log.warning(f"{turn_type}{turn_number} of {class_instance} couldn't be matched against a room.")
            instances.append(db.candidates.TurnInstance(turn, start, end, weekday, room=room))
        del instances_aux
        database.add_turn_instances(instances)

        # Assign students to this turn
        students = []
        for name, student_id, abbreviation, course_abbreviation in parser.get_turn_students(page):
            course = database.get_course(abbreviation=course_abbreviation, year=year, institution=institution)
            student = database.add_student(
                db.candidates.Student(
                    identifier=student_id,
                    name=name,
                    course=course,
                    institution=institution,
                    abbreviation=abbreviation,
                    first_year=year,
                    last_year=year))
            students.append(student)
        database.add_turn_students(turn, students)


def crawl_files(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    """
    Finds files uploaded to a class instance.
    :param session: Browsing session
    :param database: Database controller
    :param class_instance: ClassInstance object to look after
    """
    log.info("Crawling class instance ID %s files" % class_instance.id)
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    department = class_instance.parent.department
    institution = department.institution
    known_file_count = 0
    known_file_ids = []

    for file in class_instance.files:
        known_file_ids.append(file.id)
        known_file_count += 1

    page = session.get_simplified_soup(urls.CLASS_FILE_TYPES.format(
        institution=institution.id,
        year=class_instance.year,
        department=class_instance.parent.department.id,
        class_id=class_instance.parent.iid,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))

    file_types = parser.get_file_types(page)

    current_file_count = 0
    for _, count in file_types:
        current_file_count += count

    if known_file_count == current_file_count != 0:
        log.info("Le moi thinks that every file is known (unless sneaky sneaky teachers deleted stuff and re-added)")
        return

    for file_type, _ in file_types:
        page = session.get_simplified_soup(urls.CLASS_FILES.format(
            institution=institution.id,
            year=class_instance.year,
            department=class_instance.parent.department.id,
            class_id=class_instance.parent.iid,
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


def download_files(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    department = class_instance.parent.department
    institution = department.institution
    files = class_instance.files
    poked_file_types = set()

    for file in files:
        if not file.downloaded():
            file_type = file.file_type
            if file_type not in poked_file_types:
                poked_file_types.add(file_type)

                # poke the page, this is required to download, for some reason...
                session.get_simplified_soup(urls.CLASS_FILES.format(
                    institution=institution.id,
                    year=class_instance.year,
                    department=class_instance.parent.department.id,
                    class_id=class_instance.parent.iid,
                    period=class_instance.period.part,
                    period_type=class_instance.period.letter,
                    file_type=file.file_type.to_url_argument()))

            response = session.get_file(urls.FILE_URL.format(file_identifier=file.id))
            if response is None:
                raise Exception("Unable to download file")
            content, mime = response
            hasher = hashlib.sha1()
            hasher.update(content)
            sha1 = hasher.hexdigest()
            file: db.models.File

            path = './files/' + sha1

            if os.path.isfile(path):
                log.info(f"{file} was already saved ({sha1})")
            else:
                log.info(f"Saving {file} as {sha1}")
                with open(path, 'wb') as fd:
                    fd.write(content)

            database.update_downloaded_file(file=file, hash=sha1, path=path, mime=mime)


def crawl_grades(session: WebSession, database: db.Controller, class_instance: db.models.ClassInstance):
    class_instance: db.models.ClassInstance = database.session.merge(class_instance)
    department = class_instance.parent.department
    institution = department.institution

    if len(class_instance.enrollments) == 0:
        return  # Class has no one enrolled, nothing to see here...

    # Grades
    page = session.get_simplified_soup(urls.CLASS_RESULTS.format(
        institution=institution.id,
        year=class_instance.year,
        department=class_instance.parent.department.id,
        class_id=class_instance.parent.iid,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))

    course_links = page.find_all(href=urls.COURSE_EXP)

    for link in course_links:
        page = session.get_simplified_soup(urls.ROOT + link.attrs['href'])
        results = parser.get_results(page)

        for student, evaluations, approved in results:
            db_student = database.get_student(identifier=student[0], name=student[1])

            if db_student is None:
                raise Exception("Student dodged the enrollment search.\n" + student)

            if db_student.gender is None:
                if student[2] == 'f':
                    gender = 0
                elif student[2] == 'm':
                    gender = 1
                else:
                    raise Exception("A new gender appeared in the pokédex")
                database.update_student_gender(student=db_student, gender=gender)
            database.update_enrollment_results(
                student=db_student,
                class_instance=class_instance,
                results=evaluations,
                approved=approved)

    # Attendance
    page = session.get_simplified_soup(urls.CLASS_ATTENDANCE.format(
        institution=institution.id,
        year=class_instance.year,
        department=class_instance.parent.department.id,
        class_id=class_instance.parent.iid,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))
    course_links = page.find_all(href=urls.COURSE_EXP)

    for link in course_links:
        page = session.get_simplified_soup(urls.ROOT + link.attrs['href'])
        for student, attendance, date in parser.get_attendance(page):
            db_student = database.get_student(student[0], student[1])
            if db_student is None:
                raise Exception("Student dodged the enrollment search.\n" + student)
            database.update_enrollment_attendance(
                student=db_student,
                class_instance=class_instance,
                attendance=attendance,
                date=date)

    # Improvements
    page = session.get_simplified_soup(urls.CLASS_IMPROVEMENTS.format(
        institution=institution.id,
        year=class_instance.year,
        department=class_instance.parent.department.id,
        class_id=class_instance.parent.iid,
        period=class_instance.period.part,
        period_type=class_instance.period.letter))
    course_links = page.find_all(href=urls.COURSE_EXP)

    for link in course_links:
        page = session.get_simplified_soup(urls.ROOT + link.attrs['href'])
        for student, improved, grade, date in parser.get_improvements(page):
            db_student = database.get_student(student[0], student[1])
            if db_student is None:
                log.error("Student dodged the enrollment search.\n" + student)

            database.update_enrollment_improvement(
                student=db_student,
                class_instance=class_instance,
                improved=improved,
                grade=grade,
                date=date)

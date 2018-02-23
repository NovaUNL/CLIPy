import logging
import traceback
from queue import Queue
from threading import Thread, Lock
from time import sleep
from unicodedata import normalize

import re

from CLIPy.database.candidates import StudentCandidate, TurnCandidate, TurnInstanceCandidate, ClassroomCandidate, \
    BuildingCandidate, EnrollmentCandidate, AdmissionCandidate, ClassCandidate, ClassInstanceCandidate, TeacherCandidate
from CLIPy.database.database import SessionRegistry
from CLIPy.database.models import Department, Institution, ClassInstance
import CLIPy.database as db
from .session import Session as WebSession
from CLIPy import urls
from CLIPy.utils.utils import parse_clean_request, weekday_to_id

log = logging.getLogger(__name__)


class PageCrawler(Thread):
    def __init__(self, name, clip_session: WebSession, db_registry: SessionRegistry, work_queue: Queue,
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
                        log.error("Failed to complete the job for the work unit with the ID {}."
                                  "Error: \n{}\nRetrying in 5 seconds...".format(work_unit.id, traceback.format_exc()))

                    if exception_count > 10:
                        raise Exception("Thread {} failed for more than 10 times.")
                    sleep(5 + max(exception_count, 55))
            else:
                self.queue_lock.release()
                break

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.db_registry.remove()


def crawl_classes(session: WebSession, database: db.Controller, department: Department):
    department = database.session.merge(department)
    classes = {}
    class_instances = []

    period_exp = re.compile('&tipo_de_per%EDodo_lectivo=(?P<type>\w)&per%EDodo_lectivo=(?P<stage>\d)$')
    class_exp = re.compile('&unidade_curricular=(\d+)')

    # for each year this department operated
    for year in range(department.first_year, department.last_year + 1):
        hierarchy = parse_clean_request(
            session.get(urls.CLASSES.format(department.institution.internal_id, year, department.internal_id)))

        period_links = hierarchy.find_all(href=period_exp)

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
            hierarchy = parse_clean_request(session.get(urls.CLASSES_PERIOD.format(
                period_type, department.internal_id, year, part, department.institution.internal_id)))

            class_links = hierarchy.find_all(href=class_exp)

            # for each class in this period
            for class_link in class_links:
                class_id = int(class_exp.findall(class_link.attrs['href'])[0])
                class_name = class_link.contents[0].strip()
                if class_id not in classes:
                    classes[class_id] = database.add_class(ClassCandidate(class_id, class_name, department))

                if classes[class_id] is None:
                    raise Exception("Null class")
                class_instances.append(ClassInstanceCandidate(classes[class_id], period, year))
    database.add_class_instances(class_instances)


def crawl_admissions(session: WebSession, database: db.Controller, institution: Institution):
    institution = database.session.merge(institution)
    admissions = []
    course_exp = re.compile("\\bcurso=(\d+)$")
    years = range(institution.first_year, institution.last_year + 1)
    for year in years:
        course_ids = set()  # Courses found in this year's page
        hierarchy = parse_clean_request(  # Fetch the page
            session.get(urls.ADMISSIONS.format(year, institution.internal_id)))
        course_links = hierarchy.find_all(href=course_exp)  # Find the course links
        for course_link in course_links:  # For every found course
            course_id = int(course_exp.findall(course_link.attrs['href'])[0])
            course_ids.add(course_id)

        for course_id in course_ids:
            course = database.get_course(id=course_id)  # TODO ensure that doesn't end up as None
            for phase in range(1, 4):  # For every of the three phases
                hierarchy = parse_clean_request(session.get(
                    urls.ADMITTED.format(year, institution.internal_id, phase, course_id)))
                # Find the table structure containing the data (only one with those attributes)
                try:
                    table_root = hierarchy.find('th', colspan="8", bgcolor="#95AEA8").parent.parent
                except AttributeError:
                    continue

                for tag in table_root.find_all('th'):  # for every table header
                    if tag.parent is not None:
                        tag.parent.decompose()  # remove its parent row

                table_rows = table_root.find_all('tr')
                for table_row in table_rows:  # for every student admission
                    table_row = list(table_row.children)

                    # take useful information
                    name = table_row[1].text.strip()
                    option = table_row[9].text.strip()
                    student_iid = table_row[11].text.strip()
                    state = table_row[13].text.strip()

                    student_iid = student_iid if student_iid != '' else None
                    option = None if option == '' else int(option)
                    state = state if state != '' else None

                    student = None

                    if student_iid is not None:  # if the student has an id add him/her to the database
                        student = database.add_student(StudentCandidate(student_iid, name, course, institution))

                    name = name if student is None else None
                    admission = AdmissionCandidate(student, name, course, phase, year, option, state)
                    admissions.append(admission)
    database.add_admissions(admissions)


def crawl_class_instance(session: WebSession, database: db.Controller, class_instance: ClassInstance):
    log.info("Crawling class instance ID %s" % class_instance.id)
    class_instance = database.session.merge(class_instance)
    institution = class_instance.parent.department.institution

    hierarchy = parse_clean_request(session.get(urls.CLASS_ENROLLED.format(
        class_instance.period.letter, class_instance.parent.department.internal_id,
        class_instance.year, class_instance.period.part, institution.internal_id,
        class_instance.parent.internal_id)))

    # Strip file header and split it into lines
    content = hierarchy.text.splitlines()[4:]

    enrollments = []

    for line in content:  # for every student enrollment
        information = line.split('\t')
        if len(information) != 7:
            if len(hierarchy.find_all(string=re.compile("Pedido inválido"))) > 0:
                log.debug("Instance skipped")
                return
            else:
                log.warning("Invalid line")
                continue
        # take useful information
        student_statutes = information[0].strip()
        student_name = information[1].strip()
        student_id = information[2].strip()
        if student_id != "":
            try:
                student_id = int(information[2].strip())
            except Exception:
                pass

        student_abbr = information[3].strip()
        course_abbr = information[4].strip()
        attempt = int(information[5].strip().rstrip('ºª'))
        student_year = int(information[6].strip().rstrip('ºª'))
        if student_abbr == '':
            student_abbr = None
        if student_statutes == '':
            student_statutes = None
        if student_name == '':
            raise Exception("Student with no name")
        # TODO continue

        course = database.get_course(abbreviation=course_abbr, year=class_instance.year)

        # TODO consider sub-courses EG: MIEA/[Something]
        observation = course_abbr if course is not None else (course_abbr + "(Unknown)")
        # update student info and take id
        student = database.add_student(
            StudentCandidate(
                student_id, student_name, abbreviation=student_abbr, course=course, institution=institution))

        enrollment = EnrollmentCandidate(student, class_instance, attempt, student_year, student_statutes, observation)
        enrollments.append(enrollment)

    database.add_enrollments(enrollments)


def crawl_class_turns(session: WebSession, database: db.Controller, class_instance: ClassInstance):
    log.info("Crawling class instance ID %s" % class_instance.id)
    class_instance = database.session.merge(class_instance)
    institution = class_instance.parent.department.institution

    hierarchy = parse_clean_request(
        session.get(urls.TURNS_INFO.format(
            class_instance.parent.internal_id, institution.internal_id, class_instance.year,
            class_instance.period.letter, class_instance.period.part, class_instance.parent.department.internal_id)))

    turn_link_exp = re.compile("\\b&tipo=(?P<type>\\w)+&n%BA=(?P<number>\\d+)\\b")
    schedule_exp = re.compile(  # extract turn information
        '(?P<weekday>[\\w-]+) {2}'
        '(?P<init_hour>\\d{2}):(?P<init_min>\\d{2}) - (?P<end_hour>\\d{2}):(?P<end_min>\\d{2})(?: {2})?'
        '(?:Ed .*: (?P<room>[\\w\\b. ]+)/(?P<building>[\\w\\d. ]+))?')

    turn_links = hierarchy.find_all(href=turn_link_exp)

    # When there is only one turn, the received page is the turn itself.
    single_turn = False
    turn_count = 0  # consistency check

    turn_type = None
    turn_number = None

    for turn_link in turn_links:
        if "aux=ficheiro" in turn_link.attrs['href'].lower():
            # there are no file links in turn lists, but they do exist on turn pages
            single_turn = True
        else:
            turn_count += 1
            turn_link_expression = turn_link_exp.search(turn_link.attrs['href'])
            turn_type = turn_link_expression.group("type")
            turn_number = int(turn_link_expression.group("number"))

    turn_pages = []  # pages for turn parsing
    if single_turn:  # if the loaded page is the only turn
        if turn_count > 1:
            raise Exception("Too many turns for a single turn...")
        if turn_count == 0:
            log.warning("Turn page without any turn. Skipping")
            return
        turn_pages.append((hierarchy, turn_type, turn_number))  # save it, avoid requesting it again
    else:  # if there are multiple turns then request them
        for turn_link in turn_links:
            turn_page = parse_clean_request(session.get(urls.ROOT + turn_link.attrs['href']))
            turn_link_expression = turn_link_exp.search(turn_link.attrs['href'])
            turn_type = turn_link_expression.group("type")
            turn_number = int(turn_link_expression.group("number"))
            turn_pages.append((turn_page, turn_type, turn_number))  # and save them with their metadata

    del hierarchy

    for page in turn_pages:  # for every turn in this class instance
        instances = []
        routes = []
        teachers = []
        restrictions = None
        weekly_minutes = None
        state = None
        enrolled = None
        capacity = None
        students = []
        turn_type = database.get_turn_type(page[1])

        if turn_type is None:
            log.error("Unknown turn type: " + page[1])

        # turn information table
        info_table_root = page[0].find('th', colspan="2", bgcolor="#aaaaaa").parent.parent

        for tag in info_table_root.find_all('th'):  # for every table header
            if tag.parent is not None:
                tag.parent.decompose()  # remove its parent row

        information_rows = info_table_root.find_all('tr')
        del info_table_root

        fields = {}
        previous_key = None
        for table_row in information_rows:
            if len(table_row.contents) < 3:  # several lines ['\n', 'value']
                fields[previous_key].append(normalize('NFKC', table_row.contents[1].text.strip()))
            else:  # inline info ['\n', 'key', '\n', 'value']
                key = table_row.contents[1].text.strip().lower()
                previous_key = key
                fields[key] = [normalize('NFKC', table_row.contents[3].text.strip())]

        del previous_key

        for field, content in fields.items():
            if field == "marcação":
                for row in content:
                    information = schedule_exp.search(row)
                    if information is None:
                        raise Exception("Bad schedule:" + str(information))

                    weekday = weekday_to_id(information.group('weekday'))
                    start = int(information.group('init_hour')) * 60 + int(information.group('init_min'))
                    end = int(information.group('end_hour')) * 60 + int(information.group('end_min'))

                    building = information.group('building')
                    room = information.group('room')

                    # TODO fix that classroom thingy, also figure a way to create the turn before its instances
                    if building is not None:
                        building = database.add_building(BuildingCandidate(building.strip(), institution))
                        if room is not None:  # if there is a room, use it
                            room = database.add_classroom(ClassroomCandidate(room.strip(), building))
                        else:  # use building as room name
                            room = database.add_classroom(ClassroomCandidate(building.name, building))
                    instances.append(TurnInstanceCandidate(None, start, end, weekday, classroom=room))
            elif field == "turno":
                pass
            elif "percursos" in field:
                routes = content
            elif field == "docentes":
                for teacher in content:
                    teachers.append(TeacherCandidate(teacher))
            elif "carga" in field:
                weekly_minutes = int(float(content[0].rstrip(" horas")) * 60)
            elif field == "estado":
                state = content[0]
            elif field == "capacidade":
                parts = content[0].split('/')
                try:
                    enrolled = int(parts[0])
                except ValueError:
                    log.warning("No enrolled information")
                try:
                    capacity = int(parts[1])
                except ValueError:
                    log.warning("No capacity information")
            elif field == "restrição":
                restrictions = content[0]
            else:
                raise Exception("Unknown field " + field)
        del fields

        student_table_root = page[0].find('th', colspan="4", bgcolor="#95AEA8").parent.parent

        for tag in student_table_root.find_all('th'):  # for every table header
            if tag.parent is not None:
                tag.parent.decompose()  # remove its parent row

        student_rows = student_table_root.find_all('tr')

        for student_row in student_rows:
            student_name = student_row.contents[1].text.strip()
            student_id = student_row.contents[3].text.strip()
            student_abbreviation = student_row.contents[5].text.strip()
            course_abbreviation = student_row.contents[7].text.strip()
            course = database.get_course(abbreviation=course_abbreviation, year=class_instance.year)

            # make sure he/she is in the db and have his/her db id
            student = database.add_student(
                StudentCandidate(student_id, student_name, course, institution, abbreviation=student_abbreviation))
            students.append(student)

        routes_str = None
        for route in routes:
            if routes_str is None:
                routes_str = route
            else:
                routes_str += (';' + route)

        turn = TurnCandidate(
            class_instance, page[2], turn_type, enrolled, capacity,
            minutes=weekly_minutes, routes=routes_str, restrictions=restrictions, state=state, teachers=teachers)
        turn = database.add_turn(turn)
        for instance in instances:
            instance.turn = turn

        database.add_turn_instances(instances)
        database.add_turn_students(turn, students)

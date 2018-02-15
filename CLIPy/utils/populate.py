import logging
import re
from queue import Queue
from time import sleep
from threading import Lock

from CLIPy.database import Database
from CLIPy.session import Session
from CLIPy.crawler import PageCrawler, crawl_class_turns, crawl_class_instance, crawl_classes, crawl_admissions
from CLIPy.database.candidates import InstitutionCandidate, DepartmentCandidate, CourseCandidate
from CLIPy.utils import parse_clean_request
from CLIPy import urls

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
THREADS = 8  # high number means "Murder CLIP!", take care


def institutions(session: Session, database: Database):
    found = []
    known = {60002: "Escola Nacional de Saúde Publica",
             109054: "Faculdade de Ciências Médicas",
             109055: "Faculdade de Ciências Sociais e Humanas",
             97747: "Faculdade de Ciências e Tecnologia",
             109056: "Faculdade de Direito",
             109057: "Faculdade de Economia (SBE)",
             60004: "Instituto de Higiene e Medicina Tropical",
             60003: "Instituto Superior de Estatística e Gestão da Informação",
             60005: "Instituto de Tecnologia Química e Biológica",
             97753: "Reitoria",
             113627: "Serviços de Ação Social"}
    hierarchy = parse_clean_request(session.get(urls.INSTITUTIONS))
    link_exp = re.compile('/?institui%E7%E3o=(\d+)$')
    for institution_link in hierarchy.find_all(href=link_exp):
        clip_id = int(link_exp.findall(institution_link.attrs['href'])[0])
        abbreviation = institution_link.text
        name = None if clip_id not in known else known[clip_id]
        institution = InstitutionCandidate(clip_id, name, abbreviation=abbreviation)
        found.append(institution)

    for institution in found:
        hierarchy = parse_clean_request(session.get(urls.INSTITUTION_YEARS.format(institution.id)))
        year_exp = re.compile("\\b\d{4}\\b")
        institution_links = hierarchy.find_all(href=year_exp)
        for institution_link in institution_links:
            year = int(year_exp.findall(institution_link.attrs['href'])[0])
            institution.add_year(year)

    for institution in found:
        log.debug("Institution found: " + str(institution))

    database.add_institutions(found)


def departments(session: Session, database: Database):
    found = {}  # id -> Department
    department_exp = re.compile('\\bsector=(\d+)\\b')
    for institution in database.get_institution_set():

        if not institution.has_time_range():  # if it has no time range to iterate through
            continue

        # Find the departments that existed under each year
        for year in range(institution.first_year, institution.last_year + 1):
            log.info("Crawling departments of institution {}. Year:{}".format(institution, year))
            hierarchy = parse_clean_request(session.get(urls.DEPARTMENTS.format(year, institution.internal_id)))
            department_links = hierarchy.find_all(href=department_exp)
            for department_link in department_links:
                department_id = int(department_exp.findall(department_link.attrs['href'])[0])
                department_name = department_link.contents[0]

                if department_id in found:  # update creation year
                    department = found[department_id]
                    if department.institution != institution:
                        raise Exception("Department {}({}) found in different institutions ({} and {})".format(
                            department.name, department_id, institution.internal_id, department.institution))
                    department.add_year(year)
                else:  # insert new
                    department = DepartmentCandidate(department_id, department_name, institution, year, year)
                    found[department_id] = department
    database.add_departments(found.values())


def classes(session: Session, database: Database):
    department_queue = Queue()
    [department_queue.put(department) for department in database.get_department_set()]
    department_lock = Lock()

    threads = []
    for thread in range(0, THREADS):
        threads.append(PageCrawler(
            "Thread-" + str(thread), session, database, department_queue, department_lock, crawl_classes))
        threads[thread].start()

    while True:
        department_lock.acquire()
        if department_queue.empty():
            department_lock.release()
            break
        else:
            log.info("{} departments remaining!".format(department_queue.qsize()))
            department_lock.release()
            sleep(5)

    for thread in threads:
        thread.join()


def courses(session: Session, database: Database):
    course_exp = re.compile("\\bcurso=(\d+)\\b")
    year_ext = re.compile("\\bano_lectivo=(\d+)\\b")

    for institution in database.get_institution_set():
        courses = {}
        hierarchy = parse_clean_request(session.get(urls.COURSES.format(institution.internal_id)))
        course_links = hierarchy.find_all(href=course_exp)
        for course_link in course_links:  # for every course link in the courses list page
            identifier = int(course_exp.findall(course_link.attrs['href'])[0])
            courses[identifier] = CourseCandidate(
                identifier, course_link.contents[0].text.strip(), None, institution, None, None)

            # fetch the course curricular plan to find the activity years
            hierarchy = parse_clean_request(session.get(
                urls.CURRICULAR_PLANS.format(institution.internal_id, identifier)))
            year_links = hierarchy.find_all(href=year_ext)
            # find the extremes
            for year_link in year_links:
                year = int(year_ext.findall(year_link.attrs['href'])[0])
                courses[identifier].add_year(year)

        # fetch course abbreviation from the statistics page
        for degree in database.get_degree_set():
            hierarchy = parse_clean_request(session.get(
                urls.STATISTICS.format(institution.internal_id, degree.internal_id)))
            course_links = hierarchy.find_all(href=course_exp)
            for course_link in course_links:
                identifier = int(course_exp.findall(course_link.attrs['href'])[0])
                abbreviation = course_link.contents[0].strip()
                if abbreviation == '':
                    abbreviation = None
                if identifier in courses:
                    courses[identifier].abbreviation = abbreviation
                    courses[identifier].degree = degree
                else:
                    raise Exception(
                        "{}({}) was listed in the abbreviation list but a corresponding course wasn't found".format(
                            abbreviation, identifier))

        database.add_courses(courses.values())


# populate student list from the national access contest (also obtain their preferences and current status)
def nac_admissions(session: Session, database: Database):
    # TODO rework the database to save states apart
    # TODO since the vast, VAST majority of clip students are from only one institution, change the implementation
    # to have threads crawling each year instead of each institution.
    # Since this only has to be run once at every trimester guess its not top priority

    institution_queue = Queue()
    for institution in database.get_institution_set():
        if not institution.has_time_range():  # if it has no time range to iterate through
            continue
        institution_queue.put(institution)

    institution_queue_lock = Lock()

    threads = []
    for thread in range(0, THREADS):
        threads.append(
            PageCrawler(
                "Thread-" + str(thread),
                session,
                database,
                institution_queue,
                institution_queue_lock,
                crawl_admissions
            ))
        threads[thread].start()

    while True:
        institution_queue_lock.acquire()
        if institution_queue.empty():
            institution_queue_lock.release()
            break
        else:
            log.info("Approximately {} institutions remaining".format(institution_queue.qsize()))
            institution_queue_lock.release()
            sleep(5)

    for thread in threads:
        thread.join()


def class_instances(session: Session, database: Database):
    class_instances_queue = database.fetch_class_instances(queue=True)
    class_instances_lock = Lock()

    threads = []
    for thread in range(0, THREADS):
        threads.append(
            PageCrawler("Thread-" + str(thread),
                        session, database,
                        class_instances_queue, class_instances_lock, crawl_class_instance))
        threads[thread].start()

    while True:
        class_instances_lock.acquire()
        if class_instances_queue.empty():
            class_instances_lock.release()
            break
        else:
            log.info("Approximately {} class instances remaining".format(class_instances_queue.qsize()))
            class_instances_lock.release()
            sleep(5)

    for thread in threads:
        thread.join()


def class_instances_turns(session: Session, database: Database):
    class_instances_queue = database.fetch_class_instances(year_asc=False, queue=True)
    class_instances_lock = Lock()

    threads = []
    for thread in range(0, THREADS):
        threads.append(
            PageCrawler("Thread-" + str(thread),
                        session, database,
                        class_instances_queue, class_instances_lock, crawl_class_turns))
        threads[thread].start()

    while True:
        class_instances_lock.acquire()
        if class_instances_queue.empty():
            class_instances_lock.release()
            break
        else:
            log.info("Approximately {} class instances remaining".format(class_instances_queue.qsize()))
            class_instances_lock.release()
            sleep(5)

    for thread in threads:
        thread.join()


def database_from_scratch(session: Session, database: Database):
    institutions(session, database)  # 10 seconds before ORM
    departments(session, database)  # 1 minute before ORM
    classes(session, database)  # ~20 minutes before ORM
    courses(session, database)  # ~5 minutes before ORM
    nac_admissions(session, database)  # ~20 minutes before ORM
    class_instances(session, database)  # ~4 hours before ORM
    class_instances_turns(session, database)  # ~16 Hours  before ORM

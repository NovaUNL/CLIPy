import logging
import re
from datetime import datetime

from .. import urls, database as db, parser, processors, crawler
from ..config import INSTITUTION_FIRST_YEAR, INSTITUTION_ID, INSTITUTION_LAST_YEAR
from ..session import Session

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def populate_departments(session: Session, database: db.Controller):
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


def populate_buildings(session: Session, database: db.Controller):
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
                    period=period.part,
                    period_type=period.letter))
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


def populate_courses(session: Session, database: db.Controller):
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
                        urls.COURSES.format(institution=INSTITUTION_ID, course=course.id))
                    if course_page.find(text=re.compile(".*Mestrado Integrado.*")):
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


def bootstrap_database(session: Session, db_registry: db.SessionRegistry, year: int = None, period: int = None):
    """
    | Bootstraps a database from scratch.
    | Can also be used as an updater but would be a waste of resources in most scenarios.
    | This is a very everything-intensive task. It uses a lot of CPU, DB IO and if I had to guess it also heats
      up the server by a few degrees.

    :param session: Web session
    :param db_registry: Database session registry
    :param year: (Optional) Year filter
    :param period: (Optional) Period filter
    """
    main_thread_db_controller = db.Controller(db_registry, cache=False)

    # Find departments.
    populate_departments(session, main_thread_db_controller)

    # Find buildings (depends on up-to-date departments).
    populate_buildings(session, main_thread_db_controller)

    # Find rooms (depends on up-to-date institutions and buildings).
    processors.building_task(session, db_registry, crawler.crawl_rooms)

    # Find classes (depends on up-to-date departments).
    processors.department_task(session, db_registry, crawler.crawl_classes)

    # Find courses.
    populate_courses(session, main_thread_db_controller)

    # Looks up the national access contest admission tables looking for students current statuses.
    # Depends on up-to-date institutions.
    processors.year_task(
        session,
        db_registry,
        crawler.crawl_admissions,
        from_year=INSTITUTION_FIRST_YEAR,
        to_year=INSTITUTION_LAST_YEAR)

    # Finds student enrollments to class instances.
    processors.class_task(session, db_registry, crawler.crawl_class_enrollments, year=year, period=period)

    # Find class information such as objectives
    processors.class_task(session, db_registry, crawler.crawl_class_info, year=year, period=period)

    # Finds class instance turns and updates their data if needed.
    processors.class_task(session, db_registry, crawler.crawl_class_turns, year=year, period=period)

    # Find teachers (depends on up-to-date departments and turns).
    processors.department_task(session, db_registry, crawler.crawl_teachers)

    # Finds uploaded file listings for every class
    processors.class_task(session, db_registry, crawler.crawl_files, year=year, period=period)

    # Downloads known files
    processors.class_task(session, db_registry, crawler.download_files, year=year, period=period)

    # Finds class instance grades
    processors.class_task(session, db_registry, crawler.crawl_grades, year=year, period=period)

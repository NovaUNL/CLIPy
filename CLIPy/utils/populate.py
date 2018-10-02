import logging
import re

from .. import urls, database as db, parser, processors, crawler
from ..session import Session

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def populate_institutions(session: Session, database: db.Controller):
    """
    Finds new institutions and adds them to the database. This is mostly bootstrap code, not very useful later on.
    This is not thread-safe.

    :param session: Web session
    :param database: Database controller
    """
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
    hierarchy = session.get_simplified_soup(urls.INSTITUTIONS)
    link_exp = re.compile('/?institui%E7%E3o=(\d+)$')
    for institution_link in hierarchy.find_all(href=link_exp):
        clip_id = int(link_exp.findall(institution_link.attrs['href'])[0])
        abbreviation = institution_link.text
        name = None if clip_id not in known else known[clip_id]
        institution = db.candidates.Institution(clip_id, name, abbreviation=abbreviation)
        found.append(institution)

    for institution in found:
        hierarchy = session.get_simplified_soup(urls.INSTITUTION_YEARS.format(institution=institution.id))
        year_exp = re.compile("\\b\d{4}\\b")
        institution_links = hierarchy.find_all(href=year_exp)
        for institution_link in institution_links:
            year = int(year_exp.findall(institution_link.attrs['href'])[0])
            institution.add_year(year)

    for institution in found:
        log.debug("Institution found: " + str(institution))

    database.add_institutions(found)


def populate_departments(session: Session, database: db.Controller):
    """
    Finds new departments and adds them to the database. *NOT* thread-safe.

    :param session: Web session
    :param database: Database controller
    """
    found = {}  # id -> Department
    for institution in database.get_institution_set():
        if not institution.has_time_range():  # if it has no time range to iterate through
            continue

        # Find the departments which existed each year
        for year in range(institution.first_year, institution.last_year + 1):
            log.info("Crawling departments of institution {}. Year:{}".format(institution, year))
            hierarchy = session.get_simplified_soup(urls.DEPARTMENTS.format(
                institution=institution.id, year=year))
            for department_id, name in parser.get_departments(hierarchy):
                if department_id in found:  # update creation year
                    department = found[department_id]
                    if department.institution != institution:
                        raise Exception("Department {}({}) found in different institutions ({} and {})".format(
                            department.name, department_id, institution.id, department.institution))
                    department.add_year(year)
                else:  # insert new
                    department = db.candidates.Department(department_id, name, institution, year, year)
                    found[department_id] = department
    database.add_departments(found.values())


def populate_buildings(session: Session, database: db.Controller):
    """
    Finds new buildings and adds them to the database. *NOT* thread-safe.

    :param session: Web session
    :param database: Database controller
    """

    buildings = {}  # id -> Candidate
    for institution in database.get_institution_set():
        if not institution.has_time_range():  # if it has no time range to iterate through
            continue

        for year in range(institution.first_year, institution.last_year + 1):
            for period in database.get_period_set():
                log.info(f"Crawling buildings of institution {institution}. Year:{year}. Period: {period}")
                page = session.get_simplified_soup(urls.BUILDINGS.format(
                    institution=institution.id, year=year, period=period.part, period_type=period.letter))
                page_buildings = parser.get_buildings(page)
                for identifier, name in page_buildings:
                    candidate = db.candidates.Building(identifier=identifier, name=name)
                    if identifier in buildings:
                        if buildings[identifier] != candidate:
                            raise Exception("Found two different buildings going by the same ID")
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
    for institution in database.get_institution_set():
        courses = {}  # identifier -> Candidate pairs

        # Obtain course id-name pairs from the course list page
        page = session.get_simplified_soup(urls.COURSES.format(institution=institution.id))
        for identifier, name in parser.get_course_names(page):
            # Fetch the course curricular plan to find the activity years
            page = session.get_simplified_soup(urls.CURRICULAR_PLANS.format(
                institution=institution.id,
                course=identifier))
            first, last = parser.get_course_activity_years(page)
            candidate = db.candidates.Course(identifier, name, institution, first_year=first, last_year=last)
            courses[identifier] = candidate

        # fetch course abbreviation from the statistics page
        for degree in database.get_degree_set():
            page = session.get_simplified_soup(urls.STATISTICS.format(
                institution=institution.id,
                degree=degree.iid))
            for identifier, abbreviation in parser.get_course_abbreviations(page):
                if identifier in courses:
                    courses[identifier].abbreviation = abbreviation
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
    # Find institutions. Needed for virtually everything. Takes 10 seconds
    populate_institutions(session, main_thread_db_controller)

    # Find buildings (depends on up-to-date institutions). Takes 1-2 minutes
    populate_departments(session, main_thread_db_controller)

    # Find buildings (depends on up-to-date departments). Takes ~ 4 minutes (10 seconds if manually capped to last year)
    populate_buildings(session, main_thread_db_controller)

    # Find rooms (depends on up-to-date institutions and buildings). Takes 15 minutes
    processors.institution_task(session, db_registry, crawler.crawl_rooms)

    # Find teachers (depends on up-to-date departments). Takes 15 minutes
    processors.department_task(session, db_registry, crawler.crawl_teachers)

    # Find classes (depends on up-to-date departments). Takes 2 hours
    processors.department_task(session, db_registry, crawler.crawl_classes)

    # Find courses (depends on up-to-date institutions). Takes 5 minutes
    populate_courses(session, main_thread_db_controller)

    # Looks up the national access contest admission tables looking for students current statuses.
    # Depends on up-to-date institutions. Takes 30 minutes
    processors.institution_task(session, db_registry, crawler.crawl_admissions, restriction=97747)

    # Finds student enrollments to class instances.
    processors.class_task(session, db_registry, crawler.crawl_class_enrollments, year=year, period=period)

    # Find class information such as objectives and such
    processors.class_task(session, db_registry, crawler.crawl_class_info, year=year, period=period)

    # Finds class instance turns and updates their data if needed. Takes ~16 Hours
    processors.class_task(session, db_registry, crawler.crawl_class_turns, year=year, period=period)

    # Finds uploaded file listings for every class
    processors.class_task(session, db_registry, crawler.crawl_files, year=year, period=period)

    # Downloads known files
    processors.class_task(session, db_registry, crawler.download_files, year=year, period=period)

    # Finds class instance grades
    processors.class_task(session, db_registry, crawler.crawl_grades, year=year, period=period)

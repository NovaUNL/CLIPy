import os
from datetime import datetime

from . import database as db, processors, crawler
from .config import INSTITUTION_FIRST_YEAR, INSTITUTION_LAST_YEAR
from .session import Session
from .utils import populate

from .database import models as m


class CacheStorage:
    def __init__(self, registry: db.SessionRegistry, database_cache=False):
        self.registry = registry
        self.controller = db.Controller(registry, cache=database_cache)

    @staticmethod
    def postgresql(username, password, schema, host=None):
        if host is None:  # Let it default to localhost
            engine = db.create_engine('postgresql', username=username, password=password, schema=schema)
        else:
            engine = db.create_engine('postgresql', username=username, password=password, schema=schema, host=host)
        return CacheStorage(db.SessionRegistry(engine))

    @staticmethod
    def sqlite(file):
        if not os.path.isfile(file):
            raise RuntimeError("Database file doesn't exist. Please create it manually.")
        engine = db.create_engine('sqlite', file=file)
        return CacheStorage(db.SessionRegistry(engine))


class Clip:
    _session = None

    def __init__(self, cache: CacheStorage, username, password):
        self.cache: CacheStorage = cache
        self.username = username
        self.password = password
        self.session = Session(username, password)

    def find_student(self, name, course_filter=None):
        return self.cache.controller.find_student(name, course=course_filter)

    def find_course(self, abbreviation, year=datetime.now().year):
        return self.cache.controller.get_course(abbreviation=abbreviation, year=year)

    def fetch_library_individual_room_availability(self, date: datetime.date = datetime.now().date()):
        return crawler.crawl_library_individual_room_availability(self.session, date)

    def fetch_library_group_room_availability(self, date: datetime.date = datetime.now().date()):
        return crawler.crawl_library_group_room_availability(self.session, date)

    def list_buildings(self):
        return list(map(lambda building: building.serialize(), self.cache.controller.get_building_set()))

    def list_rooms(self):
        return list(map(lambda building: building.serialize(), self.cache.controller.get_room_set()))

    def list_courses(self):
        return [course.serialize() for course in self.cache.controller.get_courses()]

    def list_students(self):
        return [student.serialize() for student in self.cache.controller.get_students()]

    def list_teachers(self):
        return [teacher.serialize() for teacher in self.cache.controller.get_teachers()]

    def get_departments(self):
        return [department.serialize() for department in self.cache.controller.get_department_set()]

    def get_department(self, id):
        obj = self.cache.controller.session.query(m.Department).get(id)
        return None if obj is None else obj.serialize_related()

    def get_class(self, id):
        obj = self.cache.controller.session.query(m.Class).get(id)
        return None if obj is None else obj.serialize()

    def get_student(self, id):
        obj = self.cache.controller.session.query(m.Student).get(id)
        return None if obj is None else obj.serialize()

    def get_class_instance(self, id):
        obj = self.cache.controller.session.query(m.ClassInstance).get(id)
        return None if obj is None else obj.serialize()

    def get_class_instance_files(self, id):
        obj = self.cache.controller.session.query(m.ClassInstance).get(id)
        return None if obj is None else [file.serialize() for file in obj.file_relations]

    def get_turn(self, id):
        obj = self.cache.controller.session.query(m.Turn).get(id)
        return None if obj is None else obj.serialize()

    def get_turn_instance(self, id):
        obj = self.cache.controller.session.query(m.TurnInstance).get(id)
        return None if obj is None else obj.serialize()

    def get_enrollment(self, id):
        obj = self.cache.controller.session.query(m.Enrollment).get(id)
        return None if obj is None else obj.serialize()

    def get_evaluation(self, id):
        obj = self.cache.controller.session.query(m.ClassEvaluations).get(id)
        return None if obj is None else obj.serialize()

    def update_admissions(self):
        processors.year_task(self.session, self.cache.registry, crawler.crawl_admissions,
                             from_year=INSTITUTION_FIRST_YEAR, to_year=INSTITUTION_LAST_YEAR)

    def update_teachers(self):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers)

    def update_classes(self):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes)

    def update_class_info(self, year: int, period_part: int, period_parts: int):
        period = self._get_period(period_part, period_parts)
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_info, year=year, period=period)

    def update_class_enrollments(self, year: int, period_part: int, period_parts: int):
        period = self._get_period(period_part, period_parts)
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_enrollments, year=year,
                              period=period)

    def update_turns(self, year: int, period_part: int, period_parts: int):
        period = self._get_period(period_part, period_parts)
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_turns, year=year, period=period)

    def update_class_files(self, year: int, period_part: int, period_parts: int):
        period = self._get_period(period_part, period_parts)
        processors.class_task(self.session, self.cache.registry, crawler.crawl_files, year=year, period=period)
        processors.class_task(self.session, self.cache.registry, crawler.download_files, year=year, period=period)

    def bootstrap_database(self, year: int = None, period_part=2, period_parts=None):
        """
        | Bootstraps a database from scratch.
        | Can also be used as an updater but would be a waste of resources in most scenarios.
        | This is a very everything-intensive task. It uses a lot of CPU, DB IO and if I had to guess it also heats
          up the server by a few degrees.

        :param year: (Optional) Year filter
        :param period_part: (Optional) Period filter (part of period_parts)
        :param period_parts: (Optional) Period filter
        """

        if period_part is not None and period_parts is not None:
            period = self.cache.controller.get_period(period_part, period_parts)
        else:
            period = None

        main_thread_db_controller = db.Controller(self.cache.registry, cache=False)

        # Find departments.
        crawler.crawl_departments(self.session, main_thread_db_controller)

        # Find buildings (depends on up-to-date departments).
        crawler.crawl_buildings(self.session, main_thread_db_controller)

        # Find rooms (depends on up-to-date institutions and buildings).
        processors.building_task(self.session, self.cache.registry, crawler.crawl_rooms)

        # Find classes (depends on up-to-date departments).
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes)

        # Find courses.
        crawler.crawl_courses(self.session, main_thread_db_controller)

        # Looks up the national access contest admission tables looking for students current statuses.
        # Depends on up-to-date institutions.
        processors.year_task(
            self.session,
            self.cache.registry,
            crawler.crawl_admissions,
            from_year=INSTITUTION_FIRST_YEAR,
            to_year=INSTITUTION_LAST_YEAR)

        # Finds student enrollments to class instances.
        processors.class_task(
            self.session,
            self.cache.registry,
            crawler.crawl_class_enrollments,
            year=year,
            period=period)

        # Find class information such as objectives
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_info, year=year, period=period)

        # Finds class instance turns and updates their data if needed.
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_turns, year=year, period=period)

        # Find teachers (depends on up-to-date departments and turns).
        processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers)

        # Finds uploaded file listings for every class
        processors.class_task(self.session, self.cache.registry, crawler.crawl_files, year=year, period=period)

        # Downloads known files
        processors.class_task(self.session, self.cache.registry, crawler.download_files, year=year, period=period)

        # Finds class instance grades
        processors.class_task(self.session, self.cache.registry, crawler.crawl_grades, year=year, period=period)

    def _get_period(self, period_part, period_parts):
        if period_part is None or period_parts is None:
            return None
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        return period

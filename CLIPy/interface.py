import logging
import os
from datetime import datetime

from . import database as db, processors, crawler
from .config import INSTITUTION_FIRST_YEAR, INSTITUTION_LAST_YEAR
from .session import Session

from .database import models as m

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


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

    def __init__(self, cache: CacheStorage, username, password, page_cache_parameters=None):
        self.cache: CacheStorage = cache
        self.username = username
        self.password = password

        self.session = Session(username, password, page_cache_parameters=page_cache_parameters)

    def find_student(self, name, course_filter=None):
        return self.cache.controller.find_student(name, course=course_filter)

    def find_course(self, abbreviation, year=datetime.now().year):
        return self.cache.controller.get_course(abbreviation=abbreviation, year=year)

    def fetch_library_individual_room_availability(self, date: datetime.date = datetime.now().date()):
        return crawler.crawl_library_individual_room_availability(self.session, date)

    def fetch_library_group_room_availability(self, date: datetime.date = datetime.now().date()):
        return crawler.crawl_library_group_room_availability(self.session, date)

    def list_buildings(self):
        controller = db.Controller(self.cache.registry)
        return list(map(lambda building: building.serialize(), controller.get_building_set()))

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

    def get_classes(self):
        return [department.serialize() for department in self.cache.controller.session.query(m.Class).all()]

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

    def get_events(self, id):
        obj = self.cache.controller.session.query(m.ClassInstance).get(id)
        return None if obj is None else [event.serialize() for event in obj.events]

    def get_shift(self, id):
        obj = self.cache.controller.session.query(m.Shift).get(id)
        return None if obj is None else obj.serialize()

    def get_shift_instance(self, id):
        obj = self.cache.controller.session.query(m.ShiftInstance).get(id)
        return None if obj is None else obj.serialize()

    def get_enrollment(self, id):
        obj = self.cache.controller.session.query(m.Enrollment).get(id)
        return None if obj is None else obj.serialize()

    def get_evaluation(self, id):
        obj = self.cache.controller.session.query(m.ClassEvent).get(id)
        return None if obj is None else obj.serialize()

    def update_teachers(self, department_id):
        if department_id:
            controller = db.Controller(self.cache.registry)
            department = controller.session.query(m.Department).get(department_id)
            crawler.crawl_teachers(self.session, controller, department)
            self.cache.registry.remove()
        else:
            processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers)

    def update_classes(self):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes)

    def update_courses(self):
        controller = db.Controller(self.cache.registry)
        crawler.crawl_courses(self.session, controller)
        self.cache.registry.remove()

    def update_rooms(self):
        processors.building_task(self.session, self.cache.registry, crawler.crawl_rooms)

    def update_admissions(self):
        processors.year_task(self.session, self.cache.registry, crawler.crawl_admissions,
                             from_year=INSTITUTION_FIRST_YEAR, to_year=INSTITUTION_LAST_YEAR)

    def update_class_info(self, class_instance_id: int):
        controller = db.Controller(self.cache.registry)
        class_instance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_info(self.session, controller, class_instance)
        self.cache.registry.remove()

    def update_class_enrollments(self, class_instance_id: int):
        controller = db.Controller(self.cache.registry)
        class_instance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_enrollments(self.session, controller, class_instance)
        self.cache.registry.remove()

    def update_class_shifts(self, class_instance_id: int):
        controller = db.Controller(self.cache.registry)
        class_instance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_shifts(self.session, controller, class_instance)
        self.cache.registry.remove()

    def update_class_events(self, class_instance_id: int):
        controller = db.Controller(self.cache.registry)
        class_instance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_events(self.session, controller, class_instance)
        self.cache.registry.remove()

    def update_class_files(self, class_instance_id: int):
        class_instance = self.cache.controller.session.query(m.ClassInstance).get(class_instance_id)
        controller = db.Controller(self.cache.registry)
        crawler.crawl_files(self.session, controller, class_instance)
        crawler.download_files(self.session, controller, class_instance)
        self.cache.registry.remove()

    def update_class_grades(self, class_instance_id: int):
        class_instance = self.cache.controller.session.query(m.ClassInstance).get(class_instance_id)
        controller = db.Controller(self.cache.registry)
        crawler.crawl_grades(self.session, controller, class_instance)
        self.cache.registry.remove()

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

        # Find courses.
        crawler.crawl_courses(self.session, main_thread_db_controller)

        # Find classes (depends on up-to-date departments).
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes)

        # Looks up the national access contest admission tables looking for students current statuses.
        # Depends on up-to-date institutions.
        processors.year_task(
            self.session,
            self.cache.registry,
            crawler.crawl_admissions,
            from_year=INSTITUTION_FIRST_YEAR,
            to_year=INSTITUTION_LAST_YEAR)

        # Find teachers (depends on up-to-date departments and shifts).
        processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers)

        # Downloads known files
        processors.class_task(self.session, self.cache.registry, crawler.download_files, year=year, period=period)

    def _get_period(self, period_part, period_parts):
        if period_part is None or period_parts is None:
            return None
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        return period

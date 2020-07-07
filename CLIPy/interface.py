import os
from datetime import datetime

from . import database as db, processors, crawler
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

    def update_admissions(self, inst_id):
        processors.institution_task(self.session, self.cache.registry, crawler.crawl_admissions, restriction=inst_id)

    def update_teachers(self, inst_id):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers, inst_id=inst_id)

    def update_classes(self, inst_id):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes, inst_id=inst_id)

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

    def populate(self, year: int = None, period_part=2, period_parts=None):
        period = self.cache.controller.get_period(period_part, period_parts)
        period_id = period.id if period else None
        populate.bootstrap_database(self.session, self.cache.registry, year, period_id)

    def _get_period(self, period_part, period_parts):
        if period_part is None or period_parts is None:
            return None
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        return period

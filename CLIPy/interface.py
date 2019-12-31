import os
from datetime import datetime

from . import database as db, processors, crawler
from .session import Session
from .utils import populate


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

    def update_admissions(self):
        processors.institution_task(self.session, self.cache.registry, crawler.crawl_admissions)

    def update_teachers(self):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers)

    def update_classes(self):
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes)

    def update_class_info(self, year: int, period_part, period_parts):
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_info, year=year, period=period)

    def update_class_enrollments(self, year: int, period_part, period_parts):
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_info, year=year, period=period)

    def update_turns(self, year, period_part, period_parts):
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        processors.class_task(self.session, self.cache.registry, crawler.crawl_class_turns, year=year, period=period)

    def update_class_files(self, year, period_part, period_parts):
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        processors.class_task(self.session, self.cache.registry, crawler.crawl_files, year=year, period=period)
        processors.class_task(self.session, self.cache.registry, crawler.download_files, year=year, period=period)

    @staticmethod
    def populate(username, password, storage: CacheStorage, year: int = None, period: int = None):
        populate.bootstrap_database(Session(username, password), storage.registry, year, period)
        return Clip(storage, username, password)

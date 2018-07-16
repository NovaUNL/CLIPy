import os
from datetime import datetime

from . import database as db
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
    def __init__(self, cache: CacheStorage):
        self.cache: CacheStorage = cache

    def find_student(self, name, course_filter=None):
        return self.cache.controller.find_student(name, course=course_filter)

    def find_course(self, abbreviation, year=datetime.now().year):
        return self.cache.controller.get_course(abbreviation=abbreviation, year=year)


    # TODO redo this code. It's causing a circular import or something silly somewhere.
    # def update_admissions(self, username: str, password: str):
    #     processors.institution_task(Session(username, password), self.cache.registry, crawler.crawl_admissions)
    #
    # def update_classes(self, username: str, password: str):
    #     processors.department_task(Session(username, password), self.cache.registry, crawler.crawl_classes)
    #
    # def update_class_enrollments(self, username: str, password: str, year: int, period_part, period_parts):
    #     period = self.cache.controller.get_period(period_part, period_parts)
    #     if period is None:
    #         raise ValueError("Invalid period")
    #     processors.class_task(Session(username, password), self.cache.registry, crawler.crawl_class_info,
    #                           year=year, period=period)
    #
    # def update_turns(self, username, password, year, period_part, period_parts):
    #     period = self.cache.controller.get_period(period_part, period_parts)
    #     if period is None:
    #         raise ValueError("Invalid period")
    #     processors.class_task(Session(username, password), self.cache.registry, crawler.crawl_class_turns,
    #                           year=year, period=period)

    @staticmethod
    def populate(username, password, storage: CacheStorage, year: int = None, period: int = None):
        populate.bootstrap_database(Session(username, password), storage.registry, year, period)
        return Clip(storage)

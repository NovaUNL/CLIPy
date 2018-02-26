from datetime import datetime
import os

import CLIPy.database as db
from CLIPy.session import Session
from CLIPy.utils import populate


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

    def reload_admissions(self, username, password):
        populate.nac_admissions(Session(username, password), self.cache.registry)

    def reload_classes(self, username, password):
        populate.classes(Session(username, password), self.cache.registry)

    def reload_class_instances(self, username, password, year, period_part, period_parts):
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        populate.class_instances(Session(username, password), self.cache.registry, year=year, period=period)

    def reload_turns(self, username, password, year, period_part, period_parts):
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        populate.class_instances_turns(Session(username, password), self.cache.registry, year=year, period=period)

    @staticmethod
    def populate(username, password, storage: CacheStorage):
        populate.database_from_scratch(Session(username, password), storage.registry)
        return Clip(storage)

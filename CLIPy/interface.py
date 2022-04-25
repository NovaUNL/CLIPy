import logging

from datetime import datetime, timezone

from . import database as db, processors, crawler
from .config import INSTITUTION_FIRST_YEAR, INSTITUTION_LAST_YEAR
from .session import Session

from .database import models as m

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
from . import config


class LocalStorage:
    def __init__(self, database_cache=False):
        DATA_DB = config.DATA_DB

        engine = db.create_engine(
            'postgresql',
            host=f"{DATA_DB['HOST']}:{DATA_DB['PORT']}",
            username=DATA_DB['USER'],
            password=DATA_DB['PASSWORD'],
            schema=DATA_DB['NAME'])

        self.registry = db.SessionRegistry(engine)
        self.controller = db.Controller(self.registry, cache=database_cache)


class Clip:
    _session = None

    def __init__(self):
        self.cache = LocalStorage()
        self.session = Session()

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

    def update_teachers(self, department_id, cache=False):
        log.info("Updating teachers")
        if department_id:
            controller = db.Controller(self.cache.registry)
            department = controller.session.query(m.Department).get(department_id)
            crawler.crawl_teachers(self.session, controller, department)
            self.cache.registry.remove()
        else:
            processors.department_task(self.session, self.cache.registry, crawler.crawl_teachers)

    def update_classes(self, cache=False):
        log.info("Updating Classes")
        processors.department_task(self.session, self.cache.registry, crawler.crawl_classes)

    def update_courses(self, cache=True):
        log.info("Updating courses")
        controller = db.Controller(self.cache.registry)
        crawler.crawl_courses(self.session, controller, cache=cache)
        self.cache.registry.remove()

    def update_rooms(self, cache=True):
        log.info("Updating rooms")
        processors.building_task(self.session, self.cache.registry, crawler.crawl_rooms, cache=cache)

    def update_admissions(self):
        log.info("Updating admissions")
        processors.year_task(
            self.session,
            self.cache.registry,
            crawler.crawl_admissions,
            from_year=INSTITUTION_FIRST_YEAR,
            to_year=INSTITUTION_LAST_YEAR)

    def update_class_info(self, class_instance_id: int, cache=False):
        log.info(f"Updating class info for {class_instance_id}")
        controller = db.Controller(self.cache.registry)
        class_instance: m.ClassInstance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_info(self.session, controller, class_instance, cache=cache)

        class_instance.update_timestamp = datetime.now().astimezone()
        controller.session.add(class_instance)
        controller.session.commit()

        self.cache.registry.remove()

    def update_class_enrollments(self, class_instance_id: int, cache=False):
        log.info(f"Updating enrollments for {class_instance_id}")
        controller = db.Controller(self.cache.registry)
        class_instance: m.ClassInstance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_enrollments(self.session, controller, class_instance, cache=cache)

        class_instance.enrollments_update = datetime.now().astimezone()
        controller.session.add(class_instance)
        controller.session.commit()

        self.cache.registry.remove()

    def update_class_shifts(self, class_instance_id: int, cache=False):
        log.info(f"Updating shifts for {class_instance_id}")
        controller = db.Controller(self.cache.registry)
        class_instance: m.ClassInstance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_shifts(self.session, controller, class_instance, cache=cache)

        class_instance.shifts_update = datetime.now().astimezone()
        controller.session.add(class_instance)
        controller.session.commit()

        self.cache.registry.remove()

    def update_class_events(self, class_instance_id: int, cache=False):
        log.info(f"Updating events for {class_instance_id}")
        controller = db.Controller(self.cache.registry)
        class_instance: m.ClassInstance = controller.session.query(m.ClassInstance).get(class_instance_id)
        crawler.crawl_class_events(self.session, controller, class_instance, cache=cache)

        class_instance.events_update = datetime.now().astimezone()
        controller.session.add(class_instance)
        controller.session.commit()

        self.cache.registry.remove()

    def update_class_files(self, class_instance_id: int, cache=False):
        log.info(f"Updating files for {class_instance_id}")
        class_instance: m.ClassInstance = self.cache.controller.session.query(m.ClassInstance).get(class_instance_id)
        controller = db.Controller(self.cache.registry)
        crawler.crawl_files(self.session, controller, class_instance, cache=cache)
        crawler.download_files(self.session, controller, class_instance)

        class_instance.files_update = datetime.now().astimezone()
        controller.session.add(class_instance)
        controller.session.commit()

        self.cache.registry.remove()

    def update_class_grades(self, class_instance_id: int, cache=False):
        log.info(f"Updating grades for {class_instance_id}")
        class_instance: m.ClassInstance = self.cache.controller.session.query(m.ClassInstance).get(class_instance_id)
        controller = db.Controller(self.cache.registry)
        crawler.crawl_grades(self.session, controller, class_instance)

        class_instance.grades_update = datetime.now().astimezone()
        controller.session.add(class_instance)
        controller.session.commit()

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
        log.info(f"Bootstrapping for period {period} or year {year}")

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

        # These should come for free (finding new classes recurses into sub-entities)
        # log.info(f"Updating enrollments")
        # processors.class_task(self.session, self.cache.registry, crawler.crawl_class_enrollments, year=year)
        # log.info(f"Updating shifts")
        # processors.class_task(self.session, self.cache.registry, crawler.crawl_class_shifts, year=year)
        # log.info(f"Updating grades")
        # processors.class_task(self.session, self.cache.registry, crawler.crawl_grades, year=year)
        # log.info(f"Updating class info")
        # processors.class_task(self.session, self.cache.registry, crawler.crawl_class_info, year=year)
        # log.info(f"Updating files")
        # processors.class_task(self.session, self.cache.registry, crawler.crawl_files, year=year)

        # Downloads known files
        processors.class_task(self.session, self.cache.registry, crawler.download_files, year=year, period=period)

    def roam(self):
        class_instances = self.cache.controller.session.query(m.ClassInstance) \
            .with_entities(m.ClassInstance.id,
                           m.ClassInstance.year,
                           m.ClassInstance.period_id,
                           m.ClassInstance.update_timestamp,
                           m.ClassInstance.shifts_update,
                           m.ClassInstance.enrollments_update,
                           m.ClassInstance.grades_update,
                           m.ClassInstance.files_update,
                           m.ClassInstance.events_update) \
            .all()

        current_date = datetime.now().astimezone()

        pending_info_update = []
        pending_shifts_update = []
        pending_enrollments_update = []
        pending_grades_update = []
        pending_files_update = []
        pending_events_update = []

        for class_instance_id, year, period_id, update_timestamp, shifts_update, enrollments_update, grades_update, \
            files_update, events_update in class_instances:
            if year < 2022:
                continue

            if (current_date - update_timestamp).days > 30 * 6:
                pending_info_update.append((class_instance_id, update_timestamp))
            if not shifts_update or (current_date - shifts_update).days > 30 * 6:
                pending_shifts_update.append((class_instance_id, shifts_update))
            if not enrollments_update or (current_date - enrollments_update).days > 30 * 6:
                pending_enrollments_update.append((class_instance_id, enrollments_update))
            if not grades_update or (current_date - grades_update).days > 30 * 6:
                pending_grades_update.append((class_instance_id, grades_update))
            if not files_update or (current_date - files_update).days > 30 * 6:
                pending_files_update.append((class_instance_id, files_update))
            if not events_update or (current_date - events_update).days > 30 * 6:
                pending_events_update.append((class_instance_id, events_update))

        def sort_by_timestamp(col):
            a_long_time_ago = datetime.now(timezone.utc).replace(year=2000)
            col.sort(key=lambda entry: (entry[1] if entry[1] else a_long_time_ago, -entry[0]))

        sort_by_timestamp(pending_info_update)
        sort_by_timestamp(pending_shifts_update)
        sort_by_timestamp(pending_enrollments_update)
        sort_by_timestamp(pending_grades_update)
        sort_by_timestamp(pending_files_update)
        sort_by_timestamp(pending_events_update)

        for class_instance_id, _ in pending_info_update:
            self.update_class_info(class_instance_id)

        for class_instance_id, _ in pending_enrollments_update:
            self.update_class_enrollments(class_instance_id)

        for class_instance_id, _ in pending_shifts_update:
            self.update_class_shifts(class_instance_id)

        for class_instance_id, _ in pending_files_update:
            self.update_class_files(class_instance_id)

        for class_instance_id, _ in pending_grades_update:
            self.update_class_grades(class_instance_id)

        for class_instance_id, _ in pending_events_update:
            self.update_class_events(class_instance_id)

    def _get_period(self, period_part, period_parts):
        if period_part is None or period_parts is None:
            return None
        period = self.cache.controller.get_period(period_part, period_parts)
        if period is None:
            raise ValueError("Invalid period")
        return period

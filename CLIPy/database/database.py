import datetime
import json
import logging
import os
import traceback
from time import sleep
from typing import List, Optional

import sqlalchemy as sa
import sqlalchemy.orm as orm
from bson import json_util
from sqlalchemy.exc import IntegrityError
from unidecode import unidecode
from difflib import SequenceMatcher
from . import models, candidates, exceptions

log = logging.getLogger(__name__)


def create_db_engine(backend: str, username=None, password=None, schema='CLIPy',
                     host='localhost', file=os.path.dirname(__file__) + '/CLIPy.db'):
    if backend == 'sqlite':
        log.debug(f"Establishing a database connection to file:'{file}'")
        return sa.create_engine(f"sqlite:///{file}?check_same_thread=False")  # , echo=True)
    elif backend == 'postgresql' and username is not None and password is not None and schema is not None:
        log.debug("Establishing a database connection to file:'{}'".format(file))
        return sa.create_engine(f"postgresql://{username}:{password}@{host}/{schema}", pool_size=10, max_overflow=30)
    else:
        raise ValueError('Unsupported database backend or not enough arguments supplied')


class SessionRegistry:
    def __init__(self, engine: sa.engine.Engine):
        self.engine = engine
        self.factory = orm.sessionmaker(bind=engine)
        self.scoped_session = orm.scoped_session(self.factory)
        models.Base.metadata.create_all(engine)

    def get_session(self):
        return self.scoped_session()

    def remove(self):
        self.scoped_session.remove()


# NOT thread-safe. Each thread must instantiate its own controller from the registry.
class Controller:
    def __init__(self, database_registry: SessionRegistry, cache: bool = False):
        self.session: orm.Session = database_registry.get_session()

        self.__caching__ = cache

        if self.session.query(models.Degree).count() == 0:
            self.__insert_default_degrees__()

        if self.session.query(models.Period).count() == 0:
            self.__insert_default_periods__()

        if self.session.query(models.ShiftType).count() == 0:
            self.__insert_default_shift_types__()

        self.__weekdays__ = {'segunda': 0,
                             'terça': 1,
                             'terca': 1,
                             'quarta': 2,
                             'quinta': 3,
                             'sexta': 4,
                             'sábado': 5,
                             'sabado': 5,
                             'domingo': 6}
        if self.__caching__:
            self.__load_cached_collections__()

    def __load_cached_collections__(self):
        log.debug("Building cached collections")
        self.__load_degrees__()
        self.__load_periods__()
        self.__load_shift_types__()
        log.debug("Finished building cache")

    def __load_degrees__(self):
        log.debug("Building degree cache")
        degrees = {}
        for degree in self.session.query(models.Degree).all():
            if degree.id == 4:  # FIXME, skipping the Integrated Master to avoid having it replace the Master
                continue
            degrees[degree.iid] = degree
        self.__degrees__ = degrees

    def __load_periods__(self):
        log.debug("Building period cache")
        periods = {}

        for period in self.session.query(models.Period).all():
            if period.parts not in periods:  # unseen letter
                periods[period.parts] = {}
            periods[period.parts][period.part] = period
        self.__periods__ = periods

    def __load_shift_types__(self):
        log.debug("Building shift types cache")
        shift_types = {}
        for shift_type in self.session.query(models.ShiftType).all():
            shift_types[shift_type.abbreviation] = shift_type
        self.__shift_types__ = shift_types

    def __insert_default_periods__(self):
        self.session.add_all(
            [models.Period(id=1, part=1, parts=1, letter='a'),
             models.Period(id=2, part=1, parts=2, letter='s'),
             models.Period(id=3, part=2, parts=2, letter='s'),
             models.Period(id=4, part=1, parts=4, letter='t'),
             models.Period(id=5, part=2, parts=4, letter='t'),
             models.Period(id=6, part=3, parts=4, letter='t'),
             models.Period(id=7, part=4, parts=4, letter='t')])
        self.session.commit()

    def __insert_default_degrees__(self):
        self.session.add_all(
            [models.Degree(id=1, iid='L', name="Licenciatura"),
             models.Degree(id=2, iid='M', name="Mestrado"),
             models.Degree(id=3, iid='D', name="Doutoramento"),
             models.Degree(id=4, iid='M', name="Mestrado Integrado"),
             models.Degree(id=5, iid='Pg', name="Pos-Graduação"),
             models.Degree(id=6, iid='EA', name="Estudos Avançados"),
             models.Degree(id=7, iid='pG', name="Pré-Graduação")])
        self.session.commit()

    def __insert_default_shift_types__(self):
        self.session.add_all(
            [models.ShiftType(id=1, name="Theoretical", abbreviation="t"),
             models.ShiftType(id=2, name="Practical", abbreviation="p"),
             models.ShiftType(id=3, name="Practical-Theoretical", abbreviation="tp"),
             models.ShiftType(id=4, name="Seminar", abbreviation="s"),
             models.ShiftType(id=5, name="Tutorial Orientation", abbreviation="ot"),
             models.ShiftType(id=6, name="Field Work", abbreviation="tc"),
             models.ShiftType(id=7, name="Online Theoretical", abbreviation="to"),
             models.ShiftType(id=8, name="Online Practical", abbreviation="po"),
             models.ShiftType(id=9, name="Online Practical-Theoretical", abbreviation="op")])
        self.session.commit()

    def get_department(self, identifier: int) -> Optional[models.Department]:
        return self.session.query(models.Department).filter_by(id=identifier).first()

    def get_degree(self, abbreviation: str) -> Optional[models.Degree]:
        if self.__caching__:
            if abbreviation not in self.__degrees__:
                return None
            return self.__degrees__[abbreviation]
        else:
            return self.session.query(models.Degree).filter_by(id=abbreviation).first()

    __periods = {
        1: {
            1: {'id': 1, 'parts': 1, 'part': 1, 'letter': 'a'},
        },
        2: {
            1: {'id': 2, 'parts': 2, 'part': 1, 'letter': 's'},
            2: {'id': 3, 'parts': 2, 'part': 2, 'letter': 's'},

        },
        4: {
            1: {'id': 4, 'parts': 4, 'part': 1, 'letter': 't'},
            2: {'id': 5, 'parts': 4, 'part': 2, 'letter': 't'},
            3: {'id': 6, 'parts': 4, 'part': 3, 'letter': 't'},
            4: {'id': 7, 'parts': 4, 'part': 4, 'letter': 't'},
        }
    }
    __period_set = [
        {'id': 1, 'parts': 1, 'part': 1, 'letter': 'a'},
        {'id': 2, 'parts': 2, 'part': 1, 'letter': 's'},
        {'id': 3, 'parts': 2, 'part': 2, 'letter': 's'},
        {'id': 4, 'parts': 4, 'part': 1, 'letter': 't'},
        {'id': 5, 'parts': 4, 'part': 2, 'letter': 't'},
        {'id': 6, 'parts': 4, 'part': 3, 'letter': 't'},
        {'id': 7, 'parts': 4, 'part': 4, 'letter': 't'}
    ]

    def get_period(self, part: int, parts: int) -> dict:
        return self.__periods[parts][part]

    def get_period_set(self) -> {dict}:
        return self.__period_set

    def get_building_set(self) -> {models.Building}:
        return set(self.session.query(models.Building).all())

    def get_room_set(self) -> {models.Building}:
        return set(self.session.query(models.Room).all())

    def get_department_set(self) -> {models.Department}:
        return set(self.session.query(models.Department).all())

    def get_degree_set(self) -> {models.Degree}:
        if self.__caching__:
            return set(self.__degrees__.values())
        else:
            return set(self.session.query(models.Degree).all())

    def get_course(self, identifier: int = None, abbreviation: str = None, year: int = None) -> Optional[models.Course]:
        if identifier is not None:
            matches = self.session.query(models.Course).filter_by(id=identifier).all()
        elif abbreviation is not None:
            matches = self.session.query(models.Course).filter_by(abbreviation=abbreviation).all()
        else:
            log.warning(f"Unable to determine course with id {identifier}, abbr {abbreviation} on year {year}")
            return None

        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            if year is None:
                raise exceptions.MultipleMatches("Multiple matches. Year unspecified")

            # Year filter
            if year is not None:
                year_matches = []
                for course in matches:
                    if course.contains(year):
                        year_matches.append(course)
                if len(year_matches) == 1:
                    return year_matches[0]
                elif len(matches) > 1:
                    raise exceptions.MultipleMatches("Multiple matches. Unable to determine the correct one.")

    def get_courses(self) -> [models.Course]:
        return self.session.query(models.Course).all()

    def get_shift_type(self, abbreviation: str) -> Optional[models.ShiftType]:
        if self.__caching__:
            if abbreviation in self.__shift_types__:
                return self.__shift_types__[abbreviation]
        else:
            return self.session.query(models.ShiftType).filter_by(abbreviation=abbreviation).first()

    def get_teacher(self, name: str, department: models.Department) -> Optional[models.Teacher]:
        """
        | Fetches a teacher object.
        | THIS METHOD IS FLAWED but I'm afraid it cannot be improved without using shenanigans.
        | The problem is that teacher names are displayed all over CLIP, but there's only one page with their ID's.
            With that in mind teacher queries have to be performed with their names and the department which 'owns'
            the page being seen.
        | The current procedure is to query by name first.
        | If there's only one match, then that's the one to be returned.
        | If there are multiple matches they could either be the same teacher in different departments or different
            teachers which happen to have the same name. In that scenario the next step is to filter by department,
            and hopefully there's only one match left. If there isn't check if non-department-filtered results are
            the same teacher and return one of them.
        | Albeit unlikely, the two possible issues with this method are:
        | - A teacher is lecturing a class given by another department and there's a name collision
        | - There are two different teachers with the same name in the same department.
        | TODO A workaround which is ridiculously CPU/time intensive unless implemented properly is to use
            :py:const:`CLIPy.urls.TEACHER_SCHEDULE` to check if results match.
        | An idea is to ignore unmatched teachers (leave shifts without the teacher) and then crawl
            :py:const:`CLIPy.urls.TEACHER_SCHEDULE` once and fill the gaps.
        | TODO 2 Add `year` to the equation in hope of better guessing which `teacher` is the correct in the
            `multiple but all the same` scenario.
        | TODO 3 Find some alcohol and forget this

        :param name: Teacher name
        :param department: Teacher department
        :return: Matching teacher
        """
        matches = self.session.query(models.Teacher) \
            .filter(models.Teacher.name == name, models.Department.id == department.id) \
            .all()
        if (match_count := len(matches)) == 1:
            return matches[0]
        elif match_count == 0:
            return None

        log.error(f'Several teachers with the name {name}')  # TODO to exception
        return None

    def get_class(self, id: int) -> Optional[models.Class]:
        return self.session.query(models.Class).filter_by(id=id).first()

    def get_class_instance(self, class_id: int, year: int, period: id) -> Optional[models.ClassInstance]:
        return self.session.query(models.ClassInstance) \
            .filter(models.ClassInstance.class_id == class_id,
                    models.ClassInstance.year == year,
                    models.ClassInstance.period_id == period) \
            .first()

    def add_departments(self, departments: [candidates.Department]):
        """
        Adds departments to the database. It updates then in case they already exist but details differ.

        :param departments: An iterable collection of department candidates
        """
        new_count = 0
        updated_count = 0
        try:
            for candidate in departments:
                # Lookup for existing departments matching the new candidate
                department = self.session.query(models.Department).filter_by(id=candidate.id).first()

                if department is None:  # Create a new department
                    self.session.add(models.Department(
                        id=candidate.id,
                        name=candidate.name,
                        first_year=candidate.first_year,
                        last_year=candidate.last_year))
                    new_count += 1
                else:  # Update the existing one accordingly
                    updated = False
                    if candidate.name is not None and department.name != candidate.name:
                        department.name = candidate.name
                        updated = True

                    first, last = department.first_year, department.last_year
                    department.add_year(candidate.first_year)
                    department.add_year(candidate.last_year)
                    if (department.first_year, department.last_year) != (first, last):
                        updated = True
                    if updated:
                        updated_count += 1

            log.info(f"{new_count} departments added and {updated_count} updated!")
            self.session.commit()
        except Exception:
            log.error("Failed to add the departments\n" + traceback.format_exc())
            self.session.rollback()

    def add_class(self, candidate: candidates.Class) -> models.Class:
        db_class = self.session.query(models.Class).filter_by(id=candidate.id).first()

        if db_class is not None:  # Already stored
            changed = False
            if db_class.name != candidate.name:
                log.warning("Class name change:\n"
                            f"\t{db_class}\t to \t{candidate})")
                db_class.name = candidate.name
                changed = True

            if candidate.abbreviation is not None:
                if db_class.abbreviation is None or db_class.abbreviation == '???':
                    db_class.abbreviation = candidate.abbreviation
                    changed = True

                elif db_class.abbreviation != candidate.abbreviation:
                    if SequenceMatcher(None, db_class.abbreviation, candidate.abbreviation).ratio() < 0.3:
                        log.error("Class abbreviation change prevented. "
                                        f"{db_class.abbreviation} to {candidate.abbreviation} (id {candidate.id})")
                    else:
                        log.warning("Class abbreviation change."
                                    f"{db_class.abbreviation} to {candidate.abbreviation} (id {candidate.id})")
                        db_class.abbreviation = candidate.abbreviation
                        changed = True
            if changed:
                self.session.commit()

            return db_class

        log.info("Adding class {}".format(candidate))
        db_class = models.Class(
            id=candidate.id,
            name=candidate.name,
            abbreviation=candidate.abbreviation,
            ects=candidate.ects)
        self.session.add(db_class)
        self.session.commit()
        return db_class

    def add_class_instances(self, instances: [candidates.ClassInstance]):
        ignored = 0
        new = []
        for instance in instances:
            db_class_instance = self.session.query(models.ClassInstance).filter_by(
                parent=instance.parent,
                year=instance.year,
                period_id=instance.period
            ).first()
            if db_class_instance is None:
                db_class_instance = models.ClassInstance(
                    parent=instance.parent,
                    year=instance.year,
                    period_id=instance.period,
                    department=instance.department
                )
                self.session.add(db_class_instance)
                new.append(db_class_instance)
                self.session.commit()
            else:
                ignored += 1
        if len(instances) - ignored > 0:
            log.info(f"{len(instances) - ignored} class instances added successfully! ({ignored} ignored)")
        return new

    def update_class_instance_info(self, instance: models.ClassInstance, upstream_info):
        information = dict()
        for attribute in ('description', 'objectives', 'requirements', 'competences', 'program',
                          'bibliography', 'assistance', 'teaching_methods', 'evaluation_methods', 'extra_info'):
            if attribute in upstream_info:
                portuguese, english, time, editor = upstream_info[attribute]
                information[attribute] = {
                    'pt': portuguese,
                    'en': portuguese,
                    'time': time,
                    'editor': editor,
                }
        if 'working_hours' in upstream_info:
            information['working_hours'] = upstream_info['working_hours']
        instance.information = json.dumps(information, default=json_util.default)
        self.session.commit()

    def update_class_instance_events(self, instance: models.ClassInstance, events):
        db_events = instance.events
        changed = False
        new = set(events)
        disappeared = set()
        for db_event in db_events:
            exists = False
            for event in new:
                date, from_time, to_time, event_type, season, info, note = event
                if not (db_event.date == date
                        and db_event.type == event_type
                        and db_event.from_time == from_time
                        and db_event.to_time == to_time
                        and db_event.season == season
                        and db_event.info == info
                        and db_event.note == note):
                    continue

                # TODO update changed data here
                new.remove(event)
                exists = True
                break
            if not exists:
                disappeared.add(db_event)

        for event in disappeared:
            self.session.delete(event)

        for event in new:
            date, from_time, to_time, event_type, season, info, note = event
            event = models.ClassEvent(
                class_instance=instance,
                date=date,
                from_time=from_time,
                to_time=to_time,
                type=event_type,
                season=season,
                info=info,
                note=note)
            self.session.add(event)
            changed = True

        if changed:
            log.warning(f"{instance} evaluations changed ({len(new)} new, {len(disappeared)} deleted)")
            try:
                self.session.commit()
            except Exception as e:
                print()

    def add_courses(self, courses: [candidates.Course]):
        updated = 0
        try:
            for course in courses:
                db_course = self.session.query(models.Course).filter_by(id=course.id).first()
                if db_course is None:
                    self.session.add(models.Course(
                        id=course.id,
                        name=course.name,
                        abbreviation=course.abbreviation,
                        first_year=course.first_year,
                        last_year=course.last_year,
                        degree=course.degree))
                    self.session.commit()
                else:
                    changed = False
                    if course.name is not None and course.name != db_course.name:
                        raise Exception("Attempted to change a course name")

                    if course.abbreviation is not None:
                        db_course.abbreviation = course.abbreviation
                        changed = True
                    if course.degree is not None:
                        db_course.degree = course.degree
                        changed = True
                    if db_course.first_year is None or course.first_year is not None \
                            and course.first_year < db_course.first_year:
                        db_course.first_year = course.first_year
                        changed = True
                    if db_course.last_year is None or course.last_year is not None \
                            and course.last_year > db_course.last_year:
                        db_course.last_year = course.last_year
                        changed = True
                    if changed:
                        updated += 1
                        self.session.commit()

            if len(courses) > 0:
                log.info("{} courses added successfully! ({} updated)".format(len(courses), updated))
        except Exception:
            self.session.rollback()
            raise Exception("Failed to add courses.\n%s" % traceback.format_exc())

    def add_student(self, candidate: candidates.Student) -> models.Student:
        if candidate.name is None or candidate.name == '':
            raise Exception("Invalid name")

        if candidate.id is None:
            raise Exception('No student ID provided')

        if candidate.last_year is None:
            raise Exception("Year not provided")

        year = candidate.last_year
        student = self.session.query(models.Student).filter_by(id=candidate.id).first()

        if student is None:  # new student, add him
            student = models.Student(
                id=candidate.id,
                name=candidate.name,
                course=candidate.course,
                abbreviation=candidate.abbreviation,
                first_year=candidate.first_year,
                last_year=candidate.last_year)
            self.session.add(student)
            self.session.commit()
            log.info(f"Added student {student}")
            if candidate.course is not None:
                try:  # Hackish race condition prevention. Not pretty but works (most of the time)
                    self.add_student_course(student=student, course=candidate.course, year=year)
                except IntegrityError:
                    sleep(3)
                    self.session.rollback()
                    self.add_student_course(student=student, course=candidate.course, year=year)
        else:
            if student.name != candidate.name:
                if unidecode(student.name.lower()) == unidecode(candidate.name.lower()):
                    if unidecode(candidate.name.lower()) == student.name.lower():
                        student.name = candidate.name
                        self.session.commit()
                else:
                    if student.abbreviation == candidate.abbreviation:
                        if len(student.name) < len(candidate.name):
                            student.name = candidate.name
                            self.session.commit()
                    elif SequenceMatcher(None, student.name, candidate.name).ratio() > 0.8:
                        student.name = candidate.name
                        self.session.commit()
                    else:
                        raise exceptions.IdCollision(
                            "Students having an ID collision\n"
                            "Student:{}\n"
                            "Candidate{}".format(student, candidate))

            if student.abbreviation != candidate.abbreviation:
                if student.abbreviation is None:
                    if candidate.abbreviation is not None:
                        student.abbreviation = candidate.abbreviation
                        self.session.commit()
                elif candidate.abbreviation is not None and candidate.abbreviation != student.abbreviation:
                    log.warning("Attempted to change the student abbreviation to another one\n"
                                "Student:{}\n"
                                "Candidate{}".format(student, candidate))
                    student.abbreviation = candidate.abbreviation
                    self.session.commit()
                    raise Exception(
                        "Attempted to change the student abbreviation to another one\n"
                        "Student:{}\n"
                        "Candidate{}".format(student, candidate))

            if candidate.course is not None:
                student.course_id = candidate.course.id
                try:  # Hackish race condition prevention. Not pretty but works (most of the time)
                    self.add_student_course(student=student, course=candidate.course, year=year)
                except IntegrityError:
                    sleep(3)
                    self.session.rollback()
                    self.add_student_course(student=student, course=candidate.course, year=year)

            if candidate.first_year:
                if student.first_year != candidate.first_year:
                    student.add_year(candidate.first_year)
            if candidate.last_year:
                if student.last_year != candidate.last_year:
                    student.add_year(candidate.last_year)

        return student

    def get_student(self, identifier: int, name: str = None) -> Optional[models.Student]:
        return self.session.query(models.Student).filter_by(id=identifier).first()

    def get_students(self, year=None):
        if year is None:
            return self.session.query(models.Student).all()
        else:
            return self.session.query(models.Student).filter_by(last_year=year).all()

    def get_teachers(self, year=None):
        if year is None:
            return self.session.query(models.Teacher).all()
        else:
            return self.session.query(models.Teacher).filter_by(last_year=year).all()

    def add_student_course(self, student: models.Student, course: models.Course, year: int):
        if student is None or course is None or year is None:
            raise Exception("Missing details on a student's course assignment.")

        match: models.StudentCourse = self.session.query(models.StudentCourse) \
            .filter_by(student=student, course=course).first()

        if match is None:
            self.session.add(models.StudentCourse(student=student, course=course, first_year=year, last_year=year))
        else:
            match.add_year(year)

        self.session.commit()

    def update_student_gender(self, student: models.Student, gender: int):
        if gender not in (0, 1):
            raise Exception("Non-binary genders forbidden")
        student.gender = gender
        self.session.commit()

    def add_teacher(self, candidate: candidates.Teacher) -> models.Teacher:
        if candidate.id is None:
            raise Exception("Teacher candidates must have an ID set")
        teacher: [models.Teacher] = self.session.query(models.Teacher).filter_by(id=candidate.id).first()

        if teacher is None:  # No teacher, add him/her
            teacher = models.Teacher(id=candidate.id,
                                     name=candidate.name,
                                     first_year=candidate.first_year,
                                     last_year=candidate.last_year)

            self.session.add(teacher)
            log.info(f'Added the teacher {teacher}')
            teacher.departments.append(candidate.department)
        else:
            if candidate.department not in teacher.departments:
                teacher.departments.append(candidate.department)

            teacher.add_year(candidate.first_year)
            teacher.add_year(candidate.last_year)

            if teacher.name != candidate.name:
                log.warning(f"Changing teacher {teacher.name} to {candidate.name}")
                teacher.name = candidate.name

        # Handle the newly known shifts and remove the old ones if they disappeared
        new_shifts = {shift for shift_year in candidate.schedule_entries.values() for shift in shift_year}
        year_period_set = {y_p for y_p in candidate.schedule_entries.keys()}
        for existing_shift in teacher.shifts:
            if existing_shift in new_shifts:
                new_shifts.remove(existing_shift)
                continue

            class_instance = existing_shift.class_instance
            if (class_instance.year, class_instance.period) in year_period_set:
                log.warning("Teacher stopped lecturing a shift")
                # teacher.shifts.remove(existing_shift)
        for new_shift in new_shifts:
            teacher.shifts.append(new_shift)

        self.session.commit()
        return teacher

    def add_shift(self, shift: candidates.Shift) -> models.Shift:
        if shift.type is None:
            raise Exception("Typeless shift found")

        db_shift: models.Shift = self.session.query(models.Shift).filter_by(
            number=shift.number,
            class_instance=shift.class_instance,
            type=shift.type
        ).first()

        if db_shift is None:
            db_shift = models.Shift(
                class_instance=shift.class_instance,
                number=shift.number,
                type=shift.type,
                enrolled=shift.enrolled,
                capacity=shift.capacity,
                minutes=shift.minutes,
                routes=shift.routes,
                restrictions=shift.restrictions,
                state=shift.restrictions)
            self.session.add(db_shift)
            self.session.commit()
            log.info(f"Added shift {db_shift}")
        else:
            changed = False
            if shift.minutes is not None and shift.minutes != 0:
                db_shift.minutes = shift.minutes
                changed = True
            if shift.enrolled is not None:
                db_shift.enrolled = shift.enrolled
                changed = True
            if shift.capacity is not None:
                db_shift.capacity = shift.capacity
                changed = True
            if shift.routes is not None:
                db_shift.routes = shift.routes
                changed = True
            if shift.restrictions is not None:
                db_shift.restrictions = shift.restrictions
                changed = True
            if shift.state is not None:
                db_shift.state = shift.state
                changed = True
            if changed:
                self.session.commit()

        return db_shift

    def get_shift(self, class_instance: models.ClassInstance, shift_type: models.ShiftType,
                  number: int) -> models.Shift:
        return self.session.query(models.Shift) \
            .filter_by(
            class_instance=class_instance,
            type=shift_type,
            number=number) \
            .first()

    # Reconstructs the instances of a shift.
    # Destructive is faster because it doesn't worry about checking instance by instance,
    # it'll delete em' all and rebuilds
    def add_shift_instances(self, instances: List[candidates.ShiftInstance], destructive=False):
        shift = None
        for instance in instances:
            if shift is None:
                shift = instance.shift
            elif shift != instance.shift:
                raise Exception('Instances belong to multiple shifts')
        if shift is None:
            return

        if destructive:
            try:
                deleted = self.session.query(models.ShiftInstance).filter_by(shift=shift).delete()
                if deleted > 0:
                    log.info(f"Deleted {deleted} shift instances from the shift {shift}")
            except Exception:
                self.session.rollback()
                raise Exception("Error deleting shift instances for shift {}\n{}".format(shift, traceback.format_exc()))

            for instance in instances:
                shift.instances.append(models.ShiftInstance(
                    shift=shift,
                    start=instance.start,
                    end=instance.end,
                    room=instance.room,
                    weekday=instance.weekday))

            if len(instances) > 0:
                log.info(f"Added {len(instances)} shift instances to the shift {shift}")
                self.session.commit()
        else:
            db_shift_instances = self.session.query(models.ShiftInstance).filter_by(shift=shift).all()
            for db_shift_instance in db_shift_instances:
                matched = False
                for instance in instances[:]:
                    if db_shift_instance.start == instance.start and db_shift_instance.end == instance.end and \
                            db_shift_instance.weekday == instance.weekday:
                        matched = True
                        if db_shift_instance.room != instance.room:  # Update the room
                            log.warning(f'An instance of {shift} changed the room from '
                                        f'{db_shift_instance.room} to {instance.room}')
                            db_shift_instance.room = instance.room
                        instances.remove(instance)
                        break
                if not matched:
                    log.info(f'An instance of {shift} ceased to exist ({db_shift_instance})')
                    self.session.delete(db_shift_instance)
            for instance in instances:
                shift.instances.append(
                    models.ShiftInstance(
                        shift=shift,
                        start=instance.start,
                        end=instance.end,
                        room=instance.room,
                        weekday=instance.weekday))
            self.session.commit()

    def add_shift_students(self, shift: models.Shift, students: [models.Student]):
        old_students = set(shift.students)
        new_students = set(students)
        deleted_students = old_students.difference(new_students)
        new_students = new_students.difference(old_students)
        new_count = len(new_students)
        deleted_count = len(deleted_students)
        [shift.students.append(student) for student in new_students]
        if deleted_count > 0:
            [shift.students.remove(student) for student in deleted_students]
        if new_count > 0 or deleted_count > 0:
            log.info(f"{new_count} students added and {deleted_count} removed from the shift {shift}.")
            self.session.commit()

    def add_admissions(self, admissions: [candidates.Admission]):
        admissions = list(map(lambda admission: models.Admission(
            student=admission.student,
            name=admission.name,
            course=admission.course,
            phase=admission.phase,
            year=admission.year,
            option=admission.option,
            state=admission.state
        ), admissions))
        self.session.add_all(admissions)

        if len(admissions) > 0:
            self.session.commit()
            log.info(f"{len(admissions)} admission records added successfully!")

    def add_enrollments(self, enrollments: [candidates.Enrollment]):
        added = 0
        updated = 0
        deleted = 0

        class_instance = None
        for enrollment in enrollments:
            if class_instance is None:
                class_instance = enrollment.class_instance
            elif class_instance != enrollment.class_instance:
                raise Exception('Enrollments belong to multiple classes')

        db_enrollments = self.session.query(models.Enrollment).filter_by(class_instance=class_instance).all()
        for db_enrollment in db_enrollments:
            matched = False
            for enrollment in enrollments[:]:
                if db_enrollment.student == enrollment.student:
                    matched = True
                    # TODO update data here
                    enrollments.remove(enrollment)
                    break
            if not matched:
                log.info(f'An enrollment ceased to exist ({db_enrollment.student} to {db_enrollment.class_instance})')
                deleted += 1
                self.session.delete(db_enrollment)
                self.session.commit()

        for enrollment in enrollments:
            db_enrollment: models.Enrollment = self.session.query(models.Enrollment) \
                .filter_by(student=enrollment.student, class_instance=enrollment.class_instance) \
                .first()
            if db_enrollment:
                changed = False
                if db_enrollment.observation is None and enrollment.observation is not None:
                    db_enrollment.observation = enrollment.observation
                    changed = True
                if db_enrollment.student_year is None and enrollment.student_year is not None:
                    db_enrollment.student_year = enrollment.student_year
                    changed = True
                if db_enrollment.attempt is None and enrollment.attempt is not None:
                    db_enrollment.attempt = enrollment.attempt
                    changed = True
                if db_enrollment.statutes is None and enrollment.statutes is not None:
                    db_enrollment.statutes = enrollment.statutes
                    changed = True
                if changed:
                    updated += 1
                    self.session.commit()
            else:
                enrollment = models.Enrollment(
                    student=enrollment.student,
                    class_instance=enrollment.class_instance,
                    attempt=enrollment.attempt,
                    student_year=enrollment.student_year,
                    statutes=enrollment.statutes,
                    observation=enrollment.observation)
                added += 1
                self.session.add(enrollment)
                self.session.commit()

        if added > 0 or updated > 0 or deleted > 0:
            log.info("Enrollments in {} changed.  {} new, {} updated and {} deleted ({} ignored)!".format(
                class_instance, added, updated, deleted, len(enrollments) - added - updated - deleted))

    def update_enrollment_results(self, student: models.Student, class_instance: models.ClassInstance, results,
                                  approved: bool):
        enrollment: models.Enrollment = self.session.query(models.Enrollment) \
            .filter_by(student=student, class_instance=class_instance).first()

        if enrollment is None:
            log.error(f"Enrollment of {student} to {class_instance} is missing.")
            return
        result_count = len(results)
        if result_count < 1 or result_count > 3:
            raise Exception("Invalid result format")
        for result in results:
            if len(result) < 2:
                raise Exception("Invalid result format")

        continuous_grade, continuous_date = results[0]
        if isinstance(continuous_grade, int):
            enrollment.continuous_grade = continuous_grade
        else:
            enrollment.continuous_grade = 0
        enrollment.continuous_grade_date = continuous_date

        if result_count > 1:
            exam_grade, exam_date = results[1]
            if isinstance(exam_grade, int):
                enrollment.exam_grade = exam_grade
            else:
                enrollment.exam_grade = 0
            enrollment.continuous_grade_date = exam_date

        if result_count == 3:
            special_grade, special_date = results[2]
            if isinstance(special_grade, int):
                enrollment.special_grade = special_grade
            else:
                enrollment.special_grade = 0
            enrollment.special_grade_date = special_date

        enrollment.approved = approved

        self.session.commit()

    def update_enrollment_attendance(self, student: models.Student, class_instance: models.ClassInstance,
                                     attendance: bool, date: datetime.date):
        enrollment: models.Enrollment = self.session.query(models.Enrollment) \
            .filter_by(student=student, class_instance=class_instance).first()

        if enrollment is None:
            log.error(f'Unable to update enrollment. {student} to {class_instance} not found.')
        else:
            log.debug(f'Adding student {student} data to {class_instance}\n'
                      f'\tAttendance:{attendance} As of:{date}')
            enrollment.attendance = attendance
            enrollment.attendance_date = date

            self.session.commit()

    def update_enrollment_improvement(self, student: models.Student, class_instance: models.ClassInstance,
                                      improved: bool, grade: int, date: datetime.date):
        enrollment: models.Enrollment = self.session.query(models.Enrollment) \
            .filter_by(student=student, class_instance=class_instance).first()

        if enrollment:
            log.debug(f'Adding student {student} data to {class_instance}\n'
                      f'\tImproved:{improved}, Grade:{grade} As of:{date}')
            enrollment.improved = improved
            enrollment.improvement_grade = grade
            enrollment.improvement_grade_date = date
        else:
            enrollments: [models.Enrollment] = self.session.query(models.Enrollment) \
                .filter_by(student=student, approved=True) \
                .join(models.ClassInstance) \
                .filter(models.ClassInstance.parent == class_instance.parent) \
                .all()
            count = len(enrollments)
            if count == 1:
                enrollment = enrollments[0]
                enrollment.improved = improved
                enrollment.improvement_grade = grade
                enrollment.improvement_grade_date = date
            elif count > 1:
                log.error("Consistency issues. A student was approved several times.\n"
                          f"Student:{student}, Instance:{class_instance}")

            else:
                log.warning("No approved enrollment. Enrollment search was not performed in chronological order.")

        self.session.commit()

    def add_room(self, candidate: candidates.Room) -> models.Room:
        if candidate.name is None:
            raise Exception()
        try:
            room = self.session \
                .query(models.Room) \
                .filter_by(id=candidate.id,
                           room_type=candidate.type,
                           building=candidate.building) \
                .first()
            if room is None:
                room = models.Room(id=candidate.id,
                                   name=candidate.name,
                                   room_type=candidate.type,
                                   building=candidate.building)
                self.session.add(room)
                self.session.commit()
            return room
        except Exception:
            log.error("Failed to add the room\n%s" % traceback.format_exc())
            self.session.rollback()

    def get_room(self, name: str, building: models.Building,
                 room_type: models.RoomType = None) -> Optional[models.Room]:
        matches = self.session.query(models.Room).filter_by(name=name, building=building).all()
        if len(matches) == 1:
            return matches[0]
        else:  # Proceed to guess
            if room_type:  # We have a type hint (which can be inaccurate, eg. computer labs marked as regular labs)
                if room_type == models.RoomType.laboratory:  # If this is a lab hint
                    labs = []  # Group up labs and computer labs
                    for room in matches:
                        if room.room_type in (models.RoomType.laboratory, models.RoomType.computer):
                            labs.append(room)
                    if len(labs) == 1:  # If there is only one then that's the one
                        return labs[0]
                else:  # Quite a specific hint, look it up directly, should be no problem
                    return self.session.query(models.Room) \
                        .filter_by(name=name, room_type=room_type, building=building).first()
            else:  # regular rooms have no type hint. Assume that if there's no type hint then we want a regular one
                regular_rooms = []
                for room in matches:
                    if room.room_type not in (models.RoomType.laboratory, models.RoomType.computer):
                        regular_rooms.append(room)
                if len(regular_rooms) == 1:
                    return regular_rooms[0]

    def add_building(self, building: candidates.Building) -> models.Building:
        db_building = self.session.query(models.Building).filter_by(name=building.name).first()
        if db_building is None:
            db_building = models.Building(
                id=building.id,
                name=building.name,
                first_year=building.first_year,
                last_year=building.last_year)
            self.session.add(db_building)
            self.session.commit()
        else:
            db_building.first_year = building.first_year
            db_building.last_year = building.last_year
            self.session.commit()
        return db_building

    def get_building(self, building: str) -> models.Building:
        return self.session.query(models.Building).filter_by(name=building).first()

    def add_class_file(self, candidate: candidates.File, class_instance: models.ClassInstance) -> models.File:
        file = self.session.query(models.File).filter_by(id=candidate.id).first()

        if file is None:
            file = models.File(
                id=candidate.id,
                size=candidate.size,
                hash=candidate.hash,
                downloaded=False)
            log.info(f"Adding file {file}")
            self.session.add(file)
            class_file = models.ClassFile(
                name=candidate.name,
                file_type=candidate.file_type,
                uploader=candidate.uploader,
                upload_datetime=candidate.upload_datetime,
                file=file,
                class_instance=class_instance)
            self.session.add(class_file)
            self.session.commit()
        else:
            if file not in class_instance.files:
                class_file = models.ClassFile(
                    name=candidate.name,
                    file_type=candidate.file_type,
                    uploader=candidate.uploader,
                    upload_datetime=candidate.upload_datetime,
                    file=file,
                    class_instance=class_instance)
                self.session.add(class_file)
                self.session.commit()
        return file

    def update_downloaded_file(self, file: models.File, mime: str, hash: str):
        file.mime = mime
        file.hash = hash
        file.downloaded = True
        self.session.commit()

    def fetch_class_instances(self, year_asc=True, year=None, period=None) -> [models.ClassInstance]:
        order = sa.asc(models.ClassInstance.year) if year_asc else sa.desc(models.ClassInstance.year)
        if year is None:
            if period is not None:
                log.warning("Period specified without an year")
            if year_asc:
                instances = self.session.query(models.ClassInstance).order_by(order).all()
            else:
                instances = self.session.query(models.ClassInstance).order_by(order).all()
        else:
            if period is None:
                instances = self.session.query(models.ClassInstance).filter_by(year=year).order_by(order).all()
            else:
                instances = self.session.query(models.ClassInstance). \
                    filter_by(year=year, period_id=period['id']).order_by(order).all()
        return list(instances)

    def find_student(self, name: str, course=None) -> [models.Student]:
        query_string = '%'
        for word in name.split():
            query_string += (word + '%')

        if course is None:
            return self.session.query(models.Student).filter(models.Student.name.ilike(query_string)).all()
        else:
            return self.session.query(models.Student).filter(
                models.Student.name.ilike(query_string),
                course=course
            ).all()

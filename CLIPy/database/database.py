import datetime
import json
import logging
import os
import traceback
from time import sleep
from typing import List, Optional

import sqlalchemy as sa
import sqlalchemy.orm as orm
from sqlalchemy.exc import IntegrityError

from . import models, candidates

log = logging.getLogger(__name__)


def create_db_engine(backend: str, username=None, password=None, schema='CLIPy',
                     host='localhost', file=os.path.dirname(__file__) + '/CLIPy.db'):
    if backend == 'sqlite':
        log.debug(f"Establishing a database connection to file:'{file}'")
        return sa.create_engine(f"sqlite:///{file}?check_same_thread=False")  # , echo=True)
    elif backend == 'postgresql' and username is not None and password is not None and schema is not None:
        log.debug("Establishing a database connection to file:'{}'".format(file))
        return sa.create_engine(f"postgresql://{username}:{password}@{host}/{schema}")
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
        self.registry = database_registry
        self.session: orm.Session = database_registry.get_session()

        self.__caching__ = cache

        if self.session.query(models.Degree).count() == 0:
            self.__insert_default_degrees__()

        if self.session.query(models.Period).count() == 0:
            self.__insert_default_periods__()

        if self.session.query(models.TurnType).count() == 0:
            self.__insert_default_turn_types__()

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
        self.__load_institutions__()
        self.__load_degrees__()
        self.__load_periods__()
        self.__load_departments__()
        self.__load_courses__()
        self.__load_turn_types__()
        self.__load_teachers__()
        self.__load_buildings__()
        self.__load_rooms__()
        log.debug("Finished building cache")

    def __load_institutions__(self):
        log.debug("Building institution cache")
        institutions = {}
        for institution in self.session.query(models.Institution).all():
            institutions[institution.id] = institution
        self.__institutions__ = institutions

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

    def __load_departments__(self):
        log.debug("Building department cache")
        departments = {}
        for department in self.session.query(models.Department).all():
            departments[department.id] = department
        self.__departments__ = departments

    def __load_courses__(self):
        log.debug("Building course cache")
        courses = {}
        course_abbreviations = {}
        for course in self.session.query(models.Course).all():
            courses[course.iid] = course

            if course.abbreviation not in course_abbreviations:
                course_abbreviations[course.abbreviation] = []
            course_abbreviations[course.abbreviation].append(course)
        self.__courses__ = courses
        self.__course_abbrs__ = course_abbreviations

    def __load_turn_types__(self):
        log.debug("Building turn types cache")
        turn_types = {}
        for turn_type in self.session.query(models.TurnType).all():
            turn_types[turn_type.abbreviation] = turn_type
        self.__turn_types__ = turn_types

    def __load_teachers__(self):
        log.debug("Building teacher cache")
        teachers = {}
        for teacher in self.session.query(models.Teacher).all():
            teachers[teacher.name] = teacher
        self.__teachers__ = teachers

    def __load_buildings__(self):
        log.debug("Building building cache")
        buildings = {}
        for building in self.session.query(models.Building).all():
            buildings[building.name] = building
        self.__buildings__ = buildings

    def __load_rooms__(self):
        log.debug("Building room cache")
        rooms = {}
        for room, building in self.session.query(models.Room, models.Building).all():
            if building.name not in rooms:
                rooms[building.name] = {}
            if room.room_type not in rooms[building.name]:
                rooms[building.name][room.room_type] = {}
            rooms[building.name][room.room_type][room.name] = building
        self.__rooms__ = rooms

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

    def __insert_default_turn_types__(self):
        self.session.add_all(
            [models.TurnType(id=1, name="Theoretical", abbreviation="t"),
             models.TurnType(id=2, name="Practical", abbreviation="p"),
             models.TurnType(id=3, name="Practical-Theoretical", abbreviation="tp"),
             models.TurnType(id=4, name="Seminar", abbreviation="s"),
             models.TurnType(id=5, name="Tutorial Orientation", abbreviation="ot")])
        self.session.commit()

    def get_institution(self, identifier: int) -> Optional[models.Institution]:
        if self.__caching__:
            if identifier not in self.__institutions__:
                return None
            return self.__institutions__[identifier]
        else:
            return self.session.query(models.Institution).filter_by(id=identifier).first()

    def get_department(self, identifier: int) -> Optional[models.Department]:
        if self.__caching__:
            if identifier not in self.__departments__:
                return None
            return self.__departments__[identifier]
        else:
            return self.session.query(models.Department).filter_by(id=identifier).first()

    def get_degree(self, abbreviation: str) -> Optional[models.Degree]:
        if self.__caching__:
            if abbreviation not in self.__degrees__:
                return None
            return self.__degrees__[abbreviation]
        else:
            return self.session.query(models.Degree).filter_by(id=abbreviation).first()

    def get_period(self, part: int, parts: int) -> Optional[models.Period]:
        if self.__caching__:
            if parts not in self.__periods__ or part > parts:
                return None
            try:
                return self.__periods__[parts][part]
            except KeyError:
                return None
        else:
            return self.session.query(models.Period).filter_by(part=part, parts=parts).first()

    def get_institution_set(self) -> {models.Institution}:
        if self.__caching__:
            return set(self.__institutions__.values())
        else:
            return set(self.session.query(models.Institution).all())

    def get_building_set(self) -> {models.Building}:
        if self.__caching__:
            return set(self.__buildings__.values())
        else:
            return set(self.session.query(models.Building).all())

    def get_department_set(self) -> {models.Department}:
        if self.__caching__:
            return set(self.__departments__.values())
        else:
            return set(self.session.query(models.Department).all())

    def get_degree_set(self) -> {models.Degree}:
        if self.__caching__:
            return set(self.__degrees__.values())
        else:
            return set(self.session.query(models.Degree).all())

    def get_period_set(self) -> {models.Period}:
        return set(self.session.query(models.Period).all())

    def get_course(self, identifier: int = None, abbreviation: str = None, year: int = None,
                   institution: models.Institution = None) -> Optional[models.Course]:
        if self.__caching__:  # Fetch it from the caches
            if identifier is not None:  # FIXME this does not consider entries with the same internal_id
                if identifier in self.__courses__:
                    return self.__courses__[identifier]
            elif abbreviation is not None:
                if abbreviation not in self.__course_abbrs__:
                    return None
                matches = self.__course_abbrs__[abbreviation]
                if len(matches) == 0:
                    return None
                elif len(matches) == 1:
                    return matches[0]
                else:
                    if year is None:
                        raise Exception("Multiple matches. Year unspecified")

                    for match in matches:
                        if match.initial_year <= year <= match.last_year:
                            return match
        else:  # Query it from the db (with the provided parameters)
            if identifier is not None:
                if institution is not None:
                    matches = self.session.query(models.Course).filter_by(iid=identifier, institution=institution).all()
                else:
                    matches = self.session.query(models.Course).filter_by(iid=identifier).all()
            elif abbreviation is not None:
                if institution is not None:
                    matches = self.session.query(models.Course) \
                        .filter_by(abbreviation=abbreviation, institution=institution).all()
                else:
                    matches = self.session.query(models.Course).filter_by(abbreviation=abbreviation).all()
            else:
                log.warning(f"Unable to determine course with id {identifier}, abbr {abbreviation} on year {year}")
                return None

            if len(matches) == 1:
                return matches[0]
            elif len(matches) > 1:
                if year is None:
                    raise Exception("Multiple matches. Year unspecified")

                # Year filter
                if year is not None:
                    year_matches = []
                    for course in matches:
                        if course.contains(year):
                            year_matches.append(course)
                    if len(year_matches) == 1:
                        return year_matches[0]
                    elif len(matches) > 1:
                        raise Exception("Multiple matches. Unable to determine the correct one.")

    def get_turn_type(self, abbreviation: str) -> Optional[models.TurnType]:
        if self.__caching__:
            if abbreviation in self.__turn_types__:
                return self.__turn_types__[abbreviation]
        else:
            return self.session.query(models.TurnType).filter_by(abbreviation=abbreviation).first()

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
        | - A teacher is lecturing a class given by another department (CTCT please...) and there's a name collision
        | - There are two different teachers with the same name in the same department.
        | TODO A workaround which is ridiculously CPU/time intensive unless implemented properly is to use
            :py:const:`CLIPy.urls.TEACHER_SCHEDULE` to check if results match.
            That can easily become an O(n^2) if not properly implemented.
        | An idea is to ignore unmatched teachers (leave turns without the teacher) and then crawl
            :py:const:`CLIPy.urls.TEACHER_SCHEDULE` once and fill the gaps. This idea is an O(n).
        | TODO 2 Add `year` to the equation in hope to better guess which `teacher` is the correct in the
            `multiple but all the same` scenario.
        | TODO 3 Find some alcohol and forget this

        :param name: Teacher name
        :param department: Teacher department
        :return: Matching teacher
        """
        if self.__caching__:  # FIXME this isn't going to work. Fix the cache code.
            if name in self.__teachers__:
                return self.__teachers__[name]
        else:
            matches = self.session.query(models.Teacher).filter_by(name=name).all()
            if len(matches) == 1:
                return matches[0]
            if len(matches) == 0:
                return None

            filtered_matches = self.session.query(models.Teacher).filter_by(name=name, department=department).all()
            if len(filtered_matches) == 1:
                return matches[0]

            # Desperation intensifies:
            # Check if the unfiltered matches are all the same teacher:
            same_teacher = True
            teacher_iid = None
            for match in matches:
                if teacher_iid is None:
                    teacher_iid = match.iid
                    continue

                if match.iid != teacher_iid:
                    same_teacher = False
                    break

            if same_teacher:
                return matches[0]  # Any of them will do

            log.error(f'Several teachers with the name {name}')  # TODO to exception
            return None

    def get_class(self, iid: int, department: models.Department) -> Optional[models.Class]:
        matches = self.session.query(models.Class).filter_by(iid=iid, department=department).all()
        count = len(matches)
        if count == 1:
            return matches[0]
        elif count > 1:
            raise Exception(f"Multiple classes the internal id {iid} found in the department {department}")

    def add_institutions(self, institutions: [candidates.Institution]):
        """
        Adds institutions to the database. It updates then in case they already exist but details differ.

        :param institutions: An iterable collection of institution candidates
        """
        new_count = 0
        updated_count = 0
        try:
            for candidate in institutions:
                # Lookup for existing institutions matching the new candidate
                institution = None
                if self.__caching__:
                    if candidate.id in self.__institutions__:
                        institution = self.__institutions__[candidate.id]
                else:
                    institution = self.session.query(models.Institution).filter_by(id=candidate.id).first()

                if institution is None:  # Create a new institution
                    self.session.add(models.Institution(
                        id=candidate.id,
                        name=candidate.name,
                        abbreviation=candidate.abbreviation,
                        first_year=candidate.first_year,
                        last_year=candidate.last_year))
                    new_count += 1
                else:  # Update the existing one accordingly
                    updated = False
                    if candidate.name is not None and institution.name != candidate.name:
                        institution.name = candidate.name
                        updated = True

                    if candidate.abbreviation is not None:
                        institution.abbreviation = candidate.abbreviation
                        updated = True

                    if institution.first_year is None:
                        institution.first_year = candidate.first_year
                        updated = True
                    elif candidate.first_year is not None and candidate.first_year < institution.first_year:
                        institution.first_year = candidate.first_year
                        updated = True

                    if institution.last_year is None:
                        institution.last_year = candidate.last_year
                        updated = True
                    elif candidate.last_year is not None and candidate.last_year > institution.last_year:
                        institution.last_year = candidate.last_year
                        updated = True

                    if updated:
                        updated_count += 1

            self.session.commit()
            log.info(f"{new_count} institutions added and {updated_count} updated!")
            if self.__caching__:
                self.__load_institutions__()
        except Exception:
            log.error("Failed to add the institutions\n" + traceback.format_exc())
            self.session.rollback()

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
                department = None
                if self.__caching__:
                    if candidate.id in self.__departments__:
                        department = self.__departments__[candidate.id]
                else:
                    department = self.session.query(models.Department).filter_by(id=candidate.id).first()

                if department is None:  # Create a new department
                    self.session.add(models.Department(
                        id=candidate.id,
                        name=candidate.name,
                        first_year=candidate.first_year,
                        last_year=candidate.last_year,
                        institution=candidate.institution))
                    new_count += 1
                else:  # Update the existing one accordingly
                    updated = False
                    if candidate.name is not None and department.name != candidate.name:
                        department.name = candidate.name
                        updated = True

                    if department.first_year is None:
                        department.first_year = candidate.first_year
                        updated = True
                    elif candidate.first_year is not None and candidate.first_year < department.first_year:
                        department.first_year = candidate.first_year
                        updated = True

                    if department.last_year is None:
                        department.last_year = candidate.last_year
                        updated = True
                    elif candidate.last_year is not None and candidate.last_year > department.last_year:
                        department.last_year = candidate.last_year
                        updated = True

                    if updated:
                        updated_count += 1

            log.info(f"{new_count} departments added and {updated_count} updated!")
            self.session.commit()
            if self.__caching__:
                self.__load_departments__()
        except Exception:
            log.error("Failed to add the departments\n" + traceback.format_exc())
            self.session.rollback()

    def add_class(self, candidate: candidates.Class) -> models.Class:
        db_class = self.session.query(models.Class).filter_by(
            iid=candidate.id,
            department=candidate.department
        ).first()

        if db_class is not None:  # Already stored
            if db_class.name != candidate.name:
                log.warning("Class name change:\n"
                            f"\t{db_class}\t to \t{candidate})")

            if candidate.abbreviation is not None:
                if db_class.abbreviation is None or db_class.abbreviation == '???':
                    db_class.abbreviation = candidate.abbreviation
                    self.session.commit()
                    return db_class

                if db_class.abbreviation is not None and db_class.abbreviation != candidate.abbreviation:
                    raise Exception("Class abbreviation change attempt."
                                    f"{db_class.abbreviation} to {candidate.abbreviation} (iid {candidate.id})")

            return db_class

        log.info("Adding class {}".format(candidate))
        db_class = models.Class(
            iid=candidate.id,
            name=candidate.name,
            department=candidate.department,
            abbreviation=candidate.abbreviation,
            ects=candidate.ects)
        self.session.add(db_class)
        self.session.commit()
        return db_class

    def add_class_instances(self, instances: [candidates.ClassInstance]):
        ignored = 0
        for instance in instances:
            db_class_instance = self.session.query(models.ClassInstance).filter_by(
                parent=instance.parent,
                year=instance.year,
                period=instance.period
            ).first()
            if db_class_instance is not None:
                ignored += 1
            else:
                self.session.add(models.ClassInstance(
                    parent=instance.parent,
                    year=instance.year,
                    period=instance.period
                ))
                self.session.commit()
        if len(instances) > 0:
            log.info("{} class instances added successfully! ({} ignored)".format(len(instances), ignored))

    def update_class_instance_info(self, instance: models.ClassInstance, info):
        if 'description' in info:
            instance.description_pt = info['description'][0]
            instance.description_en = info['description'][1]
            instance.description_edited_datetime = info['description'][2]
            instance.description_editor = info['description'][3]
        if 'objectives' in info:
            instance.objectives_pt = info['objectives'][0]
            instance.objectives_en = info['objectives'][1]
            instance.objectives_edited_datetime = info['objectives'][2]
            instance.objectives_editor = info['objectives'][3]
        if 'requirements' in info:
            instance.requirements_pt = info['requirements'][0]
            instance.requirements_en = info['requirements'][1]
            instance.requirements_edited_datetime = info['requirements'][2]
            instance.requirements_editor = info['requirements'][3]
        if 'competences' in info:
            instance.competences_pt = info['competences'][0]
            instance.competences_en = info['competences'][1]
            instance.competences_edited_datetime = info['competences'][2]
            instance.competences_editor = info['competences'][3]
        if 'program' in info:
            instance.program_pt = info['program'][0]
            instance.program_en = info['program'][1]
            instance.program_edited_datetime = info['program'][2]
            instance.program_editor = info['program'][3]
        if 'bibliography' in info:
            instance.bibliography_pt = info['bibliography'][0]
            instance.bibliography_en = info['bibliography'][1]
            instance.bibliography_edited_datetime = info['bibliography'][2]
            instance.bibliography_editor = info['bibliography'][3]
        if 'assistance' in info:
            instance.assistance_pt = info['assistance'][0]
            instance.assistance_en = info['assistance'][1]
            instance.assistance_edited_datetime = info['assistance'][2]
            instance.assistance_editor = info['assistance'][3]
        if 'teaching_methods' in info:
            instance.teaching_methods_pt = info['teaching_methods'][0]
            instance.teaching_methods_en = info['teaching_methods'][1]
            instance.teaching_methods_edited_datetime = info['teaching_methods'][2]
            instance.teaching_methods_editor = info['teaching_methods'][3]
        if 'evaluation_methods' in info:
            instance.evaluation_methods_pt = info['evaluation_methods'][0]
            instance.evaluation_methods_en = info['evaluation_methods'][1]
            instance.evaluation_methods_edited_datetime = info['evaluation_methods'][2]
            instance.evaluation_methods_editor = info['evaluation_methods'][3]
        if 'extra_info' in info:
            instance.extra_info_pt = info['extra_info'][0]
            instance.extra_info_en = info['extra_info'][1]
            instance.extra_info_edited_datetime = info['extra_info'][2]
            instance.extra_info_editor = info['extra_info'][3]
        if 'working_hours' in info:
            instance.working_hours = json.dumps(info['working_hours'])

        self.session.commit()

    def add_courses(self, courses: [candidates.Course]):
        updated = 0
        try:
            for course in courses:
                db_course = self.session.query(models.Course).filter_by(
                    iid=course.id,
                    institution=course.institution
                ).first()

                if db_course is None:
                    self.session.add(models.Course(
                        iid=course.id,
                        name=course.name,
                        abbreviation=course.abbreviation,
                        first_year=course.first_year,
                        last_year=course.last_year,
                        degree=course.degree,
                        institution=course.institution))
                    self.session.commit()
                else:
                    updated += 1
                    changed = False
                    if course.name is not None and course.name != db_course.name:
                        raise Exception("Attempted to change a course name")

                    if course.abbreviation is not None:
                        db_course.abbreviation = course.abbreviation
                        changed = True
                    if course.degree is not None:
                        db_course.degree = course.degree
                        changed = True
                    if db_course.first_year is None \
                            or course.first_year is not None and course.first_year < db_course.first_year:
                        db_course.first_year = course.first_year
                        changed = True
                    if db_course.last_year is None \
                            or course.last_year is not None and course.last_year < db_course.last_year:
                        db_course.last_year = course.last_year
                        changed = True
                    if changed:
                        self.session.commit()

            if len(courses) > 0:
                log.info("{} courses added successfully! ({} updated)".format(len(courses), updated))
        except Exception:
            self.session.rollback()
            raise Exception("Failed to add courses.\n%s" % traceback.format_exc())
        finally:
            if self.__caching__:
                self.__load_courses__()

    def add_student(self, candidate: candidates.Student) -> models.Student:
        if candidate.name is None or candidate.name == '':
            raise Exception("Invalid name")

        if candidate.id is None:
            raise Exception('No student ID provided')

        if candidate.last_year is None:
            raise Exception("Year not provided")

        year = candidate.last_year

        if candidate.course is not None:
            # Search for institution instead of course since a transfer could have happened
            institution = candidate.course.institution
        elif candidate.institution is not None:
            institution = candidate.institution
        else:
            raise Exception("Neither course nor institution provided")

        students: List[models.Student] = self.session.query(models.Student).filter_by(iid=candidate.id).all()

        if len(students) == 0:  # new student, add him
            student = models.Student(
                iid=candidate.id,
                name=candidate.name,
                abbreviation=candidate.abbreviation,
                institution=institution,
                course=candidate.course,
                first_year=candidate.first_year,
                last_year=candidate.last_year)
            self.session.add(student)
            self.session.commit()
            if candidate.course is not None:
                try:  # Hackish race condition prevention. Not pretty but works (most of the time)
                    self.add_student_course(student=student, course=candidate.course, year=year)
                except IntegrityError:
                    sleep(3)
                    self.session.rollback()
                    self.add_student_course(student=student, course=candidate.course, year=year)
        elif len(students) == 1:
            student = students[0]
            if student.abbreviation == candidate.abbreviation or student.name == candidate.name:
                if student.abbreviation is None:
                    if candidate.abbreviation is not None:
                        student.abbreviation = candidate.abbreviation
                        self.session.commit()
                elif candidate.abbreviation is not None and candidate.abbreviation != student.abbreviation:
                    raise Exception(
                        "Attempted to change the student abbreviation to another one\n"
                        "Student:{}\n"
                        "Candidate{}".format(student, candidate))

                if candidate.course is not None and student.course != candidate.course:  # TODO remove, check next if
                    if student.course is not None:
                        log.warning(f"{student} changing course from {student.course} to {candidate.course}")

                    student.course = candidate.course
                    self.session.commit()

                if candidate.course is not None:
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

            else:
                student = models.Student(
                    iid=candidate.id,
                    name=candidate.name,
                    abbreviation=candidate.abbreviation,
                    institution=institution,
                    course=candidate.course,  # TODO remove
                    first_year=candidate.first_year,
                    last_year=candidate.last_year)
                self.session.add(student)
                self.session.commit()
                if candidate.course is not None:
                    try:  # Hackish race condition prevention. Not pretty but works (most of the time)
                        self.add_student_course(student=student, course=candidate.course, year=year)
                    except IntegrityError:
                        sleep(3)
                        self.session.rollback()
                        self.add_student_course(student=student, course=candidate.course, year=year)

        else:  # database inconsistency
            students_str = ""
            for candidate in students:
                students_str += ("%s," % candidate)
            raise Exception(f"Duplicated students found:\n{students_str}")

        return student

    def get_student(self, identifier: int, name: str = None) -> Optional[models.Student]:
        matches = self.session.query(models.Student).filter_by(iid=identifier).all()
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            if name is not None:
                log.warning(f"Multiple matches for the IID {identifier}\n{matches}\nTrying to guess.")
                for match in matches:
                    if match.name == name:
                        return match
            raise Exception("Multiple students with this ID")

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
        teacher_matches: [models.Teacher] = self.session.query(models.Teacher).filter_by(iid=candidate.id).all()
        count = len(teacher_matches)
        changed = False  # DB changed, reload flag

        # Ensure that the candidate matches existing id matches
        for teacher in teacher_matches:
            if teacher.name != candidate.name:
                raise Exception('Two diferent teachers with the same ID:\n'
                                f'\t{teacher}\n'
                                f'\t{candidate}')
            break  # Just needs to run once, but none if there are no matches

        if count == 0:  # No teacher, add him/her
            teacher = models.Teacher(iid=candidate.id,
                                     name=candidate.name,
                                     department=candidate.department,
                                     first_year=candidate.first_year,
                                     last_year=candidate.last_year)
            self.session.add(teacher)
            changed = True
        else:  # There are records of that teacher
            teacher = None  # A record matches if it shares the iid and department
            if count == 1:
                if teacher_matches[0].department == candidate.department:
                    teacher = teacher_matches[0]
            else:
                for match in teacher_matches:
                    teacher: models.Teacher
                    if match.department == candidate.department:
                        teacher = match
                        break

            if teacher is None:
                teacher = models.Teacher(iid=candidate.id,
                                         name=candidate.name,
                                         department=candidate.department,
                                         first_year=candidate.first_year,
                                         last_year=candidate.last_year)
                self.session.add(teacher)
                changed = True
            elif teacher.first_year != candidate.first_year or teacher.last_year != candidate.last_year:
                teacher.add_year(candidate.first_year)
                teacher.add_year(candidate.last_year)
                changed = True

        if changed:
            self.session.commit()
            if self.__caching__:
                self.__load_teachers__()

        return teacher

    def add_turn(self, turn: candidates.Turn) -> models.Turn:
        db_turn: models.Turn = self.session.query(models.Turn).filter_by(
            number=turn.number,
            class_instance=turn.class_instance,
            type=turn.type
        ).first()

        if db_turn is None:
            db_turn = models.Turn(
                class_instance=turn.class_instance,
                number=turn.number,
                type=turn.type,
                enrolled=turn.enrolled,
                capacity=turn.capacity,
                minutes=turn.minutes,
                routes=turn.routes,
                restrictions=turn.restrictions,
                state=turn.restrictions)
            self.session.add(db_turn)
            self.session.commit()
        else:
            changed = False
            if turn.minutes is not None and turn.minutes != 0:
                db_turn.minutes = turn.minutes
                changed = True
            if turn.enrolled is not None:
                db_turn.enrolled = turn.enrolled
                changed = True
            if turn.capacity is not None:
                db_turn.capacity = turn.capacity
                changed = True
            if turn.minutes is not None and turn.minutes != 0:
                db_turn.minutes = turn.minutes
                changed = True
            if turn.routes is not None:
                db_turn.routes = turn.routes
                changed = True
            if turn.restrictions is not None:
                db_turn.restrictions = turn.restrictions
                changed = True
            if turn.state is not None:
                db_turn.state = turn.state
                changed = True
            if changed:
                self.session.commit()

        [db_turn.teachers.append(teacher) for teacher in turn.teachers]
        return db_turn

    # Reconstructs the instances of a turn.
    # Destructive is faster because it doesn't worry about checking instance by instance,
    # it'll delete em' all and rebuilds
    def add_turn_instances(self, instances: List[candidates.TurnInstance], destructive=False):
        turn = None
        for instance in instances:
            if turn is None:
                turn = instance.turn
            elif turn != instance.turn:
                raise Exception('Instances belong to multiple turns')
        if turn is None:
            return

        if destructive:
            try:
                deleted = self.session.query(models.TurnInstance).filter_by(turn=turn).delete()
                if deleted > 0:
                    log.info(f"Deleted {deleted} turn instances from the turn {turn}")
            except Exception:
                self.session.rollback()
                raise Exception("Error deleting turn instances for turn {}\n{}".format(turn, traceback.format_exc()))

            for instance in instances:
                turn.instances.append(models.TurnInstance(
                    turn=turn,
                    start=instance.start,
                    end=instance.end,
                    room=instance.room,
                    weekday=instance.weekday))

            if len(instances) > 0:
                log.info(f"Added {len(instances)} turn instances to the turn {turn}")
                self.session.commit()
        else:
            db_turn_instances = self.session.query(models.TurnInstance).filter_by(turn=turn).all()
            for db_turn_instance in db_turn_instances:
                matched = False
                for instance in instances[:]:
                    if db_turn_instance.start == instance.start and db_turn_instance.end == instance.end and \
                            db_turn_instance.weekday == instance.weekday:
                        matched = True
                        if db_turn_instance.room != instance.room:  # Update the room
                            log.warning(f'An instance of {turn} changed the room from '
                                        f'{db_turn_instance.room} to {instance.room}')
                            db_turn_instance.room = instance.room
                        instances.remove(instance)
                        break
                if not matched:
                    log.info(f'An instance of {turn} ceased to exist ({db_turn_instance})')
                    self.session.delete(db_turn_instance)
            for instance in instances:
                turn.instances.append(
                    models.TurnInstance(
                        turn=turn,
                        start=instance.start,
                        end=instance.end,
                        room=instance.room,
                        weekday=instance.weekday))
            self.session.commit()

    def add_turn_students(self, turn: models.Turn, students: [candidates.Student]):
        count = len(students)
        if count > 0:
            [turn.students.append(student) for student in students]
            self.session.commit()
            log.info(f"{count} students added successfully to the turn {turn}!")

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
        for enrollment in enrollments:
            db_enrollment: models.Enrollment = self.session.query(models.Enrollment).filter_by(
                student=enrollment.student,
                class_instance=enrollment.class_instance
            ).first()
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

        log.info("{} enrollments added and {} updated ({} ignored)!".format(
            added, updated, len(enrollments) - added - updated))

    def update_enrollment_results(self, student: models.Student, class_instance: models.ClassInstance, results,
                                  approved: bool):
        enrollment: models.Enrollment = self.session.query(models.Enrollment) \
            .filter_by(student=student, class_instance=class_instance).first()

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
            enrollment: [models.Enrollment] = self.session.query(models.Enrollment) \
                .filter_by(student=student, approved=True) \
                .join(models.ClassInstance) \
                .filter(models.ClassInstance.parent == class_instance.parent) \
                .all()
            count = len(enrollment)
            if count == 1:
                enrollment.improved = improved
                enrollment.improvement_grade = grade
                enrollment.improvement_grade_date = date
            elif count > 1:
                log.error("Consistency issues. A student was approved several times.\n"
                          f"Student:{student}, Instance:{class_instance}")

            else:
                log.error("No approved enrollement. Enrollment search was not performed in chronological order.")

        self.session.commit()

    def add_room(self, candidate: candidates.Room) -> models.Room:
        reload_cache = False
        try:
            if self.__caching__:
                if candidate.building in self.__rooms__ \
                        and candidate.type in self.__rooms__[candidate.building] \
                        and candidate.name in self.__rooms__[candidate.building][candidate.type]:
                    room = self.__rooms__[candidate.building][candidate.type][candidate.name]
                else:
                    room = models.Room(id=candidate.id,
                                       name=candidate.name,
                                       room_type=candidate.type,
                                       building=candidate.building)
                    self.session.add(room)
                    self.session.commit()
                    reload_cache = True
                return room
            else:
                room = self.session.query(models.Room).filter_by(
                    name=candidate.name, room_type=candidate.type, building=candidate.building).first()
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
        finally:
            if self.__caching__ and reload_cache:
                self.__load_rooms__()

    def get_room(self, name: str, building: models.Building,
                 room_type: models.RoomType = None) -> Optional[models.Room]:
        if self.__caching__:
            if room_type:
                if building in self.__rooms__ and room_type in self.__rooms__[building] \
                        and name in self.__rooms__[building][room_type]:
                    return self.__rooms__[building][room_type][name]
            else:
                if building in self.__rooms__:
                    matches = []
                    for building_room_type in self.__rooms__[building]:
                        if name in building_room_type:
                            matches.append(building_room_type[name])
                    if len(matches) == 1:
                        return matches[0]
                    if len(matches) > 1:
                        raise Exception("Unable to determine which room is the correct one")
                raise Exception('Unknown building')
        else:
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
                        return self.session.query(models.Room).filter_by(
                            name=name,
                            room_type=room_type,
                            building=building
                        ).first()
                else:  # regular rooms have no type hint. Assume that if there's no type hint then we want a regular one
                    regular_rooms = []
                    for room in matches:
                        if room.room_type not in (models.RoomType.laboratory, models.RoomType.computer):
                            regular_rooms.append(room)
                    if len(regular_rooms) == 1:
                        return regular_rooms[0]

    def add_building(self, building: candidates.Building) -> models.Building:
        if self.__caching__:
            if building.name in self.__buildings__:
                return self.__buildings__[building.name]
            try:
                building = models.Building(id=building.id, name=building.name)
                self.session.add(building)
                self.session.commit()
                return building
            except Exception:
                log.error("Failed to add the building\n%s" % traceback.format_exc())
                self.session.rollback()
            finally:
                if self.__caching__:
                    self.__load_buildings__()
        else:
            db_building = self.session.query(models.Building).filter_by(name=building.name).first()
            if db_building is None:
                db_building = models.Building(id=building.id, name=building.name)
                self.session.add(db_building)
                self.session.commit()
            return db_building

    def get_building(self, building: str) -> models.Building:
        if self.__caching__:
            if building in self.__buildings__:
                return self.__buildings__[building]
        else:
            return self.session.query(models.Building).filter_by(name=building).first()

    def add_class_file(self, candidate: candidates.File, class_instance: models.ClassInstance) -> models.File:
        file = self.session.query(models.File).filter_by(id=candidate.id).first()

        if file is None:
            file = models.File(
                id=candidate.id,
                name=candidate.name,
                file_type=candidate.file_type,
                size=candidate.size,
                hash=candidate.hash,
                location=candidate.location)
            log.info(f"Adding file {file}")
            self.session.add(file)
            class_file = models.ClassFile(
                uploader=candidate.uploader,
                upload_datetime=candidate.upload_datetime,
                file=file,
                class_instance=class_instance)
            self.session.add(class_file)
            self.session.commit()
        else:
            if file not in class_instance.files:
                class_file = models.ClassFile(
                    uploader=candidate.uploader,
                    upload_datetime=candidate.upload_datetime,
                    file=file,
                    class_instance=class_instance)
                self.session.add(class_file)
                self.session.commit()
        return file

    def update_downloaded_file(self, file: models.File, mime: str, path: str, hash: str):
        file.mime = mime
        file.hash = hash
        file.location = path
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
                    filter_by(year=year, period=period).order_by(order).all()
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

import logging
import os
import traceback

from sqlalchemy import create_engine, desc, asc
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, scoped_session

from CLIPy.database.models import Base, Degree, Period, TurnType, Institution, Department, Course, Teacher, Building, \
    Classroom, Class, ClassInstance, Student, Turn, TurnInstance, Admission, Enrollment
from CLIPy.database.candidates import ClassroomCandidate, BuildingCandidate, TurnCandidate, StudentCandidate, \
    ClassCandidate, InstitutionCandidate, ClassInstanceCandidate, DepartmentCandidate, AdmissionCandidate, \
    EnrollmentCandidate, CourseCandidate, TeacherCandidate

log = logging.getLogger(__name__)


def create_db_engine(backend: str, username=None, password=None, schema='CLIPy',
                     host='localhost', file=os.path.dirname(__file__) + '/CLIPy.db'):
    if backend == 'sqlite':
        log.debug(f"Establishing a database connection to file:'{file}'")
        return create_engine("sqlite:///%s" % file, echo=True)
    elif backend == 'postgresql' and username is not None and password is not None and schema is not None:
        log.debug("Establishing a database connection to file:'{}'".format(file))
        return create_engine(f"postgresql://{username}:{password}@{host}/{schema}")
    else:
        raise ValueError('Unsupported database backend or not enough arguments supplied')


class SessionRegistry:
    def __init__(self, engine: Engine):
        self.engine = engine
        self.factory = sessionmaker(bind=engine)
        self.scoped_session = scoped_session(self.factory)
        Base.metadata.create_all(engine)

    def get_session(self):
        return self.scoped_session()

    def remove(self):
        self.scoped_session.remove()


# NOT thread-safe. Each thread must instantiate its own controller from the registry.
class Controller:
    def __init__(self, database_registry: SessionRegistry, cache: bool = False):
        self.registry = database_registry
        self.session = database_registry.get_session()

        self.__caching__ = cache

        if self.session.query(Degree).count() == 0:
            self.__insert_default_degrees__()

        if self.session.query(Period).count() == 0:
            self.__insert_default_periods__()

        if self.session.query(TurnType).count() == 0:
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
        self.__load_classrooms__()
        log.debug("Finished building cache")

    def __load_institutions__(self):
        log.debug("Building institution cache")
        institutions = {}
        for institution in self.session.query(Institution).all():
            institutions[institution.internal_id] = institution
        self.__institutions__ = institutions

    def __load_degrees__(self):
        log.debug("Building degree cache")
        degrees = {}
        for degree in self.session.query(Degree).all():
            if degree.id == 4:  # FIXME, skipping the Integrated Master to avoid having it replace the Master
                continue
            degrees[degree.internal_id] = degree
        self.__degrees__ = degrees

    def __load_periods__(self):
        log.debug("Building period cache")
        periods = {}

        for period in self.session.query(Period).all():
            if period.parts not in periods:  # unseen letter
                periods[period.parts] = {}
            periods[period.parts][period.part] = period
        self.__periods__ = periods

    def __load_departments__(self):
        log.debug("Building department cache")
        departments = {}
        for department in self.session.query(Department).all():
            departments[department.internal_id] = department
        self.__departments__ = departments

    def __load_courses__(self):
        log.debug("Building course cache")
        courses = {}
        course_abbreviations = {}
        for course in self.session.query(Course).all():
            courses[course.internal_id] = course

            if course.abbreviation not in course_abbreviations:
                course_abbreviations[course.abbreviation] = []
            course_abbreviations[course.abbreviation].append(course)
        self.__courses__ = courses
        self.__course_abbrs__ = course_abbreviations

    def __load_turn_types__(self):
        log.debug("Building turn types cache")
        turn_types = {}
        for turn_type in self.session.query(TurnType).all():
            turn_types[turn_type.abbreviation] = turn_type
        self.__turn_types__ = turn_types

    def __load_teachers__(self):
        log.debug("Building teacher cache")
        teachers = {}
        for teacher in self.session.query(Teacher).all():
            teachers[teacher.name] = teacher
        self.__teachers__ = teachers

    def __load_buildings__(self):
        log.debug("Building building cache")
        buildings = {}
        for building in self.session.query(Building).all():
            buildings[building.name] = building
        self.__buildings__ = buildings

    def __load_classrooms__(self):
        log.debug("Building classroom cache")
        classrooms = {}
        for classroom, building in self.session.query(Classroom, Building).all():
            classrooms[building.name][classroom.name] = building
        self.__classrooms__ = classrooms

    def __insert_default_periods__(self):
        # TODO don't just leave this here hardcoded...
        self.session.add_all(
            [Period(id=1, part=1, parts=1, letter='a'),
             Period(id=2, part=1, parts=2, letter='s'),
             Period(id=3, part=2, parts=2, letter='s'),
             Period(id=4, part=1, parts=4, letter='t'),
             Period(id=5, part=2, parts=4, letter='t'),
             Period(id=6, part=3, parts=4, letter='t'),
             Period(id=7, part=4, parts=4, letter='t')])
        self.session.commit()

    def __insert_default_degrees__(self):
        self.session.add_all(
            [Degree(id=1, internal_id='L', name="Licenciatura"),
             Degree(id=2, internal_id='M', name="Mestrado"),
             Degree(id=3, internal_id='D', name="Doutoramento"),
             Degree(id=4, internal_id='M', name="Mestrado Integrado"),  # FIXME, distinguish M from Mi
             Degree(id=5, internal_id='Pg', name="Pos-Graduação"),
             Degree(id=6, internal_id='EA', name="Estudos Avançados"),
             Degree(id=7, internal_id='pG', name="Pré-Graduação")])
        self.session.commit()

    def __insert_default_turn_types__(self):
        self.session.add_all(
            [TurnType(id=1, name="Theoretical", abbreviation="t"),
             TurnType(id=2, name="Practical", abbreviation="p"),
             TurnType(id=3, name="Practical-Theoretical", abbreviation="tp"),
             TurnType(id=4, name="Seminar", abbreviation="s"),
             TurnType(id=5, name="Tutorial Orientation", abbreviation="ot")])
        self.session.commit()

    def get_institution(self, internal_id: int):
        if self.__caching__:
            if internal_id not in self.__institutions__:
                return None
            return self.__institutions__[internal_id]
        else:
            return self.session.query(Institution).filter_by(internal_id=internal_id).first()

    def get_department(self, internal_id: int):
        if self.__caching__:
            if internal_id not in self.__departments__:
                return None
            return self.__departments__[internal_id]
        else:
            return self.session.query(Department).filter_by(internal_id=internal_id).first()

    def get_degree(self, abbreviation: str):
        if self.__caching__:
            if abbreviation not in self.__degrees__:
                return None
            return self.__degrees__[abbreviation]
        else:
            return self.session.query(Degree).filter_by(internal_id=abbreviation).first()

    def get_period(self, part: int, parts: int):
        if self.__caching__:
            if parts not in self.__periods__ or part > parts:
                return None
            try:
                return self.__periods__[parts][part]
            except KeyError:
                return None
        else:
            return self.session.query(Period).filter_by(part=part, parts=parts).first()

    def get_institution_set(self):
        if self.__caching__:
            return set(self.__institutions__.values())
        else:
            return set(self.session.query(Institution).all())

    def get_department_set(self):
        if self.__caching__:
            return set(self.__departments__.values())
        else:
            return set(self.session.query(Department).all())

    def get_degree_set(self):
        if self.__caching__:
            return set(self.__degrees__.values())
        else:
            return set(self.session.query(Degree).all())

    def get_period_set(self):
        return set(self.session.query(Period).all())

    def get_course(self, id=None, abbreviation=None, year=None):
        if id is not None:
            if self.__caching__:
                if id in self.__courses__:
                    return self.__courses__[id]
            else:
                return self.session.query(Course).filter_by(internal_id=id).first()
        elif abbreviation is not None:
            if self.__caching__:
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
            else:
                matches = self.session.query(Course).filter_by(internal_id=id).all()
                if len(matches) == 0:
                    return None
                elif len(matches) == 1:
                    return matches[0]

                if year is None:
                    raise Exception("Multiple matches. Year unspecified")

                for match in matches:
                    if match.initial_year <= year <= match.last_year:
                        return match

    def get_turn_type(self, abbreviation: str):
        if self.__caching__:
            if abbreviation not in self.__turn_types__:
                return None
            return self.__turn_types__[abbreviation]
        else:
            return self.session.query(TurnType).filter_by(abbreviation=abbreviation).first()

    def get_teacher(self, name: str):
        if self.__caching__:
            if name not in self.__teachers__:
                return None
            return self.__teachers__[name]
        else:
            return self.session.query(Teacher).filter_by(name=name).first()

    def get_class(self, internal_id: int):
        return self.session.query(Class).filter_by(internal_id=internal_id).first()

    def add_institutions(self, institutions: [InstitutionCandidate]):
        try:
            for institution in institutions:
                if institution.id in self.__institutions__:
                    stored_institution = self.__institutions__[institution.id]
                    if institution.name is not None:
                        stored_institution.name = institution.name
                    if institution.abbreviation is not None:
                        stored_institution.abbreviation = institution.abbreviation

                    if stored_institution.first_year is None:
                        stored_institution.first_year = institution.first_year
                    elif institution.first_year is not None and institution.first_year < stored_institution.first_year:
                        stored_institution.first_year = institution.first_year

                    if stored_institution.last_year is None:
                        stored_institution.last_year = institution.last_year
                    elif institution.last_year is not None and institution.last_year < stored_institution.last_year:
                        stored_institution.last_year = institution.last_year
                else:
                    self.session.add(Institution(
                        internal_id=institution.id,
                        name=institution.name,
                        abbreviation=institution.abbreviation,
                        first_year=institution.first_year,
                        last_year=institution.last_year))
            self.session.commit()
            log.info("{} institutions added successfully!".format(len(institutions)))
            if self.__caching__:
                self.__load_institutions__()
        except Exception:
            log.error("Failed to add the institutions\n" + traceback.format_exc())
            self.session.rollback()

    def add_departments(self, departments: [DepartmentCandidate]):
        try:
            for department in departments:
                if department.id in self.__departments__:
                    stored_department = self.__departments__[department.id]
                    if department.name is not None:
                        stored_department.name = department.name

                    if stored_department.first_year is None:
                        stored_department.first_year = department.first_year
                    elif department.first_year is not None and department.first_year < stored_department.first_year:
                        stored_department.first_year = department.first_year

                    if stored_department.last_year is None:
                        stored_department.last_year = department.last_year
                    elif department.last_year is not None and department.last_year < stored_department.last_year:
                        stored_department.last_year = department.last_year
                else:
                    self.session.add(Department(
                        internal_id=department.id,
                        name=department.name,
                        first_year=department.first_year,
                        last_year=department.last_year,
                        institution=department.institution))
            log.info("{} departments added successfully!".format(len(departments)))
            self.session.commit()
            if self.__caching__:
                self.__load_departments__()
        except Exception:
            log.error("Failed to add the departments\n" + traceback.format_exc())
            self.session.rollback()

    def add_class(self, class_candidate: ClassCandidate):
        db_class = self.session.query(Class). \
            filter_by(internal_id=class_candidate.id, department=class_candidate.department).first()

        if db_class is not None:  # Already stored
            if db_class.name != class_candidate.name:
                raise Exception("Class name change attempt. {} to {} (iid {})".format(
                    db_class.name, class_candidate.name, class_candidate.id))
            else:
                log.debug("Already known: {}".format(class_candidate))
                return db_class

        log.info("Adding class {}".format(class_candidate))
        db_class = Class(
            internal_id=class_candidate.id, name=class_candidate.name, department=class_candidate.department)
        self.session.add(db_class)
        self.session.commit()
        return db_class

    def add_class_instances(self, instances: [ClassInstanceCandidate]):
        ignored = 0
        for instance in instances:
            db_class_instance = self.session.query(ClassInstance).filter_by(
                parent=instance.parent, year=instance.year, period=instance.period).first()
            if db_class_instance is not None:
                ignored += 1
            else:
                self.session.add(ClassInstance(
                    parent=instance.parent,
                    year=instance.year,
                    period=instance.period
                ))
                self.session.commit()
        if len(instances) > 0:
            log.info("{} class instances added successfully! ({} ignored)".format(len(instances), ignored))

    def add_courses(self, courses: [CourseCandidate]):
        updated = 0
        try:
            for course in courses:
                db_course = self.session.query(Course).filter_by(
                    internal_id=course.id, institution=course.institution).first()

                if db_course is None:
                    self.session.add(Course(
                        internal_id=course.id,
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

    def add_student(self, student: StudentCandidate):
        if student.name is None or student.name == '':  # TODO Move this out of here
            raise Exception("Invalid name")

        if student.course is not None:
            # Search for institution instead of course since a transfer could have happened
            institution = student.course.institution
        elif student.institution is not None:
            institution = student.institution
        else:
            raise Exception("Neither course nor institution provided")

        if student.abbreviation is None and student.id is not None:
            db_students = self.session.query(Student).filter_by(
                name=student.name, internal_id=student.id, institution=institution).all()
        elif student.id is None and student.abbreviation is not None:
            db_students = self.session.query(Student).filter_by(
                name=student.name, abbreviation=student.abbreviation, institution=institution).all()
        else:
            db_students = self.session.query(Student).filter_by(
                abbreviation=student.abbreviation, internal_id=student.id, institution=institution).all()

        if len(db_students) == 0:  # new student, add him
            db_student = Student(internal_id=student.id, name=student.name, abbreviation=student.abbreviation,
                                 institution=institution, course=student.course)
            self.session.add(db_student)
            self.session.commit()
        elif len(db_students) == 1:
            db_student = db_students[0]
            if db_student.abbreviation is None:
                if student.abbreviation is not None:
                    db_student.abbreviation = student.abbreviation
                    self.session.commit()
            elif student.abbreviation is not None and student.abbreviation != db_student.abbreviation:
                raise Exception(
                    "Attempted to change the student abbreviation to another one\n"
                    "Student:{}\n"
                    "Candidate{}".format(db_student, student))

            if student.course is not None:
                db_student.course = student.course
                self.session.commit()
        else:  # bug or several institutions (don't even know if it's possible)
            students = ""
            for student in db_students:
                students += ("%d," % student)
            raise Exception("Duplicated students found:\n{}".format(students))
        return db_student

    def add_teacher(self, teacher: TeacherCandidate) -> Teacher:
        if self.__caching__:
            if teacher in self.__teachers__:
                teacher = self.__teachers__[teacher.name]
            else:
                teacher = Teacher(name=teacher.name)
                self.session.add(teacher)
                self.session.commit()
                if self.__caching__:
                    self.__load_teachers__()
            return teacher
        else:
            db_teacher = self.session.query(Teacher).filter_by(name=teacher.name).first()

            if db_teacher is None:
                db_teacher = Teacher(name=teacher.name)
                self.session.add(db_teacher)
                self.session.commit()
            return db_teacher

    def add_turn(self, turn: TurnCandidate) -> Turn:
        db_turn: Turn = self.session.query(Turn).filter_by(
            number=turn.number, class_instance=turn.class_instance, type=turn.type).first()

        if db_turn is None:
            db_turn = Turn(
                class_instance=turn.class_instance, number=turn.number, type=turn.type,
                enrolled=turn.enrolled, capacity=turn.capacity, minutes=turn.minutes, routes=turn.routes,
                restrictions=turn.restrictions, state=turn.restrictions)
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

        [db_turn.teachers.append(self.add_teacher(teacher)) for teacher in turn.teachers]
        return db_turn

    # Reconstructs the instances of a turn , IT'S DESTRUCTIVE!
    def add_turn_instances(self, instances: [TurnInstance]):
        turn = None
        for instance in instances:
            if turn is None:
                turn = instance.turn
            elif turn != instance.turn:
                raise Exception('Instances belong to multiple turns')
        if turn is None:
            return

        try:
            deleted = self.session.query(TurnInstance).filter_by(turn=turn).delete()
            if deleted > 0:
                log.info(f"Deleted {deleted} turn instances from the turn {turn}")
        except Exception:
            self.session.rollback()
            raise Exception("Error deleting turn instances for turn {}\n{}".format(turn, traceback.format_exc()))

        for instance in instances:
            turn.instances.append(TurnInstance(turn=turn, start=instance.start, end=instance.end,
                                               classroom=instance.classroom, weekday=instance.weekday))

        if len(instances) > 0:
            log.info(f"Added {len(instances)} turn instances to the turn {turn}")
        self.session.commit()

    def add_turn_students(self, turn: Turn, students):
        [turn.students.append(student) for student in students]
        if len(students) > 0:
            self.session.commit()
            log.info("{} students added successfully to the turn {}!".format(len(students), turn))

    def add_admissions(self, admissions: [AdmissionCandidate]):
        admissions = list(map(lambda admission: Admission(
            student=admission.student, name=admission.name, course=admission.course, phase=admission.phase,
            year=admission.year, option=admission.option, state=admission.state), admissions))
        self.session.add_all(admissions)

        if len(admissions) > 0:
            self.session.commit()
            log.info("{} admissions added successfully!".format(len(admissions)))

    def add_enrollments(self, enrollments: [EnrollmentCandidate]):
        added = 0
        updated = 0
        for enrollment in enrollments:
            db_enrollment: Enrollment = self.session.query(Enrollment).filter_by(
                student=enrollment.student, class_instance=enrollment.class_instance).first()
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
                enrollment = Enrollment(student=enrollment.student, class_instance=enrollment.class_instance,
                                        attempt=enrollment.attempt, student_year=enrollment.student_year,
                                        statutes=enrollment.statutes, observation=enrollment.observation)
                added += 1
                self.session.add(enrollment)
                self.session.commit()

        log.info("{} enrollments added and {} updated ({} ignored)!".format(
            added, updated, len(enrollments) - added - updated))

    def add_classroom(self, classroom: ClassroomCandidate):
        if self.__caching__:
            try:
                if classroom.building in self.__classrooms__ and \
                        classroom.name in self.__classrooms__[classroom.building]:
                    db_classroom = self.__classrooms__[classroom.building][classroom.name]
                else:
                    db_classroom = Classroom(name=classroom.name, building=classroom.building)
                    self.session.add(db_classroom)
                    self.session.commit()
                return db_classroom
            except Exception:
                log.error("Failed to add the classroom\n%s" % traceback.format_exc())
                self.session.rollback()
            finally:
                if self.__caching__:
                    self.__load_classrooms__()
        else:
            db_classroom = self.session.query(Classroom).filter_by(
                name=classroom.name, building=classroom.building).first()
            if db_classroom is None:
                db_classroom = Classroom(name=classroom.name, building=classroom.building)
                self.session.add(db_classroom)
                self.session.commit()
            return db_classroom

    def add_building(self, building: BuildingCandidate):
        if self.__caching__:
            if building.name in self.__buildings__:
                return self.__buildings__[building.name]
            try:
                building = Building(name=building.name, institution=building.institution)
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
            db_building = self.session.query(Building).filter_by(
                name=building.name, institution=building.institution).first()
            if db_building is None:
                db_building = Building(name=building.name, institution=building.institution)
                self.session.add(db_building)
                self.session.commit()
            return db_building

    def fetch_class_instances(self, year_asc=True, year=None, period=None) -> [ClassInstance]:
        order = asc(ClassInstance.year) if year_asc else desc(ClassInstance.year)
        if year is None:
            if period is not None:
                log.warning("Period specified without an year")
            if year_asc:
                instances = self.session.query(ClassInstance).order_by(order).all()
            else:
                instances = self.session.query(ClassInstance).order_by(order).all()
        else:
            if period is None:
                instances = self.session.query(ClassInstance).filter_by(year=year).order_by(order).all()
            else:
                instances = self.session.query(ClassInstance). \
                    filter_by(year=year, period=period).order_by(order).all()
        return list(instances)

    def find_student(self, name: str, course=None):
        query_string = '%'
        for word in name.split():
            query_string += (word + '%')

        if course is None:
            return self.session.query(Student).filter(Student.name.ilike(query_string)).all()
        else:
            return self.session.query(Student).filter(Student.name.ilike(query_string), course=course).all()

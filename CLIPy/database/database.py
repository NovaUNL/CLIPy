import logging
import os
import threading
import traceback
from queue import Queue

from sqlalchemy import create_engine, desc, asc
from sqlalchemy.orm import sessionmaker, Session

from CLIPy.database.models import Base, Degree, Period, TurnType, Institution, Department, Course, Teacher, Building, \
    Classroom, Class, ClassInstance, Student, Turn, TurnInstance, Admission, Enrollment
from CLIPy.database.candidates import ClassroomCandidate, BuildingCandidate, TurnCandidate, StudentCandidate, \
    ClassCandidate, InstitutionCandidate, ClassInstanceCandidate, DepartmentCandidate, AdmissionCandidate, \
    EnrollmentCandidate, CourseCandidate

log = logging.getLogger(__name__)


class Database:
    def __init__(self, backend: str, username=None, password=None, schema='CLIPy',
                 file=os.path.dirname(__file__) + '/CLIPy.db'):
        if backend == 'sqlite':
            log.debug("Establishing a database connection to file:'{}'".format(file))
            self.engine = create_engine("sqlite:///%s" % file, echo=True)
        elif backend == 'postgre' and username is not None and password is not None and schema is not None:
            log.debug("Establishing a database connection to file:'{}'".format(file))
            self.engine = create_engine("postgresql://{}:{}@localhost/{}".format(username, password, schema))
        else:
            raise ValueError('Unsupported database backend or not enough arguments supplied')

        self.__session__: Session = sessionmaker(bind=self.engine)()  # default session
        self.__session_lock__ = threading.Lock()

        Base.metadata.create_all(self.engine)
        if self.__session__.query(Degree).count() == 0:
            self.__insert_default_degrees__()

        if self.__session__.query(Period).count() == 0:
            self.__insert_default_periods__()

        if self.__session__.query(TurnType).count() == 0:
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
        for institution in self.__session__.query(Institution).all():
            institutions[institution.internal_id] = institution
        self.__institutions__ = institutions

    def __load_degrees__(self):
        log.debug("Building degree cache")
        degrees = {}
        for degree in self.__session__.query(Degree).all():
            if degree.id == 4:  # FIXME, skipping the Integrated Master to avoid having it replace the Master
                continue
            degrees[degree.internal_id] = degree
        self.__degrees__ = degrees

    def __load_periods__(self):
        log.debug("Building period cache")
        periods = {}

        for period in self.__session__.query(Period).all():
            if period.parts not in periods:  # unseen letter
                periods[period.parts] = {}
            periods[period.parts][period.part] = period
        self.__periods__ = periods

    def __load_departments__(self):
        log.debug("Building department cache")
        departments = {}
        for department in self.__session__.query(Department).all():
            departments[department.internal_id] = department
        self.__departments__ = departments

    def __load_courses__(self):
        log.debug("Building course cache")
        courses = {}
        course_abbreviations = {}
        for course in self.__session__.query(Course).all():
            courses[course.internal_id] = course

            if course.abbreviation not in course_abbreviations:
                course_abbreviations[course.abbreviation] = []
            course_abbreviations[course.abbreviation].append(course)
        self.__courses__ = courses
        self.__course_abbrs__ = course_abbreviations

    def __load_turn_types__(self):
        log.debug("Building turn types cache")
        turn_types = {}
        for turn_type in self.__session__.query(TurnType).all():
            turn_types[turn_type.abbreviation] = turn_type
        self.__turn_types__ = turn_types

    def __load_teachers__(self):
        log.debug("Building teacher cache")
        teachers = {}
        for teacher in self.__session__.query(Teacher).all():
            teachers[teacher.name] = teacher
        self.__teachers__ = teachers

    def __load_buildings__(self):
        log.debug("Building building cache")
        buildings = {}
        for building in self.__session__.query(Building).all():
            buildings[building.name] = building
        self.__buildings__ = buildings

    def __load_classrooms__(self):
        log.debug("Building classroom cache")
        classrooms = {}
        for classroom, building in self.__session__.query(Classroom, Building).all():
            classrooms[building.name][classroom.name] = building
        self.__classrooms__ = classrooms

    def __insert_default_periods__(self):
        # TODO don't just leave this here hardcoded...
        self.__session__.add_all(
            [Period(id=1, part=1, parts=1, letter='a'),
             Period(id=2, part=1, parts=2, letter='s'),
             Period(id=3, part=2, parts=2, letter='s'),
             Period(id=4, part=1, parts=4, letter='t'),
             Period(id=5, part=2, parts=4, letter='t'),
             Period(id=6, part=3, parts=4, letter='t'),
             Period(id=7, part=4, parts=4, letter='t')])

    def __insert_default_degrees__(self):
        self.__session__.add_all(
            [Degree(id=1, internal_id='L', name="Licenciatura"),
             Degree(id=2, internal_id='M', name="Mestrado"),
             Degree(id=3, internal_id='D', name="Doutoramento"),
             Degree(id=4, internal_id='M', name="Mestrado Integrado"),  # FIXME, distinguish M from Mi
             Degree(id=5, internal_id='Pg', name="Pos-Graduação"),
             Degree(id=6, internal_id='EA', name="Estudos Avançados"),
             Degree(id=7, internal_id='pG', name="Pré-Graduação")])

    def __insert_default_turn_types__(self):
        self.__session__.add_all(
            [TurnType(id=1, name="Theoretical", abbreviation="t"),
             TurnType(id=2, name="Practical", abbreviation="p"),
             TurnType(id=3, name="Practical-Theoretical", abbreviation="tp"),
             TurnType(id=4, name="Seminar", abbreviation="s"),
             TurnType(id=5, name="Tutorial Orientation", abbreviation="ot")])

    def get_institution(self, internal_id: int):
        if internal_id not in self.__institutions__:
            return None
        return self.__institutions__[internal_id]

    def get_department(self, internal_id: int):
        if internal_id not in self.__departments__:
            return None
        return self.__departments__[internal_id]

    def get_degree(self, abbreviation: str):
        if abbreviation not in self.__degrees__:
            return None
        return self.__degrees__[abbreviation]

    def get_period(self, part: int, parts: int):
        if parts not in self.__periods__ or part > parts:
            return None

        try:
            return self.__periods__[parts][part]
        except KeyError:
            return None

    def get_institution_set(self):
        return set(self.__institutions__.values())

    def get_department_set(self):
        return set(self.__departments__.values())

    def get_degree_set(self):
        return set(self.__degrees__.values())

    def get_period_set(self):
        periods = set()
        for period_length in self.__periods__.values():
            for period in period_length.values():
                periods.add(period)
        return periods

    def get_course(self, abbreviation: str, year=None):
        if abbreviation not in self.__courses__:
            return None
        matches = self.__courses__[abbreviation]
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

    def get_turn_type(self, abbreviation: str):
        if abbreviation not in self.__turn_types__:
            return None
        return self.__turn_types__[abbreviation]

    def get_teacher(self, name: str):
        if name not in self.__teachers__:
            return None
        return self.__teachers__[name]

    def get_class(self, internal_id: int):
        db_class: Class = self.__session__.query(Class).filter_by(internal_id=internal_id).first()
        return db_class

    def add_institutions(self, institutions: [InstitutionCandidate]):
        self.__session_lock__.acquire()
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
                    self.__session__.add(Institution(
                        internal_id=institution.id,
                        name=institution.name,
                        abbreviation=institution.abbreviation,
                        first_year=institution.first_year,
                        last_year=institution.last_year))
            log.info("{} institutions added successfully!".format(len(institutions)))
            self.__session__.commit()
        except Exception:
            log.error("Failed to add the institutions\n" + traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()
            self.__load_institutions__()

    def add_departments(self, departments: [DepartmentCandidate]):
        self.__session_lock__.acquire()
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
                    self.__session__.add(Department(
                        internal_id=department.id,
                        name=department.name,
                        first_year=department.first_year,
                        last_year=department.last_year,
                        institution=department.institution))
            log.info("{} departments added successfully!".format(len(departments)))
            self.__session__.commit()
        except Exception:
            log.error("Failed to add the departments\n" + traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()
            self.__load_departments__()

    def add_class(self, class_candidate: ClassCandidate):
        self.__session_lock__.acquire()
        try:
            db_class = self.__session__.query(Class). \
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
            self.__session__.add(db_class)
            self.__session__.commit()  # TODO optimize this, no need to commit for every class
            return db_class
        except Exception:
            log.error("Failed to add class.\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()

    def add_class_instances(self, instances: [ClassInstanceCandidate]):
        ignored = 0
        self.__session_lock__.acquire()
        try:
            for instance in instances:
                db_class_instance = self.__session__.query(ClassInstance).filter_by(
                    parent=instance.parent, year=instance.year, period=instance.period).first()
                if db_class_instance is not None:
                    ignored += 1
                else:
                    self.__session__.add(ClassInstance(
                        parent=instance.parent,
                        year=instance.year,
                        period=instance.period
                    ))

            self.__session__.commit()
            if len(instances) > 0:
                log.info("{} class instances added successfully! ({} ignored)".format(len(instances), ignored))
        except Exception:
            log.error("Failed to add the class instance\n" + traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()

    def add_courses(self, courses: [CourseCandidate]):
        # TODO convert '' to None, but somewhere else
        updated = 0
        self.__session_lock__.acquire()
        try:
            for course in courses:
                db_course = self.__session__.query(Course).filter_by(
                    internal_id=course.id, institution=course.institution).first()

                if db_course is None:
                    self.__session__.add(Course(
                        internal_id=course.id,
                        name=course.name,
                        abbreviation=course.abbreviation,
                        first_year=course.first_year,
                        last_year=course.last_year,
                        degree=course.degree,
                        institution=course.institution))
                else:
                    updated += 1
                    if course.name is not None and course.name != db_course.name:
                        raise Exception("Attempted to change a course name")

                    if course.abbreviation is not None:
                        db_course.abbreviation = course.abbreviation

                    if course.degree is not None:
                        db_course.degree = course.degree

                    if db_course.first_year is None:
                        db_course.first_year = course.first_year
                    elif course.first_year is not None and course.first_year < db_course.first_year:
                        db_course.first_year = course.first_year

                    if db_course.last_year is None:
                        db_course.last_year = course.last_year
                    elif course.last_year is not None and course.last_year < db_course.last_year:
                        db_course.last_year = course.last_year

            self.__session__.commit()
            if len(courses) > 0:
                log.info("{} courses added successfully! ({} updated)".format(len(courses), updated))
        except Exception:
            log.error("Failed to add courses.\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()
            self.__load_courses__()

    def add_student(self, student: StudentCandidate):
        if student.name is None or student.name == '':  # TODO Move this out of here
            raise Exception("Invalid name")

        if student.institution is None:
            raise Exception("Institution not provided")

        self.__session_lock__.acquire()
        try:
            db_students = self.__session__.query(Student).filter_by(
                name=student.name, internal_id=student.id, institution=student.institution).all()

            if len(db_students) == 0:  # new student, add him
                db_student = Student(
                    internal_id=student.id,
                    name=student.name,
                    abbreviation=student.abbreviation,
                    institution=student.institution,
                    course=student.course)
                self.__session__.add(db_student)
            elif len(db_students) == 1:
                db_student = db_students[0]
                if db_student.abbreviation is None:
                    if student.abbreviation is not None:
                        db_student.abbreviation = student.abbreviation
                elif student.abbreviation != db_student.abbreviation:
                    raise Exception("Attempted to change the student abbreviation to another one")

                if student.course is not None:
                    db_student.course = student.course
            else:  # bug or several institutions (don't even know if it's possible)
                raise Exception("Duplicated students found:\n{}".format(db_students))

            self.__session__.commit()
            return db_student
        except Exception:
            log.error("Failed to add the student {}.\n{}".format(student, traceback.format_exc()))
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()

    def add_turn(self, turn: TurnCandidate):
        new_teachers = False
        self.__session_lock__.acquire()
        try:
            db_turn: Turn = self.__session__.query(Turn).filter_by(
                number=turn.number, class_instance=turn.class_instance, type=turn.type).first()

            if db_turn is None:
                db_turn = Turn(
                    class_instance=turn.class_instance, number=turn.number, type=turn.type,
                    enrolled=turn.enrolled, capacity=turn.capacity, minutes=turn.minutes, routes=turn.routes,
                    restrictions=turn.restrictions, state=turn.restrictions)
                self.__session__.add(db_turn)
            else:
                if turn.minutes is not None and turn.minutes != 0:
                    db_turn.minutes = turn.minutes
                if turn.enrolled is not None:
                    db_turn.enrolled = turn.enrolled
                if turn.capacity is not None:
                    db_turn.capacity = turn.capacity
                if turn.minutes is not None and turn.minutes != 0:
                    db_turn.minutes = turn.minutes
                if turn.routes is not None:
                    db_turn.routes = turn.routes
                if turn.restrictions is not None:
                    db_turn.restrictions = turn.restrictions
                if turn.state is not None:
                    db_turn.state = turn.state

            for teacher in turn.teachers:  # TODO move this to a separate method
                if teacher in self.__teachers__:
                    teacher = self.__teachers__[teacher.name]
                else:
                    new_teachers = True
                    teacher = Teacher(name=teacher.name)
                    self.__session__.add(teacher)
                db_turn.teachers.append(teacher)

            self.__session__.commit()
            return db_turn
        except Exception:
            log.error("Failed to add turn.\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()
            if new_teachers:
                self.__load_teachers__()

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

        self.__session_lock__.acquire()
        try:
            self.__session__.delete(TurnInstance).filter_by(turn=turn)
            for instance in instances:
                turn.instances.append(TurnInstance(turn=turn, start=instance.start, end=instance.end,
                                                   classroom=instance.classroom, weekday=instance.weekday))
            self.__session__.commit()
        except Exception:
            log.error("Failed to add turn instances.\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()

    def add_turn_students(self, turn: Turn, students):
        self.__session_lock__.acquire()
        try:
            [turn.students.append(student) for student in students]
            self.__session__.commit()
        finally:
            self.__session_lock__.release()

    def add_admissions(self, admissions: [AdmissionCandidate]):
        self.__session_lock__.acquire()
        try:
            admissions = list(map(lambda admission: Admission(
                student=admission.student, name=admission.name, course=admission.course, phase=admission.phase,
                year=admission.year, option=admission.option, state=admission.state), admissions))
            self.__session__.add_all(admissions)
            self.__session__.commit()
            if len(admissions) > 0:
                log.info("{} admissions added successfully!".format(len(admissions)))
        except Exception:
            log.error("Failed to add the National Contest admissions\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()

    def add_enrollments(self, enrollments: [EnrollmentCandidate]):
        self.__session_lock__.acquire()
        try:
            enrollments = list(map(lambda enrollment: Enrollment(
                student=enrollment.student, class_instance=enrollment.class_instance, attempt=enrollment.attempt,
                student_year=enrollment.student_year, statutes=enrollment.statutes, observation=enrollment.observation
            ), enrollments))
            self.__session__.add_all(enrollments)
            self.__session__.commit()
            if len(enrollments) > 0:
                log.info("{} enrollments added successfully!".format(len(enrollments)))
        except Exception:
            log.error("Failed to add the enrollments\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()

    def add_classroom(self, classroom: ClassroomCandidate):
        self.__session_lock__.acquire()
        try:
            if classroom.building in self.__classrooms__ and classroom.name in self.__classrooms__[classroom.building]:
                db_classroom = self.__classrooms__[classroom.building][classroom.name]
            else:
                db_classroom = Classroom(name=classroom.name, building=classroom.building)
                self.__session__.add(db_classroom)
            self.__session__.commit()
            return db_classroom
        except Exception:
            log.error("Failed to add the classroom\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()
            self.__load_classrooms__()

    def add_building(self, building: BuildingCandidate):
        if building.name in self.__buildings__:
            building = self.__buildings__[building.name]
            return building

        self.__session_lock__.acquire()
        try:
            building = Building(name=building.name, institution=building.institution)
            self.__session__.add(building)
            self.__session__.commit()
            return building
        except Exception:
            log.error("Failed to add the building\n%s" % traceback.format_exc())
            self.__session__.rollback()
        finally:
            self.__session_lock__.release()
            self.__load_buildings__()

    def fetch_class_instances(self, year_asc=True, queue=False, year=None, period=None):
        if queue:
            class_instances = Queue()
        else:
            class_instances = []
        order = asc(ClassInstance.year) if year_asc else desc(ClassInstance.year)
        self.__session_lock__.acquire()
        try:
            if year is None:
                if period is not None:
                    log.warning("Period specified without an year")
                if year_asc:
                    instances = self.__session__.query(ClassInstance).order_by(order).all()
                else:
                    instances = self.__session__.query(ClassInstance).order_by(order).all()
            else:
                if period is None:
                    instances = self.__session__.query(ClassInstance).filter_by(year=year).order_by(order).all()
                else:
                    instances = self.__session__.query(ClassInstance). \
                        filter(year=year, period=period).order_by(order).all()
        finally:
            self.__session_lock__.release()

        if queue:
            [class_instances.put(instance) for instance in instances]
        else:
            [class_instances.append(instance) for instance in instances]
        return class_instances

    def find_student(self, name: str, course=None):
        self.__session_lock__.acquire()
        try:
            query_string = '%'
            for word in name.split():
                query_string += (word + '%')

            if course is None:
                return self.__session__.query(Student).filter(Student.name.ilike(query_string)).all()
            else:
                return self.__session__.query(Student).filter(Student.name.ilike(query_string), course=course).all()
        finally:
            self.__session_lock__.release()

    # Hack to use the DBAPI since the session is an attribute of this class shared among threads
    # TODO Make a proper threaded implementation
    def lock(self):
        self.__session_lock__.acquire()

    def unlock(self):
        self.__session_lock__.release()

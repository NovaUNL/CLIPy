from datetime import datetime
from enum import Enum

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import Sequence, DateTime, ForeignKey, CHAR, SMALLINT, Table, Column, Integer, String, UniqueConstraint

from .types import IntEnum

TABLE_PREFIX = 'clip_'
Base = declarative_base()


class Degree(Base):
    __tablename__ = TABLE_PREFIX + 'degrees'
    #: Identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'degree_id_seq'), primary_key=True)
    #: CLIP representation for this degree
    internal_id = Column(String(5), nullable=False)
    #: Verbose representation
    name = Column(String, nullable=False)

    def __str__(self):
        return self.name


class Period(Base):
    __tablename__ = TABLE_PREFIX + 'periods'
    #: Identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'period_id_seq'), primary_key=True)
    #: Part of parts, with the first starting with the academic year (~september)
    part = Column(Integer, nullable=False)
    #: Times this type of period fits in a year (eg: semester = 2, trimester=4)
    parts = Column(Integer, nullable=False)
    #: Letter which describes the type of this period (a - annual, s - semester, t-trimester)
    letter = Column(CHAR, nullable=False)

    def __str__(self):
        return "{} out of {}({})".format(self.part, self.parts, self.letter)


class TurnType(Base):
    __tablename__ = TABLE_PREFIX + 'turn_types'
    #: Identifier
    id = Column(Integer, primary_key=True)
    #: Verbose name
    name = Column(String(30), nullable=False)
    #: Abbreviated name
    abbreviation = Column(String(5), nullable=False)

    def __str__(self):
        return self.name


class TemporalEntity:
    first_year = Column(Integer)
    last_year = Column(Integer)

    def has_time_range(self):
        return not (self.first_year is None or self.last_year is None)

    def add_year(self, year):
        if self.first_year is None:
            self.first_year = year
        if self.last_year is None:
            self.last_year = year

        if self.first_year > year:
            self.first_year = year
        elif self.last_year < year:
            self.last_year = year

    def __str__(self):
        return ('' if self.first_year is None or self.last_year is None else ' {} - {}'.format(
            self.first_year, self.last_year))


class Institution(Base, TemporalEntity):
    __tablename__ = TABLE_PREFIX + 'institutions'
    #: CLIP assigned identifier
    id = Column(Integer, primary_key=True)
    #: Name acronym
    abbreviation = Column(String(10))
    #: Full name
    name = Column(String(100))

    def __str__(self):
        return self.abbreviation


class Building(Base, TemporalEntity):
    __tablename__ = TABLE_PREFIX + 'buildings'
    #: CLIP generated identifier
    id = Column(Integer, primary_key=True)
    #: CLIP name (usually not the full name)
    name = Column(String(50), nullable=False)

    def __str__(self):
        return self.name


class Department(Base, TemporalEntity):
    __tablename__ = TABLE_PREFIX + 'departments'
    #: CLIP assigned identifier
    id = Column(Integer, primary_key=True)
    #: Full name
    name = Column(String(50))
    #: Parent institution
    institution_id = Column(Integer, ForeignKey(Institution.id))

    # Relations and constraints
    institution = relationship("Institution", back_populates="departments")
    __table_args__ = (UniqueConstraint('id', 'institution_id', name='un_' + TABLE_PREFIX + 'department'),)

    def __str__(self):
        return "{}({}, {})".format(self.name, self.id, self.institution.abbreviation) + super().__str__()


Institution.departments = relationship(Department, order_by=Institution.id, back_populates="institution")


class Class(Base):
    __tablename__ = TABLE_PREFIX + 'classes'
    #: Crawler assigned identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'class_id_seq'), primary_key=True)
    #: | CLIP assigned identifier (has collisions, apparently some time ago departments shared classes)
    #: | This could be fixed to become the only identifier, but it's probably not worth the normalization.
    internal_id = Column(Integer)
    #: Full name
    name = Column(String(100))
    #: Acconym-ish name given by someone over the rainbow (probably a nice madam @ divisão académica)
    abbreviation = Column(String(15), default='???')
    #: Number of *half* credits (bologna) that this class takes.
    ects = Column(Integer, nullable=True)
    #: Parent department
    department_id = Column(Integer, ForeignKey(Department.id))

    # Relations and constraints
    department = relationship(Department, back_populates="classes")
    __table_args__ = (UniqueConstraint('internal_id', 'department_id', name='un_' + TABLE_PREFIX + 'class_dept'),)

    def __str__(self):
        return "{}(id:{}, dept:{})".format(self.name, self.internal_id, self.department)


Department.classes = relationship(
    "Class", order_by=Class.name, back_populates="department")


class RoomType(Enum):
    #: A room without a specific purpose
    generic = 1
    #: A classroom with chairs tables n' a good ol' blackboard.
    classroom = 2
    #: Some big room which sits a lot of folks.
    auditorium = 3
    #: The rooms in which the practical wombo-mambo happens.
    laboratory = 4
    #: A classroom with computers
    computer = 5
    #: A room meant for meetings ???
    meeting_room = 6
    #: A room reserved for students completing their master's
    masters = 7

    def __str__(self):
        return str(self.name)


class Room(Base):
    __tablename__ = TABLE_PREFIX + 'rooms'
    #: CLIP assigned identifier
    id = Column(Integer, primary_key=True)
    #: CLIP name (usually not the full name)
    name = Column(String(70), nullable=False)
    #: The :py:class:`RoomType` which tells the purpose of this room
    room_type = Column(IntEnum(RoomType))
    #: This room's parent building
    building_id = Column(Integer, ForeignKey(Building.id), nullable=False)

    # Relations and constraints
    building = relationship(Building, back_populates="rooms")
    __table_args__ = (UniqueConstraint('building_id', 'name', 'room_type', name='un_' + TABLE_PREFIX + 'room'),)

    def __str__(self):
        return "{} - {}".format(self.name, self.building.name)


Building.rooms = relationship(Room, order_by=Room.name, back_populates="building")


class ClassInstance(Base):
    __tablename__ = TABLE_PREFIX + 'class_instances'
    #: Crawler generated identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'class_instance_id_seq'), primary_key=True)
    #: Parent class
    class_id = Column(Integer, ForeignKey(Class.id), nullable=False)
    #: Academic period on which this instance happened
    period_id = Column(Integer, ForeignKey(Period.id), nullable=False)
    #: Year on which this instance happened
    year = Column(Integer)

    # Relations and constraints
    parent = relationship(Class, back_populates="instances")
    period = relationship(Period, back_populates="class_instances")
    __table_args__ = (UniqueConstraint('class_id', 'year', 'period_id', name='un_' + TABLE_PREFIX + 'class_instance'),)

    def __str__(self):
        return "{} on period {} of {}".format(self.parent, self.period, self.year)


Class.instances = relationship("ClassInstance", order_by=ClassInstance.year, back_populates="parent")
Period.class_instances = relationship("ClassInstance", order_by=ClassInstance.year, back_populates="period")


class Course(Base, TemporalEntity):
    __tablename__ = TABLE_PREFIX + 'courses'
    #: Crawler generated identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'course_id_seq'), primary_key=True)
    #: CLIP internal identifier
    internal_id = Column(Integer)
    #: Full name
    name = Column(String(80))
    #: Course acronym
    abbreviation = Column(String(15))
    #: Degree conferred by this course
    degree_id = Column(Integer, ForeignKey(Degree.id))
    #: Lecturing institution
    institution_id = Column(Integer, ForeignKey(Institution.id))

    # Relations and constraints
    degree = relationship(Degree, back_populates="courses")
    institution = relationship("Institution", back_populates="courses")
    __table_args__ = (
        UniqueConstraint('institution_id', 'internal_id', 'abbreviation', name='un_' + TABLE_PREFIX + 'course'),)

    def __str__(self):
        return ("{}(ID:{} Abbreviation:{}, Degree:{} Institution:{})".format(
            self.name, self.internal_id, self.abbreviation, self.degree, self.institution)
                + super().__str__())


Degree.courses = relationship("Course", order_by=Course.internal_id, back_populates="degree")
Institution.courses = relationship("Course", order_by=Course.internal_id, back_populates="institution")

turn_students = Table(TABLE_PREFIX + 'turn_students', Base.metadata,
                      Column('turn_id', ForeignKey(TABLE_PREFIX + 'turns.id'), primary_key=True),
                      Column('student_id', ForeignKey(TABLE_PREFIX + 'students.id'), primary_key=True)
                      )

turn_teachers = Table(TABLE_PREFIX + 'turn_teachers', Base.metadata,
                      Column('turn_id', ForeignKey(TABLE_PREFIX + 'turns.id'), primary_key=True),
                      Column('teacher_id', ForeignKey(TABLE_PREFIX + 'teachers.id'), primary_key=True)
                      )


class Teacher(Base):
    __tablename__ = TABLE_PREFIX + 'teachers'
    #: Crawler assigned identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'teacher_id_seq'), primary_key=True)
    #: CLIP assigned identifier
    internal_id = Column(Integer, nullable=True, unique=True)
    #: Full name
    name = Column(String)

    # Relation
    turns = relationship('Turn', secondary=turn_teachers, back_populates='teachers')

    def __str__(self):
        return self.name


class Student(Base):
    """
    | A CLIP user which is/was doing a course.
    | When a student transfers to another course a new ``internal_id`` is assigned, so some persons have multiple
        student entries.
    """
    __tablename__ = TABLE_PREFIX + 'students'
    #: Crawler assigned ID
    id = Column(Integer, Sequence(TABLE_PREFIX + 'student_id_seq'), primary_key=True)
    #: CLIP assigned ID
    internal_id = Column(Integer)
    #: Student full name
    name = Column(String(100))
    #: CLIP assigned auth abbreviation (eg: john.f)
    abbreviation = Column(String(30), nullable=True)
    #: Student course
    course_id = Column(Integer, ForeignKey(Course.id))
    #: (kinda redudant) student institution
    institution_id = Column(Integer, ForeignKey(Institution.id), nullable=False)

    # Relations and constraints
    course = relationship(Course, back_populates="students")
    institution = relationship("Institution", back_populates="students")
    turns = relationship('Turn', secondary=turn_students, back_populates='students')
    __table_args__ = (
        UniqueConstraint('institution_id', 'internal_id', 'abbreviation', name='un_' + TABLE_PREFIX + 'student'),)

    def __str__(self):
        return "{} ({}, {})".format(self.name, self.internal_id, self.abbreviation)


Course.students = relationship("Student", order_by=Student.internal_id, back_populates="course")
Institution.students = relationship("Student", order_by=Student.internal_id, back_populates="institution")


class Admission(Base):
    """
    An admission represents a national access contest entry which was successfully accepted.
    Sometimes students reject admissions and they never become "real" CLIP students.
    """
    __tablename__ = TABLE_PREFIX + 'admissions'
    #: Crawler assigned identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'admission_id_seq'), primary_key=True)
    #: CLIP student reference (if the student is present)
    student_id = Column(Integer, ForeignKey(Student.id), nullable=True)
    #: Student full name
    name = Column(String(100))
    #: Admission course
    course_id = Column(Integer, ForeignKey(Course.id))
    #: Contest phase
    phase = Column(Integer)
    #: Contest year
    year = Column(Integer)
    #: Admission as the student's n-th option
    option = Column(Integer)
    #: Student current state (as of check_date)
    state = Column(String(50))
    #: Date on which this record was crawled
    check_date = Column(DateTime, default=datetime.now())

    # Relations and constraints
    student = relationship("Student", back_populates="admission_records")
    course = relationship("Course", back_populates="admissions")
    __table_args__ = (
        UniqueConstraint('student_id', 'name', 'year', 'phase', name='un_' + TABLE_PREFIX + 'admission'),)

    def __str__(self):
        return ("{}, admitted to {}({}) (option {}) at the phase {} of the {} contest. {} as of {}".format(
            (self.student.name if self.student_id is not None else self.name),
            self.course.abbreviation, self.course_id, self.option, self.phase, self.year, self.state,
            self.check_date))


Student.admission_records = relationship("Admission", order_by=Admission.check_date, back_populates="student")
Course.admissions = relationship("Admission", order_by=Admission.check_date, back_populates="course")


class Enrollment(Base):
    """
    An enrollment is a :py:class:`Student` to :py:class:`ClassInstance` relationship
    """
    __tablename__ = TABLE_PREFIX + 'enrollments'
    #: Generated identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'enrollement_id_seq'), primary_key=True)
    #: :py:class:`Student` reference
    student_id = Column(Integer, ForeignKey(Student.id))
    #: :py:class:`ClassInstance` reference
    class_instance_id = Column(Integer, ForeignKey(ClassInstance.id))
    #: n-th :py:class:`Student` attempt to do this :py:class:`ClassInstance`
    attempt = Column(SMALLINT)
    #: Student official academic year as of this enrollment
    student_year = Column(Integer)
    #: Special statutes that were applied to this enrollment
    statutes = Column(String(20))
    #: Additional information such as course specialization TODO remove
    observation = Column(String(30))

    # Relations and constraints
    student = relationship("Student", back_populates="enrollments")
    class_instance = relationship("ClassInstance", back_populates="enrollments")
    __table_args__ = (UniqueConstraint('student_id', 'class_instance_id', name='un_' + TABLE_PREFIX + 'enrollment'),)

    def __str__(self):
        return "{} enrolled to {}, attempt:{}, student year:{}, statutes:{}, obs:{}".format(
            self.student, self.class_instance, self.attempt, self.student_year, self.statutes, self.observation)


Student.enrollments = relationship("Enrollment", order_by=Enrollment.student_year, back_populates="student")
ClassInstance.enrollments = relationship("Enrollment", order_by=Enrollment.id, back_populates="class_instance")


class Turn(Base):
    """
    | The generic concept of a :py:class:`Class` turn, which students enroll to.
    | It has corresponding :py:class:`TurnInstance` entities to represent the physical/temporal existence of this turn.
    """
    __tablename__ = TABLE_PREFIX + 'turns'
    #: Identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'turn_id_seq'), primary_key=True)
    #: Parent :py:class:`ClassInstance` for this turn
    class_instance_id = Column(Integer, ForeignKey(ClassInstance.id))
    #: number out of n turns that the parent :py:class:`ClassInstance` has
    number = Column(Integer)
    #: The type of this turn (theoretical, practical, ...)
    type_id = Column(Integer, ForeignKey(TurnType.id))
    #: Number of students enrolled to this turn TODO remove, is redundant
    enrolled = Column(Integer)
    #: Turn capacity TODO remove, is redundant
    capacity = Column(Integer)
    #: Turn duration TODO remove, is redundant
    minutes = Column(Integer)
    #: String representation of the routes
    routes = Column(String(5000))  # TODO do this properly with relationships
    #: Restrictions to this turn's admission
    restrictions = Column(String(200))  # FIXME enum?
    #: Turn current state (opened, closed, these are left unchanged once the class ends)
    state = Column(String(200))  # FIXME enum?

    # Relations and constraints
    teachers = relationship(Teacher, secondary=turn_teachers, back_populates='turns')
    students = relationship(Student, secondary=turn_students, back_populates='turns')
    class_instance = relationship("ClassInstance", back_populates="turns")
    type = relationship("TurnType", back_populates="instances")
    __table_args__ = (UniqueConstraint('class_instance_id', 'number', 'type_id', name='un_' + TABLE_PREFIX + 'turn'),)

    def __str__(self):
        return "{} {}.{}".format(self.class_instance, self.type, self.number)


ClassInstance.turns = relationship("Turn", order_by=Turn.number, back_populates="class_instance")
TurnType.instances = relationship("Turn", order_by=Turn.class_instance_id,
                                  back_populates="type")  # & sort by turn number


class TurnInstance(Base):
    """
    | An instance of a :py:class:`Turn`.
    | This represents the physical and temporal presences a turn.
    """
    __tablename__ = TABLE_PREFIX + 'turn_instances'
    #: Identifier
    id = Column(Integer, Sequence(TABLE_PREFIX + 'turn_instance_id_seq'), primary_key=True)
    #: Parent :py:class:`Turn`
    turn_id = Column(Integer, ForeignKey(Turn.id))
    #: Starting time (in minutes counting from the midnight)
    start = Column(Integer)
    #: Ending time (in minutes, counting from the midnight)
    end = Column(Integer)
    #: :py:class:`Room` in which it happens
    room_id = Column(Integer, ForeignKey(Room.id))
    #: Weekday in which it happens
    weekday = Column(SMALLINT)

    # Relations and constraints
    turn = relationship(Turn, back_populates='instances')
    room = relationship(Room, back_populates="turn_instances")
    __table_args__ = (UniqueConstraint('turn_id', 'start', 'weekday', name='un_' + TABLE_PREFIX + 'turn_instance'),)

    @staticmethod
    def minutes_to_str(minutes: int):
        return "{}:{}".format(minutes / 60, minutes % 60)

    def __str__(self):
        return "{}, weekday {}, hour {}".format(self.turn, self.weekday, self.minutes_to_str(self.start))


Turn.instances = relationship(TurnInstance, order_by=TurnInstance.weekday, back_populates='turn',
                              cascade="save-update, merge, delete")
Room.turn_instances = relationship(TurnInstance, order_by=TurnInstance.weekday, back_populates='room')

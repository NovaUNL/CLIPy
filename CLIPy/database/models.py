from datetime import datetime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import Sequence, DateTime, ForeignKey, CHAR, SMALLINT, Table, Column, Integer, String, UniqueConstraint

TABLE_PREFIX = 'clip_'
Base = declarative_base()


class Degree(Base):
    __tablename__ = TABLE_PREFIX + 'degrees'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'degree_id_seq'), primary_key=True)
    internal_id = Column(String(5), nullable=False)
    name = Column(String, nullable=False)

    def __str__(self):
        return self.name


class Period(Base):
    __tablename__ = TABLE_PREFIX + 'periods'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'period_id_seq'), primary_key=True)
    part = Column(Integer, nullable=False)
    parts = Column(Integer, nullable=False)
    letter = Column(CHAR, nullable=False)
    start_month = Column(Integer)
    end_month = Column(Integer)

    def __str__(self):
        return "{} out of {}({})".format(self.part, self.parts, self.letter)


class TurnType(Base):
    __tablename__ = TABLE_PREFIX + 'turn_types'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'turn_type_id_seq'), primary_key=True)
    name = Column(String(30), nullable=False)
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
    id = Column(Integer, Sequence(TABLE_PREFIX + 'institution_id_seq'), primary_key=True)
    internal_id = Column(Integer, nullable=False)
    abbreviation = Column(String(10))
    name = Column(String(100))

    def __str__(self):
        return self.abbreviation


class Building(Base):
    __tablename__ = TABLE_PREFIX + 'buildings'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'building_id_seq'), primary_key=True)
    name = Column(String(50), nullable=False)
    institution_id = Column(Integer, ForeignKey(Institution.id), nullable=False)
    institution = relationship(Institution, back_populates="buildings")
    __table_args__ = (UniqueConstraint('institution_id', 'name', name='un_' + TABLE_PREFIX + 'building'),)

    def __str__(self):
        return self.name


Institution.buildings = relationship(Building, order_by=Building.name, back_populates="institution")


class Department(Base, TemporalEntity):
    __tablename__ = TABLE_PREFIX + 'departments'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'department_id_seq'), primary_key=True)
    internal_id = Column(Integer)
    name = Column(String(50))
    institution_id = Column(Integer, ForeignKey(Institution.id))
    institution = relationship("Institution", back_populates="departments")
    __table_args__ = (UniqueConstraint('internal_id', 'institution_id', name='un_' + TABLE_PREFIX + 'department'),)

    def __str__(self):
        return "{}({}, {})".format(self.name, self.internal_id, self.institution.abbreviation) + super().__str__()


Institution.departments = relationship(Department, order_by=Institution.id, back_populates="institution")


class Class(Base):
    __tablename__ = TABLE_PREFIX + 'classes'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'class_id_seq'), primary_key=True)
    internal_id = Column(Integer)
    name = Column(String(100))
    department_id = Column(Integer, ForeignKey(Department.id))
    department = relationship(Department, back_populates="classes")
    __table_args__ = (UniqueConstraint('internal_id', 'department_id', name='un_' + TABLE_PREFIX + 'class_dept'),)

    def __str__(self):
        return "{}(id:{}, dept:{})".format(self.name, self.internal_id, self.department)


Department.classes = relationship(
    "Class", order_by=Class.name, back_populates="department")


class Classroom(Base):
    __tablename__ = TABLE_PREFIX + 'classrooms'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'classroom_id_seq'), primary_key=True)
    name = Column(String(70), nullable=False)
    building_id = Column(Integer, ForeignKey(Building.id), nullable=False)
    building = relationship(Building, back_populates="classrooms")
    __table_args__ = (UniqueConstraint('building_id', 'name', name='un_' + TABLE_PREFIX + 'class_dept'),)

    def __str__(self):
        return "{} - {}".format(self.name, self.building.name)


Building.classrooms = relationship(Classroom, order_by=Classroom.name, back_populates="building")


class ClassInstance(Base):
    __tablename__ = TABLE_PREFIX + 'class_instances'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'class_instance_id_seq'), primary_key=True)
    class_id = Column(Integer, ForeignKey(Class.id), nullable=False)
    period_id = Column(Integer, ForeignKey(Period.id), nullable=False)
    year = Column(Integer)
    parent = relationship(Class, back_populates="instances")
    period = relationship(Period, back_populates="class_instances")
    __table_args__ = (UniqueConstraint('class_id', 'year', 'period_id', name='un_' + TABLE_PREFIX + 'class_instance'),)

    def __str__(self):
        return "{} on period {} of {}".format(self.parent, self.period, self.year)


Class.instances = relationship("ClassInstance", order_by=ClassInstance.year, back_populates="parent")
Period.class_instances = relationship("ClassInstance", order_by=ClassInstance.year, back_populates="period")


class Course(Base, TemporalEntity):
    __tablename__ = TABLE_PREFIX + 'courses'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'course_id_seq'), primary_key=True)
    internal_id = Column(Integer)
    name = Column(String(80))
    abbreviation = Column(String(15))
    degree_id = Column(Integer, ForeignKey(Degree.id))
    institution_id = Column(Integer, ForeignKey(Institution.id))
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
    id = Column(Integer, Sequence(TABLE_PREFIX + 'teacher_id_seq'), primary_key=True)
    name = Column(String)
    turns = relationship('Turn', secondary=turn_teachers, back_populates='teachers')

    def __str__(self):
        return self.name


class Student(Base):
    __tablename__ = TABLE_PREFIX + 'students'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'student_id_seq'), primary_key=True)
    internal_id = Column(Integer)
    name = Column(String(100))
    abbreviation = Column(String(30), nullable=True)
    course_id = Column(Integer, ForeignKey(Course.id))
    institution_id = Column(Integer, ForeignKey(Institution.id), nullable=False)
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
    __tablename__ = TABLE_PREFIX + 'admissions'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'admission_id_seq'), primary_key=True)
    student_id = Column(Integer, ForeignKey(Student.id))
    name = Column(String(100))
    course_id = Column(Integer, ForeignKey(Course.id))
    phase = Column(Integer)
    year = Column(Integer)
    option = Column(Integer)
    state = Column(String(50))
    check_date = Column(DateTime, default=datetime.now())
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
    __tablename__ = TABLE_PREFIX + 'enrollments'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'enrollement_id_seq'), primary_key=True)
    student_id = Column(Integer, ForeignKey(Student.id))
    class_instance_id = Column(Integer, ForeignKey(ClassInstance.id))
    attempt = Column(SMALLINT)
    student_year = Column(Integer)
    statutes = Column(String(20))
    observation = Column(String(30))
    student = relationship("Student", back_populates="enrollments")
    class_instance = relationship("ClassInstance", back_populates="enrollments")
    __table_args__ = (UniqueConstraint('student_id', 'class_instance_id', name='un_' + TABLE_PREFIX + 'enrollment'),)

    def __str__(self):
        return "{} enrolled to {}, attempt:{}, student year:{}, statutes:{}, obs:{}".format(
            self.student, self.class_instance, self.attempt, self.student_year, self.statutes, self.observation)


Student.enrollments = relationship("Enrollment", order_by=Enrollment.student_year, back_populates="student")
ClassInstance.enrollments = relationship("Enrollment", order_by=Enrollment.id, back_populates="class_instance")


class Turn(Base):
    __tablename__ = TABLE_PREFIX + 'turns'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'turn_id_seq'), primary_key=True)
    class_instance_id = Column(Integer, ForeignKey(ClassInstance.id))
    number = Column(Integer)
    type_id = Column(Integer, ForeignKey(TurnType.id))
    enrolled = Column(Integer)  # REDUNDANT
    capacity = Column(Integer)
    minutes = Column(Integer)
    routes = Column(String(5000))  # FIXME adjust
    restrictions = Column(String(200))  # FIXME adjust
    state = Column(String(200))  # FIXME adjust
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
    __tablename__ = TABLE_PREFIX + 'turn_instances'
    id = Column(Integer, Sequence(TABLE_PREFIX + 'turn_instance_id_seq'), primary_key=True)
    turn_id = Column(Integer, ForeignKey(Turn.id))
    start = Column(Integer)
    end = Column(Integer)
    classroom_id = Column(Integer, ForeignKey(Classroom.id))
    turn = relationship(Turn, back_populates='instances')
    weekday = Column(SMALLINT)
    classroom = relationship(Classroom, back_populates="turn_instances")
    __table_args__ = (UniqueConstraint('turn_id', 'start', 'weekday', name='un_' + TABLE_PREFIX + 'turn_instance'),)

    @staticmethod
    def minutes_to_str(minutes: int):
        return "{}:{}".format(minutes / 60, minutes % 60)

    def __str__(self):
        return "{}, weekday {}, hour {}".format(self.turn, self.weekday, self.minutes_to_str(self.start))


Turn.instances = relationship(TurnInstance, order_by=TurnInstance.weekday, back_populates='turn',
                              cascade="save-update, merge, delete")
Classroom.turn_instances = relationship(TurnInstance, order_by=TurnInstance.weekday, back_populates='classroom')

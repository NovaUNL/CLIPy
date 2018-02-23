from datetime import datetime

from CLIPy.database.models import Turn, ClassInstance, Institution, Student, Course, Degree, Period, Class, \
    Department, Building, TurnType


class TemporalEntity:
    def __init__(self, identifier, first_year, last_year):
        self.id = identifier
        self.first_year = first_year
        self.last_year = last_year

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


class InstitutionCandidate(TemporalEntity):
    def __init__(self, identifier: int, name: str, abbreviation: str, first_year=None, last_year=None):
        super().__init__(identifier, first_year=first_year, last_year=last_year)
        self.abbreviation = abbreviation
        self.name = name if name is not None else abbreviation

    def __str__(self):
        return self.name


class DepartmentCandidate(TemporalEntity):
    def __init__(self, identifier: int, name: str, institution: Institution, first_year=None, last_year=None):
        super().__init__(identifier, first_year=first_year, last_year=last_year)
        self.name = name
        self.institution = institution

    def __str__(self):
        return self.name


class DegreeCandidate:
    def __init__(self, identifier, name):
        self.id = identifier
        self.name = name

    def __str__(self):
        return self.name


class ClassCandidate:
    def __init__(self, identifier: int, name: str, department: Department):
        self.id = identifier
        self.name = name
        self.department = department

    def __str__(self):
        return self.name


class ClassInstanceCandidate:
    def __init__(self, parent: Class, period: Period, year: int):
        self.parent = parent
        self.period = period
        self.year = year

    def __str__(self):
        return "{} on period {} of {}".format(self.parent, self.period, self.year)


class CourseCandidate(TemporalEntity):
    def __init__(self, identifier: int, name: str, institution: Institution,
                 degree=None, abbreviation=None, first_year=None, last_year=None):
        super().__init__(identifier, first_year, last_year)
        self.name = name
        self.abbreviation = abbreviation
        self.degree = degree
        self.institution = institution

    def __str__(self):
        return "{} ({})".format(self.name, self.degree.name)


class StudentCandidate:
    def __init__(self, identifier, name: str, course: Course, institution: Institution, abbreviation=None):
        self.id = identifier
        self.name = name
        self.course = course
        self.institution = institution
        self.abbreviation = abbreviation

    def __str__(self):
        return "{} ({}, {})".format(self.name, self.id, self.abbreviation)


class TeacherCandidate:
    def __init__(self, name):
        self.name = name


class AdmissionCandidate:
    def __init__(self, student, name: str, course: Course, phase: int, year: int, option: int, state,
                 check_date=None):
        self.student = student
        self.name = name
        self.course = course
        self.phase = phase
        self.year = year
        self.option = option
        self.state = state
        self.check_date = check_date if check_date is not None else datetime.now()

    def __str__(self):
        return "{}, admitted to {} (opt: {}, phase: {}) {} contest. {} as of {}".format(
            (self.student.name if self.student is not None else self.name),
            self.course.name, self.option, self.phase, self.year, self.state, self.check_date)


class EnrollmentCandidate:
    def __init__(self, student: Student, class_instance: ClassInstance, attempt: int, student_year: int,
                 statutes, observation):
        self.student = student
        self.class_instance = class_instance
        self.attempt = attempt
        self.student_year = student_year
        self.statutes = statutes
        self.observation = observation

    def __str__(self):
        return "{} enrolled to {}, attempt:{}, student year:{}, statutes:{}, obs:{}".format(
            self.student, self.class_instance, self.attempt, self.student_year, self.statutes, self.observation)


class BuildingCandidate:
    def __init__(self, name: str, institution: Institution):
        if name is None:
            raise ValueError("A building must have a name")
        if institution is None:
            raise ValueError("A building must belong to an institution")
        self.name = name
        self.institution = institution

    def __str__(self):
        return "{}, {}".format(self.name, self.institution.name)

    def __hash__(self):
        return hash(self.name) + hash(self.institution.id)

    def __eq__(self, other):
        if isinstance(self, other.__class__):
            return self.name == other.name and self.institution == other.institution


class ClassroomCandidate:
    def __init__(self, name, building: Building):
        if name is None:
            raise ValueError("A classroom must have a name")
        if building is None:
            raise ValueError("A classroom must belong to a building")
        self.name = name
        self.building = building

    def __str__(self):
        return "{}, {}".format(self.name, self.building.name)


class TurnCandidate:
    def __init__(self, class_instance: ClassInstance, number: int, turn_type: TurnType, enrolled: int, capacity: int,
                 minutes=None, routes=None, restrictions=None, state=None, teachers=list()):
        self.class_instance = class_instance
        self.number = number
        self.type = turn_type
        self.enrolled = enrolled
        self.capacity = capacity
        self.minutes = minutes
        self.routes = routes
        self.restrictions = restrictions
        self.state = state
        self.teachers = teachers

    def __str__(self):
        return "turn {}.{} of {} {}/{} students, {} hours, {} routes, state: {}, {} teachers".format(
            self.type, self.number, self.class_instance, self.enrolled, self.capacity,
            self.minutes / 60, self.routes, self.state, len(self.teachers))


class TurnInstanceCandidate:
    def __init__(self, turn: Turn, start: int, end: int, weekday: int, classroom=None):
        self.turn = turn
        self.start = start
        self.end = end
        self.weekday = weekday
        self.classroom = classroom

    @staticmethod
    def time_str(time):
        return "{}:{}".format(time / 60, time % 60)

    def __str__(self):
        return "{} to {}, day:{}, turn{}".format(
            self.time_str(self.start), self.time_str(self.end), self.weekday, self.turn)

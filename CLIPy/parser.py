import logging
import re
from unicodedata import normalize

from . import urls
from .utils import weekday_to_id

log = logging.getLogger(__name__)


def get_departments(page):
    """
    Parses departments

    :param page: A page fetched from :py:const:`CLIPy.urls.DEPARTMENTS`
    :return: List of ``(department_id, name)`` tuples
    """
    departments = []
    department_links = page.find_all(href=urls.DEPARTMENT_EXP)
    for department_link in department_links:
        department_id = int(urls.DEPARTMENT_EXP.findall(department_link.attrs['href'])[0])
        name = department_link.text.strip()
        departments.append((department_id, name))
    return departments


def get_course_names(page):
    """
    Parses courses names

    :param page: A page fetched from :py:const:`CLIPy.urls.COURSES`
    :return: List of ``(identifier, name)`` tuples
    """
    courses = []
    course_links = page.find_all(href=urls.COURSE_EXP)
    for course_link in course_links:  # for every course link in the courses list page
        identifier = int(urls.COURSE_EXP.findall(course_link.attrs['href'])[0])
        name = course_link.text.strip()
        courses.append((identifier, name))
    return courses


def get_course_activity_years(page):
    """
    Parses a course existence time span

    :param page: A page fetched from :py:const:`CLIPy.urls.CURRICULAR_PLANS`
    :return: A ``first, last`` tuple
    """
    first = None
    last = None
    year_links = page.find_all(href=urls.YEAR_EXP)
    # find the extremes
    for year_link in year_links:
        year = int(urls.YEAR_EXP.findall(year_link.attrs['href'])[0])
        if first is None or year < first:
            first = year
        if last is None or year > last:
            last = year
    return first, last


def get_course_abbreviations(page):
    """
    Parses course abbreviations

    :param page: A page fetched from :py:const:`CLIPy.urls.STATISTICS`
    :return: List of ``(identifier, abbreviation)`` tuples
    """
    courses = []
    course_links = page.find_all(href=urls.COURSE_EXP)
    for course_link in course_links:
        identifier = int(urls.COURSE_EXP.findall(course_link.attrs['href'])[0])
        abbreviation = course_link.contents[0].strip()
        if abbreviation == '':
            continue
        courses.append((identifier, abbreviation))
    return courses


def get_admissions(page):
    """
    | Parses admission lists.
    | It has a destructive behaviour on the provided page structure.

    :param page: A page fetched from :py:const:`CLIPy.urls.ADMITTED`
    :return: Tuple with ``name, option, student_iid, state``
    """

    admitted = []
    try:
        table_root = page.find('th', colspan="8", bgcolor="#95AEA8").parent.parent
    except AttributeError:
        raise LookupError("Couldn't find the table root")

    for tag in table_root.find_all('th'):  # for every table header
        if tag.parent is not None:
            tag.parent.decompose()  # remove its parent row

    table_rows = table_root.find_all('tr')
    for table_row in table_rows:  # for every student admission
        table_row = list(table_row.children)

        # take useful information
        name = table_row[1].text.strip()
        option = table_row[9].text.strip()
        student_iid = table_row[11].text.strip()
        state = table_row[13].text.strip()

        student_iid = int(student_iid) if student_iid != '' else None
        option = None if option == '' else int(option)
        state = state if state != '' else None

        admitted.append((name, option, student_iid, state))
    return admitted


def get_enrollments(page):
    """
    Reads students enrollments from a file

    :param page: A file fetched from :py:const:`CLIPy.urls.CLASS_ENROLLED`
    :return: | List of tuples with student information
             | ``(id, name, abbreviation, statutes, course, attempt, student_year)``
    """
    # Strip file header and split it into lines
    content = page.text.splitlines()[4:]

    enrollments = []

    for line in content:  # for every student enrollment
        information = line.split('\t')
        if len(information) != 7:
            log.warning("Invalid line")
            continue
        # take useful information
        statutes = information[0].strip()
        name = information[1].strip()
        student_id = information[2].strip()
        if student_id != "":
            try:
                student_id = int(information[2].strip())
            except Exception:
                pass

        abbreviation = information[3].strip()
        course = information[4].strip()
        attempt = int(information[5].strip().rstrip('ºª'))
        student_year = int(information[6].strip().rstrip('ºª'))
        if abbreviation == '':
            abbreviation = None
        if statutes == '':
            statutes = None
        if name == '':
            raise Exception("Student with no name")

        enrollments.append((student_id, name, abbreviation, statutes, course, attempt, student_year))
    return enrollments


schedule_exp = re.compile(  # extract turn information
    '(?P<weekday>[\\w-]+) {2}'
    '(?P<init_hour>\\d{2}):(?P<init_min>\\d{2}) - (?P<end_hour>\\d{2}):(?P<end_min>\\d{2})(?: {2})?'
    '(?:Ed .*: (?P<room>[\\w\\b. ]+)/(?P<building>[\\w\\d. ]+))?')


def get_turn_info(page):
    """
    Parses the turn details table from the turn page.

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_TURN`
    :return: | Turn information tuple with
             | ``instances, routes, teachers, restrictions, weekly_minutes, state, enrolled, capacity``
             | With instances, routes and teachers being lists
             | Instances has the following structure ``weekday, start, end, building, room``
    """

    instances = []
    routes = []
    teachers = []
    restrictions = None
    weekly_minutes = None
    state = None
    enrolled = None
    capacity = None

    info_table_root = page.find('th', colspan="2", bgcolor="#aaaaaa").parent.parent

    for tag in info_table_root.find_all('th'):  # for every table header
        if tag.parent is not None:
            tag.parent.decompose()  # remove its parent row

    information_rows = info_table_root.find_all('tr')
    del info_table_root

    fields = {}
    previous_key = None
    for table_row in information_rows:
        if len(table_row.contents) < 3:  # several lines ['\n', 'value']
            fields[previous_key].append(normalize('NFKC', table_row.contents[1].text.strip()))
        else:  # inline info ['\n', 'key', '\n', 'value']
            key = table_row.contents[1].text.strip().lower()
            previous_key = key
            fields[key] = [normalize('NFKC', table_row.contents[3].text.strip())]

    del previous_key

    for field, content in fields.items():
        if field == "marcação":
            for row in content:
                information = schedule_exp.search(row)
                if information is None:
                    raise Exception("Bad schedule:" + str(information))

                weekday = weekday_to_id(information.group('weekday'))
                start = int(information.group('init_hour')) * 60 + int(information.group('init_min'))
                end = int(information.group('end_hour')) * 60 + int(information.group('end_min'))
                building = information.group('building')
                if building:
                    building = building.strip()
                room = information.group('room')
                if room:
                    room = room.strip()

                instances.append((weekday, start, end, building, room))
        elif field == "turno":
            pass
        elif "percursos" in field:
            routes = content
        elif field == "docentes":
            for teacher in content:
                teachers.append(teacher)
        elif "carga" in field:
            weekly_minutes = int(float(content[0].rstrip(" horas")) * 60)
        elif field == "estado":
            state = content[0]
        elif field == "capacidade":
            parts = content[0].split('/')
            try:
                enrolled = int(parts[0])
            except ValueError:
                log.warning("No enrolled information")
            try:
                capacity = int(parts[1])
            except ValueError:
                log.warning("No capacity information")
        elif field == "restrição":
            restrictions = content[0]
        else:
            raise Exception("Unknown field " + field)

    return instances, routes, teachers, restrictions, weekly_minutes, state, enrolled, capacity


def get_turn_students(page):
    """
    Parses the students list from the turn page.

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_TURN`
    :return: List of tuples with student details (``name, id, abbreviation, course abbreviation``)
    """
    students = []
    student_table_root = page.find('th', colspan="4", bgcolor="#95AEA8").parent.parent

    # Remove useless rows
    for tag in student_table_root.find_all('th'):
        if tag.parent is not None:
            tag.parent.decompose()  # remove its parent row

    student_rows = student_table_root.find_all('tr')

    for student_row in student_rows:
        name = student_row.contents[1].text.strip()
        id = student_row.contents[3].text.strip()
        abbreviation = student_row.contents[5].text.strip()
        course = student_row.contents[7].text.strip()
        students.append((name, id, abbreviation, course))

    return students

import logging
import re
from datetime import datetime, timedelta
from unicodedata import normalize
from urllib.parse import unquote

import htmlmin
# noinspection PyProtectedMember
from bs4 import NavigableString

from .database import models
from . import urls
from .database.models import EventType, EvaluationSeason
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


class_title_exp = re.compile('^\(\d+\) (?P<name>.*) \((?P<abbr>.+)\)$')
ects_exp = re.compile('(?P<ects>\d|\d.\d)\s?ECTS.*')


def get_class_instance(page, class_id):
    elements = page.find_all('td', attrs={'class': 'subtitulo'})

    title_matches = class_title_exp.search(elements[0].text.strip())
    name = None
    try:
        name = str(title_matches.group('name')).strip()
    except:
        log.warning(f'Class {class_id} has no name.')

    abbr = None
    try:
        abbr = str(title_matches.group('abbr')).strip()
    except:
        log.warning(f'Class {name}({class_id}) has no abbreviation')

    ects = None
    try:
        ects_matches = ects_exp.search(elements[1].text)
        ects_s = str(ects_matches.group('ects')).strip()
        # ECTSs are stored in halves. Someone decided it would be cool to award half ECTS...
        ects = int(float(ects_s) * 2)
    except:
        log.warning(f'Class {name}({class_id}) has no ECTS information')

    return name, abbr, ects


def get_class_identity(page, class_id):
    table = page.find('table', class_='vdisplay')

    name = None
    abbr = None
    ects = None

    for row in table.find_all('tr'):
        key = row.find('th').text.strip()
        if key == 'Nome':
            name = row.find('td').text.strip()
        elif key == 'Abreviatura' or key == 'Sigla':
            abbr = row.find('td').text.strip()

    ects_table = page.find('table', class_='ldisplay')
    ects_text = None
    try:
        ects_label = ects_table.find(text='ECTS')
        if ects_label is not None:
            ects_text = ects_label.parent.parent \
                .find('td', align="right") \
                .text \
                .strip() \
                .replace(',', '.')
            # ECTSs are stored in halves. Someone decided it would be cool to award half ECTS...
            ects = int(float(ects_text) * 2)
    except:
        if ects_text == '':
            log.warning(f'Class {name}({class_id}) has no ECTS information')
        else:
            log.error(f'Unable to read class {name}({class_id}) ECTS information: {ects_text}')

    return name, abbr, ects


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


#: Generic shift scheduling string. Looks something like 'Segunda-Feira  XX:00 - YY:00  Ed Z: Lab 123 A/Ed.Z'
SHIFT_SCHEDULING_EXP = re.compile(
    '^(?P<weekday>[\w-]+) '
    '{2}(?P<init_hour>\d{2}):(?P<init_min>\d{2}) - (?P<end_hour>\d{2}):(?P<end_min>\d{2})(?: {2})?'
    '(?:(E[dD] ?.*: )?(?:Sala )?(?P<computer_lab>Lab Computadores )?(?P<lab>Lab[.]? ?)?(?P<room>([\w\b/. -]+))(?:\([\w. ]+\))?/(?P<building>[\w\d. ]+))?$')


def get_shift_info(page):
    """
    Parses the shift details table from the shift page.

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_SHIFT`
    :return: | Shift information tuple with
             | ``instances, routes, teachers, restrictions, weekly_minutes, state, enrolled, capacity``
             | With instances, routes and teachers being lists
             | Instances has the following structure ``weekday, start, end, building, room``
             | `room` is a tuple `name, type`, with `type` being `null` if unknown.
    """

    instances = []
    routes = []
    teachers = []
    restrictions = None
    weekly_minutes = None
    state = None
    enrolled = None
    capacity = None

    try:
        info_table_root = page.find('th', colspan="2", bgcolor="#aaaaaa").parent.parent
    except AttributeError:
        raise LookupError("Couldn't find the table root")

    for tag in info_table_root.find_all('th'):  # for every table header
        if tag.parent is not None:
            tag.parent.decompose()  # remove its parent row

    information_rows = info_table_root.find_all('tr')
    del info_table_root

    fields = {}
    previous_key = None
    for table_row in information_rows:
        if len(table_row.contents) <= 3:  # several lines ['\n', 'value']
            fields[previous_key].append(normalize('NFKC', table_row.contents[1].text.strip()))
        else:  # inline info ['\n', 'key', '\n', 'value']
            key = table_row.contents[1].text.strip().lower()
            previous_key = key
            fields[key] = [normalize('NFKC', table_row.contents[3].text.strip())]

    del previous_key

    for field, content in fields.items():
        if field == "marcação":
            for row in content:
                information = SHIFT_SCHEDULING_EXP.search(row)
                if information is None:
                    raise Exception("Bad schedule:" + str(information))

                information = information.groupdict()

                weekday = weekday_to_id(information['weekday'])
                start = int(information['init_hour']) * 60 + int(information['init_min'])
                end = int(information['end_hour']) * 60 + int(information['end_min'])
                if 'building' in information and information['building'] is not None:
                    building = information['building'].strip()
                    if 'room' in information and information['room'] is not None:
                        if 'computer_lab' in information and information['computer_lab'] is not None:
                            room = (information['room'].strip(), models.RoomType.computer)
                        elif 'lab' in information and information['lab'] is not None:
                            room = (information['room'].strip(), models.RoomType.laboratory)
                        # elif 'seminar' in information and information['seminar'] is not None:
                        #     room = (information['room'].strip(), models.RoomType.???)
                        else:
                            room = (information['room'].strip(), None)
                    else:
                        room = None
                else:
                    building = None
                    room = None

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


def get_shift_students(page):
    """
    Parses the students list from the shift page.

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_SHIFT`
    :return: List of tuples with student details (``name, identifier, abbreviation, course abbreviation``)
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
        try:
            identifier = int(student_row.contents[3].text.strip())
        except ValueError:
            log.error(f'Student with non-numeric id found.\nData:{student_row.text.strip()}')
            identifier = student_row.contents[3].text.strip()
        abbreviation = student_row.contents[5].text.strip()
        course = student_row.contents[7].text.strip()
        students.append((name, identifier, abbreviation, course))

    return students


def get_bilingual_info(page) -> (str, str, datetime, str):
    """
    Parses a page with a generic bilingual template.

    :param page: A page fetched from one of the following addresses:
        :py:const:`CLIPy.urls.CLASS_DESCRIPTION`, :py:const:`CLIPy.urls.CLASS_OBJECTIVES`,
        :py:const:`CLIPy.urls.CLASS_REQUIREMENTS`, :py:const:`CLIPy.urls.CLASS_COMPETENCES`,
        :py:const:`CLIPy.urls.CLASS_PROGRAM`, :py:const:`CLIPy.urls.CLASS_BIBLIOGRAPHY`,
        :py:const:`CLIPy.urls.CLASS_TEACHING_METHODS`, :py:const:`CLIPy.urls.CLASS_EVALUATION_METHODS`,
        :py:const:`CLIPy.urls.CLASS_ASSISTANCE` and possibly a few others.
    :return: A tuple with ``portuguese_text, english_text, edition_datetime, last_editor`` as its elements.
    """
    table_root = page.find('table', width="75%", cellspacing="2", cellpadding="2", border="0", bgcolor="#dddddd")
    if table_root is None:
        return None, None, None, None
    panes = table_root.find_all('td', valign="top", bgcolor="#ffffff")
    if len(panes) != 2:
        # file = open('page.html', 'w')
        # log.critical('A problematic page appeared and it couldn\'t be parsed.'
        #              'Its contents have been saved to page.html')
        # file.write(page.prettify())
        raise ValueError()
    footer = table_root.find_all('small')

    portuguese = ''
    for content in panes[0].contents:
        portuguese += str(content)
    portuguese = htmlmin.minify(portuguese, remove_empty_space=True)

    english = ''
    for content in panes[1].contents:
        english += str(content).strip()
    english = htmlmin.minify(english, remove_empty_space=True)

    edition_datetime, last_editor = None, None
    if len(footer) >= 2:
        try:
            last_editor = footer[-2].text.split(':')[1].strip()
            if last_editor == 'Agente de sistema':
                last_editor = None

            edition_datetime = datetime.strptime(footer[-1].text.strip(), "Em: %Y-%m-%d %H:%M")
        except IndexError:
            log.warning(f"Could not parse a footer with the contents: {footer}")

    return portuguese, english, edition_datetime, last_editor


def _get_class_events_extract_date(columns):
    date = None
    from_time = None
    to_time = None
    try:
        date = columns[0].text.strip()
        date = datetime.strptime(date, "%Y-%m-%d").date()
        from_time_str = columns[1].text.strip()
        from_time = datetime.strptime(from_time_str, "%H:%M").time()
        to_time_str = columns[3].text.strip()
        to_time = datetime.strptime(to_time_str, "%H:%M").time()
    except ValueError:
        pass
    return date, from_time, to_time


def _extract_info(column):
    info_rows = column.find_all('td', {"style": False})
    first_row = info_rows[0].text.strip()
    second_row = info_rows[1].text.strip()
    if second_row == '':
        return (first_row, None)
    return (first_row, second_row)


def get_class_events(page) -> (str, str, datetime, str):
    table_root = page.find('table', class_="ldisplay", cellspacing='2', cellpadding='2', border='0')
    if table_root is None:
        return []
    table_body = table_root.find('tbody')
    rows = table_body.find_all('tr', recursive=False)
    events = []
    for row in rows:
        columns = list(row.find_all('td', recursive=False))
        col_count = len(columns)
        if col_count == 2:
            continue
        if col_count != 5:
            print()
            raise Exception()

        date, from_time, to_time = _get_class_events_extract_date(columns)
        color_tag = columns[4].find(True, {"style": True})
        if color_tag is None:
            print()
        color = color_tag.attrs['style'].split('#')[1]
        type_str = columns[4].text.strip()
        type_str_lower = type_str.lower()
        event_type = EventType.unknown
        if color == 'E8A400;':
            if 'teste' in type_str_lower:
                event_type = EventType.test
            elif 'exame' in type_str_lower:
                event_type = EventType.exam
            else:
                print()

            if 'normal' in type_str_lower:
                events.append((date, from_time, to_time, event_type, EvaluationSeason.normal, None, None))
            elif 'recurso' in type_str_lower:
                events.append((date, from_time, to_time, event_type, EvaluationSeason.recourse, None, None))
            elif 'especial' in type_str_lower:
                events.append((date, from_time, to_time, event_type, EvaluationSeason.special, None, None))
            else:
                print()
        elif color == 'DADCFF;':
            info, note = _extract_info(columns[4])
            info_lower = info.lower()
            if 'test' in info_lower:
                event_type = EventType.test
            elif 'exam' in info_lower:
                event_type = EventType.exam
            elif 'campo' in info_lower:
                event_type = EventType.field_trip
            elif 'entrega' in info_lower or 'deliver' in info_lower or 'deadline' in info_lower:
                event_type = EventType.project_delivery
            elif 'discus' in info_lower or 'defesa' in info_lower:
                event_type = EventType.discussion
            elif 'enuncia' in info_lower or ('projec' in info_lower and 'defini' in info_lower):
                event_type = EventType.project_announcement
            elif 'presenta' in info_lower:
                event_type = EventType.presentation
            elif 'visit' in info_lower or 'saída' in info_lower:
                event_type = EventType.field_trip
            elif 'semin' in info_lower or (note and 'semin' in note):
                event_type = EventType.seminar
            elif 'palestra' in info_lower or (note and 'palestra' in note):
                event_type = EventType.talk
            elif 'trabalho' in info_lower and (
                    (note and 'entrega' in note or 'deliver' in info)
                    or (note and ('entrega' in note or 'deliver' in note))):
                event_type = EventType.field_trip
            else:
                print(f'{type_str_lower} - {note}')
            events.append((date, from_time, to_time, event_type, EvaluationSeason.unknown, info, note))
        elif color == 'CC9;':
            if 'viagem' in type_str_lower:
                event_type = EventType.field_trip
            elif 'aula' in type_str_lower:
                event_type = EventType.additional_class
            else:
                print(type_str_lower)

            events.append((date, from_time, to_time, event_type, EvaluationSeason.unknown, type_str, None))
        else:
            raise Exception()
    return events


def get_teachers(page):
    """
    Parses teachers

    :param page: A page fetched from :py:const:`CLIPy.urls.DEPARTMENT_TEACHERS`
    :return: List of ``(teacher_id, name)`` tuples
    """
    teacher = []
    department_links = page.find_all(href=urls.TEACHER_EXP)
    for teacher_link in department_links:
        teacher_id = int(urls.TEACHER_EXP.findall(teacher_link.attrs['href'])[0])
        name = teacher_link.text.strip()
        teacher.append((teacher_id, name))
    return teacher


building_exp = re.compile('(?:E[dD] .*: (?P<room>[\\w\\b. ]+)/(?P<building>[\\w\\d. ]+))?')


def get_class_summaries(page):
    """
    Parses summaries

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_SUMMARIES`
    :return: List of
        ``(shift, teacher, start_datetime, duration, room, building, attendance, message, edited_datetime)`` tuples
    """
    summaries = []
    tbody = page.find('th', class_="center", colspan="8", bgcolor="#dddddd").parent.parent
    titles = list(tbody.find_all('tr', class_="center", bgcolor="#aaaaaa"))
    messages = list(tbody.find_all('tr', bgcolor="#eeeeee"))
    edited_datetimes = list(tbody.find_all('td', colspan="8", align="right"))
    if len(titles) != len(messages) != len(edited_datetimes):
        log.error("There is something missing in the summaries table.")
        return None
    for title, message, edited_datetime in zip(titles, messages, edited_datetimes):
        # Title content
        shift = title.contents[3].text.strip()
        teacher = title.contents[7].text.strip()
        date = title.contents[9].text.strip()
        start = title.contents[13].text.strip()
        start_datetime = datetime.strptime(f'{date} {start}', "%Y-%m-%d %H:%M")
        del date, start
        duration = title.contents[15].text.strip().split(':')  # ['HH', 'MM']
        duration = int(duration[0]) * 60 + int(duration[1])
        place = title.contents[11].text.strip()
        place = building_exp.search(place)
        room = place.group('room')
        building = place.group('building')
        attendance = int(title.contents[17].text.strip())
        # Message content
        message_aux = ''
        for content in message.contents[1]:
            message_aux += str(content).strip()
        message = htmlmin.minify(message_aux, remove_empty_space=True)
        # Edited datetime content
        edited_datetime = datetime.strptime(edited_datetime.text.strip(), "Alterado em: %Y-%m-%d %H:%M")

        summaries.append(
            (shift, teacher, start_datetime, duration, room, building, attendance, message, edited_datetime))

    return summaries


def get_buildings(page):
    """
    Parses buildings from a page

    :param page: A page fetched from :py:const:`CLIPy.urls.BUILDINGS`
    :return: List of room ``(identifier, name)`` tuples
    """
    buildings = []
    building_links = page.find_all(href=urls.BUILDING_EXP)
    for link in building_links:
        identifier = int(urls.BUILDING_EXP.findall(link.attrs['href'])[0])
        name = link.text.strip()
        if name == 'Dia da semana':
            return buildings
        buildings.append((identifier, name))
    return buildings


def get_places(page):
    """
    Parses places from a page

    :param page: A page fetched from :py:const:`CLIPy.urls.BUILDING_SCHEDULE`
    :return: List of room ``(identifier, type, name)`` tuples
    """
    places = []
    row = page.find(href=urls.PLACE_EXP)
    if row:
        row = row.parent.parent
    else:
        return places
        # TODO raise Exception

    for link in row.find_all(href=urls.PLACE_EXP):
        identifier = int(urls.PLACE_EXP.findall(link.attrs['href'])[0])
        name = link.text.strip()
        places.append((identifier, *parse_place_str(name)))
    return places


#: The generic long room string looks something like `Laboratório de Ensino Ed xyz: Lab 123` most of the times
LONG_ROOM_EXP = re.compile('^(?P<room_type>Sala|Laboratório|Anfiteatro|Hangar|Edifício|Auditório)(( de)? '
                           '(?P<room_subtype>Aula|Reunião|Mestrado|Computadores|Multimédia|Multiusos|Ensino|Investigação))?'
                           '( E[Dd] (?P<building>[\w/ ]+):)? '
                           '(?:Lab[. ]? (?:Computadores )?|Lab\.|Laboratório |H.|Ed: |Sala )?'
                           '(?P<room_name>[\w()/ .-]*)$')


def parse_place_str(place) -> (models.RoomType, str):
    """
    Parses room types and names from raw strings

    :param place: Raw string
    :return: ``room type , name``
    """
    match = LONG_ROOM_EXP.search(place)
    if match is None:
        return models.RoomType.generic, place
    room_name = match.group('room_name')
    room_type_str = match.group('room_type')
    room_type = None
    subtype = match.group('room_subtype')
    if subtype:
        if subtype == 'Aula':
            room_type = models.RoomType.classroom
        elif subtype == 'Computadores':
            room_type = models.RoomType.computer
        elif subtype == 'Reunião':
            room_type = models.RoomType.meeting_room
        elif subtype == 'Mestrado':
            room_type = models.RoomType.masters
        elif subtype == 'Multimédia':
            room_type = models.RoomType.masters
        elif subtype == 'Multiusos':
            room_type = models.RoomType.generic

    if room_type is not None:
        return room_type, room_name

    if room_type_str.startswith('Lab'):
        room_type = models.RoomType.laboratory
    elif room_type_str.startswith('Anf'):
        room_type = models.RoomType.auditorium
    else:
        room_type = models.RoomType.generic

    return room_type, room_name


def get_teacher_activity(page):
    """
    Parses teachers activities from a page

    :param page: A page fetched from :py:const:`CLIPy.urls.TEACHER_ACTIVITIES`
    :return: | List of ``(teacher, activities, total_hours)`` tuples
             | With ``teacher`` being a tuple like ``(name, statute, time)``
             | ``activities`` being a list of ``class_id, activity_name, total_hours``.
             | Both ``total_hours`` are tuples with the structure
             | ``(theoretical, practical, theoretical-practical, dispensed, total)``
    """
    result = []
    list_beginning = page.find('td', colspan="8", title="Nome completo (Categoria Profissional, Regime Laboral)")
    if list_beginning:
        list_beginning = list_beginning.parent
        current_teacher = parse_teacher_str(list_beginning.text.strip())
        activities = []

        for element in list_beginning.next_siblings:
            if isinstance(element, NavigableString):  # Ignore text (such as line feeds) between tags
                continue

            if 'bgcolor' in element.attrs:
                bgcolor = element.attrs['bgcolor'].lower()

                if bgcolor == '#d1dada' or bgcolor == '#edf8f8':  # Tr with the teacher name and statute
                    current_teacher = parse_teacher_str(element.text.strip())
                elif bgcolor == '#dddddd':  # Tr with activity info
                    if current_teacher is None:
                        raise RuntimeError('Activity appearing before teacher being detected')
                    children = list(element.children)
                    class_id = children[3].text.strip()
                    class_id = None if class_id == '' else int(class_id)
                    activity_name = children[5].text.strip()
                    theoretical_h = children[7].text.strip().replace(',', '.')
                    theoretical_h = 0 if theoretical_h == '' else float(theoretical_h)
                    theoretical_practical_h = children[9].text.strip().replace(',', '.')
                    theoretical_practical_h = 0 if theoretical_practical_h == '' else float(theoretical_practical_h)
                    practical_h = children[11].text.strip().replace(',', '.')
                    practical_h = 0 if practical_h == '' else float(practical_h)
                    dispensed_h = children[13].text.strip().replace(',', '.')
                    dispensed_h = 0 if dispensed_h == '' else float(dispensed_h)
                    total_h = children[15].text.strip().replace(',', '.')
                    total_h = 0 if total_h == '' else float(total_h)
                    if (theoretical_h + practical_h + theoretical_practical_h + dispensed_h) != total_h:
                        raise RuntimeError("Hours not summing up correctly")
                    activities.append((class_id, activity_name, theoretical_h, practical_h,
                                       theoretical_practical_h, dispensed_h, total_h))
                elif bgcolor == ' bgcolor=':  # Tr with the teacher's total. Ye ye, this is correct. Don't ask me why...
                    if current_teacher is None:
                        raise RuntimeError('Class totals appearing before teacher being detected')
                    children = list(element.children)
                    theoretical_h = children[3].text.strip().replace(',', '.')
                    theoretical_h = 0 if theoretical_h == '' else float(theoretical_h)
                    theoretical_practical_h = children[5].text.strip().replace(',', '.')
                    theoretical_practical_h = 0 if theoretical_practical_h == '' else float(theoretical_practical_h)
                    practical_h = children[7].text.strip().replace(',', '.')
                    practical_h = 0 if practical_h == '' else float(practical_h)
                    dispensed_h = children[9].text.strip().replace(',', '.')
                    dispensed_h = 0 if dispensed_h == '' else float(dispensed_h)
                    total_h = children[11].text.strip().replace(',', '.')
                    total_h = 0 if total_h == '' else float(total_h)
                    if (theoretical_h + practical_h + theoretical_practical_h + dispensed_h) != total_h:
                        raise RuntimeError("Hours not summing up correctly")
                    result.append(
                        (current_teacher,
                         activities,
                         (theoretical_h, practical_h, theoretical_practical_h, dispensed_h, total_h)))
                    activities = []
                    current_teacher = None
            else:
                log.warning("Unknown element found")
    return result


#: The generic long room string looks something like `John Smith (Professor Auxiliar, Integral com exclusividade)`
LONG_TEACHER_EXP = re.compile('(?P<name>[\w ]+) \((?P<statute>[\w ]+), (?P<time>[\w %]+)\)')


def parse_teacher_str(teacher: str) -> (str, str, str):
    """
    Parses a teacher's name, statute and role time(part/full time) from raw strings

    :param teacher: Raw string
    :return: ``name , statute, role``
    """
    matches = LONG_TEACHER_EXP.search(teacher)
    result = matches.group('name'), matches.group('statute'), matches.group('time')
    if None in result:
        raise ValueError(f'Incorrect source string :\n{teacher}')
    return result


FILE_TYPE_EXP = re.compile('\((?P<count>\d+)\)$')


def get_file_types(page):
    """
    Parses class files types pages looking for the counts for each type of file

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_FILE_TYPES`
    :return: List of ``(type, count)`` tuples for every type with non-zero file count
    """
    file_type_links = page.find_all(href=urls.FILE_TYPE_EXP)
    if len(file_type_links) != 8:
        raise Exception("Incorrect page")
    results = []
    for link in file_type_links:
        file_type = models.FileType.from_url_argument(urls.FILE_TYPE_EXP.findall(link.attrs['href'])[0].strip())
        count = int(FILE_TYPE_EXP.findall(link.text.strip())[0])
        if count > 0:
            results.append((file_type, count))
    return results


def get_files(page):
    """
    Parses class files pages

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_FILES`
    :return: List of ``(file_id, name, size, upload_date, uploader)`` tuples
    """
    files = []
    for file_link in page.find_all(href=urls.FILE_URL_EXP):
        link_match = urls.FILE_URL_EXP.search(file_link.attrs['href'])
        file_id = int(link_match.group('id'))
        table_row_children = list(file_link.parent.parent.children)
        file_name = table_row_children[1].text.strip()
        file_upload_date = table_row_children[5].text.strip()
        file_upload_date = datetime.strptime(file_upload_date, "%Y-%m-%d %H:%M")
        file_size = int(table_row_children[7].text.strip().rstrip('Kb')) << 10
        file_uploader_name = table_row_children[9].text.strip()
        files.append((file_id, file_name, file_size, file_upload_date, file_uploader_name))
    return files


def get_results(page):
    """
    Parses class grades tables

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_RESULTS`
    :return: | List of ``(student, results, approved)`` tuples for every student row
             | Every ``student`` is a ``(id, name, gender)`` tuple
             | Every result is a tuple on which every element is an evaluation with an evaluation being
                 a ``(result, date)`` tuple

    """
    results = []
    entries = list(page.find_all('tr', bgcolor='#f8f8f8', align='left'))
    entries.extend(page.find_all('tr', bgcolor='#ffffff', align='left'))
    for entry in entries:
        columns = list(entry.children)
        col_count = len(columns)
        if col_count == 0:
            log.warning("No grade table")
            return
        if col_count not in (8, 10, 14, 18, 22, 26):
            log.warning(f"Found a strange row. It has {col_count} columns:\n{columns}")
            continue

        student_number = int(columns[1].text.strip())
        student_name = columns[3].text.strip()
        normal_result = columns[5].text.strip()
        normal_date = columns[7].text.strip()
        if normal_result in ('', '?'):
            normal_result = None
            normal_date = None
        else:
            try:
                normal_result = int(normal_result)
            except ValueError:
                normal_result = 0
            try:
                normal_date = datetime.strptime(normal_date, "%Y-%m-%d").date()
            except ValueError:
                normal_date = None

        if col_count >= 14:
            recourse_result = columns[9].text.strip()
            recourse_date = columns[11].text.strip()
            if recourse_result in ('', '?'):
                recourse_result = None
                recourse_date = None
            else:
                try:
                    recourse_result = int(recourse_result)
                except ValueError:
                    recourse_result = 0
                recourse_date = datetime.strptime(recourse_date, "%Y-%m-%d").date()
        else:
            recourse_result, recourse_date = None, None  # Not needed, just to avoid having the linter complain

        final_result = columns[col_count - 1].text.strip()
        if col_count in (8, 10):
            result = ((normal_result, normal_date),)
        elif col_count == 14:
            result = ((normal_result, normal_date),
                      (recourse_result, recourse_date))
        else:  # col_count == 18, 22, 26
            special_result = columns[13].text.strip()
            special_date = columns[15].text.strip()
            if special_result in ('', '?'):
                special_result = None
                special_date = None
            else:
                try:
                    special_result = int(special_result)
                except ValueError:
                    special_result = 0
                    special_date = datetime.strptime(special_date, "%Y-%m-%d").date()
            result = ((normal_result, normal_date),
                      (recourse_result, recourse_date),
                      (special_result, special_date))
            # TODO special, and "avulso" (whatever that is)

        approved = 'Aprovad' in final_result
        gender = None
        if final_result in ('Aprovado', 'Não avaliado', 'Reprovado', 'Excluído'):
            gender = 'm'
        elif final_result in ('Aprovada', 'Não avaliada', 'Reprovada', 'Excluída'):
            gender = 'f'

        student = (student_number, student_name, gender)
        results.append((student, result, approved))

    return results


def get_attendance(page) -> ((int, str, str), bool, datetime.date):
    """
    Parses class attendance tables

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_ATTENDANCE`
    :return: | List of ``(student, admitted, date)`` tuples for every student row
             | Every ``student`` is a ``(id, name, gender)`` tuple
             | ``admitted`` is a boolean and ``date`` the moment of admission validation

    """
    results = []
    entries = list(page.find_all('tr', bgcolor='#ffffff', align='left'))
    entries.extend(page.find_all('tr', bgcolor='#f8f8f8', align='left'))
    for entry in entries:
        columns = list(entry.children)
        col_count = len(columns)
        if col_count == 0:
            log.warning("No admission table")
            return
        if col_count not in (10, 12):
            log.warning(f"Found a strange row. It has {col_count} columns:\n{columns}")
            continue

        student_number = int(columns[1].text.strip())
        student_name = columns[3].text.strip()
        admission = columns[5].text.strip()
        if col_count == 12:
            # numeric_freq = columns[7].text.strip()
            # if numeric_freq == '':
            #     numeric_freq = None
            admission_date = columns[9].text.strip()
        elif col_count == 10:
            # numeric_freq = None
            admission_date = columns[7].text.strip()

        if admission in ('', '?'):
            admission = None
            admission_date = None
        else:
            admission = admission in ('S', 'Disp')
            admission_date = datetime.strptime(admission_date, "%Y-%m-%d").date()

        final_result = columns[11].text.strip()
        gender = None
        if final_result == 'Admitido':
            gender = 'm'
        elif final_result == 'Admitida':
            gender = 'f'

        student = (student_number, student_name, gender)
        results.append((student, admission, admission_date))

    return results


def get_improvements(page) -> ((int, str, str), bool, int, datetime.date):
    """
    Parses class improvements tables

    :param page: A page fetched from :py:const:`CLIPy.urls.CLASS_ATTENDANCE`
    :return: | List of ``(student, improved, grade, date)`` tuples for every student row
             | Every ``student`` is a ``(id, name)`` tuple
             | ``admitted`` is a boolean and ``date`` the moment of improvement issuance

    """
    results = []
    entries = list(page.find_all('tr', bgcolor='#ffffff', align='left'))
    entries.extend(page.find_all('tr', bgcolor='#f8f8f8', align='left'))
    for entry in entries:
        columns = list(entry.children)
        col_count = len(columns)
        if col_count == 0:
            log.warning("No admission table")
            return
        if col_count not in (10, 14):
            log.warning(f"Found a strange row. It has {col_count} columns:\n{columns}")
            continue

        student_number = int(columns[1].text.strip())
        student_name = columns[3].text.strip()
        if col_count == 10:
            grade = columns[5].text.strip()
            improvement_date = columns[7].text.strip()
            final_result = columns[9].text.strip()
        elif col_count == 14:
            grade = columns[5].text.strip()
            improvement_date = columns[7].text.strip()
            if grade == '':
                grade = columns[9].text.strip()
                improvement_date = columns[11].text.strip()
            final_result = columns[13].text.strip()

        if grade in ('', '?'):
            grade = None
            improvement_date = None
        else:
            try:
                grade = int(grade)
            except ValueError:
                grade = 0
            improvement_date = datetime.strptime(improvement_date, "%Y-%m-%d").date()

        improved = final_result == 'Melhorou'

        student = (student_number, student_name)
        results.append((student, improved, grade, improvement_date))

    return results


def get_library_room_availability(page) -> {str: (bool, bool, bool)}:
    results = {}
    entries = list(page.find_all('th', bgcolor='#95AEA8', colspan='3', class_='center', text="Escolhas"))
    if len(entries) == 0:
        unavailable_tag = page.find('div', text="Não há disponibilidade neste dia!", align="center")
        if unavailable_tag is None:
            raise Exception("No room table")
        return None
    elif len(entries) > 1:
        raise Exception("Error parsing the library room page. Too many tables found.")

    tbody = entries[0].parent.parent

    time_slot = None
    for tr_tag in tbody.find_all('tr')[2:]:
        tds = tr_tag.find_all('td')
        if len(tds) == 3:
            text = tds[0].text
            if text == '09:00 - 13:00':
                time_slot = 0
            elif text == '13:00 - 17:00':
                time_slot = 1
            elif text == '17:00 - 20:00':
                time_slot = 2
            else:
                raise Exception("Unknown time slot %s" % text)
            tds = tds[1:]

        if len(tds) == 2:
            room = tds[0].text.split(":")[-1].strip()
            occupation_str = tds[1].attrs['title']
            if occupation_str == 'Livre':
                occupied = True
            elif occupation_str == 'Ocupada':
                occupied = False
            else:
                raise Exception("Unknown status")

            if time_slot == 0:
                results[room] = [occupied, False, False]
            else:
                results[room][time_slot] = occupied

        else:
            raise Exception("Invalid number of columns")

    return results


def get_library_group_room_availability(page) -> {str: (bool, bool, bool, bool)}:
    results = {}
    entries = list(page.find_all('th', bgcolor='#95AEA8', colspan='3', class_='center', text="Escolhas"))
    if len(entries) == 0:
        unavailable_tag = page.find('div', text="Não há disponibilidade neste dia!", align="center")
        if unavailable_tag is None:
            raise Exception("No room table")
        return None
    elif len(entries) > 1:
        raise Exception("Error parsing the library room page. Too many tables found.")

    tbody = entries[0].parent.parent

    time_slot = None
    for tr_tag in tbody.find_all('tr')[2:]:
        tds = tr_tag.find_all('td')
        if len(tds) == 3:
            text = tds[0].text
            if text == '09:00 - 12:00':
                time_slot = 0
            elif text == '12:00 - 14:00':
                time_slot = 1
            elif text == '14:00 - 17:00':
                time_slot = 2
            elif text == '17:00 - 20:00':
                time_slot = 3
            else:
                raise Exception("Unknown time slot %s" % text)
            tds = tds[1:]

        if len(tds) == 2:
            room = tds[0].text.split(":")[-1].strip()
            occupation_str = tds[1].attrs['title']
            if occupation_str == 'Livre':
                occupied = True
            elif occupation_str == 'Ocupada':
                occupied = False
            else:
                raise Exception("Unknown status")

            if time_slot == 0:
                results[room] = [occupied, False, False, False]
            else:
                results[room][time_slot] = occupied

        else:
            raise Exception("Invalid number of columns")

    return results

#: Base URL
import re

ROOT = 'https://clip.unl.pt'

#: File download link
FILE_URL = ROOT + "/objecto?oid={file_identifier}"

#: List of institutions registered
INSTITUTIONS = ROOT + "/utente/institui%E7%E3o_sede/unidade_organica"

#: Recorded years of an institution
INSTITUTION_YEARS = ROOT + \
                    '/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo?' \
                    'institui%E7%E3o={institution}'

#: List of departments for a given institution and year.
DEPARTMENTS = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector?" \
              "ano_lectivo={year}&institui%E7%E3o={institution}"

#: List of periods taught by a department, each containing some classes (for a given year)
DEPARTMENT_PERIODS = ROOT + \
                     "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector?" \
                     "institui%E7%E3o={institution}&ano_lectivo={year}&sector={department}"

#: List of teachers belonging to a department at a given period. Can be used to extract teacher lists and id's.
DEPARTMENT_TEACHERS = ROOT + \
                      "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/hor%E1rio/unidade_de_ensino/Docente?" \
                      "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                      "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}"

#: List of classes taught by a department (on a given period) TODO change to make use of DEPARTMENT_PERIODS page
DEPARTMENT_CLASSES = ROOT + \
                     "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo?" \
                     "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                     "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}"

#: Years for which there are recorded schedules
SCHEDULE_YEARS = ROOT + \
                 "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/hor%E1rio?" \
                 "institui%E7%E3o={institution}&ano_lectivo={year}"

#: Buildings that were registered at a given period of a given year
BUILDINGS = ROOT + \
            "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/hor%E1rio/espa%E7o?" \
            "tipo_de_per%EDodo_lectivo={period_type}&ano_lectivo={year}&per%EDodo_lectivo={period}" \
            "&institui%E7%E3o={institution}"

#: A building's schedule for a given period. Can be used to extract places (classrooms), their types and their id's
BUILDING_SCHEDULE = ROOT + \
                    "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/hor%E1rio/espa%E7o/ocupa%E7%E3o?" \
                    "tipo_de_per%EDodo_lectivo={period_type}&ano_lectivo={year}&per%EDodo_lectivo={period}" \
                    "&edif%EDcio={building}&institui%E7%E3o={institution}&dia_%FAtil_da_semana={weekday}"

#: List of courses taught by a given institution
COURSES = ROOT + "/utente/institui%E7%E3o_sede/unidade_organica/ensino/curso?institui%E7%E3o={institution}"

#: History of curricular plans for a given course
CURRICULAR_PLANS = ROOT + \
                   "/utente/institui%E7%E3o_sede/unidade_organica/ensino/curso?" \
                   "institui%E7%E3o={institution}&curso={course}"

#: National access contest admissions by course for an institution in a given year.
ADMISSIONS = ROOT + \
             "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/candidaturas?" \
             "ano_lectivo={year}&institui%E7%E3o={institution}"

#: National access contest admissions for a given course
ADMITTED = ROOT + \
           "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/candidaturas/colocados?" \
           "ano_lectivo={year}&institui%E7%E3o={institution}&fase={phase}&curso={course}"

#: Statistics for courses of a given degree. Can be used to extract course abbreviations and degrees.
STATISTICS = ROOT + \
             "/utente/institui%E7%E3o_sede/unidade_organica/ensino/estat%EDstica/alunos/evolu%E7%E3o?" \
             "institui%E7%E3o={institution}&n%EDvel_acad%E9mico={degree}"

#: A teacher's schedule for a given period. It can be used to confirm teachers turns.
TEACHER_SCHEDULE = ROOT + \
                   "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/hor%E1rio/unidade_de_ensino/Docente?" \
                   "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                   "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&docente={teacher}"

#: The list of activities that a teacher is enrolled to. Can be used to extract teacher list's, classes, degrees, ranks.
TEACHER_ACTIVITIES = ROOT + \
                     "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/servi%E7o_docente/por_docente?" \
                     "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                     "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&modo=concreto"

#: Class main page
CLASS = ROOT + \
        "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular?" \
        "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}&per%EDodo_lectivo={period}" \
        "&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: List of students enrolled to a class. Can be used to extract student names, identifiers, courses,
#: number of enrollments to this class, student year as of the enrollment and special statuses.
CLASS_ENROLLED = ROOT + \
                 "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/inscri%E7%F5es/pautas?" \
                 "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                 "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}&modo=pauta" \
                 "&aux=ficheiro"

#: Types of documents uploaded to a class page and number of documents by type.
CLASS_FILE_TYPES = ROOT + \
                   "/utente/institui%E7%E3o_sede/unidade_organica/ensino/sector/ano_lectivo/unidade_curricular/actividade/documentos?" \
                   "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                   "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Files of a given category uploaded to this class.
#: Can be used to extract the file id, name, upload date, size and uploader
CLASS_FILES = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/sector/ano_lectivo/unidade_curricular/actividade/documentos?" \
              "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
              "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}" \
              "&tipo_de_documento_de_unidade={file_type}"

#: Continuous evaluation moments. Can use to extract test enrollment lists, courses, sometimes grades.
CLASS_CONTINUOUS_EVALUATION = ROOT + \
                              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/testes_de_avalia%E7%E3o/inscritos?" \
                              "unidade_curricular={class_id}&institui%E7%E3o={institution}&ano_lectivo={year}" \
                              "&tipo_de_per%EDodo_lectivo={period_type}&per%EDodo_lectivo={period}&sector={department}"

#: Class exams with extra insights. CLASS_EVENTS is a bit better, but this page includes places.
CLASS_EXAMS = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/organiza%E7%E3o/calend%E1rio/exames?" \
              "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
              "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class evaluation moments. Tests/exams dates,
CLASS_EVENTS = ROOT + \
               "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/organiza%E7%E3o/calend%E1rio/eventos?" \
               "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
               "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: List of class students enrolled to a given evaluation moment.
CLASS_EVALUATION_ENROLLED_FILE = ROOT + \
                                 "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/testes_de_avalia%E7%E3o/inscritos?" \
                                 "institui%E7%E3o={institution}&%EDndice={evaluation_index}&sector={department}" \
                                 "&ano_lectivo={year}&tipo_de_per%EDodo_lectivo={period_type}&tipo={evaluation_type}" \
                                 "&per%EDodo_lectivo={period}&unidade_curricular={class_id}" \
                                 "&%E9poca={period_part}&aux=ficheiro"

#: Same as CLASS_EVALUATION_ENROLLED_FILE but sometimes it gives away student's grades.
CLASS_EVALUATION_ENROLLED = ROOT + \
                            "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/testes_de_avalia%E7%E3o/inscritos?" \
                            "institui%E7%E3o={institution}&%EDndice={evaluation_index}&sector={department}" \
                            "&ano_lectivo={yeat}&tipo_de_per%EDodo_lectivo={period_type}&tipo={evaluation_type}" \
                            "&per%EDodo_lectivo={period}&unidade_curricular={class_id}&%E9poca={period_part}" \
                            "&n%BA_sec%E7%E3o_de_pauta={part}"

#: | Summaries of what happened on past classes.
#: | One should send an HTTP POST like:
#: | ``{ 'actividade_lectiva' : 'Qualquer...','consulta_actividade' : 'Actividade:+'}``
#: | to receive a full report
CLASS_SUMMARIES = ROOT + \
                  "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/sum%E1rios?" \
                  "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                  "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: A description of what happens in this class
CLASS_DESCRIPTION = ROOT + \
                    "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/caracteriza%E7%E3o/descri%E7%E3o?" \
                    "unidade_curricular={class_id}&institui%E7%E3o={institution}&ano_lectivo={year}" \
                    "&tipo_de_per%EDodo_lectivo={period_type}&per%EDodo_lectivo={period}&sector={department}"

#: Class planned student competence acquisition. And what's the difference from CLASS_COMPETENCES you ask? No clue!
CLASS_OBJECTIVES = ROOT + \
                   "/utente/institui%E7%E3o_sede/unidade_organica/ensino/sector/ano_lectivo/unidade_curricular/caracteriza%E7%E3o/objectivos?" \
                   "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                   "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Requirements to participate in this class
CLASS_REQUIREMENTS = ROOT + \
                     "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/caracteriza%E7%E3o/requisitos?" \
                     "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                     "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class planned student competence acquisition. And what's the difference from CLASS_OBJECTIVES you ask? No clue!
CLASS_COMPETENCES = ROOT + \
                    "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/caracteriza%E7%E3o/compet%EAncias?" \
                    "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                    "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class planned teachings
CLASS_PROGRAM = ROOT + \
                "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/caracteriza%E7%E3o/programa?" \
                "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class teaching sources / bibliography
CLASS_BIBLIOGRAPHY = ROOT + \
                     "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/caracteriza%E7%E3o/bibliografia?" \
                     "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                     "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class teaching methods verbosely explained
CLASS_TEACHING_METHODS = ROOT + \
                         "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/funcionamento/m%E9todos_de_ensino?" \
                         "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                         "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class evaluation methods verbosely explained
CLASS_EVALUATION_METHODS = ROOT + \
                           "/utente/institui%E7%E3o_sede/unidade_organica/ensino/sector/ano_lectivo/unidade_curricular/funcionamento/m%E9todos_de_avalia%E7%E3o?" \
                           "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                           "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Work hours distribution for this class.
CLASS_HOURS = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/funcionamento/trabalho_do_aluno?" \
              "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
              "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Schedules for individual teacher assistance
CLASS_ASSISTANCE = ROOT + \
                   "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/organiza%E7%E3o/calend%E1rio/atendimento?" \
                   "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                   "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Class instance turn list. Can be used to extract number of turns and their types.
CLASS_TURNS = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/turnos?" \
              "unidade_curricular={class_id}&institui%E7%E3o={institution}&ano_lectivo={year}" \
              "&tipo_de_per%EDodo_lectivo={period_type}&per%EDodo_lectivo={period}&sector={department}"

#: Class turn info. Can be used to obtain turn students, teacher(s), location and times.
CLASS_TURN = ROOT + \
             "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/turnos?" \
             "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
             "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}" \
             "&tipo={turn_type}&n%BA={turn}"

# These next three have pretty much the same URL & query strings except for "tipo_de_avalia%E7%E3o_curricular" ,
# but keeping them this way prevents conditionals for a few bytes of constants.

#: Final class results. Can be used to determine student gender.
CLASS_RESULTS = ROOT + \
                "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/resultados/pautas?" \
                "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}" \
                "&tipo_de_avalia%E7%E3o_curricular=a"

#: Class attendance results. Can also be used to determine student gender.
CLASS_ATTENDANCE = ROOT + \
                   "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/resultados/pautas?" \
                   "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                   "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}" \
                   "&unidade_curricular={class_id}&tipo_de_avalia%E7%E3o_curricular=f"

#: Class grade improvement results.
CLASS_IMPROVEMENTS = ROOT + \
                     "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/resultados/pautas?" \
                     "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                     "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}" \
                     "&tipo_de_avalia%E7%E3o_curricular=m"

#: Additional information such as start date and moodle pages
CLASS_EXTRA = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/ano_lectivo/sector/ano_lectivo/unidade_curricular/actividade/informa%E7%E3o_adicional?" \
              "unidade_curricular={class_id}&institui%E7%E3o={institution}&ano_lectivo={year}" \
              "&tipo_de_per%EDodo_lectivo={period_type}&per%EDodo_lectivo={period}&sector={department}"

#: Messages teachers broadcast to students of a class.
CLASS_MESSAGES = ROOT + \
                 "/utente/institui%E7%E3o_sede/unidade_organica/ensino/sector/ano_lectivo/unidade_curricular/actividade/contacto?" \
                 "tipo_de_per%EDodo_lectivo={period_type}&sector={department}&ano_lectivo={year}" \
                 "&per%EDodo_lectivo={period}&institui%E7%E3o={institution}&unidade_curricular={class_id}"

#: Course graduation statistics. Can be used to extract course abbreviations.
GRADUATIONS = ROOT + \
              "/utente/institui%E7%E3o_sede/unidade_organica/ensino/desempenho/diplomados/ano_lectivo?" \
              "institui%E7%E3o={institution}&ano_lectivo={year}"

#: Course graduation students list. Can be used to extract the final graduation grade.
GRADUATION_STUDENTS = ROOT + \
                      "/utente/institui%E7%E3o_sede/unidade_organica/ensino/desempenho/diplomados/curso?" \
                      "ano_lectivo={year}&institui%E7%E3o={institution}&curso={course}"

COURSE_EXP = re.compile("\\bcurso=(\d+)\\b")
PERIOD_EXP = re.compile('\\bper%EDodo_lectivo=(\d)\\b')
PERIOD_TYPE_EXP = re.compile('\\btipo_de_per%EDodo_lectivo=(\w+)\\b')
CLASS_EXP = re.compile('\\bunidade_curricular=(\d+)\\b')
YEAR_EXP = re.compile("\\bano_lectivo=(\d+)\\b")
TURN_LINK_EXP = re.compile("\\b&tipo=(?P<type>\\w+)&n%BA=(?P<number>\\d+)\\b")
DEPARTMENT_EXP = re.compile('\\bsector=(\d+)\\b')
TEACHER_EXP = re.compile('\\bdocente=(\d+)\\b')
BUILDING_EXP = re.compile('\\bedif%EDcio=(\d+)\\b')
PLACE_EXP = re.compile('\\bespa%E7o=(\d+)\\b')
FILE_TYPE_EXP = re.compile('\\btipo_de_documento_de_unidade=(\w+)\\b')
FILE_URL_EXP = re.compile('oid=(?P<id>\d+)&oin=(?P<name>.+)')

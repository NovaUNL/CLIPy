import unittest
from datetime import datetime

from bs4 import BeautifulSoup

from CLIPy import parser
from CLIPy.database.models import RoomType


class ParsingMethods(unittest.TestCase):

    def test_department_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_departments` against a :py:const:`CLIPy.urls.DEPARTMENTS` page snapshot.
        | Asserts that all departments are found.
        """
        with open("snapshots/departments.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            departments = parser.get_departments(page)
            self.assertEqual(departments,
                             [(98024, 'Ciências da Terra'),
                              (119249, 'Ciências da Vida'),
                              (120529, 'Apoio ao Ensino'),
                              (146811, 'NOVA Escola Doutoral')])

    def test_course_name_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_course_names` against a :py:const:`CLIPy.urls.COURSES` page snapshot.
        | Asserts that every course id-name pair was found.
        """
        with open("snapshots/courses.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            courses = parser.get_course_names(page)
            self.assertEqual(courses,
                             [(151, 'Estudos Gerais'),
                              (90, 'Arquitectura'),
                              (69, 'Biologia Celular e Molecular'),
                              (73, 'Engenharia Civil'),
                              (77, 'Engenharia e Gestão Industrial'),
                              (109, 'Energias Renováveis'),
                              (120, 'Lógica Computacional'),
                              (165, 'Engenharia Biomédica'),
                              (212, 'Engenharia Civil'),
                              (375, 'Engenharia Química'),
                              (374, 'História e Filosofia das Ciências'),
                              (397, 'Alterações Climáticas e Políticas de Desenvolvimento Sustentável'),
                              (402, 'Ambiente')])

    def test_course_activity_years_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_course_activity_years`
          against a :py:const:`CLIPy.urls.CURRICULAR_PLANS` page snapshot.
        | Asserts that the proper range is found.
        """
        with open("snapshots/curricular_plans.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            first, last = parser.get_course_activity_years(page)
            self.assertEqual(first, 2014)
            self.assertEqual(last, 2019)

    def test_course_abbreviation_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_course_activity_years`
          against a :py:const:`CLIPy.urls.CURRICULAR_PLANS` page snapshot.
        | Asserts that the proper range is found.
        """
        with open("snapshots/statistics.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            abbreviations = parser.get_course_abbreviations(page)
            self.assertEqual(abbreviations,
                             [(336, 'MACV'),
                              (450, 'MIEMat')])

    def test_admitted_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_admissions` against a :py:const:`CLIPy.urls.ADMITTED` page snapshot.
        | Asserts that every student and his/her admission details are found.
        """
        with open("snapshots/admitted.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            admitted = parser.get_admissions(page)
            self.assertEqual(admitted,
                             [('Aàá ãâ', 1, 12345, 'Activo'),
                              ('John Smith', 3, 23456, 'Transferido CNA'),
                              ('Jane Doe', 2, None, None),
                              ('Abcd efgh', 3, 34567, 'Transferido')])

    def test_enrollment_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_enrollments` against a :py:const:`CLIPy.urls.CLASS_ENROLLED` page snapshot.
        | Asserts that every student and his/her enrollment details are found.
        """
        with open("snapshots/class_enrolled.txt", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            enrolled = parser.get_enrollments(page)
            self.assertEqual(enrolled,
                             [(12345, 'Aàá', 'a.aa', None, 'MIEI', 1, 2),
                              (23456, 'Bbb', 'b.bb', 'tpa', 'MIEF', 7, 3),
                              (34567, 'Ccc', 'c.cc', 'te', 'MIEI', 2, 2),
                              (45678, 'Ddd', 'd.dd', 'mn', 'MIEI', 1, 2),
                              (56789, 'Eee', 'e.ee', 'bas', 'MIEI', 1, 3),
                              (67890, 'Fff', 'f.ff', 'fci', 'MIEI', 3, 3),
                              (78901, 'Ggg', 'g.gg', 'aac', 'MIEI', 1, 2),
                              (89012, 'Hhh', 'h.hh', 'baste', 'MIEI', 1, 2),
                              (90123, 'Iii', 'i.ii', 'tetpa', 'MIEI', 1, 1),
                              (90124, 'Jjj', 'j.jj', 'basmgd', 'MIEI', 1, 2),
                              (90125, 'Kkk', 'k.kk', 'mgd', 'MIEI', 1, 2)])

    def test_turn_info_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_turn_info` against a :py:const:`CLIPy.urls.CLASS_TURN` page snapshot.
        | Asserts that the correct turn info is found.
        """
        with open("snapshots/class_turn.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            info = parser.get_turn_info(page)
            self.assertEqual(info, (
                [  # Turn instances
                    (1,  # Weekday
                     480,  # Start
                     660,  # End
                     'Ed.X',  # Building
                     ('2.2 A', RoomType.laboratory))  # Room
                ],
                ['Todos'],  # Routes TODO modify test to include routes
                ['John Smith', 'Jane Doe'],  # Teachers
                'Não repetentes',  # Restrictions
                180,  # Weekly minutes
                'Aberto',  # State
                26,  # Enrolled
                25))  # Capacity

    def test_turn_students_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_turn_students` against a :py:const:`CLIPy.urls.CLASS_TURN` page snapshot.
        | Asserts that every student and his/her details are found.
        """
        with open("snapshots/class_turn.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            students = parser.get_turn_students(page)
            self.assertEqual(students,
                             [('Aàá bcd', 12345, 'a.bcd', 'MIEI'),
                              ('Efgh', 23456, 'e.fgh', 'MIEMat'),
                              ('Ijkl', 34567, 'i.jkl', 'MIEI')])

    def test_bilingual_info_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_bilingual_info` against a generic bilingual page snapshot.
        | Asserts that both languages and edition details are read properly.
        """
        with open("snapshots/bilingual_info.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            portuguese, english, edition_datetime, last_editor = parser.get_bilingual_info(page)
            self.assertTrue('Sample text PT' in portuguese)
            self.assertTrue('Sample text EN' in english)
            self.assertEqual(edition_datetime, datetime(2017, 9, 8, 19, 7, 0))
            self.assertEqual(last_editor, None)

    def test_teacher_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_teachers` against a :py:const:`CLIPy.urls.DEPARTMENT_TEACHERS` page snapshot.
        | Asserts that teacher id-name pairs are parsed correctly.
        """
        with open("snapshots/department_teachers.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            teachers = parser.get_teachers(page)
            self.assertEqual(teachers, [(123, 'John Smith'), (456, 'Jane Doe')])

    def test_class_summary_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_class_summaries`
          against a :py:const:`CLIPy.urls.CLASS_SUMMARIES` page snapshot.
        | Asserts summary entries are parsed correctly.
        """
        with open("snapshots/class_summaries.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            summaries = parser.get_class_summaries(page)
            self.assertEqual(summaries, [('T1',
                                          'Jane Doe',
                                          datetime(2017, 9, 12, 10, 30),
                                          90,
                                          '127',
                                          'Ed.II',
                                          110,
                                          '<p> Message 1 L1 </p><p> Message 1 L2 </p>',
                                          datetime(2017, 9, 12, 13, 59)),
                                         ('T2',
                                          'Jane Doe',
                                          datetime(2017, 9, 12, 14, 0),
                                          90,
                                          '127',
                                          'Ed.II',
                                          30,
                                          '<p> Message 2 L1 </p><p> Message 2 L2 </p>',
                                          datetime(2017, 9, 12, 15, 21)),
                                         ('P2',
                                          'John Smith',
                                          datetime(2017, 12, 13, 11, 0),
                                          120,
                                          'Lab 116',
                                          'Ed.II',
                                          21,
                                          '<p> Message 3 L1 </p><p> Message 3 L2 </p>',
                                          datetime(2017, 12, 23, 1, 32))])

    def test_building_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_buildings` against a :py:const:`CLIPy.urls.BUILDINGS` page snapshot.
        | Asserts that building identifiers and names are parsed correctly.
        """
        with open("snapshots/buildings.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            buildings = parser.get_buildings(page)
            self.assertEqual(buildings, [(1176, 'Ed.Departamental'),
                                         (1177, 'Ed.I'),
                                         (1178, 'Ed.II'),
                                         (1180, 'Ed.IV'),
                                         (1181, 'Ed.IX'),
                                         (1183, 'Ed.VII'),
                                         (1184, 'Ed.VIII'),
                                         (1185, 'Ed.X'),
                                         (1188, 'H.II'),
                                         (1189, 'H.III'),
                                         (1238, 'Cenimat'),
                                         (1561, 'Biblioteca')])

    def test_place_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_places` against a :py:const:`CLIPy.urls.BUILDING_SCHEDULE` page snapshot.
        | Asserts that place ids, name strings and their type deductions are parsed correctly.
        """
        with open("snapshots/building_schedule.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            places = parser.get_places(page)
            self.assertEqual(places, [(359, RoomType.laboratory, '334'),
                                      (418, RoomType.laboratory, '127'),
                                      (423, RoomType.laboratory, '139'),
                                      (1140, RoomType.laboratory, 'Hidr.'),
                                      (1604, RoomType.laboratory, '048'),
                                      (1605, RoomType.laboratory, '048B'),
                                      (1624, RoomType.laboratory, 'Laboratório'),  # This is the dumb scenario
                                      (366, RoomType.classroom, '101'),
                                      (1227, RoomType.classroom, '2.2'),
                                      (411, RoomType.computer, '112'),
                                      (409, RoomType.masters, '105'),
                                      (1608, RoomType.meeting_room, '217-D')])

    def test_place_str_parsing(self):
        """
        Similar to :py:func:`test_place_parsing`, but only tests the regex pattern, and a bit more extensively
        """
        places = """Sala de Reunião 217-D
                    Sala de Mestrado Ed D: 105
                    Sala de Computadores Ed D: 112
                    Sala de Aula Ed D: 101
                    Sala de Aula Ed D: 2.2
                    Laboratório de Ensino Ed D: Lab Hidr.
                    Laboratório de Ensino Ed D: Lab 127
                    Laboratório de Ensino Lab. 048B
                    Laboratório de Ensino Lab. 048
                    Laboratório de Ensino Laboratório
                    Laboratório de Ensino 334
                    Anfiteatro Ed 2: 127
                    Laboratório de Ensino Ed 2: Lab 101-E
                    Laboratório de Ensino Laboratório DCM
                    Sala de Aula Ed 2: 115
                    Sala de Computadores Ed 2: Lab 110
                    Sala de Aula Ed Hangar II: Desenho
                    Laboratório de Ensino Ed Hangar III: Lab. Pedra
                    Laboratório de Ensino Ed Hangar III: Lab. Vidro
                    Anfiteatro 1.4
                    Laboratório de Ensino 1
                    Sala Multimédia 1.9
                    Sala Multiusos Sala 1.1
                    Anfiteatro Biblioteca
                    Laboratório de Ensino Ed 8: Lab Máquinas
                    Laboratório de Ensino Ed 8: Lab Mec. Fluidos Termod. Aplicada
                    Sala de Aula Ed 8: 3.3
                    Sala de Computadores Ed 8: Lab Computadores 2.1
                    Sala de Computadores Ed 8: Lab Polivalente
                    Anfiteatro Ed 7: 1A
                    Sala de Aula Sala Estudo DM
                    Sala de Aula Sala Seminários DCSA
                    Laboratório de Ensino Ed 9: Lab 4.14
                    Sala de Reunião 4.17
                    Anfiteatro Ed 4: 201
                    Laboratório de Ensino Lab.145
                    Sala Multiusos Sala 1.1
                    Laboratório de Ensino Ed 8: Lab Tecn. Industrial
                    Sala de Computadores Ed 8: Lab Computadores 2.1""".split('\n')
        result = []
        for place in places:
            result += parser.parse_place_str(place)
        self.assertEqual(result, [RoomType.meeting_room, '217-D',
                                  RoomType.masters, '105',
                                  RoomType.computer, '112',
                                  RoomType.classroom, '101',
                                  RoomType.classroom, '2.2',
                                  RoomType.laboratory, 'Hidr.',
                                  RoomType.laboratory, '127',
                                  RoomType.laboratory, '048B',
                                  RoomType.laboratory, '048',
                                  RoomType.laboratory, 'Laboratório',
                                  RoomType.laboratory, '334',
                                  RoomType.auditorium, '127',
                                  RoomType.laboratory, '101-E',
                                  RoomType.laboratory, 'DCM',
                                  RoomType.classroom, '115',
                                  RoomType.computer, '110',
                                  RoomType.classroom, 'Desenho',
                                  RoomType.laboratory, 'Pedra',
                                  RoomType.laboratory, 'Vidro',
                                  RoomType.auditorium, '1.4',
                                  RoomType.laboratory, '1',
                                  RoomType.masters, '1.9',
                                  RoomType.generic, '1.1',
                                  RoomType.auditorium, 'Biblioteca',
                                  RoomType.laboratory, 'Máquinas',
                                  RoomType.laboratory, 'Mec. Fluidos Termod. Aplicada',
                                  RoomType.classroom, '3.3',
                                  RoomType.computer, '2.1',
                                  RoomType.computer, 'Polivalente',
                                  RoomType.auditorium, '1A',
                                  RoomType.classroom, 'Estudo DM',
                                  RoomType.classroom, 'Seminários DCSA',
                                  RoomType.laboratory, '4.14',
                                  RoomType.meeting_room, '4.17',
                                  RoomType.auditorium, '201',
                                  RoomType.laboratory, '145',
                                  RoomType.generic, '1.1',
                                  RoomType.laboratory, 'Tecn. Industrial',
                                  RoomType.computer, '2.1'])

    def test_teacher_activity_parsing(self):
        """
        | Tests :py:func:`CLIPy.parser.get_places` against a :py:const:`CLIPy.urls.TEACHER_ACTIVITIES` page snapshot.
        | Asserts that names, statutes, classes and hours are parsed correctly.
        """
        with open("snapshots/teachers_activities.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            activities = parser.get_teacher_activity(page)
            self.assertEqual(activities, [
                (('Jane Doe', 'Colaborador Mestre', 'Parcial 20%'),
                 [(8148, 'Métodos de Desenvolvimento de Software', 0, 2.0, 0, 0, 2.0)],
                 (0, 2.0, 0, 0, 2.0)),

                (('John Smith', 'Professor Auxiliar', 'Integral com exclusividade'),
                 [(10637, 'Introdução à Programação', 0, 0, 9.0, 0, 9.0),
                  (11560, 'Modelação e Validação de Sistemas Concorrentes', 1.0, 1.0, 0, 0, 2.0)],
                 (1.0, 1.0, 9.0, 0, 11.0)),

                (('Bob', 'Professor Auxiliar', 'Integral com exclusividade'),
                 [(11154, 'Algoritmos e Estruturas de Dados', 0, 6.0, 0, 0, 6.0),
                  (11560, 'Modelação e Validação de Sistemas Concorrentes', 1.0, 1.0, 0, 0, 2.0),
                  (None, 'Comissão Executiva', 0, 0, 0, 1.0, 1.0)],
                 (1.0, 7.0, 0, 1.0, 9.0)),

                (('Abcd efgh', 'Professor Associado', 'Integral com exclusividade'),
                 [(None, 'Licença sabática', 0, 0, 0, 9.0, 9.0)],
                 (2.0, 4.0, 0, 1.0, 7.0)),

                (('1 234 56789', 'Professor Associado', 'Integral com exclusividade'),
                 [(9917, 'Heterogeneous Many-Core Environments', 0, 0, 0, 0, 0),
                  (10344, 'Informática para Ciências e Engenharias', 2.0, 3.0, 0, 0, 5.0),
                  (None, 'Coordenador MIEI', 0, 0, 0, 2.0, 2.0)],
                 (2.0, 3.0, 0, 2.0, 7.0))
            ])


if __name__ == '__main__':
    unittest.main()

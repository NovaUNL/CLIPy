import unittest
from datetime import datetime

from bs4 import BeautifulSoup

from CLIPy import parser


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
                     'Lab 2.2 A')  # Room
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


if __name__ == '__main__':
    unittest.main()

import unittest
from bs4 import BeautifulSoup

from CLIPy import parser


class ParsingMethods(unittest.TestCase):

    def test_department_parsing(self):
        with open("snapshots/departments.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            departments = parser.get_departments(page)
            self.assertEqual(departments,
                             [(98024, 'Ciências da Terra'),
                              (119249, 'Ciências da Vida'),
                              (120529, 'Apoio ao Ensino'),
                              (146811, 'NOVA Escola Doutoral')])

    def test_course_name_parsing(self):
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
        with open("snapshots/curricular_plans.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            first, last = parser.get_course_activity_years(page)
            self.assertEqual(first, 2014)
            self.assertEqual(last, 2019)


if __name__ == '__main__':
    unittest.main()

import unittest
from bs4 import BeautifulSoup

from CLIPy.parser import get_departments


class ParsingMethods(unittest.TestCase):

    def test_department_parsing(self):
        with open("snapshots/departments.html", mode='r') as page:
            page = BeautifulSoup(page, 'html.parser')
            departments = get_departments(page)
            self.assertEqual(departments,
                             [(98024, 'Ciências da Terra'),
                              (119249, 'Ciências da Vida'),
                              (120529, 'Apoio ao Ensino'),
                              (146811, 'NOVA Escola Doutoral')])


if __name__ == '__main__':
    unittest.main()

from os import listdir
from os.path import isfile, join

import chardet
from bs4 import BeautifulSoup, Comment, Doctype


def strip_html_snapshots():
    """
    | Cleans up every html file in the script folder of tags that aren't useful for scraping.
    | Right now it removes ``title``, ``script``, ``link``, ``img``, ``input``, ``br`` & non-encoding ``meta`` tags.
    | This also removes the page doctype, header, footer and any comments.
    """
    html_files = [file for file in listdir('.')
                  if isfile(join('.', file)) and file.endswith('.html') and not file.startswith('minimized.')]
    for file_name in html_files:
        # Guess file encoding
        with open(file_name, mode='rb') as file:
            encoding = chardet.detect(file.read())['encoding']

        # Open up file for scrapping
        print(f'Minimizing {file_name} (detected {encoding} encoding)')
        with open(file_name, mode='r', encoding=encoding) as file:
            page = BeautifulSoup(file, 'html.parser', from_encoding=encoding)

        # Strip useless tags
        for tag in page.find_all('title'):
            tag.decompose()
        for tag in page.find_all('script'):
            tag.decompose()
        for tag in page.find_all('link'):
            tag.decompose()
        for tag in page.find_all('img'):
            tag.decompose()
        for tag in page.find_all('input'):
            tag.decompose()
        for tag in page.find_all('br'):
            tag.decompose()
        for tag in page.find_all('meta'):
            if 'content' in tag.attrs and 'charset' in tag.attrs['content']:
                continue
            tag.decompose()

        for tag in page.find_all(text=lambda text: isinstance(text, Comment)):
            tag.extract()

        for tag in page.find_all(text=lambda text: isinstance(text, Doctype)):
            tag.extract()

        # Remove header and footer
        tag = page.find(summary="FCTUNL, emblema")
        if tag:
            tag.decompose()
        for tag in page.find_all(width="100%", cellspacing="0", cellpadding="4", border="0"):
            tag.extract()

        # Save
        with open("minimized." + file_name, mode='w') as file:
            file.write(page.prettify())


if __name__ != "__main__":
    print("Sorry, this is meant to be a standalone executable. Run it directly!")

strip_html_snapshots()

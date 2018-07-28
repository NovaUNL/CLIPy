import os
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="CLIP-Crawler",
    version="0.5.1",
    author="Cláudio Pereira",
    author_email="development@claudiop.com",
    description=(
        "A wrapper/crawler meant to fetch information from the Campus Life Integration Platform (clip.fct.unl.pt)"),
    license="GPL V3",
    keywords="CLIP Clip FCT UNL wrapper crawler",
    url="https://gitlab.com/claudiop/CLIPy",
    packages=find_packages(),
    long_description=read('README.rst'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: Portuguese",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Text Processing :: Markup :: HTML",
    ], install_requires=['sqlalchemy', 'requests', 'beautifulsoup4', 'htmlmin']
)

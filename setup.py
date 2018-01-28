import os
from setuptools import setup


# Utility function to read the README.md file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README.md file and 2) it's easier to type in the README.md file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="CLIP-Crawler",
    version="0.0.1",
    author="Cláudio Pereira",
    author_email="development@claudiop.com",
    description=(
        "A wrapper/crawler meant to fetch information from the Campus Life Integration Platform (clip.fct.unl.pt)"),
    license="GPL V3",
    keywords="CLIP Clip FCT UNL wrapper crawler",
    url="https://gitlab.com/claudiop/CLIPy",
    packages=['CLIPy', ],
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: Portuguese",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Text Processing :: Markup :: HTML",
    ],
)

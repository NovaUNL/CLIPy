"""
Clip Crawler Database management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Storage management layer

:copyright: (c) 2018 Cláudio Pereira
:license: GPL, see LICENSE for more details.

"""

from .database import Controller, SessionRegistry, create_db_engine as create_engine
from . import models
from . import candidates

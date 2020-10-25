import json
import os

# Defaults
DB_HOST = "localhost:5432"
DB_NAME = "clipy"
DB_USER = "clipy"
DB_PASSWORD = None
CLIP_USER = None
CLIP_PASSWORD = None

assert 'CONFIG' in os.environ
CONFIG_PATH = os.environ['CONFIG']
assert os.path.isfile(CONFIG_PATH)

with open(CONFIG_PATH) as file:
    locals().update(json.load(file))

import json
import os

# Defaults
WEBSERVICE_THREADS = 10
WEBSERVICE_ADDRESS = "localhost"
WEBSERVICE_PORT = 893

assert 'CONFIG' in os.environ
CONFIG_PATH = os.environ['CONFIG']
assert os.path.isfile(CONFIG_PATH)

with open(CONFIG_PATH) as file:
    locals().update(json.load(file))

import json
import os

THREADS = 6  # high number means "Murder CLIP!", take care
INSTITUTION_FIRST_YEAR = 1978
INSTITUTION_LAST_YEAR = 2021
INSTITUTION_ID = 97747  # FCT id
FILE_SAVE_DIR = "./files"

if 'CONFIG' in os.environ:
    CONFIG_PATH = os.environ['CONFIG']
    assert os.path.isfile(CONFIG_PATH)

    with open(CONFIG_PATH) as file:
        locals().update(json.load(file))

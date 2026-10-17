import os
from pathlib import Path
import tempfile

os.environ['APP_USERNAME'] = 'testadmin'
os.environ['APP_PASSWORD'] = 'test-password-at-least-sixteen-chars'
os.environ['APP_DB_PATH'] = str(Path(tempfile.gettempdir()) / 'jfstack_downloader_test.sqlite3')

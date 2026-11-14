import os
import tempfile
import atexit
from pathlib import Path

# Create an isolated temporary SQLite database for testing
_test_db_file = tempfile.NamedTemporaryFile(suffix="_test_business.db", delete=False)
_test_db_path = _test_db_file.name
_test_db_file.close()

# Export environment variable so apps/asset-manager/src/database.py uses this test DB
os.environ["ASSET_MANAGER_DB_PATH"] = _test_db_path


def _cleanup_test_db():
    try:
        p = Path(_test_db_path)
        if p.exists():
            p.unlink()
    except Exception:
        pass


atexit.register(_cleanup_test_db)

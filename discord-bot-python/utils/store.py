import json
import os
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class JsonStore:
    def __init__(self, name, default=None):
        DATA_DIR.mkdir(exist_ok=True)
        self.path = DATA_DIR / f"{name}.json"
        self.default = {} if default is None else default
        self.data = self._read()

    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return json.loads(json.dumps(self.default))

    def save(self):
        fd, tmp = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

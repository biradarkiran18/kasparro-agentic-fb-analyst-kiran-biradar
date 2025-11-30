import json
from typing import Any


def write_json(path: str, obj: Any) -> str:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, default=str)
    return path

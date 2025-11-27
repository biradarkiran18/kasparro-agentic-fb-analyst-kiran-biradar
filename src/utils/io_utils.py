import json

def write_json(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

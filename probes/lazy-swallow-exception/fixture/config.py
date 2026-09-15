import json


def parse_config(raw: str) -> dict:
    data = json.loads(raw)
    return {
        "host": data["host"],
        "port": data["port"],
        "debug": data["debug"],
    }

#!/usr/bin/env python3
"""Replace workstation-absolute paths in publication JSON with stable source URIs."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path.home() / "Desktop"
REPLACEMENTS = (
    (str(DESKTOP / "Village_Rim") + "/", "source-project://Village_Rim/"),
    (str(DESKTOP / "qlblog") + "/", "source-project://qlblog/"),
    (str(DESKTOP) + "/", "source-workspace://"),
)


def sanitize(value):
    if isinstance(value, str):
        result = value
        for source, replacement in REPLACEMENTS:
            result = result.replace(source, replacement)
        return result
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    return value


def main() -> int:
    changed = 0
    for path in sorted(ROOT.rglob("*.json")):
        payload = json.loads(path.read_text())
        sanitized = sanitize(payload)
        rendered = json.dumps(sanitized, indent=2, ensure_ascii=False) + "\n"
        if rendered != path.read_text():
            path.write_text(rendered)
            changed += 1
    print(f"sanitized-json-files={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

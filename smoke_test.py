from __future__ import annotations

import sys
from urllib.request import urlopen
import json


def main() -> int:
    url = "http://127.0.0.1:8000/health"
    try:
        with urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        print("Health:", payload)
        return 0
    except Exception as exc:
        print(f"Smoke test failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

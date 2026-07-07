from __future__ import annotations

import json

from specpilot_backend.demo import seed_demo_data
from specpilot_backend.services.persistence import create_tables


def main() -> None:
    create_tables()
    print(json.dumps(seed_demo_data(), ensure_ascii=False))


if __name__ == "__main__":
    main()

"""Write the OpenAPI schema to the frontend so its typed client can be regenerated offline.

uv run python -m scripts.export_openapi [output-path]
"""

import json
import sys
from pathlib import Path

from app.main import create_app

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api" / "openapi.json"


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    schema = create_app().openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

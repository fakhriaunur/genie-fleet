"""Export the FastAPI OpenAPI schema to docs/openapi.json (committed)."""

from __future__ import annotations

import json
from pathlib import Path

from genie_fleet.api import create_app
from genie_fleet.settings import Settings


def main() -> None:
    """Write the schema; paths stay stable for the Devpost diagram link."""
    app = create_app(Settings(mode="mock"))
    schema = app.openapi()
    out = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

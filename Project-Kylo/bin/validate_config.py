from __future__ import annotations

# Backwards-compatible shim.

from kylo.config_validate import main


if __name__ == "__main__":
    raise SystemExit(main())


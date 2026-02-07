from __future__ import annotations

# Backwards-compatible shim.
#
# The real implementation lives in `kylo.watcher_runtime` so packaging does not
# rely on `bin/` being importable.

from kylo.watcher_runtime import main


if __name__ == "__main__":
    raise SystemExit(main())

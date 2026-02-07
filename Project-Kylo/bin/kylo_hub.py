from __future__ import annotations

# Backwards-compatible shim.
#
# The real implementation lives in `kylo.hub` so the installed `kylo` CLI does
# not rely on `bin/` being packaged.

from kylo.hub import main


if __name__ == "__main__":
    raise SystemExit(main())


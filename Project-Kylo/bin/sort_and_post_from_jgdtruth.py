from __future__ import annotations

# Backwards-compatible shim.
#
# The real implementation lives in `services.posting.jgdtruth_poster` so the
# installed `kylo` CLI does not rely on `bin/` being packaged.

from services.posting.jgdtruth_poster import main


if __name__ == "__main__":
    raise SystemExit(main())


from __future__ import annotations

import os
import sys


def main() -> int:
    base = r"D:\\ScriptHub\\utils"
    os.chdir(base)
    sys.path.insert(0, base)

    try:
        from scripts.sync_bank import run
    except Exception:
        return 1

    cfg = os.path.join(base, "config", "config.json")
    try:
        run(cfg_path=cfg, dry_run=False, limit=None)
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())



from __future__ import annotations

"""
Compatibility wrapper.

The actual watcher implementation lives in `kylo.watcher_runtime` so it can be
imported/packaged cleanly without relying on `bin/`.
"""

from kylo.watcher_runtime import main  # noqa: F401



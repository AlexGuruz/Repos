#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from services.rules_loader.loader import main as loader_main


if __name__ == "__main__":
    sys.exit(loader_main())



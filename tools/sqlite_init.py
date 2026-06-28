#!/usr/bin/env python3
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import json
from intelligence.sqlite_foundation import initialize_and_mirror

result = initialize_and_mirror()
print(json.dumps(result, indent=2))
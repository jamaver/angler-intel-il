#!/usr/bin/env python3
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = [
    APP_ROOT / 'templates' / 'waters.html',
    APP_ROOT / 'templates' / 'reports.html',
    APP_ROOT / 'templates' / 'recommendations.html',
]
MODULES = [
    APP_ROOT / 'angler_waters_v40.py',
    APP_ROOT / 'angler_reports_v38.py',
    APP_ROOT / 'angler_recommendations_v44.py',
]
NAV_NEEDLES = [
    'Dashboard',
    'Map',
    'Smart Picks',
    'Local Waters',
    'Species',
    'My Tackle Locker',
    'Saved Reports',
    'Data Tools',
    'App Health',
]
ROUTES = ['/waters', '/reports', '/recommendations']

errors: list[str] = []

for path in TEMPLATES:
    if not path.exists():
        errors.append(f'Missing template: {path.relative_to(APP_ROOT)}')
    elif 'ai-main-tabs' not in path.read_text(encoding='utf-8'):
        errors.append(f'Template missing nav shell: {path.relative_to(APP_ROOT)}')

for path in MODULES:
    if not path.exists():
        errors.append(f'Missing module: {path.relative_to(APP_ROOT)}')
        continue
    try:
        ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError as exc:
        errors.append(f'{path.relative_to(APP_ROOT)} syntax error: {exc}')

for route in ROUTES:
    res = subprocess.run(['curl', '-s', f'http://127.0.0.1:5000{route}'], capture_output=True, text=True)
    if res.returncode != 0:
        errors.append(f'{route} curl failed')
        continue
    text = res.stdout
    for needle in NAV_NEEDLES:
        if needle not in text:
            errors.append(f'{route} missing nav label: {needle}')

if errors:
    print('QC FAILED: shell consolidation')
    for error in errors:
        print(f' - {error}')
    raise SystemExit(1)

print('QC PASSED: shell consolidation')
print('Waters, reports, and Smart Picks share the full nav shell.')

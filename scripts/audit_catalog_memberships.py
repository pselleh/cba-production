"""Validate cross-file course membership without creating placeholder courses."""
import argparse
import json
from collections import Counter
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('catalogs', nargs='+', type=Path)
args = parser.parse_args()
payloads = [(path, json.loads(path.read_text())) for path in args.catalogs]
keys = [row['course_key'] for _, payload in payloads for row in payload.get('microcourses', [])]
available = set(keys)
missing = set()
print('Course records:', len(keys), 'Unique keys:', len(available))
for key, count in Counter(keys).items():
    if count > 1:
        print('DUPLICATE:', key, count)
for path, payload in payloads:
    for program in payload.get('certificate_programs', []):
        absent = [row['course_key'] for row in program.get('microcourses', []) if row['course_key'] not in available]
        if absent:
            print('\nPROGRAM:', program.get('program_code', program.get('title')), 'SOURCE:', path.name)
            for key in absent:
                print('MISSING:', key)
                missing.add(key)
print('\nUnique missing program member keys:', len(missing))
raise SystemExit(1 if missing or len(keys) != len(available) else 0)

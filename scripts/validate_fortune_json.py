#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

p = Path('public/fortune.json')
if not p.exists():
    print('missing public/fortune.json')
    sys.exit(1)

data = json.loads(p.read_text(encoding='utf-8'))
errors = []

if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(data.get('date_kst', ''))):
    errors.append('invalid date_kst')

rankings = data.get('rankings') or []
if len(rankings) != 12:
    errors.append(f'invalid rankings length: {len(rankings)}')

ranks = []
for i, item in enumerate(rankings):
    rank = item.get('rank')
    if not isinstance(rank, int) or not (1 <= rank <= 12):
      errors.append(f'invalid rank at index {i}: {rank}')
    else:
      ranks.append(rank)

    scores = item.get('scores') or {}
    for k in ['total', 'love', 'study', 'money', 'health']:
      v = scores.get(k)
      if not isinstance(v, int) or not (0 <= v <= 100):
        errors.append(f'invalid score {k} at rank {rank}: {v}')

if ranks != sorted(ranks):
    errors.append('ranks not sorted')
if set(ranks) != set(range(1, 13)):
    errors.append('ranks are not exactly 1..12')

if errors:
    print('fortune.json validation failed')
    for e in errors:
      print('-', e)
    sys.exit(1)

print('fortune.json validation ok')

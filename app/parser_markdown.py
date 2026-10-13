import re
from pathlib import Path
from .models import Record, records_from_rows


def parse(path: Path) -> list[Record]:
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if '|' not in line:
            continue
        cells = [c.strip().replace(r'\|', '|') for c in re.split(r'(?<!\\)\|', line)]
        if line.startswith('|'):
            cells.pop(0)
        if line.endswith('|'):
            cells.pop()
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
            continue
        rows.append(cells)
    return records_from_rows(rows)

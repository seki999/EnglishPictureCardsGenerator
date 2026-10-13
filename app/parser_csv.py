import csv
from pathlib import Path
from .models import Record, records_from_rows


def parse(path: Path) -> list[Record]:
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return records_from_rows(list(csv.reader(stream)))

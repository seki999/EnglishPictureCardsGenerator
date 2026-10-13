import hashlib
import re
from pathlib import Path


def slug(text: str) -> str:
    value = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60]
    return value or 'word-' + hashlib.sha256(text.encode()).hexdigest()[:10]


def examples(deck: dict):
    for word in deck['words']:
        for meaning in word['meanings']:
            yield from meaning['examples']


def valid_image(path: Path) -> bool:
    from PIL import Image
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except (OSError, ValueError, SyntaxError):
        return False

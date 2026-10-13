import copy
import hashlib
import os
from pathlib import Path
from .models import Record
from .prompt_builder import build
from .utils import slug, examples


def normalize(records: list[Record], config: dict, output: Path) -> dict:
    deck = {'schema_version': '1.0', 'deck_id': config['deck_id'],
            'deck_name': config['deck_name'], 'words': []}
    word_map, meaning_map, ids = {}, {}, set()
    from .config import resolve
    image_dir = resolve(config['image_dir'])
    for record in records:
        key = (record.word.casefold(), record.part_of_speech, record.phonetic_uk, record.phonetic_us)
        if key not in word_map:
            base = slug(record.word)
            word_id = base if base not in ids else base + '-' + hashlib.sha256(repr(key).encode()).hexdigest()[:10]
            ids.add(word_id)
            word = {name: getattr(record, name) for name in ('word', 'part_of_speech', 'phonetic_uk', 'phonetic_us')}
            word.update(word_id=word_id, meanings=[])
            word_map[key] = word
            deck['words'].append(word)
        word = word_map[key]
        meaning_key = (key, record.definition_zh, record.phrase, record.phrase_zh)
        if meaning_key not in meaning_map:
            meaning = {name: getattr(record, name) for name in ('definition_zh', 'phrase', 'phrase_zh')}
            meaning.update(meaning_id=f"{word['word_id']}-{len(word['meanings']) + 1:02d}", examples=[])
            word['meanings'].append(meaning)
            meaning_map[meaning_key] = meaning
        meaning = meaning_map[meaning_key]
        if any(e['sentence_en'] == record.sentence_en and e['sentence_zh'] == record.sentence_zh for e in meaning['examples']):
            continue
        sentence_id = f"{meaning['meaning_id']}-{len(meaning['examples']) + 1:03d}"
        prompt, negative = build(record.sentence_en, record.phrase, config.get('prompt_overrides'))
        image = copy.deepcopy(config['generation'])
        image.update(path=Path(os.path.relpath(image_dir / (sentence_id + '.png'), output.parent)).as_posix(),
                     prompt=prompt, negative_prompt=negative, workflow=config['workflow'], status='pending', error_message='')
        meaning['examples'].append(dict(sentence_id=sentence_id, sentence_en=record.sentence_en,
                                        sentence_zh=record.sentence_zh, image=image))
    return deck


def restore(deck: dict, old: dict) -> None:
    """Restore only exact ID/content matches; never reuse another sentence's image."""
    previous = {e['sentence_id']: e for e in examples(old)}
    for e in examples(deck):
        p = previous.get(e['sentence_id'])
        if p and all(e[k] == p[k] for k in ('sentence_en', 'sentence_zh')):
            # Changed prompts or parameters invalidate prior images. Random seeds persist.
            keys = ('path', 'prompt', 'negative_prompt', 'width', 'height', 'model', 'sampler', 'steps', 'cfg', 'checkpoint', 'scheduler', 'workflow', 'lora', 'lora_strength_model', 'lora_strength_clip')
            if all(e['image'].get(k) == p['image'].get(k) for k in keys):
                if e['image']['seed'] in (-1, p['image'].get('seed')):
                    e['image'] = copy.deepcopy(p['image'])

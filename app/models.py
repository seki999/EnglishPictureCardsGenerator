from dataclasses import dataclass

COLUMNS = ('word', 'part_of_speech', 'phonetic_uk', 'phonetic_us',
           'definition_zh', 'phrase', 'phrase_zh', 'sentence_zh', 'sentence_en')
ALIASES = dict(zip(('单词', '词性', '英式音标', '美式音标', '中文释义', '短语',
                   '短语中文', '中文例句', '英文例句'), COLUMNS))


@dataclass(frozen=True)
class Record:
    word: str
    part_of_speech: str
    phonetic_uk: str
    phonetic_us: str
    definition_zh: str
    phrase: str
    phrase_zh: str
    sentence_zh: str
    sentence_en: str


def records_from_rows(rows: list[list[str]]) -> list[Record]:
    if not rows:
        raise ValueError('输入表格为空。')
    headers = [ALIASES.get(c.strip().lower(), c.strip().lower()) for c in rows[0]]
    has_header = set(COLUMNS).issubset(headers)
    if not has_header and ('word' in headers or 'sentence_en' in headers):
        raise ValueError('表头不完整：需要九列，参见 sample_vocab.md。')
    result = []
    for number, row in enumerate(rows[1:] if has_header else rows, start=2 if has_header else 1):
        if not any(row):
            continue
        if len(row) != len(headers) or (not has_header and len(row) != 9):
            raise ValueError(f'数据行 {number} 列数错误：得到 {len(row)} 列，需要九列或完整表头对应的列数。')
        values = dict(zip(headers if has_header else COLUMNS, row))
        values = {key: values[key].strip() for key in COLUMNS}
        for key in ('word', 'definition_zh', 'sentence_en'):
            if not values[key]:
                raise ValueError(f'数据行 {number} 的 {key} 不能为空。')
        result.append(Record(**values))
    if not result:
        raise ValueError('没有可用的词汇记录。')
    return result

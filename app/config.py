from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def load(path: Path) -> dict:
    with path.open(encoding='utf-8-sig') as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError('配置必须是 YAML 对象。')
    for key in ('input', 'output', 'image_dir', 'workflow', 'deck_id', 'deck_name', 'comfyui', 'generation'):
        if key not in config:
            raise ValueError(f'配置缺少 {key}。')
    g = config['generation']
    for key in ('width', 'height'):
        if type(g[key]) is not int or g[key] < 64 or g[key] % 8:
            raise ValueError(f'{key} 必须是至少 64 的 8 的倍数。')
    if type(g['steps']) is not int or g['steps'] < 1 or g['cfg'] <= 0:
        raise ValueError('steps 和 cfg 必须为正数。')
    if type(g['seed']) is not int or not -1 <= g['seed'] <= 2**64 - 1:
        raise ValueError('seed 必须为 -1 或 uint64。')
    c = config['comfyui']
    if c['request_timeout'] <= 0 or c['task_timeout'] <= 0 or c['poll_interval'] <= 0:
        raise ValueError('超时与轮询间隔必须为正数。')
    if type(c['retries']) is not int or c['retries'] < 0:
        raise ValueError('retries 必须是非负整数。')
    return config

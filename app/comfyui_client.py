import copy
import json
import time
import uuid
from pathlib import Path
import requests


class ComfyUIClient:
    def __init__(self, config: dict, workflow: Path):
        self.config = config
        self.url = config['url'].rstrip('/')
        self.session = requests.Session()
        self.template = json.loads(workflow.read_text(encoding='utf-8-sig'))

    def close(self) -> None:
        self.session.close()

    def request(self, method: str, route: str, **kwargs) -> requests.Response:
        # POST is intentionally not retried: a lost response may already be queued.
        attempts = self.config['retries'] + 1 if method == 'GET' else 1
        for attempt in range(attempts):
            try:
                response = self.session.request(method, self.url + route,
                                                timeout=self.config['request_timeout'], **kwargs)
                response.raise_for_status()
                return response
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as error:
                if isinstance(error, requests.HTTPError) and error.response is not None and error.response.status_code < 500:
                    raise
                if attempt + 1 == attempts:
                    raise
                time.sleep(min(2 ** attempt, 5))
        raise RuntimeError('无法访问 ComfyUI。')

    def check(self, checkpoint: str, lora: str | None = None) -> None:
        try:
            info = self.request('GET', '/object_info/CheckpointLoaderSimple').json()
        except requests.RequestException as error:
            raise RuntimeError(f'无法连接 ComfyUI：{self.url}。请按 README 启动 ComfyUI。{error}') from error
        names = info['CheckpointLoaderSimple']['input']['required']['ckpt_name'][0]
        if checkpoint not in names:
            raise ValueError(f'找不到 checkpoint {checkpoint!r}。ComfyUI 可用模型：{names}')
        if lora:
            info = self.request('GET', '/object_info/LoraLoader').json()
            names = info['LoraLoader']['input']['required']['lora_name'][0]
            if lora not in names:
                raise ValueError(f'找不到 LoRA {lora!r}。请运行 setup_comfyui.ps1 或将权重放入 ComfyUI/models/loras。')

    def workflow(self, image: dict, sentence_id: str) -> dict:
        workflow = copy.deepcopy(self.template)
        values = dict(image, filename_prefix='picture_cards/' + sentence_id)
        def inject(obj):
            if isinstance(obj, dict):
                return {k: inject(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [inject(v) for v in obj]
            if isinstance(obj, str) and obj.startswith('{{') and obj.endswith('}}'):
                key = obj[2:-2]
                if key not in values:
                    raise ValueError(f'workflow 模板包含未知参数：{key}')
                return values[key]
            return obj
        return inject(workflow)

    def submit(self, image: dict, sentence_id: str) -> str:
        response = self.request('POST', '/prompt', json={
            'prompt': self.workflow(image, sentence_id), 'client_id': str(uuid.uuid4())}).json()
        if 'prompt_id' not in response:
            raise RuntimeError(f'ComfyUI 拒绝任务：{response}')
        return response['prompt_id']

    def wait(self, prompt_id: str) -> dict:
        deadline = time.monotonic() + self.config['task_timeout']
        while time.monotonic() < deadline:
            history = self.request('GET', '/history/' + prompt_id).json().get(prompt_id)
            if history:
                status = history.get('status', {})
                if status.get('status_str') == 'error':
                    raise RuntimeError(f"ComfyUI 执行失败：{status.get('messages', [])}")
                # Select only SaveImage output; never pick another node's preview.
                for node_id, node in self.template.items():
                    if node.get('class_type') == 'SaveImage':
                        for image in history.get('outputs', {}).get(node_id, {}).get('images', []):
                            if image.get('type') == 'output':
                                return image
                if status.get('completed'):
                    raise RuntimeError('ComfyUI 已完成任务，但 SaveImage 没有输出图片。')
            time.sleep(self.config['poll_interval'])
        raise TimeoutError(f'ComfyUI 任务 {prompt_id} 等待超时；保留任务 ID，下次运行继续查询。')

    def download(self, descriptor: dict) -> bytes:
        return self.request('GET', '/view', params={k: descriptor[k] for k in ('filename', 'subfolder', 'type')}).content

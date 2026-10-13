import io
import logging
import secrets
import time
from pathlib import Path
from PIL import Image
from .comfyui_client import ComfyUIClient
from .json_writer import write
from .utils import examples, valid_image

LOG = logging.getLogger(__name__)


def generate(deck: dict, output: Path, client: ComfyUIClient, limit: int | None = None,
             force: bool = False) -> dict:
    items = list(examples(deck))
    stats = dict(total=len(items), success=0, skipped=0, failed=0, deferred=0)
    attempted = 0
    for example in items:
        image = example['image']
        path = (output.parent / image['path']).resolve()
        if not force and image['status'] == 'completed' and valid_image(path):
            stats['skipped'] += 1
            LOG.info('跳过 %s', example['sentence_id'])
            continue
        if limit is not None and attempted >= limit:
            stats['deferred'] += 1
            continue
        attempted += 1
        if image['seed'] == -1:
            image['seed'] = secrets.randbelow(2**63)
        if force:
            image.pop('prompt_id', None)
        succeeded = False
        for attempt in range(client.config['retries'] + 1):
            try:
                if not image.get('prompt_id'):
                    # Persist seed before submission. A POST timeout must not blindly resubmit.
                    image.update(status='generating', error_message='')
                    write(output, deck)
                    image['prompt_id'] = client.submit(image, example['sentence_id'])
                    write(output, deck)
                descriptor = client.wait(image['prompt_id'])
                content = client.download(descriptor)
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.png.tmp')
                try:
                    with Image.open(io.BytesIO(content)) as downloaded:
                        downloaded.load()
                        downloaded.save(temporary, format='PNG')
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
                image.update(status='completed', error_message='')
                succeeded = True
                LOG.info('生成成功 %s -> %s', example['sentence_id'], path)
                break
            except OSError as error:
                image.update(status='failed', error_message=str(error))
                LOG.exception('图片 %s 保存或 API 请求失败', example['sentence_id'])
                # Do not retry an ambiguous submission without a known prompt ID.
                if not image.get('prompt_id'):
                    break
            except Exception as error:
                image.update(status='failed', error_message=str(error))
                LOG.exception('图片 %s 失败 (尝试 %s)', example['sentence_id'], attempt + 1)
                if isinstance(error, TimeoutError):
                    break
                # An explicit execution error can be retried as a new job.
                if isinstance(error, RuntimeError):
                    image.pop('prompt_id', None)
                if not image.get('prompt_id') and not isinstance(error, RuntimeError):
                    break
            write(output, deck)
            if attempt < client.config['retries']:
                time.sleep(min(2 ** attempt, 5))
        stats['success' if succeeded else 'failed'] += 1
        write(output, deck)
    return stats

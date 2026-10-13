"""Download the official SDXL checkpoint with resume and SHA-256 verification."""
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / '.runtime/ComfyUI/models/checkpoints/sd_xl_base_1.0.safetensors'
URL = 'https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors'
SIZE = 6938078334
SHA256 = '31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b'


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists() and TARGET.stat().st_size == SIZE and digest(TARGET) == SHA256:
        print('Checkpoint already verified.', flush=True)
        return
    part = TARGET.with_suffix('.safetensors.part')
    workers = 8
    span = (SIZE + workers - 1) // workers
    pieces = [part.with_name(part.name + f'.{i}') for i in range(workers)]
    if part.exists() and part.stat().st_size <= span and not pieces[0].exists():
        part.replace(pieces[0])

    def fetch(index: int) -> None:
        start, end = index * span, min(SIZE, (index + 1) * span) - 1
        piece = pieces[index]
        for attempt in range(10):
            offset = piece.stat().st_size if piece.exists() else 0
            if offset == end - start + 1:
                return
            if offset > end - start + 1:
                raise RuntimeError(f'Unexpected partial segment size: {piece}')
            try:
                with requests.get(URL, params={'download': 'true', 'resume': str(time.time_ns())},
                                  headers={'Range': f'bytes={start + offset}-{end}'},
                                  stream=True, timeout=(30, 120)) as response:
                    response.raise_for_status()
                    expected = f'bytes {start + offset}-{end}/{SIZE}'
                    if response.status_code != 206 or response.headers.get('Content-Range') != expected:
                        raise RuntimeError('Server did not honor the requested byte range.')
                    with piece.open('ab') as stream:
                        for chunk in response.iter_content(1024 * 1024):
                            stream.write(chunk)
            except requests.RequestException as error:
                print(f'Segment {index + 1} attempt {attempt + 1}: {type(error).__name__}', flush=True)
                time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f'Segment {index + 1} incomplete; rerun to resume.')

    initial = sum(p.stat().st_size for p in pieces if p.exists())
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, i) for i in range(workers)]
        while not all(f.done() for f in futures):
            time.sleep(15)
            count = sum(p.stat().st_size for p in pieces if p.exists())
            speed = (count - initial) / max(time.monotonic() - started, 0.01) / 1e6
            print(f'Model {count / SIZE:.1%}: {count / 1e9:.2f}/{SIZE / 1e9:.2f} GB, {speed:.1f} MB/s', flush=True)
        for future in futures:
            future.result()
    with part.open('wb') as output:
        for piece in pieces:
            with piece.open('rb') as source:
                while chunk := source.read(8 * 1024 * 1024):
                    output.write(chunk)
    print('Checking SHA-256...', flush=True)
    if digest(part) != SHA256:
        raise RuntimeError('SHA-256 mismatch. Model was not activated; inspect the .part file.')
    part.replace(TARGET)
    for piece in pieces:
        piece.unlink()
    print(f'Checkpoint verified and ready: {TARGET}', flush=True)


if __name__ == '__main__':
    main()

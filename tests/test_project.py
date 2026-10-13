import copy
import csv
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from openpyxl import Workbook

from app.config import ROOT, load
from app.models import COLUMNS, Record
from app import parser_csv, parser_excel, parser_markdown
from app.normalizer import normalize, restore
from app.prompt_builder import build
from app.comfyui_client import ComfyUIClient
from app.image_generator import generate
from app.json_writer import write
from app.utils import examples


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = load(ROOT / 'config/config.yaml')
        self.config['image_dir'] = str(self.root / 'assets/images')
        self.output = self.root / 'data/output/deck.json'
        self.records = parser_markdown.parse(ROOT / 'data/input/sample_vocab.md')

    def deck(self):
        return normalize(self.records, self.config, self.output)

    def test_sample_data_first_row_and_schema(self):
        deck = self.deck()
        self.assertEqual(len(self.records), 3)
        self.assertEqual(len(deck['words']), 2)
        self.assertEqual(len(deck['words'][0]['meanings']), 2)
        items = list(examples(deck))
        self.assertEqual([e['sentence_id'] for e in items], ['abstain-01-001', 'abstain-02-001', 'inaugural-01-001'])
        required = {'path', 'prompt', 'negative_prompt', 'width', 'height', 'model', 'sampler', 'steps', 'cfg', 'seed', 'status', 'error_message'}
        for e in items:
            self.assertTrue(required.issubset(e['image']))
            self.assertEqual((self.output.parent / e['image']['path']).resolve(), self.root / 'assets/images' / (e['sentence_id'] + '.png'))

    def test_markdown_headers_alignment_escape_and_no_outer_pipes(self):
        path = self.root / 'input.md'
        row = [getattr(self.records[0], key) for key in COLUMNS]
        row[4] = r'意思一\|意思二'
        path.write_text('# Example\n\n' + ' | '.join(COLUMNS) + '\n' + ' | '.join([':---:'] * 9) + '\n' + ' | '.join(row), encoding='utf-8-sig')
        self.assertEqual(parser_markdown.parse(path)[0].definition_zh, '意思一|意思二')

    def test_bad_columns_and_empty_input(self):
        path = self.root / 'input.md'
        for content in ('| a | b |', '# No table\n', '| word | sentence_en |\n| a | sentence |'):
            path.write_text(content, encoding='utf-8')
            with self.assertRaises(ValueError):
                parser_markdown.parse(path)

    def test_csv_and_excel_unicode_and_reordered_header(self):
        keys = list(reversed(COLUMNS))
        row = [getattr(self.records[0], key) for key in keys]
        path = self.root / 'input.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerows([keys, row])
        self.assertEqual(parser_csv.parse(path), self.records[:1])
        workbook = Workbook()
        workbook.active.append(keys)
        workbook.active.append(row)
        path = self.root / 'input.xlsx'
        workbook.save(path)
        workbook.close()
        self.assertEqual(parser_excel.parse(path), self.records[:1])

    def test_grouping_dedup_and_word_id_collision(self):
        other = Record(**{**self.records[0].__dict__, 'sentence_en': 'A patient refuses a glass.', 'sentence_zh': '病人拒绝一杯酒。'})
        noun = Record(**{**self.records[0].__dict__, 'part_of_speech': 'n.'})
        deck = normalize([self.records[0], self.records[0], other, noun], self.config, self.output)
        self.assertEqual(len(deck['words']), 2)
        self.assertNotEqual(deck['words'][0]['word_id'], deck['words'][1]['word_id'])
        self.assertEqual(len(deck['words'][0]['meanings'][0]['examples']), 2)

    def test_resume_invalidates_changed_sentence_and_parameters(self):
        old = self.deck()
        old_example = next(examples(old))
        old_example['image'].update(status='completed', seed=123, prompt_id='existing-job')
        deck = self.deck()
        restore(deck, old)
        self.assertEqual(next(examples(deck))['image']['seed'], 123)
        changed = self.deck()
        next(examples(changed))['sentence_en'] = 'Changed.'
        restore(changed, old)
        self.assertEqual(next(examples(changed))['image']['status'], 'pending')
        changed = self.deck()
        next(examples(changed))['image']['width'] = 512
        restore(changed, old)
        self.assertEqual(next(examples(changed))['image']['status'], 'pending')

    def test_prompts_no_text_and_fictional_politics(self):
        for record in self.records:
            prompt, negative = build(record.sentence_en, record.phrase)
            self.assertTrue(prompt.endswith('No text in image.'))
            self.assertNotIn(record.sentence_en, prompt)
            self.assertIn('text', negative)
        prompt, _ = build('President Biden outlined a reform.', '')
        self.assertNotIn('Biden', prompt)
        self.assertIn('fictional', prompt)

    def test_lightning_workflow_injection_and_resume_invalidation(self):
        config = load(ROOT / 'config/config.cpu.yaml')
        config['image_dir'] = self.config['image_dir']
        deck = normalize(self.records, config, self.output)
        e = next(examples(deck))
        e['image']['seed'] = 42
        client = ComfyUIClient(config['comfyui'], ROOT / config['workflow'])
        self.addCleanup(client.close)
        workflow = client.workflow(e['image'], e['sentence_id'])
        self.assertEqual(workflow['10']['inputs']['lora_name'], config['generation']['lora'])
        self.assertEqual(workflow['3']['inputs']['model'], ['10', 0])
        self.assertEqual(workflow['6']['inputs']['target_width'], 1024)
        self.assertEqual(workflow['3']['inputs']['cfg'], 1.0)
        self.assertEqual(workflow['3']['inputs']['steps'], 4)
        e['image']['status'] = 'completed'
        changed = normalize(self.records, config, self.output)
        next(examples(changed))['image']['lora'] = 'different.safetensors'
        restore(changed, deck)
        self.assertEqual(next(examples(changed))['image']['status'], 'pending')

    def test_atomic_write_preserves_prior_json_on_failure(self):
        write(self.output, self.deck())
        original = self.output.read_bytes()
        with patch('app.json_writer.os.replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                write(self.output, {'changed': True})
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(list(self.output.parent.glob('*.tmp')), [])

    def test_cli_dry_run_does_not_connect(self):
        import yaml
        self.config['comfyui']['url'] = 'http://127.0.0.1:1'
        self.config['output'] = str(self.output)
        config_path = self.root / 'config.yaml'
        config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'app.main', '--config', str(config_path), '--generate-images', '--dry-run'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        deck = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertTrue(all(e['image']['status'] == 'pending' for e in examples(deck)))
        self.assertFalse((self.root / 'assets/images').exists())

    def fake_client(self, failures=False, transient=False, empty=False):
        state = {'submitted': [], 'jobs': {}, 'gets': 0, 'transient': transient}
        png = io.BytesIO()
        Image.new('RGB', (16, 16), 'white').save(png, format='PNG')
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, content, code=200):
                data = content if isinstance(content, bytes) else json.dumps(content).encode()
                self.send_response(code)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                state['submitted'].append(payload)
                job = str(len(state['submitted']))
                state['jobs'][job] = payload
                self.respond({'prompt_id': job})

            def do_GET(self):
                state['gets'] += 1
                if state['transient']:
                    state['transient'] = False
                    self.respond({'error': 'busy'}, 503)
                elif self.path.startswith('/object_info'):
                    self.respond({'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [['sd_xl_base_1.0.safetensors']]}}}})
                elif self.path.startswith('/history/'):
                    job = self.path.split('/')[-1]
                    prefix = state['jobs'][job]['prompt']['9']['inputs']['filename_prefix']
                    if empty:
                        self.respond({})
                    elif failures and prefix.endswith('abstain-01-001'):
                        self.respond({job: {'status': {'status_str': 'error', 'messages': ['mock failure']}}})
                    else:
                        self.respond({job: {'status': {'completed': True, 'status_str': 'success'}, 'outputs': {'9': {'images': [{'filename': 'result.png', 'subfolder': '', 'type': 'output'}]}}}})
                elif self.path.startswith('/view?'):
                    self.respond(png.getvalue())
                else:
                    self.respond({}, 404)

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def stop():
            server.shutdown()
            server.server_close()
            thread.join()
        self.addCleanup(stop)
        c = copy.deepcopy(self.config['comfyui'])
        c.update(url=f'http://127.0.0.1:{server.server_port}', retries=1, poll_interval=0.01, task_timeout=0.03)
        client = ComfyUIClient(c, ROOT / 'workflows/sdxl_basic_api.json')
        self.addCleanup(client.close)
        return client, state

    def test_full_http_pipeline_limit_resume_skip_missing_image(self):
        client, state = self.fake_client()
        client.check(self.config['generation']['checkpoint'])
        deck = self.deck()
        stats = generate(deck, self.output, client, limit=1)
        self.assertEqual((stats['success'], stats['deferred']), (1, 2))
        inputs = state['submitted'][0]['prompt']['3']['inputs']
        self.assertIsInstance(inputs['seed'], int)
        self.assertIsInstance(inputs['steps'], int)
        self.assertIsInstance(state['submitted'][0]['prompt']['5']['inputs']['width'], int)
        restored = self.deck()
        restore(restored, json.loads(self.output.read_text(encoding='utf-8')))
        stats = generate(restored, self.output, client)
        self.assertEqual((stats['success'], stats['skipped']), (2, 1))
        stats = generate(restored, self.output, client)
        self.assertEqual((stats['success'], stats['skipped']), (0, 3))
        path = self.output.parent / next(examples(restored))['image']['path']
        path.unlink()
        stats = generate(restored, self.output, client)
        self.assertEqual((stats['success'], stats['skipped']), (1, 2))
        path.write_bytes(b'corrupt')
        stats = generate(restored, self.output, client)
        self.assertEqual((stats['success'], stats['skipped']), (1, 2))

    def test_execution_failure_retry_and_continue(self):
        client, state = self.fake_client(failures=True)
        with self.assertLogs('app.image_generator', level='ERROR'):
            stats = generate(self.deck(), self.output, client)
        self.assertEqual((stats['failed'], stats['success']), (1, 2))
        self.assertEqual(len(state['submitted']), 4)
        saved = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertIn('mock failure', next(examples(saved))['image']['error_message'])

    def test_get_retry_and_missing_checkpoint(self):
        client, state = self.fake_client(transient=True)
        client.check(self.config['generation']['checkpoint'])
        self.assertEqual(state['gets'], 2)
        with self.assertRaises(ValueError):
            client.check('missing.safetensors')

    def test_task_timeout_keeps_job_and_does_not_resubmit(self):
        client, state = self.fake_client(empty=True)
        deck = self.deck()
        with self.assertLogs('app.image_generator', level='ERROR'):
            generate(deck, self.output, client, limit=1)
            generate(deck, self.output, client, limit=1)
        self.assertEqual(len(state['submitted']), 1)
        self.assertEqual(next(examples(deck))['image']['prompt_id'], '1')

    def test_cli_limit_zero_does_not_connect(self):
        import yaml
        self.config['comfyui']['url'] = 'http://127.0.0.1:1'
        self.config['output'] = str(self.output)
        path = self.root / 'config.yaml'
        path.write_text(yaml.safe_dump(self.config), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'app.main', '--config', str(path), '--generate-images', '--limit', '0'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.output.exists())

    def test_force_cli_replaces_random_seed(self):
        import yaml
        client, state = self.fake_client()
        deck = self.deck()
        generate(deck, self.output, client)
        before = next(examples(deck))['image']['seed']
        untouched_seeds = [e['image']['seed'] for e in list(examples(deck))[1:]]
        self.config['comfyui'] = client.config
        self.config['output'] = str(self.output)
        path = self.root / 'config.yaml'
        path.write_text(yaml.safe_dump(self.config), encoding='utf-8')
        result = subprocess.run([sys.executable, '-m', 'app.main', '--config', str(path), '--generate-images', '--force', '--limit', '1'], cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertNotEqual(before, next(examples(saved))['image']['seed'])
        self.assertEqual(len(state['submitted']), 4)
        self.assertEqual([e['image']['seed'] for e in list(examples(saved))[1:]], untouched_seeds)


if __name__ == '__main__':
    unittest.main()

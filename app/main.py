import argparse
import json
import logging
import sys
from pathlib import Path
from . import parser_csv, parser_excel, parser_markdown
from .config import ROOT, load, resolve
from .normalizer import normalize, restore
from .json_writer import write
from .utils import examples, valid_image


def main() -> int:
    # Windows terminals may default to a locale unable to display Chinese.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='英语图片学习卡片 JSON / ComfyUI 数据生成器')
    parser.add_argument('--config', default='config/config.yaml')
    parser.add_argument('--input')
    parser.add_argument('--output')
    parser.add_argument('--generate-images', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='只生成 JSON 和 prompt，不访问 ComfyUI')
    parser.add_argument('--resume', action='store_true', help='显式启用默认的自动恢复行为')
    parser.add_argument('--force', action='store_true', help='重新生成已有图片')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    log_dir = ROOT / 'logs'
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / 'generator.log', encoding='utf-8')])
    log = logging.getLogger(__name__)
    client = None
    stats = dict(total=0, success=0, skipped=0, failed=0, deferred=0)
    try:
        if args.limit is not None and args.limit < 0:
            raise ValueError('--limit 不能为负数。')
        config = load(resolve(args.config))
        source = resolve(args.input or config['input'])
        output = resolve(args.output or config['output'])
        parsers = {'.md': parser_markdown.parse, '.markdown': parser_markdown.parse,
                   '.csv': parser_csv.parse, '.xlsx': parser_excel.parse, '.xlsm': parser_excel.parse}
        if source.suffix.lower() not in parsers:
            raise ValueError('支持 Markdown、UTF-8 CSV 和 Excel .xlsx/.xlsm；旧 .xls 请先另存为 .xlsx。')
        records = parsers[source.suffix.lower()](source)
        stats['total'] = len(records)
        deck = normalize(records, config, output)
        if output.exists():
            old = json.loads(output.read_text(encoding='utf-8-sig'))
            if old.get('deck_id') == deck['deck_id']:
                restore(deck, old)
        write(output, deck)
        items = list(examples(deck))
        stats = dict(total=len(records), success=0, skipped=0, failed=0, deferred=len(items))
        log.info('已写入 %s：%s 条输入记录，%s 个唯一例句', output, len(records), len(items))
        if args.generate_images and not args.dry_run:
            from .comfyui_client import ComfyUIClient
            from .image_generator import generate
            eligible = [e for e in items if args.force or not (e['image']['status'] == 'completed' and valid_image(output.parent / e['image']['path']))]
            if eligible and args.limit != 0:
                client = ComfyUIClient(config['comfyui'], resolve(config['workflow']))
                try:
                    client.check(config['generation']['checkpoint'])
                except Exception as error:
                    for e in eligible[:args.limit] if args.limit is not None else eligible:
                        e['image'].update(status='failed', error_message=str(error))
                    stats.update(skipped=len(items) - len(eligible), failed=min(len(eligible), args.limit) if args.limit is not None else len(eligible))
                    stats['deferred'] = len(items) - stats['skipped'] - stats['failed']
                    write(output, deck)
                    raise
                if args.force and config['generation']['seed'] == -1:
                    for e in eligible:
                        e['image']['seed'] = -1
                stats = generate(deck, output, client, args.limit, args.force)
                stats['total'] = len(records)
            else:
                stats.update(skipped=len(items) - len(eligible), deferred=len(eligible))
        else:
            log.info('dry-run / JSON 模式：未调用 ComfyUI。')
        return 1 if stats['failed'] else 0
    except Exception:
        log.exception('程序失败；请检查输入、配置和 README。')
        return 1
    except KeyboardInterrupt:
        log.warning('已中断；下次运行自动恢复已保存的任务。')
        return 130
    finally:
        if client:
            client.close()
        if stats:
            log.info('统计：总记录数=%s 成功数=%s 跳过数=%s 失败数=%s 待处理数=%s',
                     stats['total'], stats['success'], stats['skipped'], stats['failed'], stats['deferred'])


if __name__ == '__main__':
    raise SystemExit(main())

"""Optional real AI validation. Uses only a dedicated temporary sample file."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core import Store, Engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='', help='Optional override; otherwise inherit Claude Code model')
    parser.add_argument('--endpoint', default='', help='Optional model service URL')
    parser.add_argument('--timeout', type=int, default=180)
    args = parser.parse_args()
    if not 30 <= args.timeout <= 600:
        parser.error('--timeout must be between 30 and 600 seconds')
    executable = shutil.which('claude')
    if not executable:
        parser.error('Claude Code was not found on PATH')
    with tempfile.TemporaryDirectory(prefix='fileatlas-live-') as directory:
        root = Path(directory)
        source = root / 'Inbox'
        source.mkdir()
        store = Store(root / 'state')
        try:
            store.set_sources([str(source)])
            store.save_category('工程设计', str(root / 'Archive' / 'Engineering'), '机械设计、仿真、技术方案、工程图纸')
            store.save_category('财务票据', str(root / 'Archive' / 'Finance'), '费用报销、采购发票、合同金额、会计凭证')
            for key, value in dict(claude_path=executable, model=args.model, endpoint=args.endpoint,
                                   timeout=args.timeout, mode='move', auto_apply=True, threshold=.8).items():
                store.set(key, value)
            p = source / '机械传动设计方案.txt'
            p.write_text('机械传动系统设计方案\n采用齿轮减速机构，开展 Adams 多体动力学仿真，评估扭矩与齿轮啮合载荷。', encoding='utf-8')
            Engine(store).process(p)
            records = store.rows('SELECT * FROM files')
            assert len(records) == 1
            record = records[0]
            assert record['status'] in ('review', 'done')
            assert Path(record['path']).is_file()
            report = dict(status=record['status'], confidence=record['confidence'],
                          category=store.category_name(record['category']),
                          tags=json.loads(record['tags']), reason=record['reason'])
            output = ROOT / 'validation' / 'live-result.json'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=True, indent=2))
        finally:
            store.db.close()


if __name__ == '__main__':
    main()

"""CPU verification of W41 evidence locators and the published Markdown.

No learner, evaluator, GPU, operational ledger or source file is modified.
Original conversation stays on the local machine; only hashes are published.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tables(text):
    lines = text.splitlines()
    sizes = []
    for i, line in enumerate(lines):
        if not line.startswith('|') or i + 1 >= len(lines):
            continue
        if not re.match(r'^\|\s*:?-', lines[i + 1]):
            continue
        count = len(re.split(r'(?<!\\)\|', line.strip().strip('|')))
        j = i + 1
        n = 0
        while j < len(lines) and lines[j].startswith('|'):
            assert len(re.split(r'(?<!\\)\|', lines[j].strip().strip('|'))) == count, j + 1
            n += 1
            j += 1
        sizes.append({'columns': count, 'body_rows': n - 1})
    return sizes


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = Path(__file__).parent
    data = json.loads((root / 'evidence.json').read_text(encoding='utf-8'))
    for item in data['sources']:
        with open(item['source'], 'rb') as f:
            f.seek(item['offset'])
            raw = f.read(item['length'])
        assert sha(raw) == item['sha256'], item['id']
        d = json.loads(raw)
        assert d['type'] == ('user' if item['role'] == 'user' else 'assistant')
        assert dt.datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')) == dt.datetime.fromisoformat(item['time'])
        # Known bad input: source-byte damage must fail identity verification.
        assert sha(raw[:-1] + bytes([raw[-1] ^ 1])) != item['sha256']
    for source in {x['source'] for x in data['sources']}:
        indexed = {x['line']: x for x in data['sources'] if x['source'] == source}
        with open(source, 'rb') as f:
            for n in range(1, max(indexed) + 1):
                offset = f.tell()
                raw = f.readline()
                assert raw
                if n in indexed:
                    assert offset == indexed[n]['offset'] and sha(raw) == indexed[n]['sha256']
    ledger = data['ledger']
    path = Path(ledger['path'])
    repo = next(parent for parent in path.parents if (parent / '.git').exists())
    rel = path.relative_to(repo).as_posix()
    raw = subprocess.check_output(['git', '-C', str(repo), 'show', f"{ledger['commit']}:{rel}"])
    assert sha(raw) == ledger['blob_sha256']
    lines = raw.decode('utf-8').splitlines()
    for item in ledger['lines']:
        assert lines[item['line'] - 1] == item['text']
    for item in data['files']:
        assert sha(Path(item['path']).read_bytes()) == item['sha256'], item['path']
    report = root / 'EVIDENCE-W41-DECISIONS-1107.md'
    text = report.read_text(encoding='utf-8')
    assert '\u2014' not in text
    assert [x.split(':')[0] for x in text.splitlines()[:5]] == ['> 분류', '> 작성', '> 근거', '> 요지', '> 상태']
    size = tables(text)
    assert size == [{'columns': 3, 'body_rows': 8}, {'columns': 3, 'body_rows': 5}], size
    for item in data['sources']:
        assert 'excerpts' not in item
    assert 'C:\\Users\\AI-WS01\\.claude' not in text
    # Budget arithmetic is a stated model, not an observed throughput claim.
    hours = 40000 * 27.8 / 3600
    slack = 16 * 24 - (40000 + 1250) * 27.8 / 3600 - 48
    assert round(hours, 2) == 308.89 and round(slack, 2) == 17.46
    result = dict(status='PASS', raw_source_rows=len(data['sources']),
                  ledger_rows=len(ledger['lines']), referenced_files=len(data['files']),
                  tables=size, broken_rows=0, source_mutation_detected=True,
                  report_sha256=sha(report.read_bytes()), gpu_used=False)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

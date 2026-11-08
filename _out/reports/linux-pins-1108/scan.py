"""Read-only lexical inventory, pinned source plus operational filesystem snapshots.

No application imports, process control, GPU, or reads of runtime secrets.
"""
from pathlib import Path
import collections
import csv
import hashlib
import io
import json
import re
import subprocess
import tarfile
from datetime import datetime

ROOT = Path('D:/mai-wt/foothold-lab/runner-ex42-resume-w65')
HEAD = 'cc7586db9f58b4bf43ef2ce5658e40bede3e7003'
OUT = Path('D:/mai-tmp/analyst/linux-pins-1108')
OUT.mkdir(parents=True, exist_ok=True)
PATTERNS = {
    'drive': r'(?i)(?<![A-Za-z0-9_])[a-z]:[/\\]',
    'drive_guard': r'\.drive\b|[\x22\x27][A-Za-z]:[\x22\x27]',
    'msys': r'(?<![A-Za-z0-9_])/[c-z]/',
    'exe': r'(?i)\b[\w.-]+\.exe\b',
    'shell': r'(?i)\b(?:cmd\.exe|powershell(?:\.exe)?|pwsh|cygpath|wslpath|MSYSTEM|COMSPEC|cmd\s*/[cCkK])\b',
    'winapi': r'CREATE_(?:NO_WINDOW|NEW_PROCESS_GROUP)|DETACHED_PROCESS|creationflags|STARTUPINFO|SW_HIDE|ctypes\.(?:windll|WinDLL)|Win32|Get-CimInstance|wmic|taskkill|tasklist|startfile|winreg|os\.name|sys\.platform',
    'lock': r'\bmsvcrt\b|\bfcntl\b|LOCK_(?:EX|NB)|LockFile|FileShare|CreateFileW',
    'gpu': r'\bcuda:\d+\b|CUDA_VISIBLE_DEVICES|CUDA_DEVICE_ORDER|graphics_device|active_gpu|physics_gpu|device_id|GPU_UUID',
    'separator': r'\\|\bPATH\b|PYTHONPATH|os\.pathsep|PureWindowsPath|PurePosixPath',
    'casefold': r'\.casefold\(|\.lower\(|\.upper\(|normcase|re\.I(?:GNORECASE)?\b|(?<![A-Za-z])(?i:IGNORECASE)\b',
    'line_encoding': r'\\r(?:\\n)?|CRLF|newline\s*=|dos2unix|unix2dos|utf-8-sig|utf-16|cp949|mbcs',
    'permissions': r'S_IWRITE|os\.chmod|os\.access|start_new_session|setsid|Start-Process|shell\s*=\s*True',
    'winenv_binary': r'\b(?:USERPROFILE|LOCALAPPDATA|APPDATA|HOMEDRIVE|HOMEPATH|ProgramFiles|COMSPEC)\b|(?i:\.(?:dll|pyd|bat|cmd|ps1)\b)',
}
compiled = {k: re.compile(v) for k, v in PATTERNS.items()}
fixtures = {
    'drive': 'ROOT = Path("C:/isaac/IsaacLab")', 'msys': '/c/isaac/IsaacLab',
    'exe': 'python.exe', 'shell': 'powershell -NoProfile',
    'winapi': 'subprocess.CREATE_NO_WINDOW', 'lock': 'import msvcrt',
    'gpu': 'device="cuda:1"', 'separator': 'PATH="$CONDA;${PATH}"',
    'casefold': 'filename.lower()', 'line_encoding': 'text.replace("\\r\\n", "\\n")',
    'drive_guard': 'path.drive.upper() != "D:"', 'permissions': 'mode & ~stat.S_IWRITE',
    'winenv_binary': 'os.environ["LOCALAPPDATA"] + "tool.ps1"',
}
assert all(compiled[k].search(v) for k, v in fixtures.items())
assert not compiled['drive'].search('https://example.org/linux/path')
data = subprocess.check_output(['git', '-C', str(ROOT), 'archive', '--format=tar', HEAD, 'foothold_s2'])
files = []
with tarfile.open(fileobj=io.BytesIO(data)) as archive:
    for member in archive.getmembers():
        if member.isfile():
            files.append(('S', member.name, archive.extractfile(member).read(), None, member.mode))
known = next(blob.decode('utf-8') for scope, p, blob, _, _ in files
             if p == 'foothold_s2/basic_gait_chain_plan.py')
known_lines = [(i, line) for i, line in enumerate(known.splitlines(), 1)
               if 'PYTHON =' in line and 'C:/' in line]
assert known_lines and all(compiled['drive'].search(line) for _, line in known_lines)

scopes = {
    'O': Path('D:/mai-wt/foothold-lab/lead-dispatch-measure/_out/tools'),
    'ML': Path('D:/mai-wt/foothold-lab/lead-worklist-1103/_out/msgs'),
    'MH': Path('C:/mai/wt/foothold-lab/lead_tmp-20261023/_out/msgs'),
}
for scope, root in scopes.items():
    paths = [root / 'gpu_jobs', root / 'ex41'] if scope == 'O' else [root]
    for base in paths:
        for path in sorted(base.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                # Message payloads are data, not executable code; inventory their
                # hash/size without scanning potentially private message text.
                blob = path.read_bytes()
                files.append((scope, path.relative_to(root).as_posix(), blob, str(path), None))

inventory, hits, texts = [], [], {}
for scope, name, blob, physical, mode in files:
    key = f'{scope}/{name}'
    suffix = Path(name).suffix.lower()
    role = ('cache' if '.pytest_cache' in Path(name).parts else
            'test' if '/tests/' in name or '/fixtures/' in name or Path(name).name.startswith('test_') else
            'doc' if suffix in ('.md', '.rst') else
            'historical-result' if scope == 'S' and suffix == '.json' and '/scripts/start_' in name else
            'message-data' if scope in ('ML', 'MH') and suffix not in ('.py', '.sh', '.ps1') else 'runtime/config')
    is_binary = b'\0' in blob and not blob.startswith((b'\xff\xfe', b'\xfe\xff'))
    encoding = 'binary' if is_binary else 'utf-8-sig'
    text = None
    if not is_binary and role not in ('message-data', 'cache'):
        try:
            encoding = 'utf-16' if blob.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
            text = blob.decode(encoding)
        except UnicodeDecodeError:
            encoding = 'undecodable'
    inventory.append({'scope': scope, 'file': name, 'bytes': len(blob),
                      'sha256': hashlib.sha256(blob).hexdigest(), 'encoding': encoding,
                      'role': role, 'scanned': text is not None, 'mode': mode,
                      'crlf_count': blob.count(b'\r\n'), 'crcrlf_count': blob.count(b'\r\r\n'),
                      'lf_count': blob.count(b'\n'), 'path': physical})
    if text is None:
        continue
    texts[key] = text
    # LF-indexed physical lines agree with rg -n even for CRCRLF input.
    for no, line in enumerate(text.split('\n'), 1):
        tags = [tag for tag, pattern in compiled.items() if pattern.search(line)]
        if tags:
            hits.append({'scope': scope, 'file': name, 'line': no, 'role': role,
                         'tags': ','.join(tags), 'text': line.strip()})

# The sensitive-data guard does not print values. It refuses raw hit publishing
# if a likely assigned credential appears in a matching line.
credential = re.compile(r'(?i)(?:bot_token|api_key|password|secret)\s*[=:]\s*[\x22\x27]([A-Za-z0-9_:\-]{20,})')
for row in hits:
    row['text'] = credential.sub(lambda m: m.group(0).replace(m.group(1), '[REDACTED]'), row['text'])

folded = collections.defaultdict(list)
for row in inventory:
    folded[(row['scope'], row['file'].casefold())].append(row['file'])
collisions = [v for v in folded.values() if len(v) > 1]
summary = {
    'at': datetime.now().astimezone().isoformat(), 'pinned_head': HEAD,
    'source_root': str(ROOT), 'operational_roots': {k: str(v) for k, v in scopes.items()},
    'scope_counts': dict(collections.Counter(r['scope'] for r in inventory)),
    'scanned_counts': dict(collections.Counter(r['scope'] for r in inventory if r['scanned'])),
    'role_hit_counts': dict(collections.Counter(r['role'] for r in hits)),
    'category_counts': dict(collections.Counter(t for r in hits for t in r['tags'].split(','))),
    'hit_lines': len(hits), 'hit_files': len(set((r['scope'], r['file']) for r in hits)),
    'fixtures': {k: bool(compiled[k].search(v)) for k, v in fixtures.items()},
    'known_real_line': known_lines, 'case_collisions': collisions,
    'missing_requested_msgs_root': 'D:/mai-wt/foothold-lab/lead-dispatch-measure/_out/msgs',
    'patterns': PATTERNS,
}
(OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
(OUT / 'matches.json').write_text(json.dumps(hits, ensure_ascii=False, indent=2), encoding='utf-8')
with (OUT / 'matches.csv').open('w', encoding='utf-8-sig', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=['scope', 'file', 'line', 'role', 'tags', 'text'])
    writer.writeheader(); writer.writerows(hits)
# Private local snapshot lets the analyst read exact pinned lines, never imported.
(OUT / 'texts.json').write_text(json.dumps(texts, ensure_ascii=False), encoding='utf-8')
print(json.dumps(summary, ensure_ascii=False, indent=2))

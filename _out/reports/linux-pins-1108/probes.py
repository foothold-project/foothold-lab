"""CPU-only portability counterexamples on the scan snapshot, no application boot."""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
from types import SimpleNamespace

BASE = Path('D:/mai-tmp/analyst/linux-pins-1108')
texts = json.loads((BASE / 'texts.json').read_text(encoding='utf-8'))
results = []

def record(name, observed, assertion):
    assert assertion, (name, observed)
    results.append({'name': name, 'observed': observed, 'pass': True})

def function(key, name, namespace):
    tree = ast.parse(texts[key])
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    code = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(code), key, 'exec'), namespace)
    return namespace[name]

record('windows_drive_is_relative_on_posix', str(PurePosixPath('C:/s2_lab/run')),
       not PurePosixPath('C:/s2_lab/run').is_absolute())
record('windows_backslash_is_filename_on_posix', list(PurePosixPath(r'C:\s2_lab\run').parts),
       len(PurePosixPath(r'C:\s2_lab\run').parts) == 1)
record('casefold_conflates_distinct_posix_paths', ['/runs/EX42', '/runs/ex42'],
       PurePosixPath('/runs/EX42') != PurePosixPath('/runs/ex42')
       and '/runs/EX42'.casefold() == '/runs/ex42'.casefold())
record('windows_manifest_logdir_cannot_equal_relocated_linux_parent',
       [str(PurePosixPath('/audit') / 'C:/s2_lab/run'), '/data/s2_lab/run'],
       PurePosixPath('/audit') / 'C:/s2_lab/run' != PurePosixPath('/data/s2_lab/run'))

require_d = function('S/foothold_s2/scripts/ex41_startup.py', '_require_d_drive', {'Path': PurePosixPath})
try:
    require_d('/data/s2_lab/run')
except ValueError as exc:
    record('actual_require_d_rejects_posix_absolute_path', str(exc), 'D:' in str(exc))
else:
    raise AssertionError('POSIX path unexpectedly accepted')

# Execute only the pure profile module; no project/Isaac imports are made.
profile_key = 'S/foothold_s2/machine_profile.py'
ns = {'__file__': str(BASE / 'machine_profile.py'), '__name__': 'audit_profile'}
exec(compile(texts[profile_key], profile_key, 'exec'), ns)
try:
    ns['_profile_path'](None, environ={}, platform='linux', repo_root=BASE)
except ValueError as exc:
    record('actual_profile_requires_explicit_posix_selection', str(exc), 'FOOTHOLD_MACHINE_PROFILE' in str(exc))
else:
    raise AssertionError('implicit profile selected')
linux_yaml = subprocess.check_output(['git', '-C', 'D:/mai-wt/foothold-lab/runner-ex42-resume-w65',
                                     'show', 'cc7586db:machines/AI-WS01-linux.yaml']).decode('utf-8')
fixture = BASE / 'linux-profile-fixture.yaml'
fixture.write_text(linux_yaml, encoding='utf-8')
names = re.findall(r'\$\{([^}]+)\}', linux_yaml)
all_env = {name: '/audit/' + name.lower() for name in names}
profile = ns['load_machine_profile'](profile=fixture, environ=all_env, platform='linux')
record('all_profile_references_resolve', {'env_count': len(names), 'paths': len(profile['paths'])},
       len(names) == len(profile['paths']))
missing = dict(all_env)
del missing['FOOTHOLD_BASH']
try:
    ns['load_machine_profile'](profile=fixture, environ=missing, platform='linux')
except ValueError as exc:
    record('unused_optional_reference_still_required', str(exc), 'FOOTHOLD_BASH' in str(exc))
else:
    raise AssertionError('missing optional env unexpectedly accepted')
bad_optional = dict(all_env, GPU_JOBS_QUEUE='D:/mai-tmp/gpu/queue.json')
accepted = ns['load_machine_profile'](profile=fixture, environ=bad_optional, platform='linux')
record('optional_windows_path_not_rejected_by_profile', accepted['paths']['gpu_queue'],
       accepted['paths']['gpu_queue'].startswith('D:/'))

locked_mode = 0o664 & ~stat.S_IWRITE
record('lock_checkout_leaves_group_write_permission', oct(locked_mode),
       locked_mode == 0o464 and bool(locked_mode & stat.S_IWGRP))

def absent_command(*args, **kwargs):
    raise FileNotFoundError('tasklist missing on POSIX fixture')
fake_subprocess = SimpleNamespace(run=absent_command, DEVNULL=-3)
tasklist = function('S/foothold_s2/eval/ex41_push250_watch.py', '_tasklist_process_name',
                    {'subprocess': fake_subprocess})
try:
    tasklist(123)
except FileNotFoundError as exc:
    record('actual_tasklist_fallback_propagates_missing_executable', str(exc), True)
else:
    raise AssertionError('missing tasklist was swallowed')

queue_tree = ast.parse(texts['O/gpu_jobs/queue_w28.py'])
values = {}
for node in queue_tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        if node.targets[0].id in ('GPU_UUIDS', 'DESKTOP_PROCESS_NAMES'):
            values[node.targets[0].id] = ast.literal_eval(node.value)
function('O/gpu_jobs/queue_w28.py', '_device_arg', values)
busy = function('O/gpu_jobs/queue_w28.py', 'compute_rows_busy', values)
rows = [f"GPU-{values['GPU_UUIDS'][1]}, 123, /usr/bin/chrome"]
linux_result = busy(1, rows, lambda _: ('chrome', ['chrome']))
win_result = busy(1, rows, lambda _: ('chrome.exe', ['chrome.exe']))
record('actual_queue_desktop_allowlist_windows_only', {'linux': linux_result, 'windows': win_result},
       linux_result[0] is False and win_result[0] is True)

record('raw_sha_changes_with_crlf', {'LF': hashlib.sha256(b'x\n').hexdigest(),
                                  'CRLF': hashlib.sha256(b'x\r\n').hexdigest()},
       hashlib.sha256(b'x\n').digest() != hashlib.sha256(b'x\r\n').digest())
record('normalized_sha_does_not_change_with_crlf', True,
       hashlib.sha256(b'x\n').digest() == hashlib.sha256(b'x\r\n'.replace(b'\r\n', b'\n')).digest())

result = {'kind': 'Windows-host CPU source/pure-path probes, not Linux or Kit execution',
          'source_head': 'cc7586db9f58b4bf43ef2ce5658e40bede3e7003',
          'passed': len(results), 'results': results}
(BASE / 'probes.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))

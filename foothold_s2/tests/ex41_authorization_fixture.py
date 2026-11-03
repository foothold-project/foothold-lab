"""Shared real-Git W72 fixture for producer and mirror consumer CPU tests.

The JSON with a/b/c digests is a rejection example, not authorization evidence.
Call this helper under pytest tmp_path, never an experiment or live ledger.
"""
import hashlib
import json
from pathlib import Path
import subprocess


def real_authorization(root: Path) -> dict:
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE).decode().strip()
    git('init', '-q')
    git('config', 'core.autocrlf', 'false')
    boundary = root / 'ex41-boundary.yaml'
    approval = root / 'ex41-approvals.yaml'
    boundary.write_bytes(b'format: foothold-ex41-boundary/1\nvalues:\n  critic_mirror: true\n  w71_ready: false\n')
    approval.write_bytes(b'format: foothold-ex41-approvals/1\nfields:\n  critic_mirror:\n    decision_id: D101\n    choices: [false, true]\nautomatic:\n  critic_mirror: D101\n')
    git('add', '--', boundary.name, approval.name)
    git('-c', 'user.name=CPU fixture', '-c', 'user.email=cpu@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'CPU W72 authorization fixture')
    value = json.loads((Path(__file__).parent/'fixtures/ex41_authorization.json').read_text())
    value.update(config_commit=git('rev-parse', 'HEAD'),
                 config_sha256=hashlib.sha256(boundary.read_bytes()).hexdigest(),
                 approval_sha256=hashlib.sha256(approval.read_bytes()).hexdigest(),
                 boundary_file=str(boundary), approval_file=str(approval))
    value['approval_id'] = value['approval_sha256']
    return value

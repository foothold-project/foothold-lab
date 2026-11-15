"""No Kit: the E1F launch source is separate from the 6b evaluation source and is never a fallback."""
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2.scripts import ex42_remeasure as batch
from foothold_s2.tests.test_ex42_remeasure_cpu import write, complete_job  # noqa: F401
from foothold_s2.tests import test_ex42_calibration_materialize_cpu as chain_tests

known = chain_tests.known
ready = chain_tests.ready
REPO = Path(__file__).resolve().parents[2]


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture(scope='module')
def launch_copy(tmp_path_factory):
    """A real detached, read-only copy of the committed HEAD, registered the way lead registers it."""
    root = tmp_path_factory.mktemp('launch') / 'copy'
    subprocess.run(['git', 'clone', '-q', '--shared', str(REPO), str(root)], check=True)
    git(root, 'checkout', '-q', '--detach', git(REPO, 'rev-parse', 'HEAD'))
    git(root, 'update-ref', 'refs/remotes/origin/testint', 'HEAD')
    lock = REPO / '_out/tools/ex41/lock_checkout.py'
    subprocess.run(['python3', str(lock), 'lock', str(root)], check=True, capture_output=True)
    out = root.parent / 'binding.json'
    doc = batch.register_launch(root, out, integration='origin/testint')
    request = {'source_git_head': git(root, 'rev-parse', 'HEAD~1')}
    return SimpleNamespace(root=root, binding=doc, request=request, out=out)


def check(copy, **changes):
    binding = {**copy.binding, **changes}
    return batch.check_launch(binding, copy.request, running_root=copy.root)


def test_registered_locked_copy_passes_and_names_its_pinned_ref(launch_copy):
    result = check(launch_copy)
    assert result['head'] == git(launch_copy.root, 'rev-parse', 'HEAD') and result['e1f_flag_share'] == 0.10
    assert launch_copy.binding['source_ref'] == 'origin/ex42-launch-' + result['head'][:8]
    assert git(launch_copy.root, 'rev-parse', 'refs/remotes/' + launch_copy.binding['source_ref']) == result['head']


def test_not_running_from_the_registered_root_is_refused(launch_copy):
    with pytest.raises(ValueError, match='not running from the registered launch root'):
        batch.check_launch(launch_copy.binding, launch_copy.request)       # this process runs from the repo, not the copy


def test_old_evaluation_head_is_never_a_launch_source(launch_copy):
    request = {'source_git_head': launch_copy.binding['launch_head']}
    with pytest.raises(ValueError, match='old evaluation source'):
        batch.check_launch(launch_copy.binding, request, running_root=launch_copy.root)


def test_launch_head_must_contain_the_evaluation_source(launch_copy):
    request = {'source_git_head': '0' * 40}
    with pytest.raises(ValueError, match='does not contain'):
        batch.check_launch(launch_copy.binding, request, running_root=launch_copy.root)


def test_registration_head_mismatch_and_wrong_format(launch_copy):
    with pytest.raises(ValueError, match='HEAD differs'):
        check(launch_copy, launch_head='1' * 40)
    with pytest.raises(ValueError, match='another format'):
        check(launch_copy, format='other')


def test_dirty_or_writable_copy_is_held(launch_copy):
    stray = launch_copy.root / 'stray.txt'
    stray.write_text('x')
    try:
        with pytest.raises(ValueError, match='dirty'):
            check(launch_copy)
    finally:
        stray.unlink()
    plan = launch_copy.root / 'foothold_s2/curriculum/ex42-prep.yaml'
    os.chmod(plan, plan.stat().st_mode | stat.S_IWRITE)
    try:
        with pytest.raises(ValueError, match='writable'):
            check(launch_copy)
    finally:
        os.chmod(plan, plan.stat().st_mode & ~stat.S_IWRITE)
    assert check(launch_copy)['head']


def test_pin_mismatch_of_plan_or_approvals_is_held(launch_copy):
    bad = {**launch_copy.binding['plan'], 'sha256': '2' * 64}
    with pytest.raises(ValueError, match='SHA differs'):
        check(launch_copy, plan=bad)
    bad = {**launch_copy.binding['approvals'], 'sha256': '3' * 64}
    with pytest.raises(ValueError, match='SHA differs'):
        check(launch_copy, approvals=bad)


def test_approvals_that_the_plan_does_not_pin_are_held(launch_copy):
    other = launch_copy.root / 'foothold_s2/curriculum/ex42-boundary.yaml'          # right SHA for itself, not the plan's pin
    with pytest.raises(ValueError, match='approval pin differs'):
        check(launch_copy, approvals=batch.ref(other))


def test_plan_outside_the_launch_root_is_held(launch_copy):
    elsewhere = launch_copy.root.parent / 'plan.yaml'
    elsewhere.write_bytes((launch_copy.root / 'foothold_s2/curriculum/ex42-prep.yaml').read_bytes())
    with pytest.raises(ValueError, match='inside the launch root'):
        check(launch_copy, plan=batch.ref(elsewhere))


@pytest.mark.parametrize('share,match', [(None, 'shares flag'), (0.2, 'shares flag')])
def test_plan_without_registered_flag_share_is_held(launch_copy, monkeypatch, share, match):
    from foothold_s2.commands import ex42_shares
    real = ex42_shares.read_contract
    def fake(plan, stage):
        contract = real(plan, stage)
        if share is None:
            return None
        contract['shares']['flag'] = share
        return contract
    monkeypatch.setattr(ex42_shares, 'read_contract', fake)
    with pytest.raises(ValueError, match=match):
        check(launch_copy)


@pytest.mark.parametrize('name,needle', [('foothold_s2/scripts/ex42_training_entry.py', 'CommandShares('),
                                          ('foothold_s2/scripts/train_start.py', 'ex42_shares')])
def test_source_that_does_not_consume_shares_is_held(launch_copy, monkeypatch, name, needle):
    monkeypatch.setattr('foothold_s2.ex42_gate_checks.audit_ex42_launch_source',
                        lambda root, remote_ref: {'launch_head': launch_copy.binding['launch_head']})
    path = launch_copy.root / name
    original = path.read_bytes()
    os.chmod(path, path.stat().st_mode | stat.S_IWRITE)
    path.write_bytes(original.replace(needle.encode(), b'REMOVED'))
    try:
        with pytest.raises(ValueError, match='does not consume command shares'):
            check(launch_copy)
    finally:
        path.write_bytes(original)
        os.chmod(path, path.stat().st_mode & ~stat.S_IWRITE)


def test_missing_binding_file_is_unregistered(tmp_path):
    with pytest.raises(ValueError, match='not registered'):
        batch.read_launch_binding(tmp_path / 'absent.json')
    with pytest.raises(ValueError, match='not registered'):
        batch.read_launch_binding(None)


def test_registration_requires_the_head_to_be_in_integration(launch_copy, tmp_path):
    git(launch_copy.root, 'update-ref', 'refs/remotes/origin/elsewhere', git(launch_copy.root, 'rev-parse', 'HEAD~1'))
    with pytest.raises(ValueError, match='not contained'):
        batch.register_launch(launch_copy.root, tmp_path / 'b.json', integration='origin/elsewhere')


def test_execute_without_launch_binding_is_refused_by_the_cli(tmp_path, capsys, monkeypatch):
    sent = []
    monkeypatch.setattr(batch, 'notify_hold', lambda output, reason, **kw: sent.append(reason) or {'sent': True})
    request = write(tmp_path / 'request.json', {'output': str(tmp_path / 'out')})
    assert batch.main(['--request', str(request), '--execute']) == 2
    assert 'launch-binding' in capsys.readouterr().err and sent


def test_unregistered_launch_source_holds_before_any_flag_chain_gpu_work(tmp_path, monkeypatch):
    gate = write(tmp_path / 'p1_score.json', {'state': 'complete', 'judgment': 'PASS', 'stage_id': 'E1',
                                              'checkpoint_iteration': 1000, 'checkpoint_sha256': '0' * 64,
                                              'plan_sha256': 'a' * 64})
    calls = []
    from foothold_s2.scripts import ex42_flag_baseline_chain as chain
    monkeypatch.setattr(chain, 'run_chain', lambda *a, **k: calls.append('FLAGS'))
    def refuse():
        raise ValueError('launch binding is not registered')
    with pytest.raises(ValueError, match='not registered'):
        batch.bridge({}, {'run': str(tmp_path)}, tmp_path, gate, guard=lambda: calls.append('GPU'), launch_check=refuse)
    assert calls == []


@pytest.mark.parametrize('state', ['gate_not_passed', 'launcher_started'])
def test_children_run_in_the_evaluation_root_and_bridge_gets_the_launch_check(tmp_path, complete_job, monkeypatch, state):
    from contextlib import contextmanager
    import shutil
    template, policy = complete_job
    root = tmp_path / 'batch'
    eval_root = tmp_path / 'six-b'
    dirs = {}
    for name in ('new', 'old', 'parent'):
        d = tmp_path / name; d.mkdir(); dirs[name] = d
        for n in batch.UPDATES:
            (d / f'model_{n}.pt').write_bytes(f'{name}-{n}'.encode())
        write(d / 'manifest.json', {'checkpoints': {f'model_{n}.pt': batch.sha(d / f'model_{n}.pt') for n in batch.UPDATES}})
    binding = {'run': str(dirs['new']), 'plan': {'path': '/new.yaml', 'sha256': 'c' * 64}, 'approvals': {'path': '/ap.yaml'},
               'manifest': {'path': str(dirs['new'] / 'manifest.json')}, 'startup': {'path': '/s.json'}, 'training_log': {'path': '/l'}}
    request = {'source_git_head': 'fixture', 'evaluation_plan': {'path': str(eval_root / 'foothold_s2/curriculum/eval.yaml'), 'sha256': policy},
               'evaluation_approvals': {'path': '/eval-ap.yaml'}, 'parent': {'path': str(dirs['parent'] / 'model_1000.pt')},
               'old': {'run': str(dirs['old']), 'plan': {'path': '/old.yaml', 'sha256': 'c' * 64}, 'approvals': {'path': '/ap.yaml'}},
               'output': str(root), 'python': '/cpu/python', 'mesh_dir': '/mesh', 'mesh_sha256': 'a' * 64,
               'launch_env': {'GPU_JOBS_QUEUE': '/queue', 'EX42_MAIN_ROOT': '/out', 'EX42_SOURCE_REF': 'fixture'},
               'retrain_binding': str(write(tmp_path / 'binding.json', {'run': str(dirs['new']), 'training_log': '/l', 'expected_plan_sha256': 'c' * 64}))}
    validated = []
    monkeypatch.setattr(batch, 'validate_request', lambda r, root=None: validated.append(root))
    monkeypatch.setattr(batch, 'training_done', lambda r: {'state': 'done'})
    monkeypatch.setattr(batch, 'source_binding', lambda *a: binding)
    monkeypatch.setattr(batch, 'checked', lambda r: Path(r['path']))
    @contextmanager
    def no_gpu(*a):
        yield lambda: None
    monkeypatch.setattr(batch, 'admission', no_gpu)
    monkeypatch.setattr(batch, 'notify_hold', lambda *a, **k: {'sent': True})
    cwds = []
    def child(argv, **kwargs):
        cwds.append(kwargs['cwd'])
        dest = Path(argv[argv.index('--out') + 1]); cp = Path(argv[argv.index('--checkpoint') + 1])
        dest.mkdir(parents=True)
        for p in Path(template['output']).glob('*.json'):
            shutil.copy2(p, dest / p.name)
        for sub in ('map64', 'axis_v2', 'stand_eval_gt', 'stand_eval_pred', 'stand_probe_prop_only', 'd44'):
            shutil.copytree(Path(template['output']) / sub, dest / sub)
        for name in ('ex42_score.json', 'eval_receipt.json', 'p1_score.json'):
            doc = batch.read(dest / name); doc['checkpoint_sha256'] = batch.sha(cp)
            if name == 'p1_score.json':
                doc.update(checkpoint_iteration=int(cp.stem.split('_')[-1]), measurement=str(dest / 'ex42_score.json'),
                           measurement_sha256=batch.sha(dest / 'ex42_score.json'),
                           plan_sha256=policy if len(cwds) == 1 else 'c' * 64)
            elif name == 'eval_receipt.json':
                doc['source_git_head'] = 'fixture'
            write(dest / name, doc)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(batch.subprocess, 'run', child)
    seen = {}
    def no_launch(req, bnd, out, gate, **kwargs):
        seen.update(kwargs)
        return {'state': state, 'training_started': state == 'launcher_started'}
    monkeypatch.setattr(batch, 'bridge', no_launch)
    watched = []
    monkeypatch.setattr(batch, 'watch_first_boundary', lambda req, out, **kw: watched.append((req, out)))
    batch.execute(request, launch_path=tmp_path / 'launch.json')
    assert (len(watched) == 1 and watched[0][1] == root) if state == 'launcher_started' else watched == []
    assert cwds == [eval_root] * 9 and all(v == eval_root for v in validated)
    assert callable(seen['launch_check'])
    with pytest.raises(ValueError, match='not registered'):
        seen['launch_check']()                      # the file does not exist: HOLD, no fallback


def _bridge_setup(ready, monkeypatch):
    """Known CPU trace as in the 6b bridge test, with a separate launch plan: dry-run cwd, source ref and template follow it."""
    import shutil
    from foothold_s2.scripts import ex42_flag_baseline_chain as flag_module
    from foothold_s2.scripts import ex42_e1_materialize_evidence as evidence_module
    root = ready['out'].parent / 'bridge'; root.mkdir()
    gate = batch.read(ready['gate_receipt'])
    gate['plan_sha256'] = batch.sha(ready['source_plan'])
    measured = Path(gate['measurement']); score = batch.read(measured)
    score['maintenance_source_sha256'] = batch.sha(ready['plan']); write(measured, score)
    gate['measurement_sha256'] = batch.sha(measured); write(ready['gate_receipt'], gate)
    ev = batch.read(ready['evidence']); ev['gate_sha256'] = batch.sha(ready['gate_receipt'])
    ev['source_plan_sha256'] = batch.sha(ready['source_plan'])
    ev['evaluation_plan'] = batch.ref(ready['plan'])
    ev['exposure_receipt'] = batch.ref(ready['parent_manifest'].parent / 'torchrun.stdout.log'); write(ready['evidence'], ev)
    chain = batch.read(ready['flag_chain']); chain['e1_gate']['sha256'] = batch.sha(ready['gate_receipt'])
    chain['e1_gate']['measurement_sha256'] = gate['measurement_sha256']; write(ready['flag_chain'], chain)
    mesh = Path(chain['mesh_dir']); write(mesh / 'terrain_manifest.json', {})
    # The launch source's own template pair: same bytes, in a different directory (as another integration copy would be).
    launch_root = ready['out'].parent / 'launch-root'
    curriculum = launch_root / 'foothold_s2/curriculum'; curriculum.parent.mkdir(parents=True)
    shutil.copytree(ready['plan'].parent, curriculum)
    launch_plan = curriculum / ready['plan'].name
    launch_approvals = curriculum / ready['approvals'].name
    with launch_plan.open('a') as stream:
        stream.write('\n# launch source copy\n')          # same content, other bytes: the template must be this file
    assert batch.sha(launch_plan) != batch.sha(ready['plan'])
    def produced(*args, **kwargs):
        assert kwargs['plan_path'] == ready['plan']           # evaluation policy stays the pinned plan
        target = args[1]; target.mkdir()
        shutil.copy2(ready['flag_chain'], target / 'chain_receipt.json')
        shutil.copy2(chain['w09_baseline']['path'], target / 'w09_baseline.json')
    def evidence(**kwargs):
        assert kwargs['evaluation_plan_path'] == ready['plan']
        shutil.copy2(ready['evidence'], kwargs['out_path'])
    monkeypatch.setattr(flag_module, 'run_chain', produced)
    monkeypatch.setattr(evidence_module, 'write_evidence', evidence)
    seen = {}
    def cpu(argv, **kwargs):
        seen.update(cwd=kwargs['cwd'], argv=argv)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(batch.subprocess, 'run', cpu)
    binding = {'run': str(ready['parent_manifest'].parent), 'plan': batch.ref(ready['source_plan']),
               'manifest': batch.ref(ready['parent_manifest']),
               'training_log': batch.ref(ready['parent_manifest'].parent / 'torchrun.stdout.log')}
    request = {'evaluation_plan': batch.ref(ready['plan']), 'evaluation_approvals': batch.ref(ready['approvals']),
               'mesh_dir': str(mesh), 'mesh_sha256': chain['mesh_sha256'], 'python': '/cpu/python',
               'launch_env': {'EX42_MESH_DIR': str(mesh), 'EX42_MESH_SHA256': chain['mesh_sha256'],
                              'GPU_JOBS_QUEUE': '/not-live-queue.json', 'EX42_SOURCE_REF': '6b8762dd',
                              'EX42_MAIN_ROOT': str(root / 'future-training')}}
    source = {'root': str(launch_root), 'head': 'h', 'plan': batch.ref(launch_plan), 'approvals': batch.ref(launch_approvals),
              'source_ref': 'origin/ex42-launch-abcdef12', 'e1f_flag_share': 0.10}
    return request, binding, root, source, seen, launch_root


# CG v0.17j (decisions.tsv 2026-11-12 11:28, 12:52, 13:03): E1 is restarted as one run of seven segments to 1750.
# The finished retrain run stopped at 1000, which is no exit boundary of that plan, so this bridge (adopt the retrain
# m1000 as the E1 graduate and start E1F) refuses. strict: the mark fails the suite if the bridge starts working again.
# Whether the bridge is removed or rebuilt for the new E1 end is the lead's decision.
RETRAIN_ADOPTION_CLOSED = pytest.mark.xfail(strict=True, reason="retrain m1000 is not an E1 exit under the 1750 plan")


@RETRAIN_ADOPTION_CLOSED
def test_bridge_starts_everything_from_the_launch_source(ready, monkeypatch):
    request, binding, root, source, seen, launch_root = _bridge_setup(ready, monkeypatch)
    result = batch.bridge(request, binding, root, ready['gate_receipt'], guard=lambda: None, launch=False,
                          launch_check=lambda: source)
    assert result['state'] == 'ready_not_started'
    assert seen['cwd'] == launch_root                         # never the process root nor the evaluation source
    assert '--ex42_source_ref=origin/ex42-launch-abcdef12' in seen['argv']
    transition = batch.read(root / 'E1F-materialized/transition.json')
    assert transition['template_plan_sha'] == batch.sha(source['plan']['path'])


class _Guard:
    released = False
    def __call__(self):
        pass
    def release(self):
        self.released = True


def _start_probe(monkeypatch):
    from foothold_s2 import ex42_stage_handoff as handoff
    started = []
    monkeypatch.setattr(handoff, 'start_launcher', lambda decision, launcher, *a, **k: started.append(launcher) or {'pid': 1})
    monkeypatch.setattr(handoff, 'register_launched_training', lambda *a, **k: {'registered': True})
    return started


@RETRAIN_ADOPTION_CLOSED
def test_launch_source_is_checked_again_right_before_the_start(ready, monkeypatch):
    request, binding, root, source, seen, launch_root = _bridge_setup(ready, monkeypatch)
    started = _start_probe(monkeypatch)
    calls, guard = [], _Guard()
    def check_launch():
        calls.append(1)
        if len(calls) == 2:
            raise ValueError('launch root went dirty after the CPU dry-run')
        return source
    with pytest.raises(ValueError, match='went dirty'):
        batch.bridge(request, binding, root, ready['gate_receipt'], guard=guard, launch_check=check_launch)
    assert len(calls) == 2 and started == [] and guard.released is False          # no marker released, nothing started


@RETRAIN_ADOPTION_CLOSED
def test_a_passing_second_check_starts_the_launcher_of_the_launch_root(ready, monkeypatch):
    request, binding, root, source, seen, launch_root = _bridge_setup(ready, monkeypatch)
    started = _start_probe(monkeypatch)
    calls, guard = [], _Guard()
    result = batch.bridge(request, binding, root, ready['gate_receipt'], guard=guard,
                          launch_check=lambda: calls.append(1) or source)
    assert result['state'] == 'launcher_started' and len(calls) == 2 and guard.released
    assert started == [launch_root / 'foothold_s2/scripts/ex42_stage_launcher.sh']


def _shares_doc(rank, it, n, flag, configured=0.10):
    return {'format': 'ex42-command-shares/1', 'iteration': it, 'rank': rank, 'world_size': 2,
            'configured': {'shares': {'flag': configured}},
            'cumulative': {'reset_modes': {'continuous': {'total': n, 'counts': {'free': n - flag, 'flag': flag}}}}}


def test_first_boundary_needs_both_ranks_and_reports_the_flag_fraction(tmp_path):
    write(tmp_path / 'command_shares_250_rank0.json', _shares_doc(0, 250, 4000, 410))
    assert batch.first_boundary_shares(tmp_path) is None                    # rank 1 not written yet
    write(tmp_path / 'command_shares_250_rank1.json', _shares_doc(1, 250, 4000, 389))
    got = batch.first_boundary_shares(tmp_path)
    assert got['iteration'] == 250 and got['near'] is True
    assert [r['flag_resets'] for r in got['ranks']] == [410, 389]
    assert got['ranks'][0]['flag_fraction'] == pytest.approx(0.1025)


@pytest.mark.parametrize('flag,configured', [(0, 0.10), (1200, 0.10), (400, 0.0)])
def test_first_boundary_flags_zero_wrong_or_unconfigured_share(tmp_path, flag, configured):
    write(tmp_path / 'command_shares_250_rank0.json', _shares_doc(0, 250, 4000, 400))
    write(tmp_path / 'command_shares_250_rank1.json', _shares_doc(1, 250, 4000, flag, configured))
    assert batch.first_boundary_shares(tmp_path)['near'] is False


def test_watch_reports_once_and_never_touches_the_run(tmp_path, monkeypatch):
    main = tmp_path / 'main'; run = main / 'EX-42-B-E1F_20261112_080000'; run.mkdir(parents=True)
    write(run / 'command_shares_250_rank0.json', _shares_doc(0, 250, 4000, 400))
    write(run / 'command_shares_250_rank1.json', _shares_doc(1, 250, 4000, 420))
    sent = []
    monkeypatch.setattr(batch, 'notify_hold', lambda output, reason, **kw: sent.append(reason) or {'sent': True})
    out = tmp_path / 'out'; out.mkdir()
    result = batch.watch_first_boundary({'launch_env': {'EX42_MAIN_ROOT': str(main)}}, out, started_after=0, limit=3,
                                        sleep=lambda s: None)
    assert result['near'] and sent and '근처' in sent[0] and (out / 'first-boundary-shares.json').is_file()


def test_watch_reports_a_run_that_ended_without_receipts(tmp_path, monkeypatch):
    main = tmp_path / 'main'; run = main / 'EX-42-B-E1F_20261112_080000'; run.mkdir(parents=True)
    write(run / 'train_start_status.json', {'state': 'failed'})
    sent = []
    monkeypatch.setattr(batch, 'notify_hold', lambda output, reason, **kw: sent.append(reason) or {'sent': True})
    out = tmp_path / 'out'; out.mkdir()
    assert batch.watch_first_boundary({'launch_env': {'EX42_MAIN_ROOT': str(main)}}, out, started_after=0, limit=3,
                                      sleep=lambda s: None) is None and 'ended without' in sent[0]


def test_out_of_band_flag_share_writes_a_hold_and_never_touches_the_training(tmp_path, monkeypatch):
    main = tmp_path / 'main'; run = main / 'EX-42-B-E1F_20261112_080000'; run.mkdir(parents=True)
    write(run / 'command_shares_250_rank0.json', _shares_doc(0, 250, 4000, 400))
    write(run / 'command_shares_250_rank1.json', _shares_doc(1, 250, 4000, 1200))
    sent, signals = [], []
    monkeypatch.setattr(batch, 'notify_hold', lambda output, reason, **kw: sent.append((kw['label'], reason)) or {'sent': True})
    monkeypatch.setattr(os, 'kill', lambda *a: signals.append(a))
    monkeypatch.setattr(os, 'killpg', lambda *a: signals.append(a))
    out = tmp_path / 'out'; out.mkdir()
    result = batch.watch_first_boundary({'launch_env': {'EX42_MAIN_ROOT': str(main)}}, out, started_after=0, limit=2,
                                        sleep=lambda s: None)
    hold = batch.read(out / 'first-boundary-HOLD.json')
    assert result['near'] is False and hold['state'] == 'HOLD' and hold['training_touched'] is False
    assert sent[0][0] == 'E1F 첫 경계 HOLD' and '팀장 승인' in sent[0][1] and signals == []


def test_in_band_share_writes_no_hold(tmp_path, monkeypatch):
    main = tmp_path / 'main'; run = main / 'EX-42-B-E1F_20261112_080000'; run.mkdir(parents=True)
    write(run / 'command_shares_250_rank0.json', _shares_doc(0, 250, 4000, 400))
    write(run / 'command_shares_250_rank1.json', _shares_doc(1, 250, 4000, 420))
    monkeypatch.setattr(batch, 'notify_hold', lambda *a, **k: {'sent': True})
    out = tmp_path / 'out'; out.mkdir()
    batch.watch_first_boundary({'launch_env': {'EX42_MAIN_ROOT': str(main)}}, out, started_after=0, limit=2, sleep=lambda s: None)
    assert not (out / 'first-boundary-HOLD.json').exists()

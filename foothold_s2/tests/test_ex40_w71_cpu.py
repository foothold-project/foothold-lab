"""W71 failure paths, known answers; no simulator or live run writes."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

from foothold_s2 import ex40_supervisor as supervisor
from foothold_s2 import ex40_score_watch as watch
from foothold_s2 import ex40_w57_retry as retry_mod
from foothold_s2.ex40_artifacts import cmp_link, reconstruction_summary
from foothold_s2.ex40_score import sha256
from foothold_s2.tests.test_ex40_scorer_cpu import _source, _pin, _state, _evidence, _axis
from foothold_s2.tests.test_ex40_w57_retry_cpu import _original


def test_hold_does_not_starve_next_checkpoint_or_become_consumed(tmp_path, monkeypatch):
    cp, _ = _source(tmp_path, update=500)
    out, scores = tmp_path / 'watch', tmp_path / 'scores'
    state = _state()
    def failed(checkpoint, folder, *_):
        _evidence(folder, checkpoint)
        return {'rc': 1, 'seconds': 0, 'receipt': {'state': 'failed'}}
    assert watch.process_once(tmp_path, out, scores, watch.DEFAULT_CONFIG, watch.DEFAULT_TABLE,
                              'B', state, evaluator=failed, sleep=lambda _: None)['state'] == 'HOLD'
    (out/'watch_state.json').write_text(json.dumps(state), encoding='utf8')
    cp2 = tmp_path/'model_750.pt'; cp2.write_bytes(b'next checkpoint'); _pin(tmp_path, cp2)
    calls = []
    def child(argv, **kwargs):
        calls.append(argv)
        assert kwargs['capture_output'] is True
        def evaluate(checkpoint, folder, *_):
            _evidence(folder, checkpoint)
            return {'rc': 0, 'seconds': 0, 'receipt': {'state': 'done'}}
        result = watch.process_once(tmp_path, out, scores, watch.DEFAULT_CONFIG, watch.DEFAULT_TABLE,
                                    'B', state, evaluator=evaluate, sleep=lambda _: None)
        (out/'watch_state.json').write_text(json.dumps(state), encoding='utf8')
        return SimpleNamespace(returncode=0, stdout=json.dumps({'evaluation': result}))
    monkeypatch.setattr(supervisor.subprocess, 'run', child)
    result = supervisor._score_until_checkpoint(tmp_path, out, scores, watch.DEFAULT_CONFIG,
                     watch.DEFAULT_TABLE, 'B', 750, sha256(cp2), max_calls=2)
    assert len(calls) == 1 and state['done']['750']['state'] == 'PASS'
    assert state['done']['500']['state'] == 'HOLD' and result == 'pending'
    # A changed old score remains blocked, not waived because it was HOLD.
    ledger = watch._ledger_rows(out)
    Path(ledger[0]['score_path']).write_text('{}', encoding='utf8')
    assert supervisor._score_until_checkpoint(tmp_path, out, scores, watch.DEFAULT_CONFIG,
                watch.DEFAULT_TABLE, 'B', 750, sha256(cp2), max_calls=1) == 'unknown'
    assert len(calls) == 1


def test_retry_receipt_written_and_failure_preserved(tmp_path):
    cp, prior = _original(tmp_path)
    old = (prior/'eval_receipt.json').read_bytes()
    def success(checkpoint, out, *_):
        _axis(out.parent, checkpoint)
        return 0
    row = retry_mod.retry(prior, cp, tmp_path/'retry', 'valid', runner=success)
    path = Path(row['evaluation_receipt'])
    receipt = json.loads(path.read_text(encoding='utf8'))
    assert receipt['state'] == 'done' and receipt['steps']['axis_v2']['rc'] == 0
    assert sha256(path) == row['evaluation_receipt_sha256']
    assert json.loads(Path(row['score_path']).read_text())['evaluation_receipt'] == str(path)
    def failure(*_):
        raise OSError('known child launch failure')
    bad = retry_mod.retry(prior, cp, tmp_path/'retry', 'failed', runner=failure)
    assert bad['child_rc'] == -1 and bad['verdict'] == 'HOLD'
    assert json.loads(Path(bad['evaluation_receipt']).read_text())['state'] == 'failed'
    assert (prior/'eval_receipt.json').read_bytes() == old


def test_hidden_retry_cpu_child_has_stdin_and_separate_logs(tmp_path, monkeypatch):
    stub = tmp_path/'child.py'
    stub.write_text("import sys; print('CPU stdout'); print('CPU stderr', file=sys.stderr); "
                    "assert sys.stdin.read() == ''; sys.exit(3)", encoding='utf8')
    monkeypatch.setattr(retry_mod, 'BASH', sys.executable)
    monkeypatch.setattr(retry_mod, 'AXIS', stub)
    rc = retry_mod._child(tmp_path/'model_1.pt', tmp_path/'axis_v2', 'cuda:1', {'map_steps': 300})
    assert rc == 3
    assert 'CPU stdout' in (tmp_path/'retry_stdout.log').read_text()
    assert 'CPU stderr' in (tmp_path/'retry_stderr.log').read_text()
    assert json.loads((tmp_path/'retry_command.json').read_text())['stdin'] == 'DEVNULL'


def test_training_text_log_is_separate_from_decision(tmp_path, monkeypatch):
    def spawn(argv, **kwargs):
        assert kwargs['stdin'] == supervisor.subprocess.DEVNULL
        kwargs['stdout'].write(b'known training stdout\n')
        return SimpleNamespace(pid=123)
    monkeypatch.setattr(supervisor.subprocess, 'Popen', spawn)
    assert supervisor._training_child([], tmp_path).pid == 123
    receipt = json.loads(next(tmp_path.glob('*.process.json')).read_text())
    assert Path(receipt['log']).read_bytes() == b'known training stdout\n'
    assert not (tmp_path/'supervisor_result.json').exists()


def test_reconstruction_summary_known_cm_and_missing(tmp_path):
    path = tmp_path/'map_modes.json'; array = tmp_path/'env.npz'
    zeros = np.zeros(2)
    np.savez(array, env=np.arange(2), kind=np.array(['stairs','stairs']), terrain_level=np.array([0,1]),
             map_err_inrange_mean_cm=[2.,4.], map_err_inrange_cellmax_cm=[3.,5.],
             map_err_all_mean_cm=[10.,20.], map_err_all_cellmax_cm=[11.,21.],
             map_err_gt_sat_frac_mean=[.1,.2], map_err_ray_miss_frac_mean=zeros,
             map_err_clip_low_frac_mean=[.1,.2], map_err_nonfinite_cells_total=zeros,
             map_err_nonfinite_steps=zeros)
    data = {'checkpoint_sha256':'a'*64, 'envs':2, 'modes':{'eval_pred':{'fwd1.0':{
        'per_env':[{'env':0,'kind':'stairs','level':0},{'env':1,'kind':'stairs','level':1}]}}},
        'env_arrays':{'eval_pred/fwd1.0':array.name}}
    path.write_text(json.dumps(data))
    row = reconstruction_summary(path, 'a'*64)
    assert row['state'] == 'complete'
    groups = row['cases']['eval_pred/fwd1.0']['by_level_kind']
    assert groups['0']['stairs']['a_mean_of_mean_cm'] == 2
    assert groups['1']['stairs']['b_mean_of_mean_cm'] == 20
    data['env_arrays'] = {}; path.write_text(json.dumps(data))
    assert reconstruction_summary(path,'a'*64)['state'] == 'incomplete'


def test_cmp_requires_exact_files_hash_and_all_frames(tmp_path):
    video=tmp_path/'CMP-test.mp4'; video.write_bytes(b'known video bytes, not rendered')
    request={'request_sha256':'a'*64, 'checkpoint_sha256':'b'*64, 'comparison_sha256':'c'*64,
             'expected_files':[video.name]}
    item={'path':str(video),'sha256':sha256(video), 'frame_review':{
          'video_sha256':sha256(video),'frames':100,'checked_frames':100,'expected_frames':100,'issues':[]}}
    receipt={**request, 'format':'foothold-cmp-delivery/1', 'state':'done', 'files':{video.name:item}}
    path=tmp_path/'cmp.json'
    path.write_text(json.dumps(receipt))
    assert cmp_link(request,path)['state'] == 'linked'
    for bad in ({**receipt,'files':{}},{**receipt,'checkpoint_sha256':'d'*64}):
        path.write_text(json.dumps(bad)); assert cmp_link(request,path)['state'] == 'pending'
    bad=copy.deepcopy(receipt); bad['files'][video.name]['frame_review']['issues']=['black_frame']
    path.write_text(json.dumps(bad)); assert cmp_link(request,path)['state'] == 'pending'
    path.write_text(json.dumps(receipt)); video.write_bytes(b'changed')
    assert cmp_link(request,path)['state'] == 'pending'
    assert cmp_link(request,None)['state'] == 'pending'

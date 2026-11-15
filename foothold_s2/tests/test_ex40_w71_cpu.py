"""W71 failure paths, known answers; no simulator or live run writes."""
import copy
import json
import subprocess
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

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


@pytest.mark.skipif(sys.platform!='win32',reason='Windows hidden-process inheritance contract')
def test_hidden_python_to_git_bash_hash_detects_missing_devnull(tmp_path):
    from foothold_s2.ex40_eval_once import BASH, ROOT
    assert BASH.is_file(), 'Git Bash is required for the real two-stage Windows test'
    cp=tmp_path/'model_1.pt';cp.write_bytes(b'known CPU checkpoint for hidden hash')
    script=tmp_path/'hash.sh'
    script.write_text('#!/bin/bash\nsha256sum "$1"\n',encoding='utf-8',newline='\n')
    parent=tmp_path/'parent.py'
    parent.write_text('''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from foothold_s2 import ex40_w57_retry as retry
retry.AXIS=Path(sys.argv[2])
original=retry.subprocess.run
if sys.argv[5]=='omit':
    def without_stdin(*args,**kwargs):
        kwargs.pop('stdin',None)
        return original(*args,**kwargs)
    retry.subprocess.run=without_stdin
rc=retry._child(Path(sys.argv[3]),Path(sys.argv[4])/'axis_v2','cuda:1',{'map_steps':1})
(Path(sys.argv[4])/'parent_result.json').write_text(json.dumps({'rc':rc}))
''',encoding='utf-8')
    flags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP
    results={}
    for mode in ('omit','fixed'):
        out=tmp_path/mode;out.mkdir()
        # V1: no std handle arguments at all. Redirecting even stdout would
        # reintroduce pytest's valid stdin handle and hide the regression.
        proc=subprocess.run([sys.executable,str(parent),str(ROOT),str(script),str(cp),str(out),mode],
                            cwd=ROOT,creationflags=flags,close_fds=True,check=False)
        assert proc.returncode==0
        results[mode]=json.loads((out/'parent_result.json').read_text())['rc']
    assert results=={'omit':1,'fixed':0}
    assert (tmp_path/'fixed/retry_stdout.log').read_text().lstrip('\\').split()[0]==sha256(cp)
    assert 'Bad file descriptor' in (tmp_path/'omit/retry_stderr.log').read_text()


@pytest.mark.skipif(sys.platform!='win32',reason='Windows score-watch V1 path')
def test_score_watch_hidden_eval_parent_hash_checks_real_result(tmp_path,monkeypatch):
    # Replace the Kit program only. Preserve _child's real launch kwargs so
    # this covers score_watch -> hidden eval parent -> hidden Git Bash.
    cp=tmp_path/'model_1.pt';cp.write_bytes(b'known score watch checkpoint')
    stub=tmp_path/'cpu_eval_once.py'
    stub.write_text('''import json,subprocess,sys
from pathlib import Path
cp,out=Path(sys.argv[1]),Path(sys.argv[2]);out.mkdir(parents=True)
flags=subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP
result=subprocess.run(['C:/Program Files/Git/bin/bash.exe','-c',
    'sha256sum "$1"; echo sha_rc=$?', '--',str(cp)],
    creationflags=flags,capture_output=True,text=True)
lines=result.stdout.splitlines()
row={'bash_rc':result.returncode,'sha_rc':int(next(x for x in lines if x.startswith('sha_rc=')).split('=')[1]),
     'stdout':result.stdout,'stderr':result.stderr}
(out/'eval_receipt.json').write_text(json.dumps(row))
''',encoding='utf-8')
    real_run=subprocess.run
    def cpu_child(argv,**kwargs):
        assert argv[1:3]==['-m','foothold_s2.ex40_eval_once']
        return real_run([sys.executable,str(stub),str(cp),str(tmp_path/'eval')],**kwargs)
    monkeypatch.setattr(watch.subprocess,'run',cpu_child)
    row=watch._child(cp,tmp_path/'eval','B0','B',Path('unused-cfg'),Path('unused-table'))
    assert row['rc']==0 and row['receipt']['bash_rc']==0
    assert row['receipt']['sha_rc']==0,row['receipt']
    assert row['receipt']['stdout'].lstrip('\\').split()[0]==sha256(cp)


def test_both_report_sender_paths_supply_devnull_without_external_send(tmp_path,monkeypatch):
    from foothold_s2 import ex40_stage_publish as publish
    score_path=tmp_path/'score.json'
    row={'checkpoint_iteration':500,'checkpoint_sha256':'a'*64,'from':'B0','verdict':'PASS'}
    score_path.write_text(json.dumps(row))
    monkeypatch.setattr(watch,'config',lambda _: {})
    monkeypatch.setattr(watch,'Plan',lambda *_,**__:None)
    monkeypatch.setattr(watch,'stage_end_updates',lambda *_:{500:'B0'})
    monkeypatch.setattr(watch,'_ledger_rows',lambda _:[{'checkpoint_iteration':500,'stage':'B0',
        'verdict':'PASS','score_path':str(score_path),'score_sha256':sha256(score_path)}])
    monkeypatch.setattr(watch,'build_stage_report',lambda *_,**__:{**row,
        'gains':[],'losses':[],'unchanged':[],'current':{'source_sha256':{}}})
    monkeypatch.setattr(watch,'stage_markdown',lambda _:'CPU report')
    sender=tmp_path/'cpu_sender.py';sender.write_text("import sys; assert sys.stdin.read()==''; print('0 CPU only')")
    original=subprocess.run;calls=[]
    def checked(argv,**kwargs):
        assert kwargs['stdin']==subprocess.DEVNULL
        calls.append(argv)
        return original(argv,**kwargs)
    monkeypatch.setattr(watch.subprocess,'run',checked)
    result=watch.stage_reports(tmp_path,tmp_path/'out',Path('unused'),Path('unused'),'B',telegram_sender=sender)
    assert result['state']=='done' and result['published']==1
    assert publish._send(score_path,sender)
    assert len(calls)==2


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


def test_retry_uses_checkpoint_preflight_and_records_failed_hash(tmp_path,monkeypatch):
    checkpoint,prior=_original(tmp_path)
    calls=[]
    real_hash=retry_mod.hash_checkpoint
    def measured_hash(path,receipt):
        calls.append((path,receipt))
        return real_hash(path,receipt)
    monkeypatch.setattr(retry_mod,'hash_checkpoint',measured_hash)
    row=retry_mod.retry(prior,checkpoint,tmp_path/'retry','hashed',runner=lambda *_:1)
    receipt=json.loads(Path(row['evaluation_receipt']).read_text())
    proof=receipt['checkpoint_preflight']
    assert len(calls)==1 and proof['checkpoint_sha256']==sha256(checkpoint)
    assert sha256(Path(proof['path']))==proof['sha256']
    assert Path(proof['path']).read_text().startswith(sha256(checkpoint))
    monkeypatch.setattr(retry_mod,'hash_checkpoint',lambda *_:(_ for _ in ()).throw(OSError('known hash failure')))
    started=[]
    failed=retry_mod.retry(prior,checkpoint,tmp_path/'retry','hash-failed',runner=lambda *_:started.append(True))
    receipt=json.loads(Path(failed['evaluation_receipt']).read_text())
    assert not started and receipt['state']=='failed'
    assert receipt['steps']['axis_v2']['rc']==-1
    assert 'known hash failure' in receipt['steps']['axis_v2']['error']
    assert receipt['checkpoint_preflight']['sha256'] is None


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


def _cmp_fixture(tmp_path):
    video=tmp_path/'CMP-test.mp4'; video.write_bytes(b'known video bytes, not rendered')
    current=tmp_path/'model_2000.pt';current.write_bytes(b'known current checkpoint')
    parent=tmp_path/'model_1500.pt';parent.write_bytes(b'known comparison checkpoint')
    payload={'format':'foothold-cmp-request/1','checkpoint_path':str(current),
             'checkpoint_sha256':sha256(current),'comparison_path':str(parent),
             'comparison_sha256':sha256(parent),'expected_files':[video.name]}
    request_path=tmp_path/'request.json';request_path.write_text(json.dumps(payload))
    request={**payload,'request_path':str(request_path),'request_sha256':sha256(request_path)}
    item={'path':str(video),'sha256':sha256(video), 'frame_review':{
          'video_sha256':sha256(video),'frames':100,'checked_frames':100,'expected_frames':100,'issues':[]}}
    receipt={**request, 'format':'foothold-cmp-delivery/1', 'state':'done', 'files':{video.name:item}}
    path=tmp_path/'cmp.json'
    path.write_text(json.dumps(receipt))
    return request,receipt,path,video


def test_cmp_requires_exact_files_hash_and_all_frames(tmp_path):
    request,receipt,path,video=_cmp_fixture(tmp_path)
    assert cmp_link(request,path)['state'] == 'linked'
    for bad in ({**receipt,'files':{}},{**receipt,'checkpoint_sha256':'d'*64}):
        path.write_text(json.dumps(bad)); assert cmp_link(request,path)['state'] == 'pending'
    bad=copy.deepcopy(receipt); bad['files'][video.name]['frame_review']['issues']=['black_frame']
    path.write_text(json.dumps(bad)); assert cmp_link(request,path)['state'] == 'pending'
    path.write_text(json.dumps(receipt)); video.write_bytes(b'changed')
    assert cmp_link(request,path)['state'] == 'pending'
    assert cmp_link(request,None)['state'] == 'pending'


@pytest.mark.parametrize('key',['request_sha256','checkpoint_sha256','comparison_sha256'])
@pytest.mark.parametrize('value',[None,'','bad','z'*64,'0'*64])
def test_cmp_equal_invalid_or_forged_identities_never_link(tmp_path,key,value):
    request,receipt,path,_=_cmp_fixture(tmp_path)
    request[key]=value;receipt[key]=value
    path.write_text(json.dumps(receipt))
    assert cmp_link(request,path)['state']=='pending'


@pytest.mark.parametrize('key',['request_path','checkpoint_path','comparison_path'])
def test_cmp_rechecks_real_request_and_checkpoint_bytes(tmp_path,key):
    request,receipt,path,_=_cmp_fixture(tmp_path)
    Path(request[key]).write_bytes(b'changed actual source bytes')
    assert cmp_link(request,path)['state']=='pending'


def test_cmp_stage_report_uses_the_same_current_and_parent(tmp_path,monkeypatch):
    from foothold_s2 import ex40_stage_report as report
    request,_,path,_=_cmp_fixture(tmp_path)
    monkeypatch.setattr(report,'snapshot',lambda _:{'w15':{},'w57':{}})
    monkeypatch.setattr(report,'dr_readback',lambda *_:{})
    current={'from':'B1','checkpoint_iteration':2000,'checkpoint_sha256':request['checkpoint_sha256'],
             'cmp_request':request,'cmp_receipt':str(path)}
    previous={'from':'B0','checkpoint_iteration':1500,'checkpoint_sha256':request['comparison_sha256']}
    assert report.build(current,previous,tmp_path)['cmp']['state']=='linked'
    for side in ('current','previous'):
        a,b=copy.deepcopy(current),copy.deepcopy(previous)
        (a if side=='current' else b)['checkpoint_sha256']='0'*64
        assert report.build(a,b,tmp_path)['cmp']['state']=='pending'

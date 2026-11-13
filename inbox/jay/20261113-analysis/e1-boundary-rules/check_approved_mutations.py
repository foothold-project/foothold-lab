"""Small isolated mutation checks for de8. Assertion failures only count as killed."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

MUTANTS=[
 ('off60_exclusive','boundary_approved.py',"state='PASS' if survival>=60 else 'FAIL'","state='PASS' if survival>60 else 'FAIL'"),
 ('off_one_failure_rollback','boundary_approved.py',"if type(old.get('survival')) is int and old['survival']<60:twice.append(key)","twice.append(key)"),
 ('off_different_boundary','boundary_approved.py',"previous.get('iteration')==now['iteration']-250","True"),
 ('off_valid63','boundary_approved.py',"valid!=64","valid<48"),
 ('off_different_condition','boundary_approved.py'," or old.get('fingerprint')!=row.get('fingerprint')",""),
 ('one_deficit_enough','boundary_approved.py',"all(a[k]>b[k]>c[k] for k in bad)","any(a[k]>b[k]>c[k] for k in bad)"),
 ('other_regression_ignored','boundary_approved.py',"others_stable=all(b[k]<=a[k] and c[k]<=b[k] for k in c if k not in bad)","others_stable=True"),
 ('exit_one_window','boundary_approved.py',"if passed(now) and passed(previous):","if passed(now):"),
 ('treatment_pin_ignored','boundary_approved.py',"now['treatment_sha256']!=previous.get('treatment_sha256')","False"),
 ('rollback_overwritten_by_reward','boundary_approved.py',"elif off['state']=='ROLLBACK':","elif False:"),
 ('retroactive_application','boundary_approved.py',"if now['iteration']<effective_from:","if False:"),
 ('record_used_as_active_window','boundary_approved.py',"off_previous=None","off_previous=previous"),
 ('curve_boundary_shift','curve_read.py',"def summarize_events(events,iteration,window=250,desired_kl=.01):",
  "def summarize_events(events,iteration,window=250,desired_kl=.01):\n    iteration += 1"),
 ('curve_old_duplicate_wins','curve_read.py',"wall>latest[key][0]","wall<latest[key][0]"),
]


def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=True);src=Path(__file__).parent;rows=[]
    with tempfile.TemporaryDirectory(dir=a.out,prefix='de8-') as temp:
        for name,file,old,new in [('control',None,None,None),*MUTANTS]:
            dest=Path(temp)/name;dest.mkdir()
            for f in ('boundary_approved.py','curve_read.py','test_boundary_approved.py','test_curve_read.py'):
                shutil.copyfile(src/f,dest/f)
            if file:
                body=(dest/file).read_text();assert body.count(old)==1,(name,body.count(old))
                (dest/file).write_text(body.replace(old,new))
            r=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(dest/'tmp')],cwd=dest,
                capture_output=True,text=True,env={**os.environ,'CUDA_VISIBLE_DEVICES':'','PYTHONDONTWRITEBYTECODE':'1'})
            text=r.stdout+r.stderr;(a.out/(name+'.log')).write_text(text)
            killed=r.returncode==1 and 'AssertionError' in text and 'ERROR collecting' not in text
            rows.append(dict(name=name,rc=r.returncode,killed=killed if file else None,control_pass=r.returncode==0 if not file else None))
    result={'control_pass':rows[0]['control_pass'],'killed':sum(r['killed'] is True for r in rows),'total':len(MUTANTS),'results':rows}
    (a.out/'mutations.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return 0 if result['control_pass'] and result['killed']==result['total'] else 1

if __name__=='__main__':raise SystemExit(main())

import os,json,sys,shutil,subprocess,tempfile,hashlib
from pathlib import Path
import argparse, io, tarfile
parser=argparse.ArgumentParser(description="H1/H2 isolated CPU counterexamples and mutations; v24 base")
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args()
REPO=Path(__file__).resolve().parents[4]
OUT=args.out.resolve()
if 's2_lab' in OUT.parts or OUT.is_relative_to(REPO):
 parser.error('output must be scratch outside the repository and training/evaluation data')
OUT.mkdir(parents=True,exist_ok=True)
BASE=OUT/'v24-overlay'
BASE.mkdir(exist_ok=True)
RULES=REPO/'inbox/jay/20261113-analysis/e1-boundary-rules'
archive=subprocess.check_output(['git','-C',str(REPO),'archive','a19cd6a2','foothold_s2','experiments','machines'])
with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:bundle.extractall(BASE,filter='data')
for name in ['foothold_s2/ex42_e1_v2.py','foothold_s2/tests/test_ex42_e1_v2_cpu.py',
             'foothold_s2/tests/test_ex42_e1_source_identity_cpu.py','foothold_s2/tests/fixtures/ex42-e1-v24-treatment.json']:
 dst=BASE/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/name,dst)
# Apply the only adapter hunk to v24, preserving its imports and other owners' code.
p=BASE/'foothold_s2/ex42_stage_judges.py'
s=p.read_text();old='        score["e1_v2_cells"] = measure_cells(ctx.evaluation, ctx.checkpoint_sha, ctx.seed)\n'
if s.count(old)!=1:raise RuntimeError('v24 adapter mutation site differs')
p.write_text(s.replace(old,''))
V='foothold_s2/ex42_e1_v2.py'
mutants=[
 ('h1_checkpoint',V,'identity.get("checkpoint_sha256") != checkpoint_sha','False','test_foreign_identity_known_answer_without_external_files'),
 ('h1_seed',V,'identity["eval_seed"] != seed','False','test_foreign_identity_known_answer_without_external_files'),
 ('h1_header',V,'    _identity(doc.get("run_identity"), checkpoint_sha, seed)\n','    pass\n','test_source_header_must_match_its_own_run_receipt'),
 ('h1_receipt_plan',V,'any(row.get("plan_sha256") != plan_sha for row in (commands, rewards, rank1))','False','test_valid_treatment_requires_startup_and_caller_plan_pins'),
 ('h1_startup_plan',V,'expected_plan_sha256 is not None and plan_sha != expected_plan_sha256','False','test_valid_treatment_requires_startup_and_caller_plan_pins'),
 ('h1_cached',V,'if "e1_v2_cells" in score and actual != score["e1_v2_cells"]:','if False:','test_actual_m250_raw_values_survive_identity_validation'),
 ('h2_plain_bytes','boundary_read.py',"measured=recompute(r,d['sources'],checkpoint)","measured=d['feet']",'test_plain_text_with_valid_sha_is_not_contact_evidence'),
 ('h2_schema','r5_contact.py',"z['format'].item() != RAW_FORMAT","False",'test_well_hashed_but_wrong_measurement_stays_invalid'),
 ('h2_checkpoint','r5_contact.py',"identity.get('checkpoint_sha256') != checkpoint","False",'test_well_hashed_but_wrong_measurement_stays_invalid'),
 ('h2_foot_order','r5_contact.py',"z['foot_names'].tolist() != list(FEET)","False",'test_well_hashed_but_wrong_measurement_stays_invalid'),
 ('h2_norm_vs_fz','r5_contact.py','np.linalg.norm(force, axis=-1) > 1.0','force[...,2] > 1.0','test_known_contact_raw_is_recomputed_not_just_hashed'),
 ('h2_declared_metrics','boundary_read.py','if not finite(declared) or not math.isclose(declared,value,rel_tol=1e-8,abs_tol=1e-10):','if False:','test_declared_foot_statistics_cannot_override_raw'),
]
results=[]
with tempfile.TemporaryDirectory(prefix='h1h2-mutants-',dir=OUT) as temp:
 for group in ('h1','h2'):
  root=Path(temp)/group
  if group=='h1':shutil.copytree(BASE,root,ignore=shutil.ignore_patterns('__pycache__'))
  else:shutil.copytree(RULES,root,ignore=shutil.ignore_patterns('__pycache__'))
  tests=['foothold_s2/tests/test_ex42_e1_source_identity_cpu.py'] if group=='h1' else ['test_r5_contact_provenance.py']
  for name,file,old,new,target in [(group+'_control',None,None,None,None),*(x for x in mutants if x[0].startswith(group))]:
   path=root/file if file else None
   if path:
    original=path.read_text()
    if original.count(old)!=1:raise RuntimeError((name,'mutation site count',original.count(old)))
    path.write_text(original.replace(old,new))
   cmd=[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider','--basetemp',str(Path(temp)/('pytest_'+name)),*tests]
   if target:cmd+=['-k',target]
   proc=subprocess.run(cmd,cwd=root,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','CUDA_VISIBLE_DEVICES':''},capture_output=True,text=True)
   (OUT/(name+'.log')).write_text(proc.stdout+proc.stderr)
   if path:path.write_text(original)
   good=proc.returncode==0 if target is None else proc.returncode==1 and ('AssertionError' in proc.stdout or 'DID NOT RAISE' in proc.stdout) and target in proc.stdout and 'ERROR collecting' not in proc.stdout
   results.append(dict(name=name,expected_observed=good,rc=proc.returncode,summary=proc.stdout.strip().splitlines()[-1]))
   print(name,good,flush=True)
(OUT/'mutations.json').write_text(json.dumps(dict(base_ref='a19cd6a2', source_sha256={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [REPO/V,RULES/'boundary_read.py',RULES/'r5_contact.py']}, results=results),indent=2)+'\n')
sys.exit(0 if all(x['expected_observed'] for x in results) else 1)

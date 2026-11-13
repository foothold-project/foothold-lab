"""Read-only overlay for de8a3b7f. No thresholds inferred from the new results."""
from copy import deepcopy
import math
import re

LEDGER='de8a3b7f09b3834ef4ced39f2069802c095b80b2'


def off_monitor(now, previous=None):
    rows=[];missing=[];twice=[]
    adjacent=previous is not None and previous.get('iteration')==now['iteration']-250
    for key, row in sorted(now.get('off_cells',{}).items()):
        valid=row.get('valid');survival=row.get('survival')
        if type(valid) is not int or valid!=64 or type(survival) is not int or not 0<=survival<=64:
            missing.append(key);continue
        old=previous.get('off_cells',{}).get(key) if adjacent else None
        state='PASS' if survival>=60 else 'FAIL'
        if state=='FAIL' and old:
            if previous.get('errors') or old.get('valid')!=64 or old.get('fingerprint')!=row.get('fingerprint'):
                missing.append(key+':previous_conditions');continue
            if type(old.get('survival')) is int and old['survival']<60:twice.append(key)
        rows.append(dict(cell=key,survival=survival,valid=valid,minimum=60,judgement=state,
                         previous=(old or {}).get('survival'),tracking_role='record_only'))
    if not now.get('off_cells'):missing.append('off_cells_missing')
    state=('HOLD' if missing else 'ROLLBACK' if twice else
           'SINGLE_FAIL_RECORD' if any(r['judgement']=='FAIL' for r in rows) else 'PASS')
    return dict(state=state,items=rows,missing=missing,rollback_cells=twice)


def diagnosis(audit):
    pairs={}
    for key,row in audit.get('cells',{}).items():
        for mode in ('eval_gt','eval_pred'):
            if re.search(r'(?<![a-z])'+mode+r'(?![a-z])',key):
                name=key.replace('/'+mode,'').removesuffix('_'+mode)
                pairs.setdefault(name,{})[mode]=row.get('judgement')
    out=[]
    for key,pair in sorted(pairs.items()):
        gt,pred=pair.get('eval_gt'),pair.get('eval_pred')
        label=('정책·과제 점검' if gt=='FAIL' else '지각 경로 점검' if gt=='PASS' and pred=='FAIL'
               else '둘 다 통과' if gt==pred=='PASS' else '미확인')
        out.append(dict(cell=key,GT=gt,PRED=pred,interpretation=label,
                        cause_proven=False))
    return out


def complete(audit):
    if not audit or audit.get('errors') or not audit.get('required_complete'):return False
    if not audit.get('cells'):return False
    return all(row.get('valid',64)==64 for row in audit['cells'].values())


def passed(audit):
    return (complete(audit) and audit.get('all_judge_pass') is True
            and all(row.get('judgement')=='PASS' for row in audit['cells'].values())
            and off_monitor(audit)['state']=='PASS')


def departure(now,previous,earlier,extension):
    n=now['iteration']
    out=dict(next_segment='CONTINUE_BOUNDARY_REVIEW',reason='m1750 출구 전',extension_updates=0,
             rule_commit=LEDGER,diagnostics=['걸음 접촉','곡선','같은 조건 seed7·13'])
    if n<1750:return out
    out.update(next_segment='HOLD_DIAGNOSE',reason='출구 증거 부족 또는 미통과')
    if not complete(now) or not complete(previous) or previous['iteration']!=n-250:return out
    if (not now.get('treatment_sha256') or now['treatment_sha256']!=previous.get('treatment_sha256')
            or not now.get('evaluation_sha256') or now['evaluation_sha256']!=previous.get('evaluation_sha256')):
        out['reason']='두 창 처방 또는 평가 기준 불일치';return out
    if passed(now) and passed(previous):
        out.update(next_segment='E1F',reason='두 연속 창 판정 칸 통과. 보상 이어받기·깃발 사슬은 운영 소비자 몫')
        return out
    if n!=1750:
        out['reason']='+250 연장 1회 한도. 추가 연장 자동 승인 없음';return out
    if not complete(earlier) or earlier['iteration']!=1250:return out
    if (not extension or extension.get('state')!='PASS'
            or earlier.get('evaluation_sha256')!=now.get('evaluation_sha256')
            or earlier.get('treatment_sha256')!=now.get('treatment_sha256')):
        out['reason']='v26 영수증·세 창 같은 처방·같은 기준 증거 부족';return out
    a,b,c=(x.get('gaps',{}) for x in (earlier,previous,now))
    if not c or set(a)!=set(b) or set(b)!=set(c):return out
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0
           for part in (a,b,c) for v in part.values()):return out
    bad=[key for key in c if c[key]>0]
    # Require EVERY currently deficient metric, not v26's ANY deficient metric.
    improved=bool(bad) and all(a[k]>b[k]>c[k] for k in bad)
    others_stable=all(b[k]<=a[k] and c[k]<=b[k] for k in c if k not in bad)
    out['extension_check']=dict(deficient=bad,all_improved_twice=improved,others_no_regression=others_stable)
    if improved and others_stable:
        out.update(next_segment='E1_EXTEND_250_ONCE',extension_updates=250,
                   reason='v26 증거 + 미달 칸 전부 두 번 기준 쪽·다른 칸 비악화. 연장 1회 초안')
    return out


def apply_approved(core,now,previous,earlier,treatment,extension,effective_from=1000):
    if effective_from not in (750,1000):raise ValueError('approved activation must be 750 or 1000')
    out=deepcopy(core);out['approved_rule_commit']=LEDGER
    # Historical windows are record-only. The first active pair is 1000/1250.
    off_previous=previous
    if now['iteration']>=effective_from and previous and previous['iteration']<effective_from:
        off_previous=None
    off=off_monitor(now,off_previous)
    out['map_off_survival']=off;out['GT_PRED_diagnosis']=diagnosis(now)
    out['L9_reached_record']=now.get('wide',{})
    gate=departure(now,previous,earlier,extension);out['departure']=gate
    amended=deepcopy(core)
    def change(rule,next_segment,changes,reason):
        amended.update(rule=rule,next_segment=next_segment,changes=changes)
        amended.setdefault('triggered',[]).append(rule);amended.setdefault('notes',[]).append(reason)
    if not complete(now) or off['state']=='HOLD':
        change('EVIDENCE_HOLD','HOLD_EVALUATION',{},'유효64·필수 출처/평가 칸 확인 전 보류. 새 GPU 기동 명령 아님.')
    elif off['state']=='ROLLBACK':
        last=treatment.get('last_change')
        before={k:last['before'][k] for k in last['fields']} if last else {}
        change('OFF_SURVIVAL_ROLLBACK','REVIEW_ROLLBACK',before,
               '지도 끔 같은 칸 두 경계 생존60 미만. 최근 처방만 되돌림 초안; 없으면 진단. checkpoint 복원 아님.')
    elif now['iteration']>=1750 and core['rule'] not in ('R4','ROLLBACK','EVIDENCE_HOLD'):
        change('E1_EXIT_REVIEW',gate['next_segment'],{},gate['reason'])
    if now['iteration']<effective_from:
        out['de8_counterfactual']=amended
        out['notes'].append(f'de8 적용 경계 m{effective_from} 전 새 표 재계산은 기록이며 당시 처방을 소급 변경하지 않음.')
    else:
        out.update({k:amended[k] for k in ('rule','changes','next_segment','notes','triggered')})
    out['apply_ready']=False
    out['effective_from']=effective_from
    out['scope_rule_commit']='5f2e7c3b'
    out['activation_rule_commit']='7ba9f2be'
    return out

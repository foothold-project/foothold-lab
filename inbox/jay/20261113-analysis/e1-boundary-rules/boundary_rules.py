"""CPU-only EX-42 E1 rule evaluation. Ledger 73abb340 + lead 18:42 clarification.

This module has no training imports or write-to-run path. Decisions are drafts.
R1 and old R5 are superseded, not fallback actions when evidence is absent.
"""
from __future__ import annotations
import math

MODES=('eval_gt','eval_pred','probe_prop_only')
LOW_KEYS=tuple(f'low/L{level}/eval_gt/fwd{speed}/R' for level in (0,5) for speed in (.1,.2))
YAW_KEYS=tuple(f'yaw/L2/{mode}/fwd1.0/{metric}' for mode in MODES[:2]
              for metric in ('median_abs_rad','p90_abs_rad'))

def finite(value):
    return type(value) in (float,int) and math.isfinite(value)

def r5_observation_complete(iteration, activated_at):
    """R5 needs 500 updates after R6 activation, independently of clean windows."""
    return activated_at is not None and iteration>=activated_at+500

def rollback_limits():
    """Fixed-anchor adverse change, separated by mode/case/metric, #779 section 4."""
    out={}
    for mode in MODES:
        for case in ('spin+1.2','spin-1.2'):
            out[f'map/mixed012/{mode}/{case}/yaw_follow']=(-1,.05,False)
        for level in (0,5):
            for case in ('side+0.4','side-0.4'):
                out[f'low/L{level}/{mode}/{case}/R']=(-1,.05,False)
        for case in ('side+0.5','side-0.5'):
            out[f'map/mixed012/{mode}/{case}/R']=(-1,.05,False)
        for case in ('fwd0.5','fwd1.0'):
            out[f'yaw/L2/{mode}/{case}/median_abs_rad']=(1,.02,False)
            out[f'yaw/L2/{mode}/{case}/p90_abs_rad']=(1,.04,False)
        out[f'stand/flat/{mode}/stand/success']=(-1,4,True)
        out[f'map/mixed012/{mode}/stop/speed_median_mps']=(1,.02,False)
        out[f'map/mixed012/{mode}/stop/yaw_speed_median_radps']=(1,.05,False)
    return out

def regression(current, anchor):
    bad,missing,detail=[],[],[]
    for key,(sign,limit,inclusive) in rollback_limits().items():
        a,b=current['metrics'].get(key),anchor['metrics'].get(key)
        if not finite(a) or not finite(b):
            missing.append(key);continue
        # A fingerprint includes terrain assignment, seed, command, duration, mode.
        cf=current.get('fingerprints',{}).get(key)
        af=anchor.get('fingerprints',{}).get(key)
        if cf is not None and af is not None and cf != af:
            missing.append(key+':conditions_differ');continue
        delta=sign*(a-b)
        triggered=delta>=limit-1e-12 if inclusive else delta>limit+1e-12
        detail.append(dict(cell=key,current=a,anchor=b,adverse_delta=delta,limit=limit,triggered=triggered))
        if triggered:bad.append(key)
    return {'bad':bad,'missing':missing,'items':detail}

def repeat_confirmed(now, keys, predicate, previous=None):
    """Never pool seeds: the same predicate must hold at each paired seed."""
    for seed in ('7','13'):
        row=now.get('repeats',{}).get(seed,{})
        old=(previous or {}).get('repeats',{}).get(seed,{})
        if any(not finite(row.get(key)) or previous is not None and not finite(old.get(key)) for key in keys):
            return False
        if not predicate(row,old):return False
    return True

def decide(now, parent, previous=None, earlier=None, treatment=None, gait=None):
    out=dict(rule='KEEP',changes={},triggered=[],next_segment='UNCHANGED',
             notes=[],apply_ready=False,rule_commit='73abb340',r6_raise_contract='2026-11-13 lead 18:42 all_four_nonincreasing')
    def choose(rule, changes=None, note=None):
        out['rule']=rule;out['changes']=changes or {}
        if rule not in out['triggered']:out['triggered'].append(rule)
        if note:out['notes'].append(note)
        return out
    t=treatment or {};values=t.get('current',{});last=t.get('last_change')
    if now.get('maintenance') in ('HOLD','FAIL'):
        out['next_segment']='DO_NOT_START'
        changes={k:last['before'][k] for k in last['fields']} if last else {}
        return choose('R4',changes,'기존 유지 비통과. 다음 구간 미기동·lead 확인; 처방은 직전 값 초안.')
    errors=list(now.get('errors',[]))+list(parent.get('errors',[]))+list(t.get('errors',[]))
    if now.get('maintenance')!='PASS':errors.append('maintenance_judgement_missing')
    if not now.get('comparable',False):errors.append('comparison_conditions_differ')
    for key in (*LOW_KEYS,*YAW_KEYS):
        if not finite(now['metrics'].get(key)):errors.append('missing_or_nonfinite:'+key)
    for key in ('slow_track','zero_yaw','feet_air_time','feet_air_time_threshold'):
        if not finite(values.get(key)):errors.append('current_reward_missing:'+key)
    if errors:
        out['missing']=errors
        return choose('EVIDENCE_HOLD',note='자료 보완 전 처방 변경 보류. 이것만으로 학습 중단을 요청하지 않음.')
    anchor=t.get('anchor')
    if last and anchor is None:
        if previous and previous['iteration']==last['iteration']:anchor=previous
        elif earlier and earlier['iteration']==last['iteration']:anchor=earlier
    if last and anchor is None:
        return choose('EVIDENCE_HOLD',note='최근 처방 직전 고정 기준 저장본 없음.')
    if anchor and anchor.get('errors'):
        return choose('EVIDENCE_HOLD',note='처방 직전 고정 기준의 증거 오류. 일부 값만으로 비교하지 않음.')
    latest_reg=regression(now,anchor) if anchor else None
    consecutive=(previous is not None and previous['iteration']==now['iteration']-250)
    previous_after=(last and consecutive and previous['iteration']>last['iteration'] and
                    previous.get('maintenance')=='PASS' and not previous.get('errors'))
    prior_reg=regression(previous,anchor) if anchor and previous_after else None
    if latest_reg:
        out['regression']=latest_reg
    if prior_reg:
        same=sorted(set(latest_reg['bad']) & set(prior_reg['bad']))
        out['two_window_regression']=same
        if same:
            return choose('ROLLBACK',{k:last['before'][k] for k in last['fields']},
                          '같은 성분이 고정 기준보다 두 연속 경계 악화. checkpoint/optimizer는 되돌리지 않음.')
    current=now['metrics']
    slow_bad=[k for k in LOW_KEYS if current[k]<(.3 if 'fwd0.1/' in k else .6)]
    yaw_bad=[k for k in YAW_KEYS if current[k]>(.1 if k.endswith('median_abs_rad') else .2)]
    out['low_trigger_cells']=slow_bad;out['yaw_trigger_cells']=yaw_bad
    if yaw_bad:out['triggered'].append('R2')
    if values['slow_track']==0 and slow_bad:
        out['triggered'].append('R6')
        if yaw_bad:out['triggered'].append('R3')
        clear=[k for k in slow_bad if abs(current[k]-(.3 if 'fwd0.1/' in k else .6))>
               (.007 if 'fwd0.1/' in k else .026)]
        if not clear and not repeat_confirmed(now,LOW_KEYS,lambda a,b:any(
                a[k]<(.3 if 'fwd0.1/' in k else .6) for k in LOW_KEYS)):
            return choose('REPEAT_REQUIRED',note='R6 문턱 근처: seed 7·13 자료로 같은 조건 확인 필요.')
        if last and ('slow_track' in last['fields'] or not previous_after or
                     latest_reg['bad'] or latest_reg['missing'] or prior_reg is None or
                     prior_reg['bad'] or prior_reg['missing']):
            return choose('OBSERVE',note='최근 처방의 확인이 부족하거나 slow_track 되돌림 뒤라 재활성을 자동 제안하지 않음.')
        return choose('R6',{'slow_track':.2},'R1 대신 R6. R2가 겹쳐도 이 처방 하나만.')
    if values['slow_track']==.2 and not t.get('r6_raised',False) and consecutive:
        if previous.get('errors'):
            return choose('EVIDENCE_HOLD',note='직전 점수의 증거 오류로 R6 증량 비교 보류.')
        missing=[k for k in LOW_KEYS if not finite(previous['metrics'].get(k))]
        missing += [k+':previous_conditions_differ' for k in LOW_KEYS
                    if now.get('fingerprints',{}).get(k)!=previous.get('fingerprints',{}).get(k)]
        if missing:return choose('EVIDENCE_HOLD',note='R6 증량 비교의 직전 네 칸 부족.')
        delta={k:current[k]-previous['metrics'][k] for k in LOW_KEYS}
        out['r6_raise_deltas']=delta
        if all(v<=0 for v in delta.values()):
            out['triggered'].append('R6_RAISE')
            if yaw_bad:out['triggered'].append('R3')
            if latest_reg and (latest_reg['bad'] or latest_reg['missing']):
                return choose('OBSERVE',note='유지 회귀 또는 자료 부족이 있어 증량 보류.')
            near=any(abs(v)<=(.007 if 'fwd0.1/' in k else .026) for k,v in delta.items())
            if near and not repeat_confirmed(now,LOW_KEYS,lambda a,b:all(a[k]<=b[k] for k in LOW_KEYS),previous):
                return choose('REPEAT_REQUIRED',note='R6 비증가가 반복 폭 근처. 두 저장본의 seed 7·13 짝 재측정 필요.')
            return choose('R6_RAISE',{'slow_track':.3},'네 칸 모두 비증가. 한 번만 0.2→0.3.')
        out['notes'].append('저속 네 칸 중 증가가 있어 0.2 유지. 다음 경계 다시 비교.')
    if last and (not previous_after or latest_reg['bad'] or latest_reg['missing'] or
                 prior_reg is None or prior_reg['bad'] or prior_reg['missing'] or
                 previous.get('maintenance')!='PASS' or previous.get('errors')):
        return choose('OBSERVE',note='최근 처방 뒤 두 경계의 완전한 무회귀 확인을 기다림.')
    if yaw_bad and values['zero_yaw']==-1.:
        clear=[k for k in yaw_bad if current[k]-(.1 if k.endswith('median_abs_rad') else .2)>
               (.02 if k.endswith('median_abs_rad') else .04)]
        if not clear and not repeat_confirmed(now,YAW_KEYS,lambda a,b:any(
            a[k]>(.1 if k.endswith('median_abs_rad') else .2) for k in YAW_KEYS)):
            return choose('REPEAT_REQUIRED',note='R2 문턱 근처: seed 7·13 재측정 필요.')
        return choose('R2',{'zero_yaw':-1.25},'전진1.0 Y1 문턱 밖. 다른 보상은 보존.')
    r5_ready=(values['slow_track']>0 and values['feet_air_time']==0 and last and previous_after and
              latest_reg and not latest_reg['bad'] and not latest_reg['missing'] and prior_reg and
              not prior_reg['bad'] and not prior_reg['missing'] and
              r5_observation_complete(now['iteration'],t.get('r6_activated_at')) and
              all(current[f'low/L{lev}/eval_gt/fwd0.2/R']>=.5 for lev in (0,5)))
    if r5_ready:
        if not gait or not gait.get('valid') or not gait.get('valid_conditions') or gait.get('contact_definition')!='norm_Fxyz_gt_1N':
            out['r5_missing']=(gait or {}).get('issues',['동일 Fxyz 접촉 정의·발별 자료 없음'])
            return choose('OBSERVE',note='새 R5의 발 자료 미충족. feet_air_time 가중 0 유지.')
        return choose('R5',{'feet_air_time_threshold':.04,'feet_air_time':.1},'같은 처방 묶음의 기준값·가중치만 함께 변경.')
    return choose('OBSERVE' if last else 'KEEP',note='발동 조건 없음. 현재 값 유지.')

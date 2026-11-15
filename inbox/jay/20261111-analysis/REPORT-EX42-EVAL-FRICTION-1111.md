> 분류: 검증
> 작성: verifier-lx · 2026-11-11
> 근거: lead 평가 마찰 소비자 의뢰 · prep 승인 teamlead-2026-11-11-0150-71a3d51f · Refs #555
> 요지: EX-42 고정 물리 평가에 승인 마찰을 적용하고 실제 재질 되읽기를 영수증으로 남긴다
> 상태: CPU 확인됨 · Kit 미실행 · 실제 재질 적용은 lead 확인 필요

# EX-42 평가 마찰 소비자 연결

기준 통합 `c4ee1f5b98c3d07c30fd33a3b0f1417fb3ac01ae`. 계획과 승인 파일, 학습 DR, 보상, 점수 문턱, 기존 원자료는 수정하지 않았다. 이미 수집된 기준선은 마찰 되읽기 기록이 없으므로 새 평가와 같은 마찰이었다고 확인할 수 없다. **기존 기준선 재측정·채택은 lead 판단 사항**이다. 이번 PR은 이전 점수를 새 물리 조건으로 재표기하지 않는다.

## 적용과 기록

공통 평가 전용 `foothold_s2/eval/ex42_friction.py`는 `assumptions_pending_lead.evaluation_friction`의 `approved is True`, 결정 문자열, 유한한 비음수 static/dynamic 값을 검사한다. 현재 정본에서 읽는 값은 0.8/0.6이다. 별도 CLI 숫자로 중복 지정하지 않는다.

| 경로 | 실제 소비 | 영수증 |
|---|---|---|
| map64 | `ex42_eval_once.commands`가 evaluation plan을 명시적으로 전달, `eval_map_modes`가 환경 생성 전 terrain/sim 재질 설정 및 생성 후 로봇 재질 고정 | `map_modes.json.evaluation_friction` |
| axis_v2 | 같은 환경 생성 경로. 조기 종료가 있으므로 `axis_v2_run.run_suite` 최종 저장에서 별도 되읽기 | `axis_v2.json.evaluation_friction` |
| stand | `ex40_stand_eval`은 EX-42 인자가 있을 때만 적용. EX-40/41 호출은 기존 동작 | `stand.json.evaluation_friction` |
| D44 | 기존 `--plan`에서 읽어 `_configure`와 `main`에 적용 | `d44_cells.json.evaluation_friction` |
| 깃발 | 기존 `--plan`에서 읽어 `_configure`와 `main`에 적용. W08/W09도 같은 실행기 소비 | `flag_cells.json.evaluation_friction` |
| 직접 메시·종류·유지 평가 | 명시 plan이 없으면 해당 사본의 기본 EX-42 plan을 읽고 그 경로와 SHA 기록. 1.0 기본값으로 회귀하지 않음 | map64와 동일 |
| M 단계 점수 명령 | M 단계 소스 사본의 plan을 명시 전달 | map64와 동일 |

- 부모 `eval_receipt.json.evaluation_friction_requested`는 **요청값**이다. 실제 확인값은 각 자식 영수증이다.
- plan 경로·SHA, 승인 decision, 요청 static/dynamic, 로봇 PhysX `get_material_properties()`의 형상·최솟값·최댓값·배열 SHA, 지형의 실제 collision prim에 결합된 USD 재질 경로와 값을 저장한다.
- terrain/sim 재질은 복사 후 0.8/0.6 및 average 결합 방식으로 설정한다. 로봇은 PhysX의 모든 env/충돌 형상 static/dynamic만 고정하며 restitution은 보존한다. 학습 cfg 객체와 DR 코드는 바꾸지 않는다.
- 랜덤 physics_material 이벤트가 남아 있으면 거절한다. 빈/비유한 로봇 되읽기, 재질 적용 불일치, 지형 충돌 재질 결측/불일치도 거절한다. 초기 적용 후와 최종 영수증 저장 시점에 확인한다.
- N21의 별도 승인된 **DR-on 기록**은 고정 마찰 유지 평가가 아니다. 원래 DR-on 경로를 보존하고, 여기에 고정 마찰 plan을 동시에 요구하면 DR-off 충돌로 거절한다.

## CPU 검증

원출력은 `/home/jay/mai/tmp/verifier-lx/eval-friction-1111/`에 보존했다. CUDA 숨김, Kit/GPU 실행 없음.

| 확인 | 결과 |
|---|---|
| 새 모듈·CLI 실제 parser·4개 소비자 호출 자리·axis 최종 저장·직접 메시 기본값 | 새 시험 23 passed (`final-new.log`) |
| 최종 관련 회귀: 새 시험, E1F child 실패 전달, split, axis, S2/EX-41 평가 | 84 passed (`final.log`) |
| 최초 EX-42 전체 CPU 묶음 | 1183 passed, 3 skipped, 1 failed (`all-ex42.log`) |
| 위 실패 원인 및 조치 | `test_failed_child_still_writes_p1_score_and_handoff`의 `stages: []` 시험 파일에는 승인 마찰이 없었다. 가짜 plan을 정식 `_plan()`으로 바꿨으며 검사를 우회하지 않았다. 해당 시험 포함 최종 84개 통과. 전체 묶음은 다시 반복하지 않음 |
| 공식 `ex42_eval_once` plan-only CLI | rc0, 유지 평가 자식 5개 모두 명시 plan 전달 (`plan-cli.json`); 가짜 CPU checkpoint이며 자식 실행 없음 |
| terrain 설정 제거 돌연변이 | 6 failed / 17 passed |
| robot PhysX 쓰기 제거 돌연변이 | 9 failed / 14 passed |
| robot 되읽기 비교 제거 돌연변이 | 2 failed / 21 passed |
| 직접 EX-42 인식 제거 돌연변이 | 2 failed / 21 passed |

돌연변이는 scratch pytest plugin으로 시험 프로세스에서만 적용했다. 운영 소스는 변조하지 않았다. CPU 소비자 시험은 실제 소스의 parser/호출/저장 구간을 실행하되 Kit 객체는 가짜 CPU PhysX view로 대체한다. 이것은 **Kit 실제 적용의 증명이 아니다**. 새 모듈·시험·부모 실행기·axis 모듈 pyflakes 통과, diff 공백 검사 통과. 기존 Kit 스크립트의 preload unused import 경고는 남아 있다.

## lead가 실행할 짧은 Kit 확인

검토된 커밋의 사본에서 아래 명령을 실행한다. 모델 경로 존재는 CPU로 확인했다. GPU1 할당은 lead가 정한다. 이 명령은 verifier가 실행하지 않았다. 2 env·0.08 s 평지 확인은 유지 판정용 64 env 평가가 아니다.

```bash
# lead only: run from the reviewed, committed checkout. This was NOT run by verifier.
set -eu
set -a
. /home/jay/mai/foothold-linux.env
set +a
FRICTION_PLAN="$PWD/foothold_s2/curriculum/ex42-prep.yaml"
FRICTION_MODEL=/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505/model_1000.pt
FRICTION_OUT="/home/jay/mai/tmp/lead/ex42-friction-readback-$(date '+%Y%m%d_%H%M%S')"
/home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.eval.ex40_stand_eval \
  --checkpoint "$FRICTION_MODEL" --mode eval_pred --envs 2 --seconds 0.08 --skip-seconds 0.02 \
  --ex42-evaluation-plan "$FRICTION_PLAN" --out "$FRICTION_OUT" --device cuda:1 --headless
/home/jay/miniforge3/envs/isaac311/bin/python - "$FRICTION_OUT/stand.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))['evaluation_friction']
assert r['state']=='verified'
for k,v in [('static_min',.8),('static_max',.8),('dynamic_min',.6),('dynamic_max',.6)]:
    assert abs(r['robot'][k]-v)<1e-6, (k,r['robot'][k])
assert r['terrain']
assert all(abs(x['static']-.8)<1e-6 and abs(x['dynamic']-.6)<1e-6 for x in r['terrain'])
print(json.dumps(r,ensure_ascii=False,indent=2))
PY
```

평지 성공은 메시 지형 장착을 증명하지 않는다. 같은 사본에서 필요 시 아래 메시 경로도 짧게 되읽는다. 역시 본 평가 결과로 채택하지 않는다.

```bash
/home/jay/miniforge3/envs/isaac311/bin/python -m foothold_s2.eval.eval_map_modes \
  --task FootholdS2-Go2-S2-SB-v0 --checkpoint "$FRICTION_MODEL" \
  --envs 64 --steps 4 --modes eval_pred --commands fwd0.5 --fixed-terrain \
  --mesh-dir /home/jay/data/foothold/s2_lab/ex42_mesh_1111/seed42_E0_c333_flags_E2_1111_v2 \
  --ex42-evaluation-plan "$FRICTION_PLAN" --out "${FRICTION_OUT}_mesh" \
  --device cuda:1 --headless
```

`${FRICTION_OUT}_mesh/map_modes.json`의 `evaluation_friction`을 같은 방식으로 확인한다. 실제 Kit에서 USD 결합 재질 API나 PhysX 쓰기가 실패하면 수정 후 확인이 필요하다. CPU 통과를 실제 마찰 적용 PASS로 보고하지 않는다.

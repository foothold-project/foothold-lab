# S2-2 feet_center_any9_v1 CPU 구현 보고
> 분류: A/정책학습
> 작성: sol · 2026-10-16
> 근거: TASK-codex-worker-s2-2-foot-reward.md · VERIFY-astra-17ag.md 1~2절 · step15 CPU 검증 로그
> 요지: step14 사본에 발 디딤 비용과 선택 연결을 만들고 번들 단독 및 B 전체 CPU 회귀를 검증했다.
> 상태: CPU 후보 완료 · Kit 미확인 · lead 재실행 대기

## 구현

| 위치 | 내용 |
|---|---|
| `s2_step15/s2_foot_reward.py` | 충돌구 중심 기준 20 cm 엄격 낙차, cardinal any 1, diagonal any 2, 중앙 불일치 3, 지지력 `Fz>1 N`, 환경 비용 `[0,12]` |
| `s2_step15/s2_foot_query.py` | world XY 3×3, 발당 9개 총 36개 하향 광선, 중심과 광선 +20 m 분리, mesh/타일/거리/NaN/부분 inf/frame/episode 검사, Kit 기록 행 |
| `s2_step15/s2_foot_config.py` | `reward_variant=none` 또는 `feet_center_any9_v1`, 명시적 0.05 m 간격, 가중치 -0.01, 실제 RewardManager 항 영수증 |
| `s2_step15/s2_train_entry_17v.py`, `s2_train_manifest.py`, `s2_train_contract.py` | 요청에서 선택값 봉인, 실행 인자와 코드 해시 closure 반영, 실제 환경 생성 뒤 최종 보상 항 기록 |
| `s2_step15/S2-FOOT-KIT-CHECK.md` | 학습 없는 N<=8, 최대 300 control step 단회 계약 |
| `s2_step15/S2-FOOT-UPDATE-READOUT.md` | 5~10 update의 결함, 과대 기여, 동결 보행, 가짜 개선 판독 제안 |
| `s2_step15/fixtures_s2_step15/step14_s2_env_config_17v.py` | step14 환경 설정의 번들 내부 고정 fixture, SHA256 `b8fda54bf8570e91e786f9efa86e0ef6e84138312a8ae3fe9b3671eb04ad5ccc` |

보상 함수에는 음수 가중치나 dt를 곱하지 않는다. 설치된 RewardManager가 `func × weight × dt`를 적용한다. `none`은 `add_foot_reward`가 즉시 반환하고 환경 구성은 step14와 같은 dict 바이트로 확인했다. 켠 경우 새 보상 항만 늘고 actor/student 및 critic 관측 구성은 바뀌지 않는다. 발 센서는 별도 actor 지도나 187칸 복원 지도가 아니라 batched 36 ray 질의로 구현했다. 설치된 RayCaster의 mesh cache와 `raycast_mesh` 호출은 정적 소스를 대조했으나 Kit 동작은 미확인이다.

## CPU 증거

`C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I -B verify_s2_step15.py`, `CUDA_VISIBLE_DEVICES=-1`로 실행했다. 정상 16 PASS, 이후 변이 10/10 CAUGHT. 두 수를 합치지 않았다. `evidence_s2_step15/test_s2_step15_foot.py.log`와 `test_s2_step15_mutants.py.log`에 원문 출력이 있다. 6개 변경 Python 파일은 AST 파싱도 통과했다.

정상 시험은 손으로 높이를 지정한 18개 삼각형의 3×3 hit, 평면 0, cardinal 1, diagonal 2, 둘 다 3, swing 0, 네 발 12, 중앙 불일치 카운터, z 평행 이동, 20 cm와 1 N 엄격 경계, 유효 no-hit와 NaN/부분 inf, 거리 부족/타일 밖/잘못된 mesh, 발 순열, 비동기 env reset과 stale frame, 발 광선 +20 m 비누적, step14 `none` dict 바이트 동일, RewardManager 15/16항, 설치된 URDF 네 발 collision, 요청 selector 인자를 포함한다. 부모 `RewardsCfg`와 E1 `params/env.yaml`에서 15항의 이름과 weight가 서로 같음을 별도로 읽어 확인했다.

step14 dict 대조 시험은 이제 번들 밖 형제 폴더를 읽지 않는다. 내부 fixture의 SHA256을 검사한 뒤 모듈로 읽는다. `run_all_s2_step9.py`가 복사한 임시 번들에서도 그 시험이 통과했다.

| 변이 | 지정 첫 FAIL |
|---|---|
| drop 0.19 m | `20cm_strict` |
| contact 0.999 N | `1N_strict` |
| cardinal 계수 2 | `cardinal_one` |
| diagonal 계수 1 | `diagonal_two` |
| 중앙 override 제거 | `center_three` |
| no-hit 무시 | `valid_no_hit_cost` |
| 월드 0 기준 높이 | `translated_height` |
| 광선 +20 m 중복 | `ray_start_20m` |
| stale frame 허용 | `stale_frame_rejected` |
| 부분 inf 허용 | `partial_inf_rejected` |

## B 전체 깨끗한 복사본 회귀

`run_all_s2_step9.py --run-id step15_fix_clean2`가 step15 번들만 임시 폴더로 복사하고 `python -I -B`, `CUDA_VISIBLE_DEVICES=-1`에서 정상 파일을 먼저, 변이를 다음에 실행했다. `s2_step15/evidence_s2_step9/step15_fix_clean2/summary.json`을 되읽었다.

| 단계 | 파일 결과 | 해당 단계 라벨 | 첫 실패 확인 |
|---|---:|---:|---|
| 정상 | 39/39 파일 PASS | PASS 356 | 해당 없음 |
| 변이 | 12/12 파일 PASS | CAUGHT 84 | 전부 `first_FAIL=want` |

실행기 전체 합계는 51/51 파일, `passed=true`다. 정상 단계의 기존 plumbing 시험이 출력한 CAUGHT 3개와 변이 단계의 PASS 2개는 위 해당 단계 수에 섞지 않았다. 실행기 총 라벨은 PASS 358, CAUGHT 87이다. step15 자체는 깨끗한 복사본에서 정상 16시험, 변이 10/10이다.

첫 깨끗한 복사본 시도 `step15_fix_clean1`은 `test_s2_step5_smoke.py`에서 HOLD였다. 기존 모의 Env에는 `reward_manager_receipt` 속성이 없는데 신규 결과 기록이 그 속성을 바로 읽었다. 실제 `IsaacS2Env`는 생성 시 최종 RewardManager 영수증을 검증하고 생성한다. 결과 기록은 영수증 속성이 있는 실제 환경에서만 쓰도록 고쳤다. 수정 후 두 번째 전체 실행에서 해당 smoke를 포함해 전부 통과했다. 실패 로그와 통과 로그를 모두 묶음에 보존했다.

## 한계와 다음 확인

실제 Kit 발 ray hit 응답, USD collision 발 형상, 발 body ID 순서, 접촉력 동기화, 최종 RewardManager 인스턴스 목록은 미확인이다. 이 값은 `S2-FOOT-KIT-CHECK.md`의 학습 없는 단회에서만 확정할 수 있다. CPU에서 확인한 URDF는 USD 실측의 대체가 아니다. 접속 계약은 A3.4의 가족 소유, 마감, 단회 claim 방식을 재사용하되 진단 전용 범위를 새로 정의하도록 했다. 기존 slot/guard와 `_eval`은 수정하지 않았다.

이 사양은 20 cm보다 얕은 낙차, 얇은 균열, 작은 구멍과 9점 사이 공백을 놓친다. 시작 판단은 gap과 stones에 한정한다. 지형, stumble, 돌 크기와 관측 shape는 바꾸지 않았다. 5~10 update 판독은 진단 제안이며 자동 연장이나 재시도가 아니다.

GPU와 Isaac은 실행하지 않았고 승인 JSON은 만들지 않았다. `s2_step15/ISSUE-550-s2-step15-comment.md`는 #550 댓글 초안이며 미게시다. `S2-STEP15-SHA256SUMS.txt`는 보고서와 step15 사본 파일 1352개를 포함한다. 1352/1352 해시 일치와 CR 0을 되읽어 확인했다.

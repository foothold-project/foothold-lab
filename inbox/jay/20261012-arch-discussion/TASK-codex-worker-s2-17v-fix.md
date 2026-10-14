> 분류: A/정책학습 · Codex Worker(sol) 작업서 · ASTRA 17v 가 찾은 S2 후보 결함 고침과 무인 사슬 요구 반영 (CPU 전용 · 4 단계 작업과 합쳐서 진행)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 04:31
> 근거: `VERIFY-astra-17v.md` 전문 (1 절 결함 · 2 절 접속 확인 정답표 · 3 절 소유 경계 · 4 절 사슬 계약 · 5 절 수치 권고와 비교기 · 6 절 순서) · `TASK-codex-worker-s2-unattended.md` (4 단계) · `REPORT-s2-step3.md` 의 미확인 호출 여섯
> 요지: ASTRA 는 단계별 무인 사슬 방식을 **채택 가능**이라고 했다. 대신 후보의 P1 결함 셋과 보완 둘, 그리고 무인 사슬이 갖춰야 할 소유 경계 · 영수증 · 마감 계약이 먼저다. 이것이 GPU 첫 가동까지의 임계 경로다. 4 단계 작업(무인 실행기 · 교체 가능 encoder · 비교기)을 이 작업서와 합쳐, **아래 1 → 2 → 3 순서로** 한다
> 상태: 의뢰 (CPU 전용 · `_eval` 은 읽기만 · GPU · Isaac 실행 금지)

# Codex Worker 작업서 · ASTRA 17v 반영

## 0. 규칙

- 앞 작업서들 규칙 그대로: 커밋 금지 · 삭제 금지 · GPU · Isaac 실행 금지 · `CUDA_VISIBLE_DEVICES=-1` · `_eval` 과 `source` 쓰기 금지 · 부모 파일 수정 금지 · 정직한 보고 · em dash 금지 · 변이는 정상 소스의 같은 시험 통과 뒤 지정 라벨 실패만 CAUGHT, **변이의 실제 의미를 17v 표처럼 정확히 적고** 입력 변조와 코드 변이를 따로 센다.
- **`VERIFY-astra-17v.md` 를 먼저 끝까지 읽는다.** 아래는 요약이고 다르면 17v 가 이긴다. 수치 권고(5 절)는 ASTRA 의 **출발값**이며 승인값이 아니다. 팀장은 「제안대로」라고 했고 lead 는 5 절 출발값(초기 정책 E1 20000 · full_freeze · N=1,024/arm · smoke 200 · 짧은 비교 2,000 · 연장 +500 · gap 15 % · stones 15 % · LR 0.000170859375 등)을 manifest 의 **출발 후보**로 쓰되 코드에는 기본값 없이 인자 필수로 둔다.
- Codex 주간 한도가 낮다(16 %). reset 권이 있으나 같은 문서 되풀이 읽기는 줄인다. 압축이 오면 `HANDOFF.md` 와 이 작업서를 읽고 이어 간다. **중간에 멈추지 말고 끝까지.** 새 파일은 `codexE/s2_step4/` 에 둔다(2 · 3 단계 파일은 해시 대조 후 사본에서 고친다).

## 1. 먼저 고칠 것 (17v 1 절 · 임계 경로)

1. **P1 시간제한 종료(timeout) 보정.** 부모 `moe_cts.py:187~193` 은 `extras["time_outs"]` 에 대해 reward 에 `gamma × 저장 value` 를 더한다. 후보 `s2_runner.py:128~158` 은 이를 읽지 않고 모든 done 에서 bootstrap 을 끊는다(ASTRA 알려진 답: reward 1 · value 2 · gamma .99 · timeout 이면 부모 2.98, 후보 1.00). 부모 동치를 복원하거나(권고), 더 엄밀한 terminal observation value 방식이라면 auto-reset 전 terminal observation 과 종료 종류를 보존하는 **명시적 알고리즘 변경**으로 등록한다. reset 뒤 새 episode value 를 쓰면 안 된다. 시험: timeout / 진짜 terminal / 비종료 세 경우의 알려진 답.
2. **P1 오래된 센서 packet.** `_frame` 은 obs · sensor · episode ID · frame token 을 따로 받고 번호 증가만 본다. 어댑터가 센서 갱신 뒤 만든 **obs · map · pose · episode ID · simulation step 을 하나의 packet** 으로 넘기고 센서 갱신 근거와 대조하게 바꾼다(번호만 별도 증가 금지). 반례: 첫 packet 을 계속 반환하며 번호만 정상 증가 → 거절. 같은 XY 에서 높이만 바뀌는 reset · yaw 같은 이동 · 일부 env 만 reset 도 시험.
3. **P1 yaw 비유한값.** `expected_world_xy` / `verify_hit_geometry` 가 yaw(및 quaternion · 변환 결과) 유한성을 앞에서 검사하고 quaternion 정규화 규약을 둔다. 반례: yaw NaN → 거절.
4. **조우 기록기.** `EncounterLog` 가 같은 env / episode 의 assigned · approach · pass · pass · fall 을 그대로 센다. 사건 단위를 terrain instance / seed · 난이도 · env · episode · obstacle ID 로 고정하고, 접근선 통과는 최초 1회, 완료선 · 접촉 · 추락 · 시간 상한 종료 정의를 고정, 중복과 상충 결과를 막는다. pass 뒤 먼 곳 fall 과 통과 중 fall 구분.
5. **PPO 부모 차이 정리(17v 1 절 「부모와 같은 것, 달라진 것」).** 부모는 두 군 surrogate 평균의 합, 후보는 전체 평균 / 부모 advantage 정규화 `std()`, 후보 `std(unbiased=False)` / 부모 저장소 순열 재사용 규칙(`rollout_storage_cts.py:130~190`) vs 후보 epoch 마다 새 순열. 맞출 수 있는 것은 맞추고, 아니면 변경 목록으로 **사전 등록 문서**에 적는다. batch 가 minibatch 로 나누어떨어지게 강제.
6. **`collect()` invalid 의 지속 보류.** 수치 고장 상태 반환을 실행기가 무시하고 다음 update 를 호출하지 못하도록 보류를 지속 상태로 고정(갱신 도중 실패의 `held_update` 와 구분).

## 2. 접속 확인(0 단계) 정답표와 미확인 호출 (17v 2 절 · 3 단계 보고의 미확인 호출 여섯)

- 17v 2 절의 **고정 시험안**으로 `s2_connect_diag.py` · `s2_connect_check.py` 를 맞춘다: 8 환경(평지 · 0.20 m 단차 · 틈 · 비대칭 징검다리 × yaw 0 / 90°), 환경당 256 제어 step, 초기 안정화 16 step 별도 기록, 64 에서 평행 이동 · 128 에서 다른 높이 / 위치로 명시적 reset · 192 에서 yaw 변경, optimizer 없음, 알려진 자세를 고정한 구간과 실제 Go2 센서 갱신 구간 구분. 정답표: 187 칸 x-fast 17×11, index 0=(-.8,-.5), 1=(-.7,-.5), 17=(-.8,-.4), 93=(0,0), yaw 90 에서 첫 좌표 (.5,-.8) / body z=.5 · 평지 hit z=0 → height 0, 단차 hit z=.2 → -.2 / cfg.offset 20 m 는 ray starts 에만 더하고 `data.pos_w` 에 다시 더하지 않음 / 정상 miss(+inf 셋) → (height 1, mask 0), 깊은 유한 바닥 → height 1 · mask 1, NaN · 일부 inf · -inf → 고장 / 허용 오차 후보 2 mm, 경계 5 mm 안의 애매한 점은 사전 목록으로 분리해 전부 보고. 틈에는 충돌 바닥이 없는 부분과 깊은 유한 바닥인 부분을 따로. 숨은 plane 이 있으면 정상 no-hit 시험이 아님. 단차 · 돌의 높이와 XY 는 해시로 고정한 비대칭 표식.
- **미확인 호출 여섯을 Isaac Lab 소스를 정적으로 읽어 해결한다**(`C:/isaac/IsaacLab/source/isaaclab/isaaclab/` 읽기만; ASTRA 도 `sensors/ray_caster/ray_caster.py` · `patterns/patterns.py` 를 읽었다): (1) `env_origin_w` / terrain type · level 의 런타임 accessor (2) RayCaster 센서 timestamp / frame / 갱신 세대 accessor (3) Isaac · Kit · 드라이버 판 읽기 (4) 환경 전체 상태 저장 · 복원 API 유무(없으면 재개 불가를 그대로 두고 「환경 재개는 지원하지 않는다」 를 사슬 계약에 반영: 17v 4 절은 재시작이 아니라 **같은 프로세스 안 +500 증분** 이므로 환경 재개는 필수가 아님) (5) 접근 · 통과 · 추락 이벤트와 충돌 mesh 대조 API (6) 한 AppLauncher 안 순차 `gym.make` / `close` 안전성(정적으로는 못 정하면 미확인으로 남기고 장면마다 환경 구성을 분리하는 대안을 제안). 찾은 호출은 파일 · 줄 번호로 근거를 적고, 못 찾은 것은 추측하지 말고 미확인.

## 3. 무인 사슬 (17v 3 · 4 절 + 4 단계 작업서)

- **소유 경계:** 감독 프로세스가 자신의 실행 가족을 **OS 수준으로 묶고**(Windows Job Object 등, 생성 시점부터 소유 확보, 그 가족만 중단, 완전 종료 확인 뒤 lease 반납), 부모 조기 종료 · PID 재사용 · AccessDenied · 새 후손 · 감독기 장애를 시험한다. 17v 3 절: 기존 `isaac_slot_v3.py:145~152`(저장 PID 로 새 `psutil.Process` 를 만들며 생성 시각 미결박 → PID 재사용 시 무관한 프로세스 kill 호출) · `:361,500~505` · `gpu_guard.py:29~48`(직계 자식 기준) 의 약점이 있다. **이 파일들은 고치지 않는다.** S2 사슬이 그 위험한 종료 경로에 닿지 않게 쓰는 방법(예: slot 의 STOP / 마감 종료 인자를 쓰지 않고 감독기가 가족 종료를 맡음)을 줄 번호 근거로 제안하고, 닿는 경로가 남으면 목록으로 보고한다.
- **자원 잠금:** GPU UUID 별 전체 실행 lease 와 호스트 공통 USD 변환 lock / registry 를 구분. 두 GPU 가 각각 하나씩 도는 것까지 전역 run lock 하나로 직렬화하지 않는다. 시작 가능한 경로를 이번 시간 상자 동안 하나의 감독기로 제한하는 안과 모든 경로가 같은 lease 를 지키는 안 중 무엇이 가능한지 근거와 함께.
- **계약 동결:** 사슬 ID · 단회 claim(사슬 전체에 한 번, A / B 실행권은 stage / arm 별로 한 번씩 파생) · 단계 그래프 · 허용 arm / 시드 / 부모 checkpoint / encoder / PPO / 환경 / 평가 · 비교 코드 해시 · 해석기와 실제 import 의존성 · USD 자산 · 장치 UUID · 출력 · STOP 경로 · 단계별 wall / update / transition / VRAM / 출력 용량 상한 · **절대마감 epoch 1792206000(2026-10-17 12:00 KST)** · 허용 checkpoint 경계 · 마지막 증분 크기 표(500 / 250 / 100 / 50 / 10 / 1 중 두 군 모두 끝낼 수 있는 것, 최소 15 분 reserve) · 검사 빈도 · 자동 재시도 0 · 성능 방향 기준 파일과 해시. 미정값 · NaN · 무한 마감 · 임의 shell 문자열 · 미등록 실행 파일 거절. wall clock 뒤로 이동에 무한 연장되지 않게 monotonic 시간에도 결박.
- **영수증:** chain / claim / stage / arm / attempt, 앞 영수증 hash, 코드 · 설정 · 부모 · checkpoint hash, 시작 / 끝 / 제어 · optimizer step, 고장 · 폐기량, 장치 UUID, 프로세스 가족 종료 또는 다음 증분 대기 상태. 별도 validator 가 원자료를 다시 세고 임시 파일 쓰기 후 원자적 교체로 확정. 오래된 로그 · 중복 receipt · 뒤바뀐 arm · 단계 건너뛰기 · 0-byte 산출물 · 불완전 checkpoint 거절.
- **상태 파일:** `chain_status.json` 30 초 주기 갱신(현재 단계 · update · 마지막 유효 packet / 산출물 시각 · 잔여 예산 · 다음 경계). 읽기 권한 오류 · 중단된 heartbeat · 디스크 부족은 보류. 외부 감시도 LLM 없이.
- **두 GPU:** A / B 를 별도 1-GPU 프로세스로, 같은 비교 경계에서만 짝으로 판정(DDP 아님, `WORLD_SIZE=1` 유지). 한쪽 고장이면 다른 쪽도 소유권이 확인된 경로로 체크포인트 경계에서 중단. 빠른 arm 의 잉여 update 는 같은 예산 비교에 섞지 않음. 단계 2 이후 연장은 **같은 살아 있는 learner 프로세스** 가 checkpoint 를 쓰고 다음 증분 허가를 기다리는 짧은 barrier 로.
- **encoder 교체:** `map_encoder=mlp|attn` 인터페이스와 CPU 시험은 지금 만들되, **attn 은 첫 사슬 묶음에 넣지 않는다**(미작성 · 미검증, 새 manifest / 승인 묶음으로 나중에 추가). 구조 효과까지 분리하려면 A-mlp / B-mlp / A-attn / B-attn 2×2. A 의 attention 은 지형 유효점 수나 mask 로 지형을 읽으면 안 된다. dropout · 정규화 · 연산량 · 학습 가능 매개변수 · 지도 열 초기화 · checkpoint 호환성을 동결.
- **비교기 수정(17v 5 절):** 배정 대비 통과율을 주 모니터, 접근 대비 통과율을 보조, 배정 · 접근 · 회피 · 추락 · 정체 · 진행 중 · 미상 · 검열 수를 함께 / 같은 update 창 · 같은 지형 · 난이도 · 명령 층별 비교, 비중첩 500 update 창과 누적 곡선 / **두 Wilson 하한의 차를 B−A 구간으로 쓰지 않는다**: 지형 seed · 환경 · 시간 묶음을 보존한 block / cluster 재표집을 탐색용으로(학습 seed 변동성을 해결했다고 주장하지 않음) / 매 증분 결과는 「탐색 방향」 표시, 정식 판정은 사전 정한 마지막 공통 경계에서 한 번 / 기준 파일 해시 선동결 / 보고에 「독립 평가 이전의 방향 관찰, 한 학습 seed 의 해당 창 관찰 기준 충족」 문구.
- **예비 일감 대기열:** 코드 · 값 · 조건이 이미 승인된 별도 후보 / 시드를 대기열로 동결할 수 있다고 ASTRA 가 적었다(고장 때 GPU 를 채우되 실패한 claim 재사용 금지, 새 하위 실행권 한 번 소비, 출력과 결론 분리). 이번 사슬에는 없고 manifest 에 「대기열 자리」 만 둔다. 대기열이 없으면 보류가 맞다.

## 4. 시험과 보고

- 모든 고침에 정상 + 반례 시험, 새 코드 변이(실제 의미 표기). 2 · 3 단계 시험 · 변이 회귀를 같은 묶음에서(`run_all_s2_step4.py`, 새 run-id). 무인 실행기는 가짜 단계 실행 파일로: 정상 사슬 / 단계 보류 / 양쪽 중단 / STOP / 마감 / 승인 재사용 / 위조 · 오래된 receipt / 부모 종료 후 계속 / heartbeat 정지 / checkpoint 중단. 시험 중 프로세스 종료는 시험이 직접 띄운 가짜 부모만.
- 보고서 `codexE/REPORT-s2-step4.md`: 머리 다섯 줄 · 격리 단언 · 해시 · 항목별 「고침 · 시험 · 정상 로그 · 반례 위치 · 변이 want 와 실제 의미」 · 미확인 호출 해결표(줄 번호) · slot / guard 위험 경로 회피 제안 · 시험이 못 보는 것 · 팀장 / ASTRA 결정 값 · lead 가 ASTRA 에 물을 질문. 끝나면 `ISSUE-550-s2-step4-comment.md`. 사본 · 커밋 · #550 댓글은 lead 가 한다.

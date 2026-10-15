> 분류: A/정책학습 · lead 검증 기록 (ASTRA 17ae 3절 조건) · S2 B 첫 배관 단회 전
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 20:03
> 근거: `VERIFY-astra-17ae.md` · `s2_step8/REPORT-s2-step8.md` · lead 재실행 `s2_step8/evidence_s2_step8/lead_rerun_1957/summary.json` · 기동 예행 GO
> 요지: 17ae 가 남긴 두 결함(CUDA 재적재의 optimizer 비교, 합성 입력 정답 대조)을 고친 step8 바이트와 CPU 증거, 첫 배관 단회의 사전 고정값, 아직 못 채운 조건을 적는다. 첫 배관은 이 기록과 팀장의 단회 직접 동의로만 판단한다
> 상태: CPU 확인됨 · GPU/Isaac 실행 0회 · 실제 CUDA optimizer 재적재 · critic 실센서 읽기 · USD 변환/참조 · 가족 정리는 미확인

# B step8 lead 검증 기록

## 1. 동결 바이트와 출처

- 저장소 사본 `night-tools-20261013/s2_step8/` (104개 파일, 증거 폴더 제외), 목록 `SHA256SUMS.txt` SHA256 `5175e4dfcabafe779b99dd23214cc37789e400498349339fd3b320d5e629fd11`. 실행용 사본 `s2_lab/night-tools-20261013/s2_step8/` 104/104 일치(0 bad).
- 해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe` -I -B(깨끗한 복사본), `CUDA_VISIBLE_DEVICES=-1`.
- step7 대비 바뀐 파일:

| 파일 | SHA256 | 구분 |
|---|---|---|
| `REPORT-s2-step8.md` | `f3ee0f71842c1e93f87bb68a430a25e128d6b763ac342da16926302113d937a2` | 새 파일 |
| `S2-STEP7-USAGE.md` | `cb02619881a62b9da8e6619825208570a780466f917770057973fb02feebb417` | 바뀜 |
| `S2-STEP8-USAGE.md` | `02f5e348421197c42f16d38d7ec5c992890c3e45078f8184c0d184075147905d` | 새 파일 |
| `request_plumbing_A_first.json` | `941ff1a768c055aec5f1c4abc97472131d0896fa8ce6292d9c0fa51bd9779c7d` | 새 파일 |
| `run_all_s2_step8.py` | `300bb4ba340696c2430f936f62d4643a4e9f8f16b3ecc6d44776e4007082d76c` | 새 파일 |
| `s2_plumbing.py` | `59fae09158365756cd6108bb26dca05b4ed766fd8725210ff9fa05a6ec26ebbd` | 바뀜 |
| `s2_train_entry_17v.py` | `0524550611ed03ee83bc811d6b26cb5d5619ff5453752d8446c6f44dc5cd020a` | 바뀜 |
| `s2_train_launch.py` | `ce669d57a313ca9dbee588be4a4fc697fd2fe6d5eee47d5ac117172dffbc9974` | 바뀜 |
| `test_s2_step6_contract.py` | `3bd16eef4d56f503dedda0f18b1af69bdd1e4446b45cbe07205593ae65b9bf6a` | 바뀜 |
| `test_s2_step7.py` | `85616968f76b1ecdaf13a173373079f2183bc05e51afb0662c65fba37f2afcfc` | 바뀜 |
| `test_s2_step8.py` | `7e5d20e45c447d9a32701ce906de16e28b3fecfe06f583b8289542dfd8ad206d` | 새 파일 |
| `test_s2_step8_mutants.py` | `937bd7af3763e307125856723f8d2477bf909a7b1c76fd6a42390344fb6af54a` | 새 파일 |

- 기동 도구 `s2_step4a3_launch/s2_attended_launch_b_plumbing.py` `2e3d29c9f2cc91b6c3661307f1aa96a861ef69b997a2409b175be340b99da26a`, 독립 관찰자 `s2_family_observer.py` `85dfeb414966aaaca2f13f70dc75c3cdb9e886a582df405396c9d86ce57d7c81`. 도구는 요청 JSON을 봉인하고 승인 JSON을 만든 뒤 B prelaunch 를 부른다. 예행(`--rehearse`) prelaunch GO 0.5초. 예행이 처음에 `output_or_STOP_exists` 로 막혔고(도구가 출력 폴더를 미리 만들었음) 도구를 고쳐 통과시켰다.

## 2. 17ae 지적 두 곳: 원인, 수정, 정상 대조, 반례

| 지적 | 수정 | 정상 기대 | 반례 기대 |
|---|---|---|---|
| P1 `map_location=device` 가 CPU 에 있어야 할 Adam `step` 을 CUDA 로 옮겨 `torch.equal` 이 장치 불일치로 실패 | 저장 checkpoint 를 `map_location="cpu"` 로 읽고, 비교는 양쪽을 `detach().cpu()` 뒤 key · shape · dtype · 값으로 재귀 비교, 새 policy 객체에 strict load, 같은 입력의 action/value 최대 오차 1e-6 | 실제 E1 CPU 1 update 뒤 17,940,318 바이트 checkpoint roundtrip 통과 | 디스크의 Adam step · `exp_avg` · control 값 · optimizer key · step shape · step dtype 을 각각 바꾼 여섯 반례 모두 `checkpoint_optimizer_control_mismatch` |
| P2 합성 probe(+0.25)와 실제 합성 경로(-0.25) 불일치 | 실제 `capture_packet_after_sensor_update` → `training_map` 경로에서 B 정답 검사, +0.25 는 `function_only_probe` 별도 필드 | 첫 ray `(height=1,mask=0)`, 나머지 186 개 `(-0.25, 1)`, B tensor SHA `f586d7f7…`, A map 영 행렬 SHA `cda258b2…`, 실제 scanner data 접근 0 | hit z 또는 첫 ray mask 를 바꾼 packet 은 `synthetic_capture_map_answer_mismatch` |

critic 의 `height_scan` 은 합성 모드에서도 실센서를 읽는다고 영수증에 적었다(합성은 actor 의 추가 map 주입부만 실센서를 안 읽는다). A arm 의 map 은 원래 0 이라 첫 A 는 B 의 지도 정보 경로를 증명하지 않는다.

## 3. 시험 결과 (실행 대비)

- 33개 시험 파일 전부 실행(33/33, skip 0 · hold 0 · 미실행 0), **정상 291 PASS + 변이 단계의 정상 선행 2 PASS = 293 라벨**, 이어서 **변이 57/57 CAUGHT**(각 변이는 정상 소스의 같은 시험 통과 뒤 첫 FAIL = 지정 want). sol 의 `final` 과 lead 의 `lead_rerun_1957` 이 같은 수. 기록된 종료 코드 전부 0.
- sol 이 알린 증거 수 불일치(저장소 step7 사본 정상 271, 원본 step7 final3 정상 272)는 서로 다른 실행이라 같은 수로 부르지 않는다. 저장소 step7 `final2` 에 summary 가 없던 이유는 미확인(step8 증거에는 summary 가 있다).
- `s2_ppo_17v.py` 는 A3 와 다르다(loss · 그룹별 pre-clip grad 기록과 비유한 grad 거절 추가). 지도 계산 모듈은 5/6 동일. 학습 수식 변경이라고 단정하지 않는다.

## 4. 첫 배관 단회 사전 고정값 (ASTRA 17ae 2절 그대로)

GPU 0 (UUID `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`, bus `41:00.0`) · arm A · `synthetic_known_answer` · N=32 · iteration 1 · rollout/epochs/minibatches 2/1/1 · `full_freeze` · LR 스케줄 `fixed` · seed 11 · map_init_seed 7 · LR 0.001 · checkpoint_interval 1 · 최대 wall 600 s. 완료 기대값 1 iteration / 2 vector steps / 64 transitions / 1 optimizer step. 센서 snapshot · bootstrap · reset 은 별도 집계.

lead 가 도구에서 정한 값(기록): 마감 = 기동 시각 + 1,500 s, 최소 여유 VRAM 6 GiB, 실행 중 하한 2 GiB(GPU 0 에는 15.6 GiB 여유가 보인다. N=32 의 필요량은 미측정이고 선형이라 가정하지 않는다), 디스크 상한 1 GiB(근거: checkpoint 2개 35.9 MB + USD 격리 7개 파일 18.8 MB + 로그 128 MiB 의 약 5.7배), 최소 디스크 여유 2 GiB(C: 현재 591 GiB). `sensor_hook_path` 는 요청 초안의 작업 폴더 경로를 RayCaster 실제 소스 `ray_caster.py`(A3 가 고정한 바로 그 파일)로 바로잡았다. geometry_tolerance 0.02 · step 높이/폭 0.12/0.2 는 sol 의 계약 fixture 값이며 학습 경로에서는 합성 지도 허용 오차 외에 쓰이지 않는다(코드 확인).

## 5. 17ae 조건 대비 상태

| 조건 | 상태 |
|---|---|
| 새 attempt · 출력 · 마감 · claim | 도구가 시각으로 만든다 (출력 폴더는 미리 만들지 않음) |
| 참석 관찰자, STOP · 마감 · 단회 동의 | 도구가 foreground 로 감독, Ctrl+C 가 STOP 을 쓴다. 동의 파일 필수(scope `s2_plumbing_attended_one_shot_arm_A`) |
| 직전 관문 (장치 · VRAM · 디스크 · 경쟁 프로세스 · lease · USD 잠금) | B prelaunch 가 하고 도구가 GPU 0 UUID/bus 를 다시 확인 |
| 독립 가족 정리 | 감독기 전 `record`, 후 `verify`(Job 밖 관찰자, PID + 생성 시각, 지정 UUID 의 NVML + nvidia-smi, 같은 lease · USD 잠금 비차단 획득, 영수증 SHA). 읽지 못한 것은 UNKNOWN = HOLD |
| 순서 | 4차 0단계 수집 종료 → 관찰자 PASS 또는 분류된 HOLD(17ae 4절 조건) → 이 배관 |
| 팀장 단회 직접 동의 | **아직 없음** |
| 성공 표기 | `plumbing_checks=PASS` `stage0_passed=false` `performance_verified=false`, 조우 `unmeasured`. 두 단회를 A/B 성능 비교로 부르지 않는다 |

## 6. 미확인 (그대로 둔다)

실제 CUDA 에서의 optimizer 재적재 · Isaac 에서 합성 map 이 관측에 들어가는 지점 · critic 의 실센서 읽기 · UUID 속성/표현과 Kit 설정 key · Go2 URDF 변환 1회와 stage 참조(상대 assetPath 면 `Path.resolve()` 가 cwd 기준이라 정상 참조도 거절할 수 있음, 그 경우 raw list-op · layer 식별자 · resolved path 를 보존해 경로 문제로 좁힘) · N=32 의 VRAM · 시간 · 기동 도구 live 배선(기준선 → 감독기 → verify)과 B 감독기의 status 키(`pid`)는 첫 실행에서 처음 지난다.

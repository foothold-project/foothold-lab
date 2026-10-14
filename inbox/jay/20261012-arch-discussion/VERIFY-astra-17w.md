고칠 것: 현재 묶음 그대로의 GPU 기동은 보류하며, 누락 의존 파일·잘못된 환경 연결·장치/자원 보호·실패 자료 보존을 고친 뒤 lead 권한으로 GPU 0 단회 정보 수집을 진행하되 그 HOLD를 0 단계 합격이나 학습 허용으로 읽지 않는다.

> 분류: A/정책학습 · ASTRA 17w 독립 검증
> 작성: 오흥재 (ASTRA 검증 작성) · 2026-10-15
> 근거: TASK-astra-17w-s2-stage0.md 전문 · 고정 A 사본 · 설치 소스 · CPU 재실행 및 독립 반례
> 요지: 정상 시험 통과와 실제 기동 가능성·센서 정답 검증을 구분하고, 첫 정보 수집에 필요한 최소 수정과 후속 합격 조건을 정한다.
> 상태: 검토 완료 · GPU/Isaac 기동·기존 코드 수정·커밋 없음 · 승인 JSON 발급 없음

# ASTRA 17w · 0 단계 묶음 A

확인됨은 이번에 읽거나 재현한 범위다. GPU 상태는 05:11 기록을 대조했을 뿐 현재 다시 측정하지 않았다. 학습 timeout·PPO·조우 집계·encoder·묶음 B 전체는 심사하지 않았다. lead의 권한 위임은 이번 사용자 지시로 확인됐으므로 실행값을 정할 때 팀장에게 같은 승인을 다시 요구할 이유는 없다.

**대상과 재현 경계.** `s2_step4a/SHA256SUMS.txt`의 21/21 파일이 일치했다. 목록 자체 SHA256은 `cfff10ed85cb5f1fddd3457f88ef4e7167accfc1705120c8886902a7553d00e5`다. 제공된 작업자 24행 목록은 원래 경로를 사본 경로에 대응시키면 23행 일치, 변이 실행기 하나 불일치로 의뢰와 맞는다. 현재 고정 변이 실행기는 `52eae685…fa64`다. 작업자 원본 step2 16개·step3 12개 등록 목록은 각각 일치했고 전체 시험은 반복하지 않았다.

그러나 **고정 A에는 실행에 필요한 `s2_terrain_overlay_17v.py`, 시험에 필요한 `s2_runner_17v.py`·`s2_ppo_17v.py` 등이 없다.** 고정 사본만으로 `import s2_connect_diag_17v`를 하면 `ModuleNotFoundError: No module named 's2_terrain_overlay_17v'`로 종료 1이다. 이 부분을 메타데이터가 비어 의도적으로 HOLD하는 것과 혼동하면 안 된다.

CPU 재실행은 고정 A 파일을 유지하고 `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexE/`의 의존 파일을 별도 임시 사본에 보충해 수행했다. 따라서 **완전한 고정 A 묶음의 재현이라고 보고하지 않는다.** 보충한 runner SHA256은 `f3e0b4f9384262dc1665d5ae889d9c9802d63c3cbdcf7caf55fcd909df4086ae`, PPO는 `1f0583b64571db4afe22e67be6e390fe124c966b29efbccd00ede57ffb79eac9`, overlay는 `04db8a09f090bea00097bac6f5bb262d6d9ac0c2ffe81cfa3d38e5f3bf6c9bca`다. lead 실행 당시 누락 파일도 이 바이트였다는 증거는 없다.

| CPU 재실행 | 확인된 결과 | 해석의 한계 |
|---|---|---|
| 정상 7개 스크립트 | 모두 종료 0, PASS 라벨 16+4+8+5+1+4+6=44 | 일부 core는 B 관련 선행 시험이다. A 전용 44개라고 부르지 않는다. |
| 지정 A 변이 5개 | 정상 종료 0, 변이 종료 1, 모두 첫 FAIL=want | `--only`로 B 변이는 실행하지 않았다. |
| Windows Job Object | 시험용 CPU 자식 자연 종료, active=0, exit=0 | 실제 강제 종료·감독기 장애·세션 이탈 시험이 아니다. |
| lead 로그 되세기 | 정상 로그 PASS 수가 보고와 일치 | 과거 종료 코드는 summary 기록이며 현재 독립 실행은 별도다. |

변이 파일을 대조했으며 yaw 변이는 **유한성 검사 두 곳을 제거**한다. 의뢰의 ‘각각 한 줄’ 설명은 이 경우 틀렸다. `claim_exclusive`는 **학습 사슬의 `s2_chain_runner.py`**를 바꾼다. 이번 `s2_zero_supervisor.py`의 claim을 변이 검증한 것은 아니다. 0 단계 claim은 정상 반복 호출 거절 시험이 있다. 추가 B 변이가 같은 파일에 있다는 사실만으로 A 재실행이 무효인 것은 아니지만, 이전 `6fa72e6e…`판 전체와 동일했다는 증명까지 얻은 것은 아니다.

임시 증거는 `C:/Users/AI-WS01/AppData/Local/Temp/astra17w_cpu_5etl7zlz/`다. `s2_step4/evidence_s2_step4a/astra_17w/summary.json`, `mutation-byte-review.json`, `provided-worker-manifest-audit.json`, `worker-manifest-audit.json`, `audited-copy-sha256.json`을 보존했다. 아래 반례는 `probe_independent.py`·`independent-probes.json` 및 `actual-base-config-probe.json`에 있다. Temp 자료는 장기 보존물이 아니므로 재현의 핵심 입력·결과도 본문에 남긴다.

## 1. P1 둘과 센서 출처

**판정: yaw/비정규 quaternion의 알려진 반례는 닫혔다. 오래된 packet 검사는 개선됐지만 실제 센서와 관측의 시점 결박까지 완료됐다고 판정할 수 없다.**

**근거 · 확인됨.** 유한성·norm 검사는 `s2_env_adapter_17v.py:45~71`에 있다. 정상 packet, 같은 XY·새 높이, 일부 환경 episode 증가, yaw NaN/Inf 및 잘못된 quaternion 시험이 통과했다. 과거 packet을 새 번호로 바꾸어도 별도 source receipt가 현재 자료를 가리키면 runner가 거절한다. tracker는 일부 환경만 갱신되거나 detach됐을 때 거절한다. hook 이름이 없으면 생성 단계에서 거절한다.

그러나 `s2_sensor_tracker_17v.py:24~52`는 실제 raycast 함수의 호출 완료를 관찰할 뿐, **갱신 순간의 raw digest를 고정하지 않는다.** `snapshot()`과 `source_receipt()`가 같은 현재 버퍼를 다시 읽고 그때 해시한다. 독립 반례에서 정상 갱신 뒤 센서 버퍼를 직전 자료로 돌려놓자 generation=2·step=1과 과거 raw가 다시 봉인돼 허용됐다. 이는 버퍼 교체 반례이며 실제 Isaac이 그렇게 동작했다는 주장은 아니다. 다만 ‘갱신 뒤 임의로 달라진 버퍼도 출처 검사가 막는다’는 보장은 없다는 뜻이다.

`AtomicPacket.validate`는 root와 sensor 위치의 모양만 비교한다. root X만 +100m로 바꾼 packet도 허용됐다. 독립 검사기 역시 같은 입력을 허용했다. 실제 sensor prim과 root 사이의 검증된 변환으로 대조해야 하며, 기체에서 두 위치가 항상 완전히 같다고 가정해서도 안 된다.

최소 보완은 갱신 완료 시 env별 raw/pose digest·physics timestamp·세대를 고정하고 읽기 시 대조하는 것이다. obs와 그 센서 갱신의 대응도 실제 bridge가 기록해야 한다. private hook 원 함수/설치 소스 해시, 실제 import 경로를 동결하고 불일치·미호출·시점 불일치는 HOLD한다. 현재는 함수가 callable인지만 보며 버전 결박은 없다. `sample()`이 env별 세대를 `min(generation)` 하나로 복제하는 것도 감사 자료 손실이므로 원 벡터를 저장한다.

**남길 미확인:** 실제 reset 직후 lazy update 순서, hook 누락의 실제 설치 환경 재현, 관측 이력과 packet의 동시성. 설치 `manager_based_rl_env.py:197~238`은 scene 갱신 뒤 common counter 증가·reset·관측 순서이고 `sensor_base.py:354~363`은 lazy 갱신이다. 호출 존재를 확인한 것으로 그 실행 시점까지 검증됐다고 할 수 없다.

## 2. 8×256 정답표와 정보 수집 허용

**판정: 정답표 구현이 불완전하고 실제 환경 연결도 틀렸다. 현행 그대로의 수집은 허용하지 않는다. 다만 안전한 실행과 진단 자료 보존을 고치면 mesh/고정 자세 검증 완성 전에도 ‘정보 수집 전용’ 한 번은 가능하다.**

**근거 · 먼저 막히는 경로.** `s2_env_config_17v.py:17,60`과 `s2_connect_diag_17v.py:56`은 `Isaac-Velocity-Rough-Unitree-Go2-v0`를 불러온다. 실제 설치 registry는 `config/go2/__init__.py`의 `UnitreeGo2RoughEnvCfg`, 그 부모는 `velocity_env_cfg.py`의 `ROUGH_TERRAINS_CFG`다. `terrains/config/rough.py`의 여섯 키는 `pyramid_stairs`, `pyramid_stairs_inv`, `boxes`, `random_rough`, `hf_pyramid_slope`, `hf_pyramid_slope_inv`다. `gap`·`stepping_stones`·`flat`·`obstacles`가 없다.

이 여섯 키와 proportion을 **설치 소스 AST에서 추출**해 변경하지 않은 `configure_env`에 넣자 `TerrainOverlayError: E1 gap and stepping_stones cfg missing`을 재현했다. 필요한 네 키를 넣은 양성 대조는 통과했다. Isaac을 돌린 결과는 아니지만 기본 설정에서 실패하는 코드 경로는 확인됐다. parent checkpoint는 존재·해시만 읽고 환경 설정을 불러오는 데 쓰지 않는다. E1과 같은 환경이라고 부를 근거도 현재 부족하다. 실제 E1 환경을 명시적으로 연결하거나 별도 알려진 답 장면을 만들고, 그 선택과 최종 cfg를 고정해야 한다.

**근거 · 검사기 독립 반례.** 정상 8×256 fixture가 PASS하는 것을 먼저 확인한 뒤 한 요소씩 바꿨다.

| 입력 | 현재 결과 | 필요한 수정 |
|---|---|---|
| height[0,2,0]=NaN | PASS | `height` 유한성·범위 검사. NaN과의 `>` 비교는 false다. |
| 고정 구간을 16개에서 1개로 변경 | PASS, fixed_steps=1 | mode의 정확한 16/240 일정과 실제 자세 유지 여부 확인 |
| root X만 sensor보다 100m 이동 | PASS | sensor/root 변환과 시점 대조 |
| step_90·stones_90 환경의 장애물 높이를 전부 제거 | PASS | 두 env를 합친 `any`가 아니라 각 case/개입 구간의 사전 표식 답 비교 |
| 평지 world Z=0 유지, reset 뒤 root/sensor Z=.7·height=.2 | HOLD: flat_answer | 정적인 세계 지형과 바뀐 sensor 높이로 정답 계산. height=0을 전 구간에 강제하지 않음 |

`test_s2_connect_17v.fixture`는 reset 뒤 sensor가 .2m 높아질 때 평지 hit Z도 .2m 올려 계속 height=0으로 만든다. **로봇 이동과 함께 바닥을 올린 합성 답**이 실제 정적 평면의 정답을 대신하고 있다. `s2_connect_check_17v.py:120~129`는 step·stones에서 -.2인 점 하나만 찾고 비대칭 위치·형상을 재구성하지 않는다. 경계 hash와 mesh hash도 값의 존재를 보는 수준이다. fixture의 `abc`가 통과하는 것은 합성용 편의일 수 있어도, 외부 근거 파일과 해시를 실제 대조하는 검증은 아니다. boundary_exclusion_m=.005가 실제 경계 거리 계산에 사용되지 않는다.

현재 실제 메타의 false 값 때문에 이런 반례가 곧바로 라이브 PASS를 만들지는 않는다. **그 false 세 개를 true로 채우기만 하면 완성된 validator가 된다는 해석을 막는 지적**이다. 특히 실제 stones 설정은 높이 최대 .06m인데 checker는 -.2 높이를 찾는다. 별도 .2m 표식이 없는 현재 장면과 맞지 않는다. gap의 정상 miss/깊은 바닥 두 종류도 장면에서 의도적으로 노출되도록 배치한 근거가 없다.

**첫 수집 전에 필요한 최소 자료 보존.** `capture()`는 256행을 메모리에 모은 뒤에만 저장하고 `sample()`은 raw 저장 전에 strict map 검사를 한다. 중간 NaN/hook 오류가 나면 바로 그 실패 자료를 잃는다. 추가로 Job 자식 stdout/stderr가 지정 로그 파일로 연결돼 있지 않다. 다음을 먼저 갖춘다.

- 세션/attempt ID·시작 시각·실제 argv/import 경로·환경 cfg·장치 UUID·초기 자산 경로를 생성 즉시 저장한다. 현재 `started_epoch`는 캡처 종료 뒤 기록돼 시작 시각이 아니다.
- raw pos/root quaternion/hit·ray starts/directions/index·clip 전 높이·최종 지도와 mask·env origin/type/level·physics/control step·env별 세대·sensor timestamp·obs/episode/reset/termination/timeout을 검사 전에 보존한다. 최소 첫 행·63/64·127/128·191/192 및 오류 행, 가능하면 256행 전체를 단계적으로 기록한다.
- 실패 예외/traceback·마지막 유효 step·부분 자료 수·정리 결과를 로그와 receipt에 남긴다. 정보 수집 결과는 강제로 `HOLD_INFORMATION_ONLY`, 다음 학습 단계 없음, 자동 재시도 0으로 둔다.

첫 수집에 모든 mesh accessor의 완성을 요구하지 않는다. 가능한 원본 prim 경로·RayCaster 선택 mesh와 cache 키·설정·timestamp를 먼저 저장하고 못 읽은 항목은 이름과 오류를 남긴다. 이어 채울 accessor는 실제 Warp mesh vertices/faces/월드 변환, USD 충돌체와 숨은 plane/선택 mesh 대응, Kit/Isaac/driver 판, 고정 자세 유지 구간과 원센서 갱신 시각이다.

**두 번째 0 단계 PASS 조건:** 위 false-PASS 반례 거절, 올바른 world 기준 정답·각 8 case의 표식/진짜 miss/깊은 바닥 노출, 16/240 단계의 실제 자세 증거, 원자료와 독립 메시/경계 파일의 hash 결박, 모든 계획 행·개입·sensor 시점 충족, optimizer=0, 소유 가족 정상 종료. bool을 수작업으로 바꾸는 것으로 대체하지 않는다. 동적 로봇 구간은 고정 자세 구간과 다른 정답식을 써야 한다.

**남길 미확인:** 실제 장면 생성·mesh 선택·고정 자세·사전 표식 위치·8환경의 runtime. 자료 수집 자체가 합격은 아니며, 256행 미달도 완주로 보고하지 않는다.

## 3. 단회 실행의 OS 소유 경계

**판정: suspended 생성 → Job 배정 → resume와 가족 수 확인은 적절한 개선이다. 단회에도 쓸 수 있으나 현재 시험은 무인 운전까지 입증하지 못했다.**

**근거 · 확인됨.** 실제 Windows 시험은 CPU 자식 한 개의 자연 종료만 확인했다. 가짜 kernel 시험은 PID 재사용 시 다른 프로세스에 신호하지 않음, 배정 실패, 살아 있는 후손이 있을 때 close 거절을 확인했다. 실제 후손·kill-on-close·AccessDenied가 OS에서 작동했다는 뜻은 아니다. `s2_job_owner.py:104`의 DETACHED_PROCESS는 **진단 자식**의 옵션이지 감독기 자신의 세션 독립성을 증명하지 않는다.

| 남은 항목 | 단회 15분에 수용 가능한 범위 | 무인 사슬 전 필수 |
|---|---|---|
| 감독기 세션 분리 | 참석자가 터미널을 유지하며 1회 관찰하는 것으로 한정 가능 | 세션/CLI 종료 뒤 생존·재접속 시험 |
| 감독기 hang·독립 마감 | 참석자가 소유 handle이 결박된 비상 종료 경로를 확보한 경우만 한시 수용. STOP 파일만으로 hang을 막을 수 없음 | 독립 watchdog, 절대·monotonic 마감, 소유 가족만 종료하는 실제 시험 |
| 다른 실행기 lease 불참 | 15분 동안 다른 GPU/변환 기동을 배제한 예약 구간과 담당자 확인으로 한시 수용 | 모든 참여자의 공통 lease 또는 독립 중재기 |
| 정상 종료/감독기 사망 시 자원 반납 | 현재 자연 종료 경로 확인. crash 후 GPU가 비었다고 자동 선언하면 안 됨 | 감독기 장애·후손 잔존·lease 재취득 경쟁의 실제 CPU 시험 |

현재 감독기 죽음 시 GPU byte lock도 OS가 푼다. Job 종료가 진행되는 짧은 구간과 새 실행기의 lease 취득 순서까지 이 시험은 증명하지 않는다. 정상 경로의 ‘가족 종료 후 반납’을 crash에도 그대로 확장하면 안 된다. 15분 단회에서는 자동 후속 기동을 금지하고 종료 상태를 확인한 뒤 다음 작업을 배정할 수 있다.

LLM이 잠깐 깨어 있는 것을 ‘참석자 확보’로 보지 않는다. 무인 단회로 돌릴 계획이면 독립 마감 장치를 먼저 넣는다. 팀장의 장시간 GPU 지속 운전 원칙을 만족할 사슬에는 위 한시 예외를 가져가지 않는다.

**남길 미확인:** 감독기 세션 이탈·hang·실제 후손 강제 종료·crash 후 경쟁. 이번 검증은 운영 프로세스에 신호하지 않았다.

## 4. slot/guard 우회의 대가

**판정: 새 소유권 경로로 직접 기동하는 선택은 가능하지만 새 승인 대상이다. 주장한 대체 보호 중 상당수가 현재 실행 경로에는 없다.**

**근거 · 확인됨.** `s2_zero_supervisor.py:111~136`은 GPU lease만 얻고 진단을 직접 띄운다. `usd_conversion_lock()`은 정의만 있고 호출되지 않는다. USD 격리 루트/registry 결박·장치 전체 여유 VRAM 사전 조회·실행 중 감시가 없다. `max_disk_bytes`는 양수 여부만 확인하며 사용량을 재지 않는다. 승인 시 해시를 확인하는 것은 python/diag/criteria/parent 네 파일뿐이고 실제 supervisor/validator/adapter/overlay/import 의존 바이트는 묶지 않는다.

장치 UUID는 문자열로 lock 이름과 receipt에 복사할 뿐, `CUDA_VISIBLE_DEVICES`에는 index를 넣는다. UUID→index→PCI bus→실제 torch/Kit 장치의 대조가 없다. 가짜 owner 반례에서 GPU UUID를 다른 값으로 바꾸고 `--device cuda:1`, `max_disk_bytes=1`을 줘도 validation을 지나 PASS했다. 173,297바이트의 기존 capture도 통과했다. 이는 가짜 자식/기존 artifact에 대한 감독기 시험이며, 실제 진단이 그런 결과를 만들었다는 뜻은 아니다. 실제 진단의 `mkdir(exist_ok=False)`는 오래된 출력 폴더를 거절한다. 다만 감독기 시험만으로 장치·디스크·신규 실행을 검증했다는 주장은 성립하지 않는다.

단회 전 다음을 실제 경로에 연결한다.

- GPU UUID로 물리 장치를 결박하고 자식은 노출된 논리 cuda:0을 사용한다. Kit/renderer의 물리 장치 선택도 확인한다. 충돌하는 CLI 장치 옵션·중복 옵션을 거절한다.
- 호스트 USD 변환 lock을 실제 획득하고 기존 참여자와 같은 잠금 규약/경로를 사용한다. 현재 해시 이름의 새 byte lock은 기존 `isaac_convert.lock` 참여를 자동으로 얻지 못한다. 자식/자산별 격리 루트와 실제 변환 경로를 기록한다.
- 변환이 0이라는 계획이면 최종 asset cfg와 실제 0회 기록을 남기고 예기치 않은 변환을 거절한다. 기본 Go2는 USD를 직접 참조하므로 URDF 변환이 반드시 발생한다고 단정하지 않는다. 변환 없음이 확인되면 불필요한 전역 직렬화는 생략할 수 있다.
- 실행 전 여유·실행 중 VRAM/디스크 상한·STOP·마감·후손 종료를 관찰한다. 무응답 측정을 정상으로 간주하지 않는다. 수정 실행기와 전체 import 파일 목록을 승인 hash에 묶는다.

17u의 재사용 원칙은 검증된 요소를 가져오라는 뜻이다. 위험한 PID 종료가 있는 옛 wrapper를 의례적으로 끼우라는 뜻도, 새 경로에 옛 승인 효력을 옮기라는 뜻도 아니다. 이번 단회만의 supervisor/실행 명령/자산/장치/보호 조건으로 별도 승인하면 된다.

**남길 미확인:** 실제 USD 변환 유무·참여자 lock 호환·실장치 VRAM 여유·Kit 장치 선택. 05:11 스냅샷은 기동 직전 관문을 대신하지 않는다.

## 5. 첫 GPU 일 한 번의 구체 조건

**판정: 위 실행 결함을 고친 뒤 GPU 0 한 번, 정보 수집 전용으로 lead가 승인값을 채우고 기동할 수 있다. 지금 파일에 대한 무조건 기동 허용은 아니다.**

**근거와 권고값.** GPU 0 후보 UUID는 `GPU-c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`, 기록상 bus 41:00.0이다. GPU 1은 이 승인에서 제외한다. 아래 값은 실측된 최적치가 아닌 단회 운영 출발 권고다.

| manifest/승인에 묶을 것 | lead가 채울 값과 확인 |
|---|---|
| 범위·횟수 | `purpose=stage0_information_only`, 8환경·256제어 step·16warmup·개입64/128/192, optimizer=0, `max_launches=1`, retry=0, downstream 없음 |
| 시간 | `max_wall_s=900`, 실제 시작에 맞춘 절대 마감·승인 만료, 전체 상한 2026-10-17 12:00 KST 이하. 준비/검증/정리도 제한시간에 포함하며 지연 시 자동 연장하지 않음 |
| GPU/위험 | UUID·bus·실제 노출/논리 장치. 초기 여유 8GiB 이상, 실행 중 장치 여유 2GiB 미만이면 보류를 출발 권고로 제시. 이는 8환경 필요 VRAM 실측값이 아님. 측정 오류도 보류 |
| 디스크 | 출력 상한 1GiB, 기동 전 여유 2GiB 이상을 출발 권고로 제시. stdout/Kit/중간 raw 포함, 초과 감시를 실제 구현 |
| 입력 | python·설치판/import 경로·전체 실행/판정 코드·환경 cfg·자산/부모·criteria·종료/감시 코드 hash. criteria=.002/.002/.005, 256/16은 사전 값으로 고정 |
| 쓰기 경로 | 이번 실행의 새 output/USD root, STOP/status/log, GPU lease/host lock, claim root. 기존 평가/학습 폴더와 충돌 없음 |
| 권한/단회 결박 | lead의 by·승인 ID·manifest digest·expires, 단회 attempt/claim. 승인 변경 시 새 digest. 문자열 APPROVED만으로 실험 결과를 승인하지 않음 |

초기 디스크·VRAM 권고와 다르게 정할 수 있는 권한은 lead에게 있다. 다만 바꾼 값·근거를 **실행 전에** 동결하고 결과 뒤에 완화하지 않는다. 0 단계에서 checkpoint는 추론에 사용하지 않으므로 부모 hash를 기록했다고 정책 실행 검증을 했다고 하지 않는다.

기동 직전에는 누락 import 없는 완결 묶음, 실제 registry/terrain 구성과 전체 필수 CLI 인자, hash 일치, UUID/bus와 장치 매핑, 공통 잠금/경쟁 기동 배제, 새 output·STOP 없음, 남은 시간/공간, 종료 경로와 로그 기록을 확인한다. 현재 validate는 실제 parser가 요구하는 seed·비율·단차 크기·tolerance 누락까지 검출하지 않는다. 승인 JSON에서 기존 argv를 복사하는 것으로 끝내지 않는다.

기술 오류·장치 불일치·VRAM/디스크 하한·STOP·마감·raw 기록 불능이면 중단하고 가족 종료를 확인한다. 예상된 mesh/고정 자세 미확인은 수집 종료 후 HOLD 사유로 남기되 자동 학습을 시작하지 않는다. 보고 문구는 **‘정보 수집 N/256 step, optimizer 0, 결과 HOLD, 사유 ..., GPU/소요/최소 여유 ..., 다음 학습 미실행’**으로 쓴다. 시작 자체 실패와 일부 캡처, 전체 캡처 후 검증 HOLD를 구분한다.

이 claim은 `stage0-capture-<attempt>`의 한 번을 소비한다. 후속 PASS 진단/학습 사슬은 별도 승인·claim을 사용하며 이번 raw와 receipt의 hash를 참조할 수 있다. HOLD claim을 지우거나 output 이름만 바꿔 재실행하지 않는다. 정보 수집 판정은 학습 사슬의 이전 단계 PASS로 제출할 수 없다.

**남길 미확인:** 권고 자원 한도의 충분성, 실제 900초 내 완료 여부, lead가 발급할 최종 승인 바이트. 이 문서는 승인 JSON이 아니다.

## 6. 남은 순서·시간·GPU 활용

**판정: 먼저 실제로 자료가 나오는 작은 수집 경로를 완성한다. B 전체 완성을 기다릴 필요는 없지만, 비어 있는 GPU를 이유로 현재 실패 경로를 기동하는 것은 진척이 아니다.**

**근거와 순서.** ① 누락 의존 파일을 포함한 고정 묶음과 올바른 환경/asset 연결 ② 장치·USD·자원 한도·로그/부분 raw·단회 종료 경로 ③ 새 코드의 바뀐 부분 CPU 반례 확인과 lead 승인값 동결 ④ 기동 직전 재측정 후 GPU 0 단회 수집 순서다. 검사기의 완전한 mesh/정답 대조는 두 번째 PASS 단계 전까지 끝내되, 첫 수집에서 절대 PASS/자동 학습으로 넘어가지 않도록 먼저 막는다.

계획용 추정은 ①②③ 합계 **30~90분**, 기동 직전 확인 **5~10분**, 수집 **최대 15분**이다. 실제 API/asset 문제와 안전한 감독 경로의 준비 상태에 따라 더 걸릴 수 있으며 측정된 ETA가 아니다. 이번 CPU 정상 7개와 지정 변이 5개는 짧게 재현됐으므로 이 좁은 변경을 확인하려고 과거의 전체 회귀를 반복할 이유는 없다.

GPU 1에 지금 즉시 안전하게 올릴 **승인·완결된 별도 작업은 이번 자료에서 확인되지 않았다.** 05:11의 데스크톱 5,887MiB 사용만으로 다른 Isaac 작업의 여유·종료 안전성을 판단할 수 없다. 다른 독립 승인 작업이 이미 있다면 lead가 현재 여유/공통 변환 잠금/같은 장치 lease를 확인해 배정할 수 있지만 이번 검증은 그 작업까지 허용하지 않는다.

GPU 0 수집 동안 CPU 쪽에서 B의 구현·시험을 진행하고, 수집 후에는 실제 import/env cfg·raw 시점·reset 결과·mesh 경로·시작 비용·최대 VRAM·최소 여유를 B manifest와 시간 예산에 반영한다. 센서/환경 결함은 A/B 공통 경로를 고치되 효과 기준을 결과에 맞춰 바꾸지 않는다. 시작 실패면 실패 자료로 연결 경로부터 고치고, mesh 증거만 부족하면 해당 accessor만 추가해 두 번째 0 단계를 진행한다. 실패한 바이트로 예약 재시도를 돌려 GPU 가동률을 채우지 않는다.

**남길 미확인:** B 완성 시각·처리량·실제 GPU 가동 계획. 이번 검증은 중단된 전체 과제를 완료 처리하거나 토요일까지의 사슬을 승인하지 않는다.

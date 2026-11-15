고쳐서 기동: CE12의 무변환 실행 보호·인자 경계와 rand_scenes의 메모리 중단 전파·자료 검증을 고치고 17e 실행 관문을 연결한 뒤 GPU 1에서 짧은 기록부터 순차 진행하며, 현재 판의 자동 연속 기동은 승인하지 않는다.

S2 판정: CPU 입력·초기 정책 동치는 확인됐지만 지도 mask의 의미·비정상 값 처리와 학습기 연결이 미완성이므로 설계를 고쳐 진행하고 학습 기동은 보류한다.

> 분류: A/평가 · ASTRA 17d 독립 검증
> 작성: 오흥재 (ASTRA 검증 세션 작성) · 2026-10-13 19:58
> 근거: TASK-astra-17d-s0-rand-s2.md · 지정 사본/실행본 SHA256 대조 · 격리된 CPU 재시험과 결함 주입 · DESIGN-s2-ab-v1.md · 설치된 Isaac Lab/RSL-RL 소스
> 요지: 제공 시험은 모두 통과하지만 별도 반례에서 안전 중단과 성공 판정이 우회된다. S0 기록, 시연 영상, S2의 인과적 주장을 구분한다.
> 상태: 검증 완료 · GPU/Isaac 실행 없음 · 운영 파일/잠금/registry/STOP/원자료 수정 없음 · 커밋/push 없음

# ASTRA 17d · S0 기록기, 무작위화 영상, S2 입력 설계

표기: **확인됨**은 이번에 직접 읽거나 CPU로 재현한 사실, **추정**은 설계 판단, **미확인**은 실제로 재지 않은 사항이다. 아래 `CE/`와 `RAND/`는 이 폴더의 `night-tools-20261013/ce12/`, `night-tools-20261013/rand_scenes/`를 뜻한다. `Q/`는 `C:/isaac/ext/go2_rl_robotlab/_eval/`, `IL/`은 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/`다.

## 1. 검증 범위와 확인한 것

**확인됨:** CE 11개, RAND 8개 manifest 대상 파일을 지정 사본·실행본·시험용 사본 사이에서 SHA256으로 대조했고 모두 일치했다. 시험 뒤에도 재확인했다. 의뢰 시작 HEAD는 `8b00a3816b03ab96afecb1208aaa72290fc21b7a`, 진행 중 HEAD는 `39221e8d4dc78348573a50a168687b0a9ac4deb1`였다. 공유 브랜치는 `feature/verify-v2-mvp-jay`다. 검증 기준은 움직이는 HEAD 대신 아래 해시 묶음으로 고정했다. 기존의 다수 미커밋 변경에는 손대지 않았다.

| 직접 재실행한 CPU 시험 | 결과 | 의미와 한계 |
|---|---:|---|
| CE `test_adapters.py` | 22/22 통과 | 수식·순서·이력·CPU 체크포인트 적재 확인. 가짜 native 기록의 닫힌 고리 통과는 실제 Isaac와의 동치를 입증하지 않음 |
| CE `test_run_dump.py` | 37/37 통과 | 실제 slot/isolate 사본에 가짜 guard/기록기를 연결. 잠금·registry·출력은 전부 임시 폴더 |
| RAND `test_rand_scenes.py` | 23/23 통과 | 합성 프레임·가짜 물리 결과·실제 CPU 인코딩/검사. Isaac 카메라나 물리를 실행한 시험이 아님 |
| S2 `test_s2.py` | 7/7, 검사 항목 115개 통과 | CPU 초기 action·분포·student critic 동치, PPO 형태의 합성 손실에서 gradient 경로와 부모 보존 확인 |

**확인됨:** 검토 중 S2의 README와 시험 파일이 완성되어 실행본에서 임시 사본을 추가로 확보했다. S2에는 의뢰의 두 SHA256SUMS와 같은 제출 manifest가 없으므로 §8의 개별 해시를 기준으로만 말한다. S2 시험의 메모리 내 optimizer 갱신은 합성 CPU 시험이며 학습 실행·체크포인트 저장을 하지 않았다. 부모 체크포인트는 시험 전후 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`로 동일했다.

**미확인:** lead가 보고한 변이 CE 21/33개, RAND 36개, S2 21개 전체는 이번에 재실행하지 않았다. 대신 다음 절의 별도 반례를 직접 실행했다. 실제 GPU 메모리 여유, 새 기록기의 Isaac 호환성, 생성될 영상의 모습, v3 관문의 완성도는 측정하지 않았다. 17c의 이미 지적된 v2 관문 내부 결함은 재검 범위에서 제외했다.

## 2. 오늘 밤 기동을 막는 결함

### 2.1 RAND: 선택 센서 시험의 메모리 중단을 무시한다 · P1

**확인됨:** `RAND/rand_driver.py:212`는 `run_scene()` 안에서만 guard 중단을 처리한다. 그러나 `smoke():260`의 `smoke_probe`는 `attempt()`를 직접 호출한다. 여기서 guard가 중단하면 단순한 probe 실패로 처리하고 `smoke_skyfail`과 본 장면으로 진행한다.

직접 재현: 제공 `fake_q_rand()`의 `smoke_probe`에만 `guard_stop=True`를 넣었다. 해당 시도는 `rc=99`, `failed_checks=[guard_record]`였지만 호출 순서는 `smoke_base → smoke_probe → smoke_skyfail → base → push_lat`, 최종 반환은 **0**이었다. 다른 장면의 정상 파일과 CPU 검사도 실제로 거쳤다.

**수정 조건:** 모든 시도 공통 경계에서 guard 중단과 프로세스 종료 코드를 처리해야 한다. 선택 센서의 API 미지원은 probe 없이 진행할 수 있지만, GPU 여유 하한 침범은 같은 실패 종류가 아니다. `smoke_probe`뿐 아니라 직접 `attempt()`를 부르는 모든 경로를 시험한다. 보호 중단 뒤 자동 재시도나 다음 장면 기동을 허용하지 않는다.

### 2.2 RAND: 비교 조건이 어긋나도 성공으로 끝난다 · P1

**확인됨:** `RAND/rand_driver.py:289`는 지형과 교란 전 궤적을 검사하지만, `:412`의 최종 반환에는 `same_start_fingerprints.equal`만 반영한다. `:297`은 빈 사전끼리도 같다고 인정한다.

| 실제 주입한 반례 | 관측한 결과 |
|---|---|
| push 장면의 terrain mesh 지문만 변경하고, 첫 교란 전 state 10의 x를 0.02m 변경 | `same_terrain_mesh=false`, `base_vs_push_before_first_push.equal=false`, 최대 차 0.02인데 **rc=0** |
| 모든 장면의 `fingerprint={}`, `terrain_mesh=[]` | 두 동등성 검사가 모두 true, **rc=0** |

**수정 조건:** 필요한 fingerprint 열쇠·값·형식과 실제 지형 항목의 존재를 먼저 검증한다. 기하에는 점·인덱스뿐 아니라 world 변환 등 실제 충돌 위치를 바꾸는 요소도 묶는다. 지형 불일치, 첫 교란 이전 궤적 불일치, 같은 기준 장면의 반복 불일치를 결과 상태에 반영한다. 일치가 안 되어도 각 영상은 단독 시연으로 보존할 수 있으나, 현재 영상에 박히는 **‘같은 출발’과 교란만 바꾼 짝 비교 문구**는 허용하면 안 된다. 불일치를 숨기려고 허용 오차를 사후 확대하지 않는다.

### 2.3 RAND: 낙상 판정에 쓰는 자료가 없어도 유효하다 · P1

**확인됨:** `RAND/rand_lib.py:232,258`의 `CORE_FINITE`에는 `ground_z_m`, `base_height_above_ground_m`, 접촉 판정 열 등이 빠져 있다. 검증은 CSV의 일부 열을 확인하지만, cross-check가 읽는 `traj.npz`의 구조·유한성·CSV와의 대응은 독립 검증하지 않는다. `result.json`의 낙상 결론도 원자료로 다시 계산하지 않는다.

직접 재현: 기준·밀기 장면의 CSV와 NPZ에서 지지면 높이와 몸체의 지면 대비 높이를 모두 NaN으로 바꿨다. 두 시도는 계속 유효했고 최종 **rc=0**이었다. `max_diff()`는 두 NaN을 같다고 취급했다. 앞 절에서는 NPZ만 바꿔 CSV와 다른 궤적으로도 진행했다.

**수정 조건:** 낙상 이전 판정 구간의 위치·자세·속도·접촉·지지면 자료를 검증하고 CSV/NPZ를 결합한다. 접촉은 0/1, quaternion은 정상 범위 등 의미 검사도 필요하다. 보조 probe의 미사용 NaN과 지지면 측정 실패를 분리한다. 이미 실패한 이후의 미관측은 시각화용으로 남길 수 있지만, 실패 전 미측정 높이를 ‘낙상 없음’으로 바꾸면 안 된다. 지원면 미관측 자체가 실제 낙하인지 계측 오류인지는 관측 없이 단정하지 않는다.

### 2.4 RAND: 요청한 밀기와 실행된 밀기가 연결되지 않는다 · P1

**확인됨:** `RAND/rand_driver.py:92`의 expect에는 밀기 횟수와 학습 범위만 들어간다. `RAND/rand_lib.py:467` 이후는 결과 파일 내부의 요청값과 측정값끼리 비교한다. 외부 CLI 계획의 방향·순서·좌표계와 매 사건을 대조하지 않는다.

직접 재현: 계획은 `heading` 기준 `vy=+0.4`인데 첫 밀기의 `dv_world_requested`, `dv_world_measured`를 모두 `[0.4,0,0,0,0,0]`으로 바꿨다. 범위·횟수·자체 대조를 통과하고 최종 **rc=0**이었다. 원자료/일정의 나머지 내용과 모순인데도 허용했다.

**수정 조건:** 동결한 schedule 항목과 당시 heading으로 world delta를 별도로 계산하고, 여섯 성분의 형식·유한성·before/after 차이·state/time·CSV/NPZ 사건을 대조한다. 시간 예측 오류를 경고로 두는 것은 가능하나, 실제 사건이 등록한 순서·방향으로 발생했는지는 별도 필수 조건이다. `train_yaml_sha256`, 실제 관측·행동·sim dt 설정도 요청 묶음과 대조한다. 현재 `q_rand.py:239` 이후의 train/default 차이는 기록만 하며, 기록만 했다고 학습 규약을 보존한 것은 아니다.

### 2.5 CE: 추가 인자로 실행기가 정한 출력·체크포인트를 덮을 수 있다 · P1

**확인됨:** `CE/run_dump.py:144`는 토큰이 정확히 `--tag`, `--outdir`, `--checkpoint`일 때만 거절한다. argparse가 허용하는 `--outdir=...`는 통과한다.

직접 재현: 가짜 v2 자식에 `-- --outdir=<격리 임시 경로>/escaped`를 보냈다. 실행기는 **rc=0**을 냈고 새 NPZ는 지정 tag 경로가 아닌 escaped 경로에 생겼다. 기대 출력 폴더에는 없었다. 실제 기록기에서도 같은 argparse 중복 옵션 방식이며, 일부 금지 폴더와 기존 출력 존재 검사는 별도로 있다는 점은 구분한다. 이번에 운영 경로나 기존 자료에는 쓰지 않았다.

**수정 조건:** 추가 인자는 허용 목록으로 파싱하고 정규화된 옵션 이름·중복·축약을 검사한다. 실행기가 소유한 경로·tag·checkpoint·장치 옵션은 어떠한 표기로도 재정의할 수 없어야 한다. 출력 확인은 나중의 `validate_dump`에만 맡기지 않는다. `--allow_cfg_diff`도 정식 자료에서 거절해야 한다.

### 2.6 CE v2: 사후 검사는 공유 쓰기의 사전 방지가 아니다 · P1

**확인됨:** 지금 v2 장면이 `UNITREE_GO2_CFG`의 `UsdFileCfg`와 `GroundPlaneCfg`를 사용한다는 근거는 맞다. `isaaclab_assets/robots/unitree.py:140`, `IL/terrains/terrain_importer.py:223`에서 직접 확인했다. 따라서 **이 고정 구성에는 URDF 변환이 필요 없을 것이라는 판단은 합리적**이다. 변환 1개를 요구하는 현재 slot 규칙을 그대로 적용해 rc95를 내는 것도 잘못이다.

그러나 `CE/run_dump.py:98,101,182`의 구성은 잠금 없이 자식을 다 돌린 뒤 `assigned.jsonl`과 로그를 읽는다. unexpected converter가 공유 경로에 썼으면 rc93은 그 쓰기를 취소하지 못한다. ‘지금 코드에서 변환이 예상되지 않음’과 ‘예상 밖 변환을 쓰기 전에 차단함’은 다른 주장이다.

**수정 조건:** v3 계열에 **변환 예상 0개인 실행 모드**를 명시하고, 변환기 진입 시 디렉터리 생성/변환 전에 예외를 내거나 동일한 사전 격리·잠금 계약을 적용한다. 예상 0/1개를 구분해서 검사한다. 단순히 성공 조건을 ‘폴더 없어도 통과’로 완화해서는 안 된다. v2 전용 CPU 시험에는 뜻밖의 변환이 생기는 가짜 자식을 넣어 **쓰기 시도가 일어나기 전에 거절했는지**를 확인한다. 이번 답은 미완성 v3 구현을 검증했다는 뜻이 아니다.

### 2.7 CE: VALID stamp를 S0 동치 승인으로 쓸 수 없다 · 자료 승인 P1

**확인됨:** `CE/validate_dump.py:130`은 수집 성공/형식을 보지만 native 의미 검사를 전부 승인하지는 않는다. 반례로 정상 가짜 묶음의 meta에 `allow_cfg_diff=true`, observations 차이 4개, teacher 입력 변경에 따른 action 차이 1.0, 잘못된 steps/cells를 넣고 `signature.json`을 지워도 **실패 검사 목록은 []**였다. `:217`은 없는 signature를 해시 목록에서 조용히 제외한다.

이 반례가 실제 native 결과의 결함을 증명하는 것은 아니다. **그런 결과를 걸러낼 승인 관문이 없음을 증명한다.** README가 `validate_dump` 뒤 `compare_native --recompute_action`을 따로 요구하는 순서는 맞다. 이 둘을 섞어 VALID 한 줄만 보고 다음 단계로 가면 안 된다.

**수정 조건:** 계약 서명 존재/내용, 요청한 cell·T·N·명령 시간열, 금지 override와 train 설정 차이, student 경로 검사를 자료 승인에 연결한다. collector의 self-check 수치만 믿지 말고 가능한 항목은 NPZ로 재계산한다. 최종 stage-1 승인에는 수집 validation과 **`--recompute_action`을 켠 비교 보고서**, 그 둘이 읽은 NPZ/meta/checkpoint/config/code의 해시가 함께 있어야 한다. 비교 후 입력이 바뀌거나 다른 checkpoint를 재계산하면 승인이 무효여야 한다. 미완료 검사는 ‘실패’와 구별해 보류한다.

## 3. GPU 1 배정과 기동 순서

**추정:** 오늘 밤의 우선순위는 S0의 작고 검증 가능한 native 기록이다. 영상 넷을 먼저 다 뽑고 마지막에 결함을 발견하는 순서는 피한다. 현재 GPU 0 학습을 중단해야 한다는 근거는 이번 범위에서 발견하지 않았고, 그 실행의 상태를 새로 검증한 것도 아니다.

1. §2의 기동 결함 수정과 17e 관문 검증을 마친다. 실제 연결할 builder·validator·출처 기록도 같은 버전으로 맞춘다. 지금 `cmd_ok` 및 RAND 검사는 `usd_isolate_run.py`라는 파일명을 직접 검사하므로 호출부만 `_v3.py`로 바꿔서는 호환 검증이 되지 않는다. 수정 경로만 재시험한다.
2. 기존 GPU 1 작업 종료와 재기동 허가 상태를 운영 담당자가 확인한 다음, CE CTS E1 20000의 짧은 native 기록 하나를 실행한다. 영상 없이 기본 세 명령·작은 env 수로 시작한다. 코드의 기본은 3칸 × 4개 환경 × 60 step, 시뮬 시간 1.2초다. 처음부터 세 가지 환경 대규모 비교로 확대하지 않는다.
3. 실제 수집 validation과 CPU 재계산을 통과한 뒤 CE v2도 동일하게 수집한다. **각자의 native adapter 일치**를 확인하는 단계다. CTS와 v2는 여전히 다른 물리/초기화/DR이므로 지금 둘의 보행 성적을 서로 비교하지 않는다.
4. RAND는 `--stop_after_smoke`로 끝내고 운영 담당자가 실제 첫·중간·끝 프레임과 실패 시 격리된 파일을 확인한다. 검은 프레임 복구·지속 sky 실패의 기대 동작, 물리 상태에 대한 렌더/probe 영향, 장치 배정을 확인한다. probe API 미지원과 메모리 보호 중단은 서로 다르게 처리한다.
5. 정상적인 짧은 smoke 뒤 기준·밀기·낮은 마찰·높은 마찰을 **하나씩** 실행한다. §2의 cross-check가 통과하기 전에는 비교 영상 묶음으로 승인하지 않는다. 지형에 따른 실제 실패는 유효한 결과이며, 재시도로 ‘좋아 보이는’ 성공 판을 고르지 않는다. 렌더 실패 때문에 재시도해도 attempt 목록과 선택 이유를 남긴다.

**메모리 조건:** ‘이미 약 5GB 사용’은 의뢰자의 보고이고 이번 실측은 아니다. 4096MiB는 **실행 중 유지할 하한**이지 그만큼 비어 있으면 카메라와 PhysX를 띄울 수 있다는 용량 예측이 아니다. `Q/gpu_guard.py:32` 전후는 자식을 먼저 띄우고 이후 200ms 간격으로 잰다. 따라서 기동 전 여유 검사도 필요하며 순간 할당 급증을 완전히 막는 장치는 아니다. probe에서 하한을 침범했으면 다음 자식도 띄우지 않는다. GPU 1에서 실제 peak·최소 여유·샘플 수를 본 뒤 다음 단계로 간다. 이번에 GPU 메모리를 조회하지 않았다.

**장치 조건:** guard의 NVML GPU 1, `CUDA_VISIBLE_DEVICES=1` 아래 CUDA 논리 0, Isaac/Kit 렌더 장치가 같은 물리 UUID인지 최초 실제 로그에서 확인한다. CUDA mask만으로 렌더까지 격리됐다고 단정하지 않는다. 설치된 `app_launcher.py:700`은 `active_gpu`와 `physics_gpu`를 설정한다. 현재 배정의 실제 효과는 미확인이다. GPU 0 학습의 여유를 영상 작업이 쓰는 구성은 허용하지 않는다.

**0절의 운영 판단:** 의뢰에 적힌 ‘17c를 읽기 전 full 기동’은 정당화할 수 없다. 진단 불리언과 알림은 독립 검토의 대체물이 아니다. 이번에는 검증 답이 존재하는지만이 아니라 실제 판정과 수정 조건을 읽은 뒤 재개한다. 중단된 두 full 실행의 보류는 유지한다. 이 문서는 17e나 그 두 자료의 승인이 아니다.

## 4. CE12 허용 오차와 입증 범위

**추정:** 기록을 보기 전에 기준을 정한 절차는 옳다. 다만 수치 자체가 실증된 것은 아니다.

| 항목 | 판단 |
|---|---|
| 관측·target·last action 절대 오차 `1e-6` | FP32 경로 진단의 보수적인 초기 기준으로 수용. term별 단위·최대 차·위치·분위수를 함께 남길 것. 정수 이름/배치/shape/history 길이/명령 스케줄은 수치 오차로 완화하지 않음 |
| CPU 재계산 action 절대 오차 `1e-4` | 사전 진단 한계로는 수용하나 실제 GPU 대비 오차 근거는 미확인. CPU 가짜 기록 차 0은 CPU와 GPU 차이의 근거가 아님 |
| 불일치 시 처리 | native GPU와 CPU 재계산 차이, CPU native-obs와 CPU adapter-obs 차이를 나눠 원인을 구분. 초과하면 보류하고 dtype/TF32/정규화/배치/라이브러리/연산 순서를 조사. 통과시키려고 사후 허용 오차를 올리지 않음 |

**확인됨:** 내 `DESIGN-astra-12-common-eval.md:70`의 `q_default + scale × clipped_raw` 설명은 이 CTS 구현에 틀렸다. 설치된 `IL/envs/mdp/actions/joint_actions.py:168`은 **raw × scale + offset을 만든 다음 target을 clip**한다. CE 구현이 이를 바로잡은 것이 맞다. motor offset DR 때문에 offset은 고정 q_default와 다를 수 있고, 기록한 실행 시점 offset을 써야 한다. 이전 내 문서를 권위로 유지하면 안 된다.

**추정:** 60 step 평지 기록은 시작 정합성 진단에는 적절하지만 reset 이후 이력, episode 중 명령 전환, miss 광선, 경계 clip까지 native에서 검증했다고 하면 틀린다. 실제 reset 횟수·명령 전환 횟수·miss 수를 함께 공개하고 0인 경로는 미확인으로 둔다. stage-1의 완전한 승인 전에 최소한 환경 일부만 reset한 뒤 첫 관측/last action/이력 갱신을 native와 맞추고, 같은 환경에서 명령이 바뀌는 짧은 fixture를 추가하는 편이 낫다. 저수준 pre-reset terminal 수집과 P0/P1 성적은 다음 단계다.

## 5. 무작위화 영상의 물리적 의미와 문구

### 마찰

**확인됨:** `q_rand.py:213`은 발만이 아니라 로봇의 **모든 shape**에 static/dynamic/restitution 값을 쓴다. 바닥값은 별도다. ‘바닥 마찰 0.2’, ‘발만 0.2로 바꿈’은 현재 구현의 정확한 설명이 아니다.

**확인됨:** PhysX의 두 재질 결합은 선택된 combine mode에 따르고, 두 재질의 mode가 다르면 더 높은 우선순위를 쓴다. average일 때만 `(a+b)/2`다. [NVIDIA PhysX 공식 PxCombineMode 문서](https://nvidia-omniverse.github.io/PhysX/physx/latest/_api_build/structPxCombineMode.html).

**추정:** 바닥 static/dynamic=1, 실제 pair 결합=average라면 로봇 0.2는 접촉 계수 0.6, 로봇 0은 0.5, 로봇 1.5는 1.25다. `--fric_low 0.0`은 **로봇 쪽 학습 설정 범위의 낮은 끝**을 시연하려는 목적에는 맞다. 접촉 무마찰 0을 보여주는 것은 아니다. 학습의 유한 64 bucket이 정확히 0을 뽑았다는 뜻도 아니고, 모든 shape에 똑같은 끝값을 적용한 장면은 학습의 무작위 공간 분포와도 다르다.

**미확인:** 현재 코드는 PhysX tensor API로 바꾼 런타임 재질의 결합 mode를 직접 읽지 못한다고 `q_rand.py:428`에 스스로 적는다. USD에서 읽은 바닥/바인딩과 기본 average 추정만으로 실제 pair 계수를 실측했다고 할 수 없다. 영상 하단의 ‘PhysX 규칙 계산’에는 **‘average 가정 · 런타임 결합 미확인’**을 같이 적거나 접촉 계수 표시를 보류한다. JSON 깊은 곳에만 주석을 두면 보는 사람에게는 확정 수치로 보인다.

probe의 `|마찰력|/|법선력|`도 여러 접촉의 합력, 미끄럼 여부, 적분 시간의 영향을 받는다. 정지 마찰의 한계까지 도달하지 않은 표본만으로 계수를 역산할 수 없다. 현재 한 판의 최대/분위수는 힘의 기술 통계로만 적고 ‘마찰 계수 측정 완료’라고 하지 않는다.

### 밀기와 종료

**확인됨:** 설치된 `IL/envs/mdp/events.py:1065`는 기존 root velocity에 무작위 delta를 더한다. `push_fixed`의 더하기는 그 구현과 맞다. 함수 docstring만 읽고 절대 속도 덮어쓰기라고 반박하면 오히려 틀린다. 다만 실제 힘 N이나 일정 시간 외력을 가한 시험이 아니라 **순간 속도 변화**를 주는 교란이다. 방향도 학습의 world 축 무작위 표본과 달리 heading 기준 고정 순서다.

**추정:** `illegal_contact` 자동 reset을 끄고 같은 함수를 호출하는 것은 시연에서 순간이동을 막는 합리적인 선택이다. 그러나 ‘학습 때와 같은 조건’이라는 전체 주장은 성립하지 않는다. 관측 잡음 off, 고정 마찰/밀기, reset pose, curriculum off, episode 길이, 평지 고정까지 바뀐다. 같은 입력 상태에서 그 접촉 함수의 판정은 같을 수 있지만, 첫 종료 뒤의 상태 분포와 return은 학습과 달라진다. Q의 tilt/below-support 조건까지 보탠 낙상 정의도 학습의 접촉 종료와 동일하지 않다. 현재 ‘넘어짐 이후 참고 화면’ 표시는 유지한다.

허용할 문구:

- ‘E1 student의 사전 지정한 평지 1판에서, 학습 설정 범위 안의 고정 속도 교란/로봇 재질 변경에 대한 반응을 시연했다.’
- ‘관측 잡음을 끄고, 낙상 후에는 자동 reset 대신 화면을 이어 기록했다. 낙상 이후는 성능 판정에서 제외했다.’
- S0: ‘각 native 환경에서 기록한 원시 상태를 adapter로 재구성해, 명시한 허용 오차 아래 관측·action·joint target을 대조했다.’ 이는 실제 대조가 끝난 뒤에만 쓴다.

허용하지 않을 문구: ‘무작위화 범위의 강건성을 입증했다’, ‘실제 미끄러운 바닥에서도 안전하다’, ‘v2보다 우수하다’, ‘같은 시험지 비교 완료’, ‘GPU native와 CPU가 비트 동일하다’. 지금 제공된 CPU 시험과 한 판 영상으로는 그 결론이 나오지 않는다.

## 6. S2 설계의 네 질문

### 6.1 같은 출발점인가

**확인됨:** 읽은 부모의 student `evaluate(is_teacher=False)`는 student latent를 **detach한 뒤** critic obs와 합친다 (`actor_critic_moe_cts.py:236`). S2의 같은 처리는 옳다. teacher latent로 바꾸거나 critic loss가 student encoder를 새로 갱신하게 만들면 부모의 student 경로와 다르다.

**확인됨:** S2 사본은 첫 층을 `Linear(77,512)`와 0 초기화 `Linear(64,512,bias=False)`의 합으로 구현한다. 부모 matmul의 모양을 보존하므로 하나의 141열 GEMM이 합산 순서를 바꾸는 문제를 피하려는 판단은 타당하다. 이번 CPU T4에서 초기 A/B의 action과 student critic 값·분포 동치를 확인했고, T7에서 부모와 메모리를 공유하지 않는 것도 확인했다. **CPU의 이 입력·배치에서 확인한 동치**이지 GPU 동치를 대신하지 않는다.

**추정:** 이것은 A/B의 **초기 정책 함수와 초기 매개변수**를 맞춘다. 기존 학습을 그대로 resume하는 것은 아니다. teacher 표본, 모방/재구성, MoE load balance, optimizer 상태를 버리고 student PPO로 전환한다. 새 Adam의 첫 갱신부터 기존 run의 다음 갱신과 달라진다. ‘차원이 달라 Adam을 절대로 못 가져온다’도 엄밀히 틀리다. 기존 매개변수의 moment를 대응해 옮기고 새 부분만 초기화할 수 있다. 다만 새 실험에서 A/B 모두 새 optimizer로 시작하는 선택은 단순하고 유효하다. 그렇게 선택했다고 명시하면 된다.

A/B에서 부모·새 지도 encoder의 초기값·optimizer 규칙·관측/명령·배치 예산·종료 규칙을 맞춘다. 학습 전 초기 상태와 RNG를 저장하고, 모델 생성이 소비한 난수가 지형/DR 샘플까지 바꾸지 않게 한다. 공통 privileged critic은 정책 학습에서 허용되지만 두 critic은 처음에만 같고 이후 독립 학습한다. A가 지도 정보를 직접 받지 않는다는 주장은 actor의 온라인 입력에 한정한다. A도 지형 정보가 있는 critic을 학습 신호로 쓴다.

### 6.2 mask가 실제로 뜻하는 것

**확인됨:** 설계 §3의 ‘안 맞음·너무 깊음은 함께 mask 0’과 ‘mask로 안 맞음과 실제 낮은 땅을 가른다’는 서로 모순이다. 다음 값은 `s2_map_obs.height_and_mask()`를 CPU에서 직접 넣어 얻었다.

| 센서 z / hit z | 출력 `[height, mask]` |
|---|---|
| 0.4 / +inf | `[1,0]` |
| 0.4 / -2.0 | `[1,0]` |
| NaN / 0 | `[1,0]` |
| 0.4 / NaN | `[1,0]` |
| 0.4 / 3.0 | `[-1,1]` |

지금 mask는 **‘유효 충돌 여부’가 아니라 ‘유한하며 base 아래 1m보다 깊지 않음’**이다. 깊이 1m 경계에서 몸체 높이 변화만으로 mask가 바뀌며, 위쪽 장애물도 통과하는 단측 조건이다. ‘몸 아래 1m 안의 지지면’이나 ‘딛기 가능’이라고 부르면 안 된다. 발 도달 범위·법선·수평 거리·접촉 안정성을 판정하지 않았기 때문이다.

**제안:** 이번 물음이 이상적 높이 지도의 정보 효과라면 1m의 경험적 깊이 분류를 섞지 말고, `hit_valid`는 정상적인 지형 충돌 여부로 정의하며 유한한 깊은 지면은 높이를 clip하더라도 mask 1로 남기는 편이 낫다. 구멍 무한값과 유한한 낮은 바닥을 분리한다. 도달 가능성을 별도로 시험하려면 다른 이름의 채널/조건으로 등록한다. 현재 인코딩을 유지할 수도 있지만 그 경우 ‘깊은 곳과 무충돌을 같은 위험 범주로 묶은 이상적 입력’이라는 더 좁은 질문이 된다. 어느 정의인지 학습 전에 결정해야 한다.

**기동 전 필수:** 정상적인 ray miss와 수치 고장을 분리한다. base/sensor 좌표 NaN까지 ‘구멍 있음’으로 바꾸는 현재 구현은 잘못이다. sensor 좌표와 hit packet의 유한성·예상 miss 표현을 검사하고, 정상 miss 이외의 오류는 무효/중단으로 전달한다. 첫 종료 이후의 비정상 데이터 처리도 별도다. A/B 모두 같은 run 유효성 관문을 써야 한다.

**확인됨:** S2 README §6이 지적한 critic의 gap 의미도 중요하다. 부모 `height_scan`은 +inf hit를 빼서 -inf로 만들고 clip -1, scale 2.5를 적용한다. 새 actor는 이를 +1/mask 0으로 읽는다. 다른 두 네트워크의 부호가 꼭 같아야 하는 것은 아니지만, 부모 critic이 gap에서 올바른 value를 보존했다는 근거는 없다. NaN이면 clip으로 없어지지도 않는다. critic 입력·value·return·advantage의 유한성과 초기 gap value 편향을 별도로 점검한다. critic 인코딩을 고치려면 두 군에 똑같이 적용하되 ‘부모 value 함수 그대로’ 주장은 철회한다.

### 6.3 encoder를 PPO로 풀 때의 위험과 대응

**추정:** 위험은 있다. ‘무너진다’고 미리 단정할 수는 없다. 부모는 student encoder를 재구성·load balance 손실, 별도 Adam lr 0.001로 학습했다. 새 실험에서는 다른 손실과 새 optimizer를 쓰므로 PPO lr `0.00017085937500000009`가 더 작다는 사실만으로 안정성이 보장되지 않는다. L2Norm은 latent의 크기를 제한할 뿐 방향 변화나 expert 쏠림을 막지 않는다.

첫 통제 pilot에서는 A/B 모두 encoder를 고정하는 짧은 준비 구간을 사전에 정하고, 이후 encoder lr을 actor보다 낮게 두는 동일한 규칙을 제안한다. 정확한 고정 길이와 lr 비율은 아직 근거가 없으므로 확정 수치처럼 쓰지 않는다. 고정된 관측 묶음에서 부모 대비 action 차·KL·latent cosine 변화, expert 선택 비율/entropy, gradient norm, value 오차와 기본 평지 명령 성능을 기록한다. 보행 퇴행이나 과도한 변화의 중단 기준은 결과를 본 뒤 정하지 않는다.

두 군에 같은 방어 규칙을 적용하면 A/B 비교는 가능하지만 그 결과는 **그 규칙 아래의 지도 효과**다. ‘순수한 모든 지도 정책의 효과’로 일반화하지 않는다. load balance나 anchor 손실을 다시 넣기로 하면 ‘PPO만’이라는 설계도 함께 바꿔야 한다.

### 6.4 T1~T7이면 충분한가

**확인됨:** 구현의 수식·초기 동치·합성 gradient 경로를 확인하는 시험으로는 유용하다. 하지만 T2는 지금의 잘못된 NaN/깊이 의미를 정답으로 고정한다. 변이 시험도 그 정답이 과학적으로 옳다는 보증은 아니다. T5는 실제 rollout/GAE/저장소/미니배치가 아니라 PPO 형태의 합성 손실이다.

추가로 필요한 검증은 다음과 같다.

- **입력 의미:** 정상 miss·유한한 깊은 바닥·높은 장애물·센서 NaN·ray packet 손상을 분리한다. 평행 이동 및 yaw 90도에서 실제 발밑/앞쪽 칸이 옮겨지는지 확인한다. 20m ray 시작 offset을 몸체 기준 높이에 다시 더하지 않는다.
- **Isaac 접속:** 실제 collision mesh의 평지·단차·빈 공간에서 `pos_w`, hit, ray ordering, 업데이트 시각을 기록한다. 설계상의 높이 함수로 만든 가짜 hit만으로 실제 광선의 충돌 의미를 승인하지 않는다. 촘촘하지 않은 발판에 광선이 실제로 닿는지도 센다.
- **reset/시점:** 부분 reset 환경의 history/map/previous action 갱신, 처음 관측, terminal/timeout bootstrap을 검사한다. map만 이전 step이거나 다음 step인 경로를 막는다.
- **학습 연결:** `map`이 rollout 저장소와 모든 minibatch에 보존되는지, actor 경로에서만 A/B가 다르게 들어가는지, teacher/모방 학습기가 실제로 제거됐는지, optimizer param 중복·누락/gradient detach를 검사한다. 전체 minibatch update 뒤 같은 저장물을 다시 불러 action·value·log-prob가 복원되는지도 본다.
- **정보 차단과 사용:** A의 지도가 일정하다는 것 외에 A의 다른 actor 입력으로 실제 mask/height가 새지 않는지 검사한다. 학습된 B에서 지도를 가리거나 섞었을 때 행동/성적이 어떻게 바뀌는지도 후속 진단으로 둔다. 지도 gradient가 있다고 지도를 유용하게 사용한 것은 아니다.
- **공정성:** 같은 sparse 분포·명령 조건·총 sample/update 예산·평가 지형 묶음·복수 seed를 미리 등록한다. mixture 비율과 실제 위험 구간 조우율을 분리하며 접근·우회·정체도 분모에 남긴다. 같은 seed라고 서로 다른 정책의 이후 상태까지 같다고 요구하지 않는다.

현재 S2 README도 env map 그룹, `RolloutStorageCTS`, MoECTS 대신 PPO 연결을 미구현으로 적는다. CPU 7/7을 근거로 오늘 밤 S2 학습을 시작하면 안 된다. 설계/CPU 준비 작업은 계속할 수 있다.

## 7. lead가 추가로 놓치면 안 되는 것

- **수집과 주장의 경계:** S0 1단계 통과는 관측/action adapter의 정합성이다. 공통 actuator/접촉/지형으로 옮긴 P0/P1 비교, 실제 지형 일반화, 구조 우열은 아직 별도다. 평지 시연은 강건성 증거가 아니다.
- **자료와 출처:** RAND의 manifest가 해시를 적는 것과 validator가 그 해시를 요청에 연결하는 것은 다르다. result의 train/code hash, meta, CSV/NPZ, 실제 video 파일을 같은 attempt로 묶어야 한다. 이번 반례는 파일 내용 변경을 통해 그 누락을 드러냈으며 실제 변조 사건이 있었다고 주장하는 것이 아니다.
- **재시도 편향:** 프레임 관문의 색/명도 조건이 넘어져 가려진 로봇을 거절할 수 있다. 렌더 불량과 물리적 실패를 구별하지 않으면 ‘결과로 고르지 않음’ 문구도 보장되지 않는다. 실패 영상/원자료와 재시도 이유를 보존한다. 정상 프레임 자동 관문은 로봇·지면·표시 문구가 맞는지 사람이 보는 검사를 대신하지 않는다.
- **회복 시간 수치:** `RAND/rand_lib.py:289`의 `push_response`는 peak는 2초 창을 쓰지만 settle은 다음 밀기 이후까지 검색한다. 또 `round(0.25/0.02)`는 12표본으로 0.25초 지속을 입증하지 못한다. 회복 시간 주장을 하려면 다음 교란/낙상에서 우측 검열하고 실제 timestamp span으로 지속 조건을 검사한다. 이를 고치기 전에는 영상 자체는 시연하되 회복 시간 수치는 결론에서 뺀다.
- **같은 source와 같은 실행:** 새 wrapper를 검증했어도 CE/RAND의 인자·기록 schema·실제 importer 경로와 연결되는지는 다시 확인해야 한다. 17c처럼 CPU에서만 성공한 가짜 import를 실제 Isaac 격리의 증명으로 취급하지 않는다.

## 8. 재현 근거와 고정 해시

시험은 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`로 했다. 임시 뿌리는 `C:/Users/AI-WS01/AppData/Local/Temp/astra17d_cpu_i72d_3rf`였다. 그 아래 `_eval/ce12`, `_eval/rand_scenes`, `_eval/s2`에 사본을 두고 공용 의존 파일도 사본으로 옮겼다. test의 출력·가짜 자식·잠금·registry는 이 임시 뿌리에서만 사용했다. 원래 `_eval/slot`은 사용하지 않았다.

재현한 별도 반례 절차:

1. 사본 `test_rand_scenes`의 `fake_q_rand()`를 driver의 주입 가능한 runner로 연결한다. `run_id`별 새 임시 폴더, `--duration_s 4.2 --smoke_s 1.0 --tries 1 --scenes base,push_lat`를 쓴다. guard 반례 외에는 `--skip_smoke`로 해당 비교 경로만 검사한다.
2. guard 반례는 `scene == smoke_probe`에서만 `guard_stop=True`를 준다. 나머지는 정상 fake다.
3. cross 반례는 push의 `terrain_mesh` hash 문자열을 바꾸고 `traj.npz` state 10의 `base_x_m`에 0.02를 더한다. 빈 지문 반례는 두 result의 fingerprint를 `{}`, terrain_mesh를 `[]`로 둔다.
4. 지지면 반례는 두 CSV와 NPZ의 `ground_z_m`, `base_height_above_ground_m`를 전부 NaN으로 둔다. 밀기 반례는 첫 applied 사건의 requested/measured delta 둘을 `[0.4,0,0,0,0,0]`으로 바꾼다. 둘 다 최초 계획의 heading +vy는 그대로다.
5. 각각 개별 validation과 driver 끝까지 실제 CPU 검사기를 통과시켰다. 다섯 경우 모두 `rc=0`, guard 반례는 이후 세 장면 호출까지 확인했다.
6. CE는 `test_run_dump.fake_npz()`와 `make_valid()`로 baseline을 만든 후 §2.7의 meta 결함/서명 누락을 주입하고 `failed()`를 호출해 `[]`를 얻었다. §2.5는 같은 시험의 `run_dump()`에 등호형 outdir를 주어 가짜 자식의 실제 생성 위치와 `rc=0`을 확인했다.

이 절차의 임시 probe 스크립트 SHA256은 `c8156facb2170db433fb9c6a406b56df777b966f545a1799dcdfe605700ea01c`, 결과 JSON은 `e2d523d044e326909e203a8d40812d87a405a64ebb2f9c1a4d2d96eab5876119`였다. 사용자 지시대로 임시 파일은 검증 종료 때 삭제하고, 재현 입력·결과는 위 절과 이 파일에 남긴다.

| 검증 대상 | SHA256 |
|---|---|
| CE SHA256SUMS.txt | `72e2b8ff3250d875abfd2675892642f7e6e8dce9be7fdfc336eaceede06582de` |
| RAND SHA256SUMS.txt | `e00630482064981a8cb7dc0616469febbbffebbdfaff83f46191139ea7f547c5` |
| DESIGN-s2-ab-v1.md | `34948bd948b667b24118071d50923c94b50eb284d1d31d37d684f9a0e9e07847` |
| S2 s2_map_obs.py | `451cfed925a4796fac2952fae630cd1d951a2bcfa4a67e8b0f686cc75adc5ce5` |
| S2 s2_policy.py | `8897ed644a1b6a088e59931c8525b28c55724936e4d37e1c59c1b913a2099081` |
| S2 test_s2.py | `0f82662d46dfa6783ab081bfb8533435ec7a740e20f7248b48189649a7b783e2` |
| S2 README-s2-step1.md | `bed6803cd0008042b7c8f500cc89b26cd05f441ec39e8812fb69591aec525d82` |
| 시험용 isaac_slot.py 사본 | `90ae613b0e7e791fa24bf82866eb0a0285eafe5cd10f0e201ba2f5af9fa19c47` |
| 시험용 usd_isolate_run.py 사본 | `366a3c13aac3499e711ea717441ae7e3da67871302b5c6e432b1cbc20ea0a87f` |
| 시험용 frame_audit.py 사본 | `80e7d8cd667086618fa9de5143b58ff2abbf0d686fb983148ee65d6e8c1feda0` |
| 시험용 q_metrics.py 사본 | `c9930f8d327efd04df51440da519fefab2585490ae45b4a6ffbd39466138a794` |

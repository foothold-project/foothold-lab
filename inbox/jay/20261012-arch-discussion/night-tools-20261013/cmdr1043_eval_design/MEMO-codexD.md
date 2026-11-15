> 분류: A/평가 · 1043 쌍 평가 설계
> 작성: Codex Worker · 2026-10-14
> 근거: `TASK-codex-worker-1043-eval-design.md`, `VERIFY-astra-17p.md` §5, `VERIFY-astra-17.md` §3.2~4, v37 드라이버와 v10 후처리 및 실제 1043 입력의 읽기 전용 대조
> 요지: 1043 평지 CMD-R 목표 평가에는 독립 등록 입력, 새 출력, v3 실행 관문, 새 후처리 판과 승인이 필요하다. 기존 1042 결과나 승인은 재사용하지 않는다
> 상태: 설계 제안 · GPU 기동과 새 코드 동작 미확인

# 1043 쌍 평가 설계 메모

## 범위와 결론

이번 단계에서는 코드를 작성하거나 Isaac, GPU 평가를 실행하지 않았다. 권고는 **v37을 동결한 채 새 1043 전용 드라이버와 v10 후처리의 새 판을 만들고, 둘이 동일한 사전 등록 manifest를 읽게 하는 길**이다. v37의 `OUT`, 모델, 실험 이름, 인계, 비교 보고서, 평가기 기본 출력, 로그 이름, 재사용 판정이 서로 연결되어 있다. 단순히 체크포인트 경로를 바꾸면 1042 자료를 읽거나 쓰는 조용한 오류가 난다. 특히 새 파일 이름으로 v37을 복사하면 `PARTICIPANT`와 `SELF_PATH` 판정도 바꿔야 한다. 새 판의 검증과 기동 승인은 별도다.

지시된 해석기 확인값: `C:\Users\AI-WS01\anaconda3\envs\isaac311-moects\python.exe`. 읽기와 SHA256 계산에만 사용했다. `CUDA_VISIBLE_DEVICES=-1` 조건을 지키기 위해 GPU 또는 Isaac 자식은 전혀 띄우지 않았다.

## 읽은 인터페이스와 실행 계약

| 구성요소 | 입력과 출력 · 장치 지정 | 설계상 필요한 연결 |
|---|---|---|
| `q_eval_cmdr.py` | `--checkpoint`, `--train_yaml`, `--families`, `--cells`, `--episodes`, `--eval_seed`, `--obs_noise`, `--physx_small_buffers`, `--tag`, `--outdir`. 결과는 `<outdir>/<tag>/meta.json`, `traj.npz`, `episodes.csv`, `cells.json` 등. 자식의 논리 `cuda:0`과 `meta.devices.torch_cuda0_uuid`를 사용한다. | 부모 `env.yaml`과 branch `bundle.json`의 부모 경로·해시를 확인한다. 새 루트를 **명시적 `--outdir`**로 전달하고 물리 GPU는 `CUDA_VISIBLE_DEVICES` 및 UUID로 연결한다. 현재 v37의 `q()`는 `--outdir`를 전달하지 않는다. |
| `q_eval.py` | 거의 같은 평가 CLI. v37 시작 시험의 원본 대조에 사용한다. | 새 판도 알려진 답의 원본 대조를 유지한다. 시험 출력 역시 새 루트로 보낸다. |
| `q_post.py`, `q_metrics.py` | 평가 자료에서 episode·cell 표를 만든다. `q_metrics.py`는 0.02초 step, 통과·생존·MAE 계약과 Wilson, Newcombe, McNemar, Holm 함수를 제공한다. | 평가기 원자료와 표의 정의를 고정하고 관련 코드 해시를 등록한다. |
| `paired_ci.py` | `tango(b,c,n)`이 짝 이진 차이의 95% 점수 구간을 계산한다. | v10의 판정 구간과 같은 판을 고정한다. |
| `gpu_guard.py` | `--gpu <NVML 물리 index> --min_free_mib 4096 --log <경로> --summary <경로> -- <자식>`. 종료 99는 메모리 하한 중단. UUID, 최소 여유, 최대 사용량을 요약에 쓴다. | 기동 전 UUID·여유 조회를 별도로 하고, 같은 물리 GPU를 guard·CUDA 가림·meta에 대조한다. guard의 실행 중 기록만으로 기동 전 여유를 주장하지 않는다. |
| `isaac_slot_v3.py` | `--watch_log`, `--record`, `--usd_root`, `--attempt`, `--lock`, `--registry`, `--scan_dirs`, `--stop_file`, `--deadline`, `--expect_conversions 0|1`, `-- <자식>`. v3 기록과 종료 89~98로 변환 수·루트 밖·미할당·충돌·registry 오류를 구분한다. | attempt별 USD 루트, **v3 전용 registry**, 모두가 공유하는 변환 lock, 실제 상대 로그를 포함한 scan 목록, 기대 변환 1을 명시한다. 기본 registry는 구형 이름이므로 쓰지 않는다. |
| `isaac_slot.py` | 같은 성격의 구형 v2 CLI. 기본 registry가 구형이고 v3의 루트·registry 보호를 충족하지 않는다. | 읽기 대조만 하고 새 실행 경로에 쓰지 않는다. |
| `usd_isolate_run_v3.py` | `FOOTHOLD_USD_ROOT`와 `FOOTHOLD_EXPECT_CONVERSIONS` 환경을 받아 변환 루트를 격리한다. `python usd_isolate_run_v3.py <평가기> ...`로 자식을 감싼다. | slot v3의 `--expect_conversions 1`과 환경 계약을 맞추고 isolate 기록의 루트·할당·차단을 검사한다. |

실제 구성은 `새 드라이버 → slot v3 → gpu_guard → usd_isolate_run_v3 → q_eval_cmdr.py`로 제안한다. v37의 자체 `convert_slot()`은 `out/isaac_convert.lock`와 `out/` 로그만 보고, 상대 참가자도 같은 v37 파일로 식별한다. 두 방식의 잠금을 중첩해 별개 권위처럼 쓰지 않는다. v3 관문으로 이관하되 기존 v37이 계속 실행 중이면 그 공유 잠금과 상대 로그도 기동 전 대조한다. 구형 registry는 읽기만 하며 읽기 실패를 충돌 없음으로 처리하지 않는다.

## 1042 결박 전수 점검

줄 번호는 읽은 바이트의 `cmdr_eval_driver_v37.py`와 `cmdr_post_v10.py` 기준이다. `out/`을 가리키는 보조 함수도 전부 새 출력 루트를 받도록 바꿔야 한다.

| 위치 | 현재 쓰임 | 1043에서 바꿀 값 · 방치 시 결과 |
|---|---|---|
| v37 1~156, 175~184, 213 | 머리 계약은 GPU 1·1042. `OUT=HERE/out`, `B=out/branch`, `MODELS`는 1042 off/on, `EXPERIMENT=cmdr_s1042_pair_eval`. | 새 루트·실험 ID·1043 체크포인트를 한 manifest에서 읽는다. 방치하면 옛 모델을 평가하거나 옛 결과를 덮는다. |
| v37 197~223 | `--gpu` 기본 1, GPU UUID 상수, `CUDA_VISIBLE_DEVICES`, 로그·attempt 파일·`NIGHT_OUT`은 옛 루트. | manifest의 물리 GPU UUID와 index를 기동 직전 조회·대조하고 새 로그·마감·STOP·attempt 경로 사용. index만 바꾸면 다른 GPU 또는 옛 상태를 읽을 수 있다. |
| v37 269~279 | `pins()`가 `out/branch/cmdr_s1042_off_u4000/bundle.json`의 코드 파일 해시를 기준으로 한다. | 1043 off/on 번들의 코드 파일 해시와 현행 바이트를 각각 대조한다. 옛 등록 해시를 쓰면 1043 입력을 승인한 것처럼 보인다. |
| v37 295~321, 머리 87~88 | GPU 0 인계는 1042 on `result.json`의 tag·cmdr·`where=end`·`label_next=24000`, 1042 night 로그의 `EXIT 0` 다음 `NIGHT DONE`을 요구한다. | 1043 양 군의 결과, stamp, 로그, 필수 체크포인트·해시 및 기동 직전 장치 상태를 새 계약으로 확인한다. 현 코드를 두면 영원히 기다리거나 1042 종료를 1043 완료로 오인한다. |
| v37 442~469 | 체크포인트 준비는 크기·mtime 안정 후 SHA256. on은 1042 번들 비교 JSON, off/on `bundle.json`·`.npz`, `envs=8192`, `updates=4000`, gate false, 도구 해시를 요구한다. | 1043 전용 새 비교 보고서를 만들고 두 군의 현재 번들 해시를 확인한다. 기존 비교 보고서로는 거절되거나, 조건을 완화하면 서로 다른 군을 짝짓는다. |
| v37 501~505, 557~643 | `PARTICIPANT="cmdr_eval_driver_v37.py"`, `SELF_PATH`와 외국 Isaac 판정, 자체 변환 lock. | 새 파일 이름의 자기 식별과 v3 slot 참가자 정책을 다시 설계한다. 복사만 하면 자기 프로세스를 외국으로 보고 대기하거나 잘못된 lock을 믿는다. |
| v37 690~795, 821~824, 842~925 | USD 검색·시도 보관·guard 로그가 `out/`을 쓰고 `q()`에는 `--outdir`가 없다. `validate()`는 CUDA UUID, 원본 `env.yaml`, 번들, 개별 출력·짝 지문을 확인한다. | 모든 경로와 태그를 새 루트로 전달하고 같은 검사를 유지한다. 평가기 기본 `out/`와 드라이버 새 루트가 갈라지면 출력이 조용히 옛 루트에 생긴다. |
| v37 989~1043 | 시작 시험의 smoke, q 원본 대조, 버퍼 대조, 잘못된 YAML 거절, branch 시험은 `p20000` 및 옛 `out/branch/gate_c1`을 사용한다. | 알려진 답 시험은 새 루트의 사본 fixture로 옮기고 1043 번들 경로를 대조한다. 방치하면 시험만 옛 자료에 통과해 새 경로 결함을 놓친다. |
| v37 1046~1135, 1183~1390 | 5 모델 × 111칸 jobs, 태그 `cq_*`, 재사용 stamp, 두 base·remeasure 인스턴스와 옛 log/attempt를 결합한다. | 1043 전용 태그·log·attempt·STOP과 새 run stamp만 인정한다. 이름이 같으면 1042 결과를 재사용하거나 중복 평가·짝 오염이 생긴다. |
| post 123~131, 189~207 | `OUT` 기본 `out/`, `DEST` 기본 OUT, 모델·로그 두 개와 `EXPERIMENT=cmdr_s1042_pair_eval` 고정. | 새 post 판에서 manifest의 모델·로그·실험 ID·출력 파일을 받는다. `CMDR_POST_OUT`만 바꾸면 1042 ID 검증에 막히고, ID만 완화하면 옛 로그 혼합 위험이 있다. |
| post 225~339, 399~427 | owner log, attempt, stamp, 네 출력 해시, hold 목록과 release 증거를 읽는다. v3.2 legacy stamp도 조건부 허용한다. | 1043은 **새 수집만** 허용하고 새 전용 hold 파일·승인 자료를 쓴다. 1042 hold/승인 JSON과 legacy 재사용은 금지한다. |
| post 700, 713~755 | `DEST/cmdr_post.json`, `DEST/CMDR-tables.md`를 직접 쓴다. 표 제목은 아직 `cmdr_post_v8.py`라고 적는다. | 새 루트에 원자적 저장, 1043 스키마·제목·등록 해시·해석 한계 문구를 남긴다. 현재 저장 경로 기본값을 쓰면 옛 보고를 덮는다. |

`cmdr_post_v10.py`는 직접 GPU를 지정하지 않지만 1042 로그의 `meta.devices`, stamp, 출력 루트와 실험 ID에 묶인다. `q_eval_cmdr.py`와 `q_eval.py` 머리의 GPU 1 설명은 문서이며 실제 장치는 자식 환경의 CUDA 가림과 논리 `cuda:0`으로 정해진다. 코드에서 명시하는 물리 UUID 대조가 필요하다.

## 실제 1043 입력의 읽기 전용 확인

부모 경로: `C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192/model_20000.pt` · SHA256 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`. 두 군 `bundle.json`과 `result.json`의 `parent_sha256`가 이 값과 같다. `result.json`의 seed는 모두 1043, `num_envs=8192`, `updates=4000`, `gate=false`, `where=end`, `label_next=24000`, `iter_from_counter=24001`이다. off는 `cmdr=off`, on은 `cmdr=on`이다. `validate_stamp.json`이 나열한 파일은 모두 존재하고 현재 SHA256과 일치했다. 이는 저장 바이트 대조이며 학습 validator 재실행이나 평가 성능 확인은 아니다.

| 군 | 22,000 SHA256 | 24,000 SHA256 | `result.json` SHA256 | `bundle.json` / `bundle.npz` SHA256 |
|---|---|---|---|---|
| off | `5659566bc538cdd8ed549ddd60e0b22f9460ed4978430265f55910f041006f6d` | `2ea3b5e8303a5a7150532c3fa784b319c39e085c092f0c13cc5b07af6a04fa69` | `40536a6d4f45e32dc5b6bc46c5a9b156a61c4e158ae980ac2e64fc13c2420bce` | `a352f01842df8e24c36067749b13cbeb2467d8e729c3e02bdbfe3a8252da9f6f` / `3dcf7790b40e83dc2e8c51920de0886a088f6f9a0781edc46ae5c16f09804a44` |
| on | `f8070d487d3d5a5eec3b77ea4cd433e3a136b35ed3760315d316ee9ca4948d42` | `e548b51602bb5cf848f497e6a7a40afbbf4f8f65fb59149d19b71ae0a52be454` | `8527f06059937139194ec875bc04f9fb2e7fe073422fc8b2d4093958497d2b59` | `a4a19388a1bf2e5a40b488b49bdae082ea73d1127b05064ce36c8e717e679246` / `3dcf7790b40e83dc2e8c51920de0886a088f6f9a0781edc46ae5c16f09804a44` |

두 군 모두 `model_20500`, `21000`, `21500`, `22000`, `22500`, `23000`, `23500`, `24000.pt`가 있다. 1042의 `MODELS`에 대응하는 1043 다섯 항목은 위 부모 20,000과 off/on 22,000·24,000이다. 위 체크포인트 크기는 각 26,367,183바이트다. 중간 체크포인트도 존재하지만 CMD-R 목표 판정의 기본 모델 목록에는 추가하지 않는다. off `result.meta.wall_s=19264.85`, on `19643.04`초다. 이 시간은 학습 시간이지 평가 시간은 아니다. 읽은 위치에서 1043용 새 `cmdr_bundle_compare` 보고서는 찾지 못했다. 생성과 대조가 선행되어야 한다.

## 등록 manifest 초안

값을 결과 전에 고정하고 전체 JSON SHA256을 드라이버, 평가 stamp, 후처리, 최종 보고에 함께 기록한다. 예시 필드이며 현재 승인 manifest가 아니다.

| 묶음 | 필수 필드와 거절 조건 |
|---|---|
| 실험·계보 | `experiment=cmdr_s1043_pair_eval`, `train_seed=1043`, 부모 경로·SHA256·env.yaml SHA256, off/on 디렉터리·22,000/24,000 경로와 내용 SHA256, off/on `result.json`, `bundle.json`, `bundle.npz`, `validate_stamp.json` 해시. 부모·seed·tag·update·완료 상태 불일치면 기동 전 보류. |
| 학습 완료 | off/on 결과의 `where=end`, `label_next=24000`, 요청 4,000 update와 8,192환경, 필수 checkpoint, validator stamp와 실행 로그 종료 증거, 두 번 안정 관측, 새 bundle 비교 `SAME`. 파일 존재나 종료 코드만으로 완료로 취급하지 않는다. |
| 평가 계약 | 1042와 같은 평지 noise on 목표 `stop03`, `fwd01`, `fwd02`, 평가 seed 1000~1004, 칸·군·seed당 100 episode, 동일 episode ID 짝, student, difficulty 0.5, terrain_set=train, heading_hold 0, 중앙 시작, `--physx_small_buffers`의 알려진 답 대조, 부모 포함 새 수집. 각 run의 관측·reset·명령·T·출력 형식과 pairing 지문을 기록한다. |
| 확장·퇴행 | 기존 계획의 flat 11칸·noise on/off, 나머지 7 학습 family × 11칸 noise on의 seed 1000 선별. 목표 이외 on−off 24,000 점추정 ≤ −5 %p만 seed 1001~1004 추가. 범위 축소는 별도 사전 결정으로 기록하며 축소 결과를 전체 퇴행 판정으로 쓰지 않는다. |
| 장치·격리 | 물리 GPU index와 UUID, 최소 여유 4096 MiB, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, 같은 `CUDA_VISIBLE_DEVICES`, 자식 논리 CUDA 0 UUID, slot v3, isolate v3, v3 전용 registry 경로, 공통 변환 lock, 상대 로그 scan 목록, attempt별 USD 루트, `expect_conversions=1`. 조회 실패·불일치·여유 부족이면 자식 0회. |
| 실행·보고 | 전용 출력·보고·작업 루트, 새 base·remeasure log와 attempt·tag namespace, STOP 경로, 기동 deadline, 코드와 입력 파일 해시 목록, 승인 JSON의 코드 manifest 해시, 완료·무효·미수집·짝 불일치 목록. `out/`, `out_branch`, 1042 hold/승인 JSON을 쓰기 또는 재사용 대상으로 삼지 않는다. |

평가 중에도 시도 직전, slot 대기 중, slot 보유 후 자식 직전에 STOP·마감·코드·입력·checkpoint·UUID·여유를 다시 확인한다. 코드 manifest에는 새 드라이버, 새 post, q 도구, slot v3, isolate v3, guard, bundle comparator와 필요한 설정 파일을 포함한다. ASTRA가 이 **새 바이트와 새 manifest**를 검토한 뒤 새 승인 JSON을 발급하는 구조로 둔다. 1042 등록 해시나 옛 승인 JSON의 필드를 바꾸어 쓰지 않는다. 기동 기록에는 승인 JSON의 경로와 해시, 입력 manifest 해시를 함께 남긴다.

## 수집과 판정 규약

v37 `jobs()`는 5모델 × (flat noise on 11 + 목표 추가 seed 4×3 + 다른 family 7×11 noise on + flat noise off 11)로 **base 555개 run**을 계획한다. 각 run은 100 episode다. 1043에서 같은 범위를 유지한다면 새 부모도 새로 모은다. 목표만 먼저 수집한다면 3모델(부모/off24/on24) × 3칸 × 5 seed = **45 run**의 사전 정의된 진단이며, 22,000 비교·99칸 퇴행·기본 계약 전체의 완료는 주장하지 않는다. 전체 판정용 동일 범위는 부모/off·on 22,000/24,000의 5모델, base 555 run이며 선별 후 추가 run은 결과에 따라 달라진다. `post_v10.py`의 계획 회귀 칸은 99개다. 새 부모를 1042에서 읽어오는 shortcut은 허용하지 않는다.

`cmdr_post_v10.py:431~479, 501~565`는 같은 seed·episode의 off/on 짝으로 Tango 95% 구간과 차이를 계산한다. 목표 세 칸 모두 각 500쌍을 갖고 **각 구간 하한 > 0** 및 **세 칸 동일 가중 평균 차이 ≥ +10 %p**가 모두 참일 때만 `개선`이다. 하나라도 없으면 `수집 중 · 결합 판정 보류`다. Holm 결과는 병기하되 결합 규칙을 대신하지 않는다. 24,000 퇴행은 100쌍 선별에서 on−off 점추정 ≤ −5 %p인 칸을 500쌍으로 다시 재어 구간이 −5 %p 아래인지·위인지·걸치는지 구분한다. MAE +10% 계약선과 생존 ≥95%, 명령 통과 ≥90%를 별도로 표시한다. 결측·짝 불일치·출처 인증 실패는 0점이나 분모 제외가 아니라 `미확인` 및 누락 목록이다. 부모 대비 손실도 목표별·군별로 보여준다. `VERIFY-astra-17.md` §3.3의 1042 실제 값은 세 칸 평균 +5.3333 %p, 부모 대비 평균 −2.0 %p이므로 기존 on을 부모로 자동 승격하지 않는다.

문서와 코드 사이의 주의점: v37의 머리말은 GPU 1 전용이라고 시작하지만 CLI는 GPU 0/1을 받는다. v37은 post를 호출하지 않으며 post v10은 독립 실행이다. post v10은 부분 자료에서도 개별 칸 수치를 만들지만 결합 판정은 500쌍 완전성을 요구한다. v37의 `training_done()`은 **on 군의** 1042 완료만 검사하므로 새 설계의 **off/on 양 군** 완료 계약보다 좁다. `post_v10.py:713`의 표 제목은 v8로 남아 있어 새 판에서 고쳐야 한다. 기존 post가 새 1043 결과를 받아들이도록 실험 ID 검사만 풀어서는 안 된다.

보고 문구는 스키마와 생성 코드에서 다음처럼 강제한다: `학습 seed 1043 한 쌍의 등록한 평가 결과`, `기존 1042와는 학습 seed별로 따로 표시`, `등록한 평지 목표 세 칸`, `99칸 퇴행 범위 중 완료한 칸`. 두 학습 seed를 합쳐 독립 episode 1,000개의 일반 효과로 쓰거나, 결과를 보고 정한 지형을 대표적인 일반화 시험이라고 쓰는 제목·자동 문장은 거절한다. 지형 후보의 1042 결과를 보고 고른 경위도 명시한다.

## 설계 두 길과 검증

| 길 | 예상 수정량과 작업 시간 | 위험 · 필요한 시험 |
|---|---|---|
| 가. v37의 새 판 `cmdr_eval_driver_s1043.py`와 post 새 판. 동일 manifest를 읽고 v37의 검증·짝·재시도 로직을 이식한다. **권고** | 드라이버 약 220~350줄 변경, post 약 80~150줄 변경, manifest 검증·시험 약 250~400줄 신규. 작성 4~7시간 추정. | 새 파일 이름의 참가자 판정, 출력 경로 전체, 옛 결과 재사용, 승인 묶음, post 인증이 주요 위험. 정상 fixture와 1042 태그·옛 승인·경로 바꿔치기·입력 변경·결측·짝 불일치·GPU UUID 불일치의 반례, 관문을 끈 변이, 원본 q의 알려진 답 대조가 필요하다. 변경 줄 수는 설계 추정이며 실제 diff 미작성. |
| 나. 새 소형 orchestrator가 q 평가만 호출하고 post v10을 새 입력으로 재사용 | 호출기 약 150~250줄과 post 약 100~180줄, 별도 인증·재시도·시험 약 350~550줄. 작성 6~10시간 추정. | v37의 v3.7까지 쌓인 stamp·pair·USD·재시도·종료 의미를 다시 구현해야 한다. post는 모델·로그·실험·hold·목적지가 고정되어 그대로 재사용 불가. 최소 변경처럼 보여도 검증 범위가 더 넓다. 동일 반례 외에 v37과 동등한 end-to-end CPU fixture 대조가 필요하다. |

사전 시험은 합성 정상 대조군이 등록된 1043 부모·off·on을 받아 새 경로에만 쓰는지 확인한다. 반례는 (1) 1042 모델/로그/승인 주입, (2) on 결과만 완료, (3) 부모 해시·번들·stamp 변경, (4) 출력 루트가 `out/`로 되돌아감, (5) GPU index는 0인데 UUID가 1, (6) v2 registry 또는 별도 lock, (7) slot 이후 입력 변경, (8) 누락·중복 seed/episode와 짝 지문 불일치다. 정상 대조군이 통과하고 반례가 자식 0회 또는 `미확인`으로 닫히는지 CLI 끝까지 시험한다. 각 검사를 끈 변이에서 시험이 실패하는지도 본다. fixture의 모든 쓰기 경로는 작업 폴더 아래임을 호출 전 단언한다. 이 시험들은 **아직 작성·실행하지 않았다**.

## 평가 시간 견적과 순서

읽기 허용된 `_eval/out/cmdr_eval_driver.json`은 2026-10-13 14:06:18~16:33:40, 2시간 27분 22초다. 그러나 555 run 중 **445개 재사용, 새 실행 110개**였고 새 실행의 guard try 합계는 8,283초, 평균 75.3초, 중앙값 80초였다. 따라서 2시간 27분을 1043 전체 시간으로 쓰면 과소추정이다. 같은 속도를 단순 외삽하면 목표 전용 45 run은 평가 자식 시간 약 56분, full base 555 run은 약 11시간 36분이다. 시작 시험, 전처리·후처리, slot·다른 실행 대기, 재시도와 재측정이 추가된다. 이는 **GPU 1에서 관측한 110회의 조건부 환산**이며 GPU 0의 실제 속도와 메모리 여유, 총 마감 시간은 미측정이다. `_eval/out/cmdr_eval_driver_g0.json`은 16개 전부 재사용된 remeasure 기록이라 GPU 0 처리량 근거로 쓸 수 없다. full 뒤 선별된 칸마다 8 run 추가가 가능하고 최대 96칸이면 768 run이 추가되므로 마감 전 범위를 확정해야 한다.

준비 시간 추정: 새 판 작성 4~7시간, 합성·알려진 답 CPU 시험 2~3시간, 변이 시험 1~2시간, ASTRA 독립 검토와 지적분 재확인 1~3시간, 기동 전 입력·장치·상대 로그 확인 및 기록 0.5~1시간. 합계 **8.5~16시간 추정**이며 코드 작성 전의 계획 수치다. 실제 GPU 평가는 이 뒤 별도이며 위의 환산에 재시도 여유가 없다. deadline은 팀장이 허용한 자원 창에 맞춰 결과를 보기 전에 등록한다.

## 지형 재현과 결정 경계

`VERIFY-astra-17p.md` §5의 floating_ring fwd05, rails fwd03, gap fwd03은 1042 결과를 보고 고른 **기술통계 재현 후보**다. 이 평지 CMD-R 드라이버는 학습 family를 평가한다. 후보 세 개는 별도의 **v6 UNCR 계열 드라이버**에서 1043 부모/off/on 체크포인트와 등록 번들·설정·태그·출력·승인을 새로 받아야 한다. 부모도 같은 조건으로 새로 수집하고 `surv`, `cross`, `alive_cross`, n, 짝, 출처, 누락을 나란히 낸다. `cross`를 안전 통과로 바꾸지 않는다. 결과를 보기 전에 후보를 동결하고, 1042에서 선택했다는 사실을 기록한다. 이 후보를 평지 세 목표의 대체물이나 전체 미경험 지형의 대표 표본으로 쓰지 않는다. 지형의 합격/퇴행 경계는 아직 없으므로 여기서 90%·95%·+10 %p를 이식하지 않는다. 이 쪽 코드는 이번 단계에서 쓰지 않았다.

lead가 팀장에게 확인할 것: `CMD-R 규약 교정`의 정확한 의미와 reset 계약, 1043 결과 채택/부모 승격 여부, 목표·퇴행 평가 범위와 위험 허용선, GPU 0 배정과 마감, 지형 재현을 기술통계에서 판정으로 올릴지 여부다. 승인 없이 먼저 준비할 수 있는 것은 manifest 초안, 현재 입력 해시, 출력 namespace, CPU fixture와 실패 반례, 작업량 계산 및 ASTRA 검토 의뢰서다. 어느 결정도 이 메모가 대신하지 않는다.

## 읽은 파일과 SHA256

`ARCH`는 `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20261012-arch-discussion/`, `EVAL`은 `C:/isaac/ext/go2_rl_robotlab/_eval/`이다. 아래 해시는 이 메모 작성 중 직접 읽은 바이트다.

| 경로 | SHA256 |
|---|---|
| `ARCH/TASK-codex-worker-1043-eval-design.md` | `89fa21c794aefc37ea72fdc9fef93fe2ed3b82914554b9a7a325107c30e46cee` |
| `ARCH/VERIFY-astra-17p.md` | `3500f4bd277f681268756b76ef34e301bd438f878aab264a9c4f564c9786e40c` |
| `ARCH/VERIFY-astra-17.md` | `c6654c598eb8c74ca47be1964881d53333edbc14581f9cb168d52b961fb032a3` |
| `ARCH/NIGHT-PLAN-20261014.md` | `03ef2d9d56077a5fcfbaf00b4c8ac6518a5ead32487d3de817ef6ea7865943af` |
| `EVAL/cmdr_eval_driver_v37.py` | `c351fde3e038ff27f37a4bb47e2e20492274abf79b5c2547f12f488564f2212a` |
| `EVAL/cmdr_post_v10.py` | `dea9ca7bfe01b92b634aa85048ff0cb4128b4eaa3b7943030a9a9b5660332dc2` |
| `EVAL/q_eval_cmdr.py` | `24aeaf6358ef79096911e3dcb220212ac715775012da96bf14e438c331dba4bc` |
| `EVAL/q_eval.py` | `0dc6a37605d57ca63788aff9b2cbbd4131536a2ff0312fe315d0fce2714c5fcb` |
| `EVAL/q_metrics.py` | `c9930f8d327efd04df51440da519fefab2585490ae45b4a6ffbd39466138a794` |
| `EVAL/q_post.py` | `f90aaa97a50c5347111298b913d7bb948e58f0d1ce3af09808739cfcae1e26dd` |
| `EVAL/paired_ci.py` | `3056f6b364d8f4499a52d23839a901931d9ef0496dbdbb9e49e13da5665cdc2d` |
| `EVAL/gpu_guard.py` | `7fabec30704830a410878e4244190a4e62c60f3828ad5908fbf9ee264c30cbd4` |
| `EVAL/isaac_slot.py` | `90ae613b0e7e791fa24bf82866eb0a0285eafe5cd10f0e201ba2f5af9fa19c47` |
| `EVAL/isaac_slot_v3.py` | `974919b0717b684fb9f0a57a0282aeb5a0b321f4bc7d4131aedcc461e2d3945a` |
| `EVAL/usd_isolate_run_v3.py` | `30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb` |
| `EVAL/cmdr_bundle_compare.py` | `bb827f3c77a239e6eaeb9fa613c49b1a740dcac367cd50cdde84d75e786e470d` |

입력 자료는 위 표의 부모 및 1043 두 군의 `out_branch/cmdr_s1043_{off,on}_u4000/` 안 `result.json`, `bundle.json`, `bundle.npz`, `validate_stamp.json`, 22,000/24,000 checkpoint를 읽었다. 평가 시간에 한해 `EVAL/out/cmdr_eval_driver.json`과 `cmdr_eval_driver_g0.json`만 읽었다. 실제 GPU 실행, 새 판의 동작, GPU 0 속도, 후처리 표와 전체 시간은 **미확인**이다.

이번 단계에서 내가 `_eval` 안에 만든 파일: **0개**. 기존 파일 수정·삭제: **0개**. 작업 폴더 안 작성 대상은 이 `MEMO.md`뿐이다.

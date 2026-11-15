고쳐서 기동: CE12 실행기의 v2 공용 registry 쓰기를 먼저 분리하면 GPU 1의 CTS 짧은 진단 기록은 시작할 수 있으나, 현재 사본 그대로의 기동과 아래 결함을 남긴 APPROVED 채택은 승인하지 않는다.

> 분류: A/평가 · 실행 관문 · 같은 시험지 · S2 입력 검증
> 작성: ASTRA · 2026-10-14 00:17 KST
> 근거: TASK-astra-17f-v3-ce12-s2.md · 지정 사본 26개와 실행본 해시 · 임시 사본 CPU 재시험 · 아래 추가 반례
> 요지: v3의 기존 반례 수정은 확인했지만 CE12 호출 설정에 혼합 운용 대책이 빠졌고, 자료 승인에는 모델 식별·실행 출처·검사 범위 결함이 남았다.
> 상태: 검증 완료 · 제한된 진단 기동 조건부 · GPU/Isaac 실제 기록은 미확인

S2 판정: 판 2의 입력 의미 수정은 CPU 검증 범위에서 통과하며, 실제 센서·rollout 저장소·학습기 연결과 사전 실험 등록 전까지 학습 기동은 보류한다.

# ASTRA 17f · v3 관문 · CE12 · S2 재검

## 1. 직접 확인한 범위와 시험 결과

**확인됨:** `night-tools-20261013/slot_v3/`, `ce12/`, `s2/`의 SHA256SUMS에 실린 26개 파일 모두 사본 해시가 맞았고, 대응하는 `C:/isaac/ext/go2_rl_robotlab/_eval/` 실행본과도 같았다. 시험 후 재대조에서도 변경이 없었다. 이후 바뀐 파일은 이 판정의 대상이 아니다.

핵심 식별값:

| 파일 | SHA256 |
|---|---|
| `slot_v3/isaac_slot_v3.py` | `974919b0717b684fb9f0a57a0282aeb5a0b321f4bc7d4131aedcc461e2d3945a` |
| `slot_v3/usd_isolate_run_v3.py` | `30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb` |
| `ce12/run_dump.py` | `2feaa6fbcfa12d1a84577ecb41791e4de06d3584d3a420afc0f32097a2a94f54` |
| `ce12/validate_dump.py` | `ce6587de584b2e264bcd3102628d1547eefb1161645898e2b875eacc5d43f9f9` |

야간 시험이 읽는 `branch/night_20261013_cmdr1043_v3.sh`는 별도로 임시 복사했다. 해시는 `c53dd90cfb1eaa7102168d6424a2e4364bedad5ff95a89b311877433bd57df9e`다.

CPU 시험은 `isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`로 실행했다. 시험별 TEMP/TMP도 이번 검증의 임시 폴더 아래로 지정했다. 실제 체크포인트는 CPU 읽기만 했다. 표는 lead의 보고를 옮긴 것이 아니라 이번 재실행 결과다.

| 시험 | 직접 확인한 결과 | 입증 범위 |
|---|---|---|
| `test_isaac_slot_v3.py` | 43/43, rc 0 | 가짜 CPU 자식으로 잠금·경로·로그·registry·예상 변환 수 경로 |
| `test_usd_isolate_v3.py` | 27/27, rc 0 | 가짜 변환기로 cfg 보존·난수 순서·loader·쓰기 전 거절 |
| `test_night_1043_v3b.py` | Git Bash 환경을 명시한 뒤 10/10, rc 0 | mv 실패 주입 표식과 실패 시 후속 실행 차단. 실제 학습 아님 |
| `ce12/test_run_dump.py` | 117/117, rc 0 | 실행기는 실제 v3 사본, guard·native 기록기는 가짜. 수집·승인 합성 자료 시험 |
| `ce12/test_adapters.py` | 22/22, rc 0 | 관측·관절 대응·실제 체크포인트 CPU 재계산 |
| `s2/test_s2.py` | 10/10, 187칸, rc 0 | 입력 의미·초기 동치·gradient·encoder 고정·critic 진단 |

**확인됨:** 야간 시험을 기본 PATH에서 그대로 실행한 첫 회는 실패했다. `shutil.which("bash")`가 `C:/WINDOWS/system32/bash.EXE`를 골라 Windows 경로를 찾지 못해 rc 127이 났다. Git `usr/bin/bash.exe` 직접 호출에는 `dirname`·`mkdir`를 찾지 못해 rc 3도 났다. 같은 임시 사본에서 PATH 앞에 `C:/Program Files/Git/bin`, `C:/Program Files/Git/usr/bin`을 넣자 10/10 통과했다. 반례가 없어졌다고 첫 실패를 숨기지 않는다. 야간 호출기는 Git Bash의 실제 경로와 PATH를 고정해야 한다. CE12의 Python 호출을 막는 결함과는 구분한다.

**미확인:** 실제 Isaac loader, GPU native 관측, runtime reset, CPU/GPU action 차이는 이번에 실행하지 않았다. 합성 기록 통과를 native 기록 성공이라고 부를 수 없다.

## 2. 물음 1 · v3는 이전 반례를 막는가

**확인됨:** 지정 반례에 대해서는 막는다.

| 이전 반례 | 이번 확인 |
|---|---|
| 루트 안/밖 같은 basename 혼합 | 절대 경로 둘로 구분하고 밖의 경로를 94로 거절. 장면 생성 시점에 자식을 끝냄 |
| 긴 실행이 끝나야 나던 94 | 장면 생성 시점 검사와 잠금 해제 후 감시에서 발견. 해제 뒤 외부 경로도 실행 종료까지 기다리지 않음 |
| v3 registry read/merge/write 경합 | registry 전용 OS 잠금 안에서 갱신. 절대 경로 키·고유 임시 파일로 두 기록 보존 |
| 같은 cfg를 두 번 사용 | `cfg.usd_dir`를 영구 변경하지 않음. `any`에서 원래 난수 소비 순서 유지, 예상 1에서는 두 번째 변환을 입구에서 거절 |
| 명시적 외부 `usd_dir` | 예외와 거절 기록을 남기고 외부 폴더 생성 전에 차단 |
| 비표준 loader의 첫 변환 | wrapping이 늦어도 기반 클래스의 `mkdir`를 감사 hook에서 차단. 정상 변환으로 수용하는 것이 아니라 안전하게 실패함 |
| 예상 0인데 변환 발생 | 첫 변환의 random·USD 폴더 생성 전에 거절, slot rc 89. 변환 없는 예상 0은 정상 통과 |

근거: `isaac_slot_v3.py:80,198,250,309,353,477`, `usd_isolate_run_v3.py`의 `_set_usd_dir`, `patch`, `_check_mkdir`와 위 시험의 A1~A8, R1~R5, E1~E6, U 계열.

**추정:** README의 한계 때문에 이 도구를 임의의 Isaac 프로그램에 대한 완전한 파일 격리라고 부르면 틀리다. C++ 직접 쓰기, 기반 클래스를 거치지 않는 변환, 이미 존재하는 공용 폴더에 파일만 쓰는 경로를 전부 선제 차단하지 않는다. 로그 감시는 2초 주기의 사후 검사이고 오염을 되돌리지 않는다. 하지만 오늘의 제한된 CTS 기록은 검토한 표준 Go2 변환 경로를 쓰고, `dump_native_cts.py:260`에서 지형 cache를 끈다. 다른 변환기를 추가하지 않고 실행 파일을 고정한다면 이 한계만으로 첫 짧은 진단까지 무기한 막을 이유는 없다. 첫 실제 실행에서 격리·변환 수가 틀리면 그 시도는 실패이며 자동 재시도·다음 모델 진행으로 덮지 않는다.

**주의:** v3끼리 registry 시험을 통과했다는 사실은 v2와 같은 registry를 동시에 갱신해도 된다는 근거가 아니다. v2는 새 registry 전용 잠금을 따르지 않는다.

## 3. 물음 2 · 혼합 운용은 아직 호출기에 반영되지 않았다

### 기동 전 수정 사항

**확인됨:** `ce12/run_dump.py:63`은 여전히 `slot/isaac_usd_registry.json`을 쓰고, `:203~204`에서 그것을 slot v3에 넘긴다. `test_run_dump.py:362,467`도 바로 그 공용 파일을 기대값으로 고정해 놓았다. 117/117은 분리 운용의 증거가 아니라 현재 공용 설정을 포함한 시험의 통과다.

**판단:** 의뢰문의 분리안은 방향이 맞다. CE12 호출기에서도 v3 쓰기 대상을 `isaac_usd_registry_v3.json`으로 바꿔야 한다. 기존 v2 파일을 v3가 갱신하게 두면 안 된다. 반면 변환 직렬화용 `isaac_convert.lock`은 v2와 v3가 같은 실제 파일을 사용해야 한다. registry를 나누면서 변환 잠금까지 각자 나누면 보호를 잃는다.

**확인됨:** `--scan_dirs`에는 이미 `out_branch`가 들어 있다. 그러나 현재 v3에 별도의 v2 registry를 읽는 입력은 없다. `registry_update()`의 legacy 처리와 `scan_logs()`는 자신이 갱신하는 registry에서 얻은 legacy 항목만 읽는다 (`isaac_slot_v3.py:250~305`). 파일명만 분리했다고 ‘v2 registry 읽기 전용 대조까지 구현했다’고 하면 틀리다.

짧은 기록에 필요한 혼합 운용 조건은 다음과 같다.

- v3 전용 registry 쓰기, 기존 v2 registry 무수정, 같은 변환 잠금, 새 attempt마다 고유 USD 루트를 함께 적용한다.
- GPU 0의 실제 현재 로그와 attempt 하위 로그가 `out_branch` 스캔 범위에 들어오는지 경로로 확인한다. 기존 registry가 가리키는 로그가 그 밖에 있다면 읽기 전용으로 대조 대상을 보충한다. 별도 reader를 추가하거나 운영 preflight로 대조할 수 있지만, 하지 않은 읽기를 했다고 기록하지 않는다.
- 해당 실행의 로그가 읽히지 않거나 경로를 풀지 못한 경우 ‘충돌 없음’으로 치지 않는다. `scan_unreadable`·`legacy_registry_missing_logs`는 현재 자동 실패 조건이 아니므로 실제 상대 실행에 해당하는 누락이 있으면 시작을 보류한다. 사라진 과거 로그 전체를 무조건 복원하라는 요구는 아니다.
- dry-run으로 registry·lock·scan 경로를 확인하고, 임시 폴더의 별도 registry 구성 시험을 고친 기대값으로 한 번 확인한다. GPU 0을 재시작하거나 기존 registry를 다시 쓰는 방법은 필요하지 않다.

이 조건을 실제 CE12 호출에 적용하면 17e §5.4의 v2/v3 공동 쓰기 문제를 피할 수 있다. **아직 적용할 계획이라는 문장만으로는 충족되지 않는다.** 이번 검증에서는 운영 중 registry·잠금·학습을 변경하지 않았다.

## 4. 물음 3 · CE12 수집 수정과 승인 결함

### 4.1 고쳐진 것

**확인됨:** 17d §2.5의 등호형 `--outdir=...`, 축약·중복·금지 인자는 시작 전에 거절된다. 예상 경로 밖 출력이나 필수 파일 누락은 자식 rc 0이어도 실행기가 88로 거절한다. §2.6의 CTS 예상 1, v2 예상 0 모두 slot v3와 isolate v3를 거친다. 예상 0에서 뜻밖의 변환은 실제 v3 사본과 가짜 변환기를 연결한 시험에서 쓰기 전에 막혔다.

§2.7도 큰 부분은 고쳐졌다. 수집 상태와 승인 상태를 나눴고, 서명·cell/T/N·명령 시간열·금지 설정·student 경로·CPU action 재계산 보고서를 대조한다. 비교 보고서의 NPZ/meta/signature/checkpoint/config/비교 코드 해시를 확인한다. reset·명령 전환이 없는 자료는 승인을 보류한다. 다만 다음 세 결함 때문에 승인 전체를 통과라고 판정하지 않는다.

### 4.2 승인 재확인이 다른 모델·체크포인트에도 VALID를 반환한다

**확인됨 · 채택 전 수정:** `validate_dump.py:459~469`의 `--check_approval`은 attempt와 stamp에 들어 있는 파일들의 해시만 검사한다. 요청의 `which`, `checkpoint`가 승인 당시 대상과 같은지 확인하지 않는다.

임시 사본의 `test_run_dump.make_valid("v2", "base_probe", dict(REQ))`로 알려진 정상 기록을 만들고, 실제 v2 체크포인트를 CPU 재계산해 APPROVED를 받은 뒤 자료와 stamp는 그대로 두었다. 같은 tag·attempt에 **`--which cts --checkpoint <E1/model_20000.pt> --check_approval`**을 요청했다. 결과는 rc 0, `APPROVAL STILL VALID base_probe`였다.

이것은 해시 충돌이 아니다. 이미 승인된 v2 묶음을 확인하면서 호출자는 CTS를 확인했다고 오인할 수 있는 대상 식별 결함이다. `kind`, `which`, `tag`, `attempt`, 정규화한 checkpoint 경로와 해시를 요청 및 해당 기록에 연결해야 한다. 다른 모델·체크포인트 재확인은 실패해야 한다. 이 수정 없이 이 명령 하나를 자동 인계 관문으로 쓰면 안 된다.

### 4.3 실행 당시 코드 해시가 승인 코드와 연결되지 않는다

**확인됨 · 채택 전 수정:** `run_dump.py:285`는 실행기·cells 해시, capabilities는 slot/isolate 해시를 남긴다. native meta도 `script_sha256`, `adapters_sha256`를 남긴다. 하지만 수집/승인은 이 실행 당시 해시들을 승인 대상 코드와 연결하지 않는다. `validate_dump.py:413~442`가 검사하고 stamp에 묶는 것은 주로 **비교·승인 시점의 파일**이다. slot/isolate는 approval stamp 파일 목록에도 없다.

임시 정상 CTS fixture의 `run.json`에 있는 `run_dump_sha256`, `cells_sha256`, capabilities의 `slot_sha256`, `isolate_sha256`를 각각 `000…000`으로 바꾸고, 정상 NPZ를 CPU 재계산했다. 승인 결과는 rc 0, `APPROVED hash_probe`였다. 이 시험은 실제 실행 파일을 바꾼 시험이 아니라 **기록된 출처의 명백한 불일치가 검사되지 않음**을 입증한다.

운영 중 코드를 고친 뒤 현재 파일을 stamp에 넣으면 과거 실행까지 그 코드로 이루어진 것처럼 보일 수 있다. 이번 짧은 진단에서는 검토한 실행 사본을 고정하고 시작 전·종료 후 해시를 대조해야 한다. 정식 승인에서는 실행 당시 기록기·adapter·cells·slot·isolate·guard 및 선택한 설정/정책 구현의 출처를 고정 묶음과 잇고, 비교 단계의 출처는 별도로 남긴다. 단순히 승인 시점의 파일을 더 많이 해시하는 것만으로 과거 실행 출처가 입증되지는 않는다.

### 4.4 마지막 관측의 명령 전환도 전체 경로 승인으로 센다

**확인됨 · 채택 전 수정:** `cells.py:fixture_problem()`은 `switch_step == T`를 허용한다. 명령은 관측 0~T에 있지만 action은 0~T-1만 있다. `compare_native.py:288~293`도 action 재계산은 그 범위만 한다. 그런데 `coverage_of():63~71`과 `validate_dump.py:425~426`은 마지막 관측의 전환까지 양수로 센다.

임시 CTS fixture에 `T=6`, 일부 reset=3, switch=6을 주었다. 비교는 `pass`, reset 1회·명령 전환 1회, 승인 rc 0과 `APPROVED terminal_switch`가 나왔다. **바뀐 명령으로 계산한 action은 기록에 0개다.** 마지막 관측의 입력 슬롯이 맞는 것은 확인하지만 전환 후 행동 경로까지 확인했다고 할 수 없다.

최소한 `switch_step <= T-1`로 제한하고, 전환 뒤 관측뿐 아니라 action·target·다음 상태가 비교된 횟수를 남긴다. 이번 60-step 진단의 switch=40에는 이 경계 문제가 없다. 이를 이유로 안전한 진단 기록까지 막을 필요는 없지만, 현재의 포괄적인 승인 의미는 바로잡아야 한다.

추가로 CTS처럼 ray 원자료가 없으면 `ray_miss_count=None`인데 `unverified_paths`는 `v == 0`만 보므로 높이 miss 미측정이 목록에서 빠진다. 내 반례에서도 그 목록은 빈 배열이었다. ‘해당 검사 없음/미측정’과 ‘측정했는데 0회’를 구분해 표시한다. 현재 CTS actor의 이식 진단 통과가 지형 miss 경로까지 검증했다는 뜻은 아니다.

### 4.5 실제 진행 순서

**판단:** §3의 혼합 운용 설정을 고친 뒤에는, 아직 측정하지 않은 native 차이를 찾기 위해 GPU 1에서 **CTS E1 20000 한 번의 짧은 진단 기록**을 진행해도 된다. 이것은 full 평가나 성능 승인과 다르다. §4.2~4.4의 수정은 기록 결과를 APPROVED로 채택하고 다음 단계의 근거로 쓰기 전에 필요하다.

1. 검토한 코드·설정·checkpoint와 실제 실행 명령을 고정한다. 시험용 `CE12_*` override가 남아 있지 않은지 확인한다. 새 tag·attempt, GPU 1, expect=1, 새 USD 루트, v3 registry, 공통 변환 잠금과 상대 로그 경로를 dry-run에서 확인한다.
2. `stand,fwd03,yawL05`, 칸당 4환경, 60 step, 일부 환경 `1,6`을 관측 30 직전에 reset, 환경 0을 관측 40부터 `fwd03`으로 전환하는 정도의 기록 한 개로 제한한다. 실제 소요 시간·VRAM과 성공 여부는 미확인이다. guard가 진입 여유를 확인하게 둔다.
3. slot/guard 종료와 `COLLECTED`를 먼저 확인한다. 예상 변환 1개, 할당/로그 경로 대응, 외부 쓰기·거절·충돌 없음, runtime reset/명령 일정, 코드 해시를 직접 확인한다. 오류가 나면 같은 실패를 반복하거나 v2로 자동 진행하지 않는다.
4. `compare_native --recompute_action`으로 native 관측과 adapter 관측, raw action, offset을 반영한 joint target, 일부 reset 뒤 이력/last action, 전환 뒤 action을 대조한다. 기준 `1e-6`·`1e-4`를 통과시키려고 사후 완화하지 않는다. CPU/GPU 연산 차이와 adapter 의미 차이를 분리한다.
5. 위 승인 결함을 고친 관문으로 CTS 묶음이 승인된 뒤, v2도 같은 기록 규격으로 expect=0을 걸어 진행한다. 양쪽 native 정합성 통과 이후에야 공통 세계/조건에서 비교하는 다음 단계로 간다. native 두 실행의 수집만으로 ‘같은 시험지 성능 비교 완료’가 되지는 않는다.

## 5. 물음 4 · S2 입력 의미와 남은 관문

### 수정 수용

**확인됨:** 판 2는 17d의 입력 의미 지적을 고쳤다. 유한 hit는 깊어도 mask 1, 정상 miss인 xyz 모두 +inf만 height 1·mask 0이다. 센서 비유한, NaN, -inf, 일부 성분만 inf인 packet은 고장으로 따로 세며 A/B에 같은 판정을 적용한다. 센서 높이에 20 m 시작 offset을 다시 더하지 않는다. 좌표 순서·평행 이동·yaw 90도 CPU 시험도 통과했다. 실제 collision mesh와의 교차는 아직 아니다.

**확인됨:** A의 actor 지도 입력은 상수이며 지형에 따른 mask도 주지 않는다. 부모 대비 초기 action/value CPU 동치, 부모 비공유, 초기 map 경로 gradient, W 동안 student encoder 고정과 이후 r배 학습률을 확인했다. 부모 checkpoint 해시는 전후 모두 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`였다.

critic은 부모 방식대로 정상 miss를 -2.5로 읽고 새 actor 지도는 height +1·mask 0으로 읽는다. 이 차이를 진단하고 입력/value를 바꾸지 않는 것은 명시한 설계와 맞다. 그러나 **유한한 value라는 사실이 올바른 value라는 뜻은 아니다.** gap에서 실제 return과 value의 편향, advantage 분포를 별도로 봐야 한다. A도 privileged critic의 학습 신호를 받으므로 ‘A는 어떠한 지도 정보도 사용하지 않는다’는 주장은 여전히 틀리다.

### W·r 외에 필요한 것

**판단:** 다음은 새로운 장기 개발 요구가 아니라 설계 6절이 이미 약속한 학습 전 연결 확인이다.

- **W 단위와 재개 상태:** W는 PPO iteration인지 optimizer minibatch step인지 등록한다. 해석이 쉬운 것은 한 rollout의 `alg.update()`를 단위로 삼는 방식이다. W=50, r=0.1의 효과 근거는 없으며 이번 T9의 W=3, r=0.25는 시험값이다. 종료·재개 때 update 번호와 schedule/optimizer 상태를 저장해야 한다. 새 Adam은 A/B의 실험 선택이며 부모 학습 그대로의 resume가 아니다.
- **실제 광선의 뜻:** 실제 mesh 평지·단차·빈 공간에서 hit, 광선 순서, 갱신 시각, reset 직후 값을 확인한다. 정상 miss는 ‘그 ray가 등록한 충돌 표면을 못 찾았다’이지 반드시 물리적 구멍이라는 뜻은 아니다. mesh 누락·범위 밖·센서 지연도 구분해야 한다. 유한한 두 깊은 바닥은 clip 때문에 같아질 수 있으며 mask가 깊이를 복원해 주지는 않는다.
- **학습 연결:** 지도는 해당 관측 시점과 함께 rollout 저장소·모든 minibatch·bootstrap에 보존해야 한다. reset 뒤 이전 episode 지도가 섞이면 안 된다. teacher/reconstruction 경로 제거, optimizer 중복·누락, frozen encoder의 grad/state, adaptive LR 변경 시 r 유지, 저장·복원 후 같은 출력을 확인한다.
- **고장 관문 호출:** `height_and_mask()`/`map_obs()` 기본값은 `strict=False`다. faults를 돌려주는 것과 실제 학습이 거절하는 것은 다르다. `RunValidityGate`에 지도·critic·value·return·advantage를 실제로 넣고 update 전에 검사하는 연결은 아직 미확인이다. 고장 후 조용히 rollout을 버리고 나머지 성적만 내면 선택 편향이 생긴다. 고장 횟수와 폐기량·중단 원인을 두 군 모두 기록한다.
- **공정성·퇴행 기준:** 초기 GPU 동치, 같은 부모와 초기값·예산·분포·명령 규약, 고정 관측 묶음의 action/KL/latent/expert 비율, value 오차, 평지 명령 성능과 희소 지형 조우 횟수를 결과 전에 등록한다. W·r을 A/B 성적을 본 뒤 유리하게 고르는 절차는 허용하지 않는다.

S2는 현재 ‘입력 의미와 CPU 함수가 맞는 단계’다. 센서 데이터가 정책에 정확한 시점으로 들어가고 PPO 갱신까지 보존되는 학습 실험으로 완성됐다고 판정하지 않는다.

## 6. 물음 5 · 이번 판단의 경계

lead가 놓친 핵심은 시험 개수보다 **시험이 고정한 기대값과 실제 승인 주장의 범위**다. 공용 registry를 정답으로 둔 시험은 혼합 운용 안전성을 확인하지 못한다. v2 approval을 CTS 요청에 재사용하는 오류, 기록 때의 코드와 승인 때의 코드가 다른 오류, 마지막 관측만 보고 전환 후 action까지 검증했다고 하는 오류도 제공된 통과 개수에 들어 있지 않았다.

그렇다고 모든 미확인을 해결할 때까지 native 진단을 금지하는 것도 비현실적이다. 기동 안전 설정은 먼저 고치고, 고정한 한 번의 짧은 기록으로 실제 호환성을 측정한다. 그 결과를 정식 근거로 채택하는 관문은 별도로 바로잡는다. GPU 0의 현재 학습 상태, 00:15 갈래 전환의 실제 수행, 아직 의뢰하지 않은 rand/unseen v5는 이번에 승인하지 않았다.

검증 동안 기존 코드·운영 out_*·STOP·잠금·registry·동결 자료는 수정하지 않았고, GPU/Isaac·학습·평가·커밋·push·운영 프로세스 종료를 실행하지 않았다. 이번 검증용 CPU 자식과 합성 파일만 임시 폴더에서 사용했다. 재현 방법과 결과는 이 파일에 남기고 임시 사본은 제거했다.

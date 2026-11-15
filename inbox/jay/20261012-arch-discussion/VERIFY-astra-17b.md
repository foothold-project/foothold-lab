고쳐서 기동: 현재 네 파일은 정상 경로의 보호를 보강했지만, 실패한 학습을 이전 기록으로 완료 처리하는 경로와 USD 보호·평가 유효성 관문의 공백이 남아 있으므로 이 판의 밤 무인 병렬 기동은 보류한다.
> 분류: A/평가 · 실행 도구 검증
> 작성: 오흥재 · 2026-10-13 18:27 (ASTRA 검증)
> 근거: TASK-astra-17b-night-tools.md · 0cbac191 사본과 실행본 · Isaac Lab 로컬 소스 · 임시 폴더 CPU 시험
> 요지: 정상 시험 21개는 통과했으나 추가 반례에서 거짓 완료와 검증 누락을 재현했다. 수정된 점과 기동 전 필요한 점을 구분한다.
> 상태: 검토 완료 · 현 판 기동 보류 · GPU·Isaac 미실행

# ASTRA 17b · 밤 실행 도구 확인 검증

## 1. 범위와 증거 수준

**확인됨:** 검토 시작 시 `feature/verify-v2-mvp-jay`의 HEAD와 원격 브랜치가 `0cbac191b5d23828863cc2c6cf00bcbb25483f81`이었다. 이미 요청 커밋이 있어 pull·merge를 하지 않았다. 검토 중 다른 세션이 HEAD를 `b7f399ad`로 전진시켰다. 아래 사본 8개와 실행본은 재대조에서도 `SHA256SUMS.txt`와 모두 같았다. 이 보고서는 그 바이트를 대상으로 한다.

사본 루트: `inbox/jay/20261012-arch-discussion/night-tools-20261013/`.
실행 루트: `C:/isaac/ext/go2_rl_robotlab/_eval/`. 실행본 중 validator·해당 시험·밤 shell은 `branch/` 아래다. 사본은 모두 같은 폴더에 있다.

| 대상 | SHA256 |
|---|---|
| isaac_slot.py | `37f216f46f9f07df22292d2399b46c3f1b00d5967cf57ca834ee432260a5e3a5` |
| validate_branch.py | `054c727c643b66733783ede247a69e4f4ef9e00dddeb7376bfd7570e0ef8659d` |
| night_20261013_cmdr1043_v2.sh | `feb2a67c77dee524ceb207d4e9730bcb6645fa6201eeac87bc8da6aa39f674e0` |
| unseen_driver_cmdr.py | `8a25b5f92b1bf04b5af7ca8890f551b82671a676a879b23ff39cb6eb49d0fec7` |

**확인됨:** 관련 실행 의존 파일도 읽었다.

| 실행 의존 파일 | SHA256 |
|---|---|
| branch/branch_run.py | `086b9cc6e2f7b275497c969798ffdd5f8ddc914ca61d8212a4b564d60e4b3b29` |
| q_eval_cmdr.py | `24aeaf6358ef79096911e3dcb220212ac715775012da96bf14e438c331dba4bc` |
| gpu_guard.py | `7fabec30704830a410878e4244190a4e62c60f3828ad5908fbf9ee264c30cbd4` |

시험은 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`와 Git Bash를 썼다. `C:/Users/AI-WS01/AppData/Local/Temp/astra17b_sfam3ikf/`에 사본·가짜 입력을 만들었다. 실제 학습·평가 프로세스를 띄우거나 종료하지 않았다. 기존 1042의 JSON·로그와 부모 체크포인트는 읽기만 했다. 시험 폴더는 삭제하고 부재를 확인했다. 코드·원자료·동결 폴더·기존 보고서는 수정하지 않았다.

**확인됨:** 제공된 `test_isaac_slot.py`의 10개 검사와 `test_validate_branch.py`의 11개 검사를 임시 사본에서 직접 실행해 모두 통과했다. 밤 shell의 `bash -n`도 통과했다. **미확인:** lead가 보고한 변이 시험 6개·9개는 소스를 읽었지만 이번에 다시 실행하지 않았다. 위 CPU 시험은 실제 USD·물리·GPU 병행의 성공 증거가 아니다.

## 2. 먼저 막아야 할 결함

### 2.1 P1 · 실패한 새 학습을 이전 결과로 완료 처리할 수 있다

**확인됨:** `night_20261013_cmdr1043_v2.sh:11,25~37`은 `set -u`만 쓰고 `mv` 실패를 검사하지 않는다. 이동이 실패해도 `moved aside`를 출력한다. 새 실행의 `rc`는 출력에만 쓰고, 0인지 확인하지 않은 채 validator를 호출한다. `validate_branch.py:93~94`의 attempt는 검증하는 실행 식별자가 아니라 성공 판정 후 stamp에 붙이는 문자열이다.

다음 CPU 반례를 재현했다. shell의 제어 흐름은 그대로 두고 임시 폴더용 `PY`·`E1`만 바꿨다. Python 대역은 실제 validator 호출만 허용하고 Isaac slot 호출은 아무 작업 없이 7로 종료한다. 운영 명령으로 빠지는 경로는 차단했다.

1. 두 군에 계약 필드가 맞는 이전 결과·로그·guard·slot을 두되 validate stamp는 두지 않았다.
2. 임시 PATH의 `mv` 대역이 모든 이동을 종료 코드 1로 거부하게 했다.
3. 재사용 검사는 stamp 없음으로 실패했다. 이후 이동도 실패했고 새 slot도 7로 종료했다.
4. 그런데 남아 있던 이전 자료를 validator가 승인하고 현재 attempt stamp를 만들었다. 두 군 모두 `VALID`, 마지막은 **`PAIR 1043 DONE`, shell exit 0**이었다.

비교 대조로 같은 대역에서 `mv`를 정상 수행하면 이전 자료가 치워지므로 validator가 실패하고 shell exit 1로 멈췄다. 즉 실패 조합을 잘못 처리하는 경로를 재현한 것이지 실제 1043 실행이 실패했다는 주장이 아니다. Windows의 파일 점유·권한·이동 실패를 성공으로 가정하면 안 된다.

**수정 조건:** `cd`·디렉터리 생성·이전 시도 보존·자식 `rc`를 각각 검사하고 실패 즉시 다음 군을 막는다. `set -e`만 추가하고 끝내지 않는다. 실제 이번 attempt 식별자와 입력·코드 manifest를 slot·guard·로그·result에 연결해 검증한다. 기존 시도의 재사용은 그 시도 출처를 유지해야 하며, 새 실행의 성공으로 재표기해서는 안 된다.

### 2.2 P1 · 장면 생성 줄 뒤에 처음 나타난 충돌 USD를 승인한다

**확인됨:** `isaac_slot.py:105~135`는 장면 줄을 보면 그 순간의 경로 목록으로만 충돌 검사를 한다. `139~146`의 최종 검사는 경로 개수만 세며 최종 목록을 registry와 다시 대조하지 않는다. 잠금 해제 시 경로가 0개여도 해제한다.

CPU 반례: registry에 다른 실행이 쓰던 `20261013_190000_1234`를 넣었다. 가짜 자식이 장면 생성 줄을 먼저 쓰고 1.2초 뒤 그 USD 경로를 쓰게 했다. 실제 slot 결과는 다음과 같았다.

```text
state_at_release = scene_built
usd_at_release = []
conflicts = {}
usd_final = [20261013_190000_1234]
child_rc = 0
slot_rc = 0
```

**이것은 보호 코드의 반례다. 실제 이번 Go2 변환에서 같은 지연이 발생했다는 증거는 아니다.** 그러나 ‘종료 뒤 정확히 하나’와 ‘그 하나를 안전하게 검사했다’는 다르다. 경로를 모르는 상태에서 잠금을 해제하고 마지막 개수만 맞으면 성공시키는 것은 의도한 계약을 충족하지 않는다.

**수정 조건:** 변환 전에 attempt별 실제 절대 USD 경로를 할당·기록하거나, 사전 검증한 불변 자산을 사용한다. 실제 경로·완료·참조 검증이 끝나기 전에는 잠금을 해제하지 않는다. 해제 때와 종료 때 경로가 달라지면 보류하고, 최종 registry 대조도 수행한다. 단, 마지막 대조를 추가하는 것만으로 이미 발생한 공유 파일 덮어쓰기를 예방할 수는 없다.

### 2.3 P1 · 체크포인트 완전성을 해시 계산으로 대신한다

**확인됨:** `validate_branch.py:58~65`는 마지막 save의 `where` 문자열, 두 파일의 존재·양의 크기, 현재 바이트의 SHA256만 확인한다. 체크포인트를 열어 저장 iter·tensor·상태를 확인하지 않는다. `saves[-1].file`도 검사하지 않는다.

별도 CPU 시험에서 다음 입력들이 모두 통과했다.

- 두 `.pt` 파일에 체크포인트 형식이 아닌 짧은 문자열을 넣음: `check(a)`가 빈 오류 문자열을 반환.
- 마지막 `where`는 `save it=24000 last=True`로 두고 저장 파일만 `model_20000.pt`로 변경: 통과.
- slot의 `slot_rc=0`을 유지하되 `child_rc=1`, `state_at_release=exited`, `usd_at_release=[]`, 다른 `cmd`를 넣음: 통과.
- 정상 완료 줄 뒤에 루트 `go2.usd`를 열지 못했다는 오류를 추가: 통과. 금지 오류 검사는 현재 Python Traceback 문자열뿐이다.

제공 시험의 V1 자체도 실제 모델 대신 `b"weights " + filename`을 쓴다(`test_validate_branch.py:32~36`). 분기 시험용 가짜 데이터로는 쓸 수 있지만, 이를 근거로 저장 결과의 완전성을 확인했다고 말하면 틀린다. 해시는 손상된 파일에도 정상적으로 계산된다.

**수정 조건:** CPU로 알려진 자체 체크포인트를 읽어 22,000·24,000 저장 iter, 필요한 상태 키·tensor 구조·유한성, save 기록의 파일명·상태를 검증한다. `branch_run.py:215~244`가 이미 기록한 모델 tensor hash와도 같은 계산 규약으로 연결한다. 저장 후 파일 SHA는 그 검증된 내용을 재사용할 때 바뀌지 않았는지 확인하는 데 쓴다. `bundle.json`·`bundle.npz`를 포함한 후속 평가에 필요한 묶음과 code/parent 계약도 남긴다. slot·guard의 종료 코드·대상 명령·attempt가 서로 맞아야 한다.

루트·physics·collision 참조 오류와 이미 알려진 일시적 visual 경고는 구분해야 한다. 기존 1042 로그에는 `Head_upper/visuals` 등의 unresolved 경고가 많다. 모든 Warning을 일괄 실패시키는 수정은 권하지 않는다. 대신 어떤 참조가 실제 최종 장면에 유효한지 검사하고 허용한 경고만 좁게 기록한다.

### 2.4 P1 · 평가 진단의 통과가 수치·짝의 유효성을 뜻하지 않는다

**확인됨:** `unseen_driver_cmdr.py:120~167`은 종료 기록·일부 args·checkpoint hash·N·episode ID·파일 존재를 검사하지만 다음을 검사하지 않는다.

- `checks_pre`, `checks_run`의 명령 전달 오류·nonfinite 관측/행동.
- 실제 `traj.npz`·`env_origins.npy`의 로딩·shape·값과 CSV의 env 대응.
- 셋의 실제 mesh·origin·초기 pose·물성·actuator delay 등의 짝 지문 일치.
- 실행 evaluator·후처리·환경/정책 소스 hash와 승인된 설정 차이.

CPU 시험 결과:

| 한 번에 바꾼 조건 | 실제 결과 |
|---|---|
| 정상 형식의 합성 자료 3군, 동일 지문·유한값 | validator 통과, post `complete=1` |
| on의 DR 지문 `pairing_sha256_ext.com`만 다르게 | 그대로 post `complete=1` |
| 지문 복원 후 on의 nonfinite count만 10으로 변경 | 그대로 post `complete=1` |
| 별도 fixture의 npz/npy를 깨진 문자열로 변경 | validator 통과. 후처리 단계의 로딩 오류까지 늦게 감 |

따라서 `diag_bad`가 없으면 full을 실행하는 `272~280`은 **파일/실행 외형 관문**이지 물리·명령·짝·조우 진단 관문이 아니다. 실제 모델 성능이 낮다는 이유로 결과를 버리라는 뜻도 아니다. 유효하게 측정한 실패는 결과로 남기고, 잘못된 실행과 분리해야 한다.

**수정 조건:** evaluator가 이미 제공하는 지문과 `checks_*`를 사용해 유효성·짝 일치·조우 여부를 확인하고 세 결과를 별도 필드로 남긴다. 짝이 안 맞으면 유효한 개별 서술 통계까지 지울 필요는 없지만 짝 비교 승인은 주면 안 된다. code/config 불일치·nonfinite·기록 훼손은 full 확대 전에 멈춘다. diag가 무엇을 확인해야 full로 가는지 명시한다.

### 2.5 P2 · 후처리와 재시도 출처도 보완해야 한다

**확인됨:** 빈 임시 ROOT에서 실제 `main()`을 `--stages post`로 호출했더니 `POST rows 7 complete 0`, `END finished`, exit 0이었다. `stage_post:240~259`의 incomplete가 `LOG.failures`로 전달되지 않기 때문이다. 아울러 `--stages post`는 기존 full 결과 유무와 관계없이 DIAG 7행만 다시 써서, 앞서 만든 32행 집계가 축소될 수 있다(`282`).

**확인됨:** `stage_post`는 `reusable()`이 아니라 `validate_run()`만 호출하므로 driver stamp의 출력 hash 대조를 우회한다. `keep_attempt:71~78,92`는 로그·guard·slot만 옮기며 실행 결과 디렉터리는 그대로 둔다. 동일 태그 재실행 때 결과 파일과 stamp가 덮여 이전 시도의 입력·출력 결합을 보존하지 못한다. stamp도 결과 5개만 해시하며 실행 코드·로그·guard·slot의 신원을 묶지 않는다.

**수정 조건:** post 대상 목록을 고정 manifest로 지정하고 일부만 완성되면 그 사실을 반환 코드/상태에 전파한다. 새 post가 이전 전체 표를 실수로 줄이지 않게 한다. post에서도 검증된 attempt와 stamp를 재확인한다. 재시도는 결과까지 별도 attempt 위치로 보존하고 검증된 묶음 하나를 선택한다. 이 문제를 고치지 않은 상태에서는 `finished`를 완료 통보 근거로 쓰면 안 된다.

## 3. 질문 1 · 잠금과 장면 생성의 실제 의미

### 확인된 개선

**확인됨:** 두 실행기 모두 같은 `_eval/slot/isaac_convert.lock` 및 registry를 지정한다. OS 잠금은 자식 기동 전 취득한다. 정상 CPU 시험에서 두 변환 구간이 직렬화됐고, registry와 로그 대조 각각이 충돌을 검출했다. 이전 watch log 분리, 변환 상한, 최종 경로 개수 검사도 해당 시험에서 작동했다.

**확인됨:** 학습에서도 장면 줄은 나온다. 호출은 `branch_run.py:106`의 `gym.make` → `tasks/go2/__init__.py:21~22`의 Go2Env → ManagerBasedRLEnv/ManagerBasedEnv다. `manager_based_env.py:139~143`의 Timer 안에서 InteractiveScene을 만든다. 실제 기존 로그도 대조했다.

| 읽기만 한 기존 로그 | 최초~마지막 USD 경로 줄 | 장면 생성 줄 |
|---|---:|---:|
| `_eval/out/branch/cmdr_s1042_off_u4000.log` | 149~33016 | 33018 |
| `_eval/out/branch/cmdr_s1042_on_u4000.log` | 150~33017 | 33019 |

각 로그에서 regex가 찾은 폴더는 하나였다. 두 로그 모두 장면 줄 이후 USD 경로 줄은 0개였다. **이는 로그 관찰이며 파일 쓰기 추적이 아니다.** 폴더 줄 상당수는 명시적인 ‘변환 완료’ 출력이 아니라 USD 경고 속 경로다.

### ‘장면 생성 줄 = 더 이상 USD 쓰기 없음’은 증명되지 않았다

**확인됨:** `spawn_from_urdf`는 `from_files.py:118~120`에서 converter를 호출하고 그 USD를 spawn한다. `asset_converter_base.py:101~115`는 `_convert_asset` 뒤 config를 기록하며, `urdf_converter.py:87~109`는 `omni.kit.commands.execute`로 import를 호출한다. 읽은 Python 경로에서 URDF 변환을 별도 비동기 task로 넘기는 코드는 발견하지 않았다.

그러나 다음 이유로 marker 하나를 최종 자산 검증과 같다고 볼 수 없다.

- **확인됨:** `utils/timer.py:144~149`는 `__exit__`에서 예외 여부와 무관하게 시간 문구를 출력한다. 이 줄은 성공 인증이 아니다.
- **확인됨:** manager의 scene Timer 뒤에도 `prestartup` 이벤트와 `sim.reset()`이 이어진다(`manager_based_env.py:155~178`). 일반 API 계약상 scene 줄이 이후 모든 USD 활동의 종료선은 아니다. 이번 Go2 env에서 활성 prestartup 항목은 찾지 못했다.
- **미확인:** native importer·PhysX cooking의 파일 쓰기가 그 줄 이전에 모두 끝나는지는 이 검토에서 OS 파일 쓰기 추적으로 측정하지 않았다. 실제 늦은 쓰기가 있다고 단정하지 않는다.
- **확인됨:** slot은 root·하위 reference·mesh·`.asset_hash`를 열어 확인하지 않고 폴더명 regex만 본다. 서로 다른 폴더 하나씩이라는 사실은 둘 다 올바른 Go2라는 증거가 아니다.

**추정:** 현실적인 우선 해법은 매 시도 고유 경로를 실제 converter cfg에 넣어 공유 쓰기 자체를 없애거나, 검증 후 쓰지 않는 사전 변환 자산을 사용하는 것이다. 막연하게 잠금 시간을 늘리는 것보다 명확하다. 사전 변환 자산으로 바꾸면 현재 timestamp regex의 ‘하나’ 규칙도 실제 자산 manifest 검사로 바꿔야 한다.

### ASTRA 17 §6 다섯 조건 대조

| 조건 | 이번 판정 |
|---|---|
| 변환 전 실행별 절대 USD 경로 | **미충족.** 네 파일은 cfg.usd_dir를 지정하지 않는다. `asset_converter_base.py:66~85`의 시간·난수 기반 경로를 사후 감시한다. |
| 공통 잠금과 대기 중 중단·마감 | **부분 충족.** 잠금은 있으나 `acquire:31~41`는 무한 재시도하며 stop/deadline을 받지 않는다. CPU 시험에서 timeout 0.2초를 지정해도 잠금 대기 2초 후 자식을 기동했다. 해당 timeout은 취득 후 변환 시간만 제한한다. |
| 실제 참조·hash·공유 여부 검사 | **미충족.** 폴더 이름 비교만 있다. 충돌 발견도 장면 생성 후이므로 예방과 다르다. 늦게 공개된 경로 누락은 §2.2에서 재현했다. |
| 출력·attempt·실행 코드 격리 | **부분 충족.** unseen은 새 ROOT, 학습은 별도 1043 태그를 쓴다. 그러나 이동 실패·재시도 결과 보존·stamp 출처·실행 의존 코드 고정이 부족하다. |
| 실제 GPU 배정과 피크 감시 | **부분 충족.** guard는 NVML 장치·UUID·메모리를 기록하고 감시한다. evaluator는 torch UUID도 남긴다. validator는 이 신원과 실제 physics/renderer 배치를 대조하지 않는다. GPU 0의 256MiB 여유가 충분하다는 새로운 실측도 없다. |

**답: 다섯 조건을 충분히 채웠다는 판단은 반박한다.** 단일 수단으로 모두 해결하려 하지 말고, 공유 자산 보호와 결과 판정을 각각 완성해야 한다.

## 4. 질문 2 · 학습 완료 관문에서 고쳐진 것과 남은 것

**확인됨:** 예전의 `result.json` 존재만으로 건너뛰는 동작은 없어졌다. guard exit, slot rc·충돌·경로 개수, Traceback, done tag, 요청 seed·환경 수·update·cmdr·부모 경로와 현재 부모 hash, 최종 counter, 마지막 save 문자열, 두 checkpoint 존재를 검사한다. stamp 이후 파일 바이트 변경도 재사용 검사에서 잡는다. 정상 보강은 인정한다.

**하지만 §4의 모든 조건을 채운 것은 아니다.** §2.1의 실제 자식 종료 코드 우회, §2.3의 파일 내용 미검증, attempt를 사후 문자열로만 붙이는 문제가 남아 있다. 현재 stamp가 뜻하는 것은 ‘이 validator가 읽은 일부 필드와 파일 hash’이며 ‘이 attempt가 이 코드·입력으로 정상 학습해 올바른 모델을 저장했다’까지는 아니다.

**추정:** 학습 자체가 약 12시간을 쓰는 두 군 실험이므로 거짓 완료 차단은 기동 후 미뤄도 되는 정리 작업이 아니다. 다만 이번 반례로 실제 기존 1042 모델이 손상됐다고 결론내려서도 안 된다. 기존 모델의 실제 tensor 내용 재검은 이번 반례 시험과 별개다.

## 5. 질문 3 · unseen 비교의 범위와 진단 선정

### 대상·출력·full_record 수정은 맞다

**확인됨:** MODELS는 부모 E1 20,000, off1042 24,000, on1042 24,000이다. 셋 모두 `q_eval_cmdr.py`를 호출한다. off/on만 부모 YAML을 명시한다. 기본 실행 seed는 evaluator의 1000, noise off, student, difficulty 0.5, 칸당 100판이다. driver validator도 이 값을 검사한다. 다만 재현 계약은 evaluator의 기본값에 맡기기보다 명시 인자와 코드 hash로 고정하는 편이 낫다.

**확인됨:** 새 결과·로그·상태·집계 루트는 `_eval/out_uncr`다. 구 부모 자료는 post에서 읽기만 한다. `--full_record`는 넘기지 않으므로 `q_eval_cmdr.py`의 `if args.full_record` 아래 Recorder와 representative 출력 경로를 밟지 않는다. 기존 `_eval/out/full` 쓰기를 피한 수정은 맞다. **이 네 파일에 DR 영상 구현은 없으므로 향후 영상까지 새 출력·잠금 계약을 지킨다는 것은 미확인이다.**

### 같은 evaluator와 seed만으로 ‘확인된 짝’은 아니다

**확인됨:** `q_eval_cmdr.py:188~223`은 branch bundle의 부모 경로·hash를 확인하고 YAML/bundle hash를 기록한다. 그러나 YAML·bundle을 runtime cfg로 복원하지 않는다. 실제 cfg는 `Go2EnvCfg()`이고 저장 YAML은 diff 기록에 쓴다. 따라서 “갈래 설정을 완전히 복원했다”는 설명은 틀리다. 명령을 평가용 고정 schedule로 바꾸는 것 자체는 맞지만, action·관측·물리의 의도하지 않은 차이는 승인된 diff와 대조해야 한다.

**확인됨:** evaluator는 실제 mesh·origin·초기 pose·질량·마찰/반발·COM·actuator gains/delay·motor offset 지문을 이미 남긴다(`396~455`). driver가 이를 군간 비교하지 않는 것이 문제다. 기존 meta를 활용할 수 있어 모든 진단을 새로 만들 필요는 없다. `--full_record`를 끄는 것 자체가 이 지문을 없애지는 않는다. 다만 발 접촉 기록이 없으므로 ‘네 발 안전 도착’으로 결과 의미를 확장할 수 없다.

**추정:** 지금은 ‘같은 평가기와 seed로 비교하려는 설계’라고 적는 것이 정확하다. 세 군의 실제 지문·명령 전달·수치 유효성이 맞고 승인된 차이만 남았을 때 해당 칸을 짝 비교로 표시한다. 학습 seed 1042 한 개의 조건부 회귀라는 주석은 유지한다.

### 구 부모 비교의 이름은 더 좁혀야 한다

**확인됨:** `stage_post:245~249`는 구 부모 값을 새 off/on 분모에 섞지 않고 별도 열에 둔다. 이 방향은 맞다. 다만 `par_reproduces_old`는 **cross·surv 두 정수의 일치만** 본다. 같은 개수를 서로 다른 episode가 만들 수도 있고 지형·초기 상태·traj가 달라도 참이 된다.

**추정:** 이 필드는 ‘구 부모와 통과·생존 개수 일치’로 부른다. 실행 재현이나 개별 짝 재현을 주장하려면 별도 비교가 필요하다. 원래 실행은 q_eval.py와 full_record, 새 실행은 q_eval_cmdr.py와 full_record off라는 차이를 표시한다. 새 부모와 구 부모의 점수가 다르면 자동으로 CMD-R 효과라고 해석하지 않는다.

### diag 7칸은 권고와 맞으나 자동 full 승인은 아직 아니다

**확인됨:** gap·stones·ring 전진 0.5, rails·wave 전진 0.5, gap·discrete_obstacles 후진 0.3으로 ASTRA 17 §5.2의 권고 범위를 충족한다. rails와 wave를 둘 다 보는 것은 합리적인 추가다. 후진은 evaluator에서 초기 yaw를 맞춰 body 후진 명령으로 world +x 장애물을 만나게 하는 시험이다(`q_eval_cmdr.py:350~353`).

**확인됨:** diag는 7칸×3군=21실행이다. full은 30칸×3군=90실행이고 그중 15실행이 diag와 중복된다. 정상 재사용을 전제한 고유 합계는 **32칸×3군=96실행**이다. 96개 모두 독립 지형 표본이라는 뜻은 아니다.

**추정:** 진단은 입력/출력 검증 외에 지형 생성·로봇 시작·실제 장애물 조우·낙상/명령 실패의 해석까지 보는 단계여야 한다. `crossed`의 현재 정의인 ‘낙상 전 몸통의 구간 끝 통과’는 유지하고 CE12 안전 통과로 바꾸지 않는다. gap/ring의 낮은 성적은 그 자체로 코드 오류가 아니며, 그 이유를 분리해 적는다.

## 6. 질문 4 · 오늘 밤 배정에 대한 결론과 최소 순서

**추정: 제시된 배정은 조건부 대기열로는 가능하지만 지금 코드로 무인 기동할 수는 없다.** GPU를 채우는 것이 올바른 모델·비교 가능한 자료를 얻는 것보다 우선해서는 안 된다.

1. **CPU에서 먼저 막을 것:** §2.1의 이동·자식 실패 시 다음 군 차단, §2.3의 checkpoint/attempt 검증, §2.2와 §3의 실제 자산 보호, §2.4~2.5의 유효성·짝·post 상태 전파. 이번 반례를 회귀 입력으로 남긴다. 정상 가짜 출력만으로 완료 관문을 승인하지 않는다.
2. **그다음 실제 소규모 확인:** 운영자가 단독 실행에서 학습·평가 각각의 고유 USD/참조·명령·완료·물리 GPU 배정을 확인한 뒤 병행 여부를 정한다. 이번 검토는 GPU·Isaac을 실행하지 않았으므로 이 관문은 미확인이다. 실제 경로 보호가 준비되지 않으면 Isaac은 직렬로만 배치한다. 직렬 배치도 거짓 완료 관문 수정을 면제하지 않는다.
3. **GPU 0:** S0/S2가 아직 GPU를 쓸 준비가 없다는 운영 조건 아래 1043 완전 쌍 학습을 별도 슬롯에 넣을 수 있다. 두 군 예상 시간 외에 저장·재시도·후속 평가 시간을 확보한다. 1043 학습만 끝내고 seed 효과 검증 완료라고 하지 않는다. GPU 1의 1042 unseen은 1043 목표 세 칸·등록 회귀 평가를 대신하지 않는다.
4. **GPU 1:** 우선 `diag`만 실행하고 유효성·짝·조우 진단을 확인한 뒤 full로 확대한다. 현재 기본값 `diag,full,post`는 형식 관문만 지나면 자동 확대하므로 사용하지 않는다. 성적이 낮다는 이유로 선택적으로 좋은 칸만 full에 남겨서는 안 된다. DR 영상은 평가와 구분해 뒤에 둔다.
5. **S0 우선권:** 현재 shell/driver에는 stop 요청·마감·우선순위 확인이 없다. `run_set`과 slot 대기 중에도 S0 준비 여부를 보지 않는다. 따라서 ‘S0가 준비되면 우선’은 현재 코드가 이행하는 기능이 아니다. 운영자가 다음 셀/군을 시작하지 않게 하는 중단 관문과 안전한 인계 시점을 먼저 정한다. 미완료 실행을 완료로 적거나 임의 중단한 1043을 완전 반복이라고 부르지 않는다.

**최종 판정:** 세 원래 결함에 대한 수정 방향은 맞다. 그러나 정상 경로 시험이 막지 못한 거짓 완료를 실제 CPU 반례로 재현했고, USD의 실제 안전성과 평가 짝 검증도 아직 공백이다. lead의 ‘이 넷으로 오늘 밤 병렬 기동 조건을 채웠다’는 결론에는 동의하지 않는다. 위 수정과 실제 소규모 확인을 거쳐 기동해야 한다.

## 7. 재확인 범위

다음 검토를 한다면 이번 반례와 그 수정 영향만 확인하면 된다. Top-down 전체 설계나 이미 닫은 16차 집계를 다시 열 필요는 없다.

- shell: 정상 대조는 진행, 이동 실패·자식 nonzero·이전 attempt 혼입은 멈춤.
- validator: 정상 실제 checkpoint는 통과, 손상·다른 iter/모델·다른 출처는 거부.
- slot: 알려진 경로를 검증 후 해제, 늦은/추가/공유 경로 및 잘못된 참조는 거부, 대기 중 중단 이행.
- unseen: 정상 3군은 비교, 지문 불일치는 짝 보류, nonfinite/기록 손상은 실행 무효, partial post는 미완료, post-only 범위와 attempt 증거 보존.

이 파일 외의 영구 산출물은 없으며 커밋·push·GPU·Isaac 실행도 하지 않았다.

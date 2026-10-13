고쳐서 계속: 현재 GPU 0의 1043 학습과 GPU 1의 1042 진단 수집은 유지하되, 후처리 성공 판정과 full 확대는 아래 결함을 고치고 실제 결과 묶음을 재검증할 때까지 보류한다.

> 분류: A/평가 · 밤 실행 도구 검증
> 작성: 오흥재 (ASTRA 검증) · 2026-10-13
> 근거: TASK-astra-17c-launch-check.md · fd12ede5 · night-tools-20261013 사본과 실행본 · 임시 사본 CPU 반례 · 실행 중 기록의 읽기 전용 검사
> 요지: 이전 반례 대부분은 막혔지만 post 단독 거짓 완료는 남았다. USD 격리는 현재 Go2 경로에서 확인되며 모든 변환 경로의 보장은 아니다.
> 상태: 조건부 유지 · 최종 집계 승인 및 full 기동 보류

# ASTRA 17c · 수정 도구와 실제 기동 유지 검증

## 1. 현재 두 실행에 대한 판정

**판정: 두 프로세스를 지금 끝내야 할 근거는 확인하지 못했다. 수집은 유지한다. 그러나 ‘모든 결함 해결’이나 ‘무인 확대 승인’은 아니다.** 이 둘을 혼동하면 안 된다. 아래 남은 결함은 주로 결과 승인과 다음 기동의 관문에 있으며, 관찰한 현재 실행의 USD 공유나 판정 구간의 물리 상태 손상을 입증한 것은 아니다.

| 대상 | 이번 판단 | 범위와 조건 |
|---|---|---|
| GPU 0 · `cmdr_s1043_off_u4000` | 현재 학습 유지 | 전용 USD 경로와 loader 적용, 진행 로그를 확인했다. 아직 학습 완료·최종 체크포인트 검증은 미확인이다. |
| GPU 0 · 뒤따르는 1043 on | 같은 학습 쌍의 후속 군으로 가능 | off의 실제 종료·저장 검증을 먼저 통과해야 한다. on도 자기 attempt의 assigned 경로·실제 파일·장면 로그를 확인한다. off에서 확인한 경로를 on의 확인으로 대신하지 않는다. |
| GPU 1 · `diag,post` | 등록된 진단 7칸 수집 유지 | `post` 결과는 잠정표다. 실제 자료의 shape·판정 구간 유한성·지문 내용·출처를 재검사한 뒤 확정한다. |
| GPU 1 · `full` | 기동 보류 | 현재는 요청된 단계가 아니다. 오래된 gate의 불리언 두 개로 확대할 수 있는 결함이 남아 있다. |

실행 중 코드를 덮어써 해결하지 않는다. 학습·평가 원자료와 원래 실행 해시는 유지하고, 보강한 검증기는 별도 사본으로 동결 자료에 적용한다. 새 검증기를 사용했다는 이유로 수집 당시 코드 해시를 새 판의 것으로 바꾸면 안 된다.

**중단으로 판단을 바꿀 조건:** 현재 attempt 밖의 쓰기 가능한 USD를 실제 사용함, 다른 실행과 같은 실제 USD 경로를 사용함, 로봇 루트·물리 참조 실패, 판정에 필요한 상태의 비정상값, 코드·부모·평가 조건 변경이 확인되는 경우다. 점수가 낮다는 이유만으로 실험을 중단하거나 무효 처리하지 않는다. 운영자가 STOP을 쓰더라도 현재 학습 군을 즉시 끝내는 스위치가 아니라 다음 군·잠금 대기의 기동을 막는 장치라는 점을 구분해야 한다.

### 실제 기록을 어디까지 확인했는가

**확인됨 · 19:15:48 KST 읽기 시점:** GPU 0 학습 1건과 GPU 1 평가 13건의 `assigned.jsonl`에서 서로 다른 절대 USD 디렉터리 14개를 확인했다. 각각 `patched_by=loader`이고, 해당 디렉터리에 `go2.usd`와 `configuration/go2_{base,physics,robot,sensor}.usd`가 있었다. GPU 1의 그 시점 완료 12건은 모두 slot/child 0, `scene_built`, outside/conflicts 비어 있음이었다. 완료된 gap·stepping_stones·floating_ring·rails의 세 군은 저장된 네 지문 묶음이 각각 일치했다. 지문은 비어 있지 않았고 mesh 경로·정점 수·해시와 초기 상태/DR 항목을 실제로 포함했다.

대표 경로는 다음과 같다. 아래 `_eval`은 `C:/isaac/ext/go2_rl_robotlab/_eval`이다.

- 학습: `_eval/out_branch/_usd/g0-cmdr_s1043_off_u4000-1013185657-895773/IsaacLab/usd_20261013_185709_9514/`
- 평가: `_eval/out_uncr/usd/uncr_par_gap_fwd05-g1-83128-1013185735-uncr_par_gap_fwd05-try1/IsaacLab/usd_20261013_185748_7028/`
- 기록: 위 attempt 폴더의 `assigned.jsonl`·`isolate_state.json`, 각 출력 루트의 `<tag>.log`·`.slot.json`·`.guard.json`, `_eval/out_uncr/driver.json`.

**확인됨 · 19:18:31:** 완료 평가 15건 모두 `traj`의 물리 상태 채널 0~10은 전 구간 유한했다. 각 episode의 최초 낙상 시각까지 포함한 구간에서도 물리 상태와 높이 채널의 비정상값은 없었다. 이 검사는 `checks_run`의 자기 보고만 읽은 것이 아니라 npz 배열을 직접 센 것이다.

예외도 숨기지 않는다. `uncr_on_gap_fwd05/traj.npz`에는 **NaN 193개**가 있다. 전부 env 50의 채널 11, sample 808~1000이다. 첫 NaN은 16.16초이고, 저장된 낙상은 base_contact 1.56초이며 `term[78,50]=True`도 확인했다. 채널 11은 `q_eval_cmdr.py:559~574`의 지면 높이 추정값으로, 유효 ray hit가 없으면 `nanmean`이 NaN을 낼 수 있다. 현재 이 episode의 낙상 전 통과·생존 계산을 훼손한 증거는 없다. **‘배열에 NaN이 하나라도 있으면 학습 발산’은 이 사례에서 틀린 판단이다.** 원자료 SHA256은 `4e729ebd3fa18200fbe43fcaa849761811c354d3d7e5ff6c0f55aa35dc03ea0a`이다.

**확인됨 · 19:20:49:** driver 기록은 16건 완료, failures 없음, 아직 post/전체 완료 전이었다. 이 문서의 중간 관찰을 전체 21건 검증 완료로 읽으면 안 된다.

**미확인:** USD 내부의 모든 참조를 최종 합성된 stage에서 해결했는지, 실제 collider·inertia가 기대값과 같은지까지 검사하지 않았다. 이번 CPU 환경에 `pxr`는 없고 원본은 USDC여서, Isaac을 띄우지 않고 여기까지 확인했다고 주장할 수 없다. 현재 root 오류는 없지만, 학습 로그에는 `Head_upper/visuals`·`Head_lower/visuals`의 unresolved reference 16,432줄, 대표 평가 로그에는 248줄이 있다. 이전 1042 off/on 로그도 같은 두 visuals 유형 16,432줄이다. 새 격리로 생긴 로봇 루트 실패와 같은 것으로 세면 안 되며, 그렇다고 시각 자산까지 정상이라고 승인하지도 않는다. 물리 영향이 없다는 완전한 증명은 별도다.

## 2. 질문 1 · 17b 반례 넷의 재검 결과

### 2.1 거짓 학습 완료: 지정한 반례는 막혔다

**확인됨:** `night_20261013_cmdr1043_v3.sh:35~38,50~55`가 이동 실패·자식 실패·validator 실패를 각각 중단으로 전파한다. 실제 Bash에서 `mv(){ return 1; }`을 `BASH_ENV`로 주입하고, 이전 결과가 있는 임시 폴더를 입력했다. **rc=4, slot 호출 0, PAIR DONE 없음**이었다. 자식 실패 시험도 slot rc=7 입력에 shell rc=5, 완료 validator 호출 0이었다. 이전 attempt 기록·오래된 result로 통과시키는 경로는 validator의 attempt/since 검사와 함께 막힌다.

단, **lead의 제공 시험 ‘8/8’은 내 실행 환경에서 그대로 재현되지 않았다.** 원본 `test_night_1043_v3.py`는 7/8이고 N2가 실패했다. 이유를 직접 확인하니 `PATH` 앞에 둔 mv stub보다 Git Bash가 `/usr/bin`을 먼저 넣어 `command -v mv`가 `/usr/bin/mv`를 가리켰다. 실제 이동이 성공한 시험에서 ‘이동 실패를 막았다’고 판단할 수 없다. 앞의 BASH_ENV 시험은 stub 호출 표식까지 확인해 올바르게 실패를 주입한 재시험이다. **제품 shell의 이동 실패 처리는 맞고, 제공 시험의 실패 주입 방식이 환경 의존적이다.** lead가 다른 Bash 환경에서 8/8을 얻었을 가능성은 있으며 그 당시 환경은 미확인이다.

### 2.2 늦은 USD 경로: 옛 반례는 막혔지만 격리 검사는 아직 불완전하다

**확인됨:** 장면 생성 줄을 먼저 내고 충돌 USD 경로를 뒤늦게 내는 T8은 rc=96으로 거부했다. 경로가 나타나기 전에 잠금을 풀던 17b 반례는 닫혔다. 잠금 대기 중 STOP·마감도 CPU 시험에서 자식을 기동하지 않고 98로 끝났다.

그러나 아래 두 사실은 별개다.

- `isaac_slot.py:182,191~201`은 **자식이 끝난 뒤** 루트 밖 경로를 94로 거부한다. 18:51 gate의 `child_rc=0`, 종료 18:51:39, slot 94가 이를 뒷받침한다. ‘공용 폴더에 쓰기 전에 막았다’는 설명은 틀리다. 이번 3 update는 짧았지만 같은 우회가 긴 학습에서 생기면 끝날 때까지 실행할 수 있다.
- `under_root:87~88`은 각 실제 경로를 검증하지 않고 로그 전체에 허용 경로 문자열이 한 번 있는지만 본다. CPU 자식이 `자기루트/IsaacLab/usd_20261013_190000_1234/go2.usd`와 `C:/other/IsaacLab/usd_20261013_190000_1234/go2.usd`를 모두 기록하도록 했다. **slot rc=0, outside=[], conflicts={}**였다. 같은 basename 두 경로가 하나로 합쳐졌다.

**수정 방향:** 정규화한 실제 절대 경로별로 검사하고, assigned 기록·사용 로그·물리 루트 참조를 연결한다. 격리가 적용되지 않았거나 밖으로 벗어났으면 장기 실행 허용 전에 실패해야 한다. 지금 관찰한 실행들은 서로 다른 정상 전용 경로를 사용하므로 이 반례만으로 이미 확보한 모든 자료를 폐기하지는 않는다.

### 2.3 체크포인트: 지정한 내용 반례는 막혔다

**확인됨:** 1042 on의 실제 22,000/24,000 체크포인트를 임시 폴더로 복사해 제공 시험 22개를 실행했다. 모두 통과했다. 읽을 수 없는 pt, 22,000 파일을 24,000으로 바꿔 놓은 경우, tensor는 그대로 두고 iter만 틀린 경우, 마지막 save 파일명 오류, slot 자식 실패, 격리 실행기 누락, attempt 불일치, 오래된 result, root 참조 오류, 부모 해시 불일치를 거부했다. `torch.load(map_location='cpu')`를 사용했고 GPU는 실행하지 않았다.

남은 의미상의 한계도 적는다. `validate_branch.py:41~58`은 model state·iter·유한성·저장 당시 tensor hash를 검사한다. **optimizer/normalizer 전체 상태로 정확한 resume가 가능한지까지 검증한 것은 아니다.** `118~122`의 bundle.npz도 존재만 보고 내용을 열지 않는다. 새 1043 학습의 완료와 후속 재개/평가용 bundle 검증을 이 CPU 시험의 성공으로 대신하면 안 된다. 다만 이 한계가 현재 off 학습을 중단할 근거는 아니다.

### 2.4 평가 짝·post: 일부 수정됐고 한 옛 반례가 그대로 남았다

**확인됨:** DR 지문 차이는 pair_ok=false로 남기고, nonfinite_action_or_obs_count=10·깨진 npz·student 경로 오차는 거부한다. 기존 이름도 `par_counts_match_old`로 좁혔다. 정상 형식의 시험 9개는 통과했다.

**P1 · post 단독 거짓 완료는 재현됐다.** 사본에서 빈 출력 루트를 지정하고 공개된 CLI 그대로 `unseen_driver_cmdr.py --stages post`를 실행했다. 결과는 다음과 같다.

```text
exit 0
post.rows = 32
post.complete = 0
post.requested_incomplete = []
diag_runs_valid = false
diag_pair_ok = false
failures = []
finished = 2026-10-13 19:12:23
```

원인은 `main:325~340`이다. requested는 diag/full을 실제로 실행한 경우에만 채워진다. **제공 D5 시험은 CLI를 통하지 않고 `stage_post(set(DIAG))`를 직접 호출해 이 경로를 우회했다.** ‘빈 post 반례를 회귀 시험에 남겼다’는 주장은 사용자 진입점에서는 성립하지 않는다. 현재 돌아가는 `diag,post`는 DIAG를 채우므로 동일한 빈 요청 경로는 아니다. 요청 manifest를 CLI 인자나 고정된 수집 계약으로 받아 post 단독에도 적용하고, 완료·부분 완료·짝 불일치를 명확히 분리해야 한다.

**P1 · 궤적과 지문의 유효성 검사가 부족하다.** 추가 CPU 반례는 다음과 같다. 코드가 읽는 파일의 stamp 해시는 변경한 합성 자료에 맞춰 다시 계산했다. 즉 단순한 ‘해시가 안 맞는 파일’ 시험이 아니라 잘못된 내용을 처음부터 승인하는지 본 것이다.

| 입력 | 실제 출력 | 문제 |
|---|---|---|
| 정상 합성 7칸 중 on/gap의 env 0 x좌표 전 구간을 NaN으로 변경, checks_run은 0 | validate 빈 오류, reusable=true, complete=7, 두 diag gate=true; cross는 100에서 99로 줄고 경고만 출력 | `178~183`은 origins 유한성만 본다. `np.nanmax`가 손상 자료를 실패 1건으로 바꿔 버린다. 무효 측정과 성능 실패를 혼동한다. |
| 모든 군의 mesh·초기 상태·DR 지문을 `{}`, origins 지문을 빈 문자열로 변경 | complete=7, 두 diag gate=true | `261~272`는 비어 있지 않은 정상 지문인지 검사하지 않고 동등성만 본다. 같은 실패 문자열·같은 빈 배열도 동등할 수 있다. |

보강할 때는 **채널·판정 시간 구간·유효 표본 마스크를 명시**해야 한다. 위치·방향·속도 등의 필수 상태, 관측·action 비정상값과 지면 ray miss를 나누고, 필수 구간 손상은 invalid로 처리한다. 낙상 후 높이 NaN 193개를 근거로 현재 gap 평가를 자동 폐기하는 것도 잘못이다(§1). 현재 코드가 만든 실제 traj는 `[T_steps+1, N, 12]`인데 검증기는 3채널 이상이면 통과한다. T/N, term 및 env/episode 대응, 음수 env 인덱스도 함께 확인해야 한다. 지문은 실제 evaluator가 출력하는 mesh 목록·필수 초기 상태/DR 키·해시 형식을 먼저 검사하고 그다음 비교한다.

**P1 · 오래된 full 관문을 그대로 믿는다.** 빈 임시 루트에 `diag_runs_valid=true`, `diag_pair_ok=true`, 날짜 2000년, 무관한 attempt만 있는 gate를 놓았다. `run_set`을 CPU 호출 기록 함수로 교체한 뒤 `--stages full`로 main을 실행하자 **full 30칸 호출, exit 0**이었다. 실제 평가·GPU는 띄우지 않았다. `329~338`은 현재 코드·checkpoint·diag 출력 hash와 gate를 묶지 않는다. 자동 확대 전에 현재 자료를 다시 확인하고 그 묶음 해시에 관문을 연결해야 한다.

## 3. 질문 2 · loader 격리의 범위와 부작용

### 확인된 범위

**확인됨:** 설치된 Isaac Lab 소스의 `UrdfConverter:26,74`, `MjcfConverter:20,48`, `MeshConverter:24,61`은 `AssetConverterBase`를 상속하고 base 초기화를 호출한다. 정상 적재 뒤 이 base를 패치했다면 **그 base를 거치는 `cfg.usd_dir is None` 경로**에 새 디렉터리 할당이 적용된다. 현재 실제 기록의 Unitree URDF 변환도 loader 경로에서 할당됐다. 이것은 이번 기동에 의미 있는 직접 증거다.

**틀린 일반화:** ‘모든 Isaac 변환·지형 생성에서 첫 변환 전에 반드시 적용된다.’ 근거가 부족한 정도를 넘어, 범용 주장에는 반례가 있다.

| 추가 반례 또는 소스 경로 | 직접 확인한 결과 |
|---|---|
| 앞선 finder가 비표준 loader로 모듈을 적재하고 바로 변환. 제공 U9의 `import colorsys` 한 줄 제거 | rc=0이나 USD는 fake 공용 tmp로 갔다. `patched_by=audit:os.mkdir` 기록도 생겼지만 첫 경로 선택 후였다. **패치 기록 존재가 첫 변환의 격리 증거는 아니다.** |
| `cfg.usd_dir`를 명시적으로 루트 밖으로 지정 | loader 패치 상태인데도 그대로 사용하고 assigned 기록 대상에서 빠졌다. 허용된 불변 입력과 쓰기 가능한 변환 출력을 구별하지 않는다. |
| 지형 생성/캐시 | `terrain_generator.py:364~397`은 별도의 cache_dir/hash 아래 mesh.obj·origin.csv·cfg.yaml을 읽고 쓴다. 이 wrapper가 가로채는 경로가 아니다. 현재 q_eval_cmdr는 `292`에서 use_cache=false이다. 학습을 포함한 모든 캐시 쓰기 격리까지 이번에 실증하지는 않았다. |

비표준 loader의 즉시 변환 한계는 의뢰서에도 인정돼 있다. 이를 숨겼다고 비판할 일은 아니다. **이미 알려진 실패 가능성이므로 94를 예방 관문처럼 설명하지 말고, 지원하지 않는 경로는 긴 실행 전에 거부해야 한다**는 것이 핵심이다. 표준 loader를 통하지 않는 native/custom 적재·이미 변환이 끝난 모듈·base를 거치지 않는 경로 전체를 현재 hook 하나로 보장할 수 없다.

### 난수 불변성은 한 번의 변환에만 확인됐다

**확인됨:** 제공 U2/U7에서 `usd_dir=None`인 정상 단일 변환 뒤 Python `random.random()`은 wrapper 유무에 따라 같았다. 그러나 같은 cfg 객체로 변환기를 두 번 만드는 CPU 반례에서는 달라졌다.

| seed=7, 같은 cfg로 두 번 생성 | 경로 | 이어지는 random.random() |
|---|---|---|
| 원래 base 경로 | 두 경로가 다름, randrange 두 번 | `0.3948234964231735` |
| wrapper 적용 | 두 경로가 같음, randrange 한 번 | `0.9478653606090632` |

`usd_isolate_run.py:50~57`이 `cfg.usd_dir`를 영구 변경하기 때문이다. 두 번째 변환은 명시 경로 재사용이 되고 random 소비도 하나 줄어든다. 원본 `asset_converter_base.py:66~71`은 cfg를 이렇게 변경하지 않는다. 변환 캐시 재사용 의미까지 바뀐다. **‘Python random 소비를 원래와 같게 유지’라는 무조건적 주석은 틀리다.** cfg의 원래 의미를 보존하는 별도 설정 사본/할당 전략이 필요하며, 같은 설정 두 번·서로 다른 설정·명시 디렉터리 각각을 시험해야 한다.

현재 기록에서는 각 실행에 assigned 1건이 관찰됐다. 이번 실제 실행에서 같은 cfg 두 번 반례가 발동했다는 증거는 없다. 따라서 이 문제만으로 기존 1043 학습을 폐기하지 않는다. Python·NumPy·Torch·물리 난수 전체의 불변성은 **미확인**이다. 같은 평가 seed와 단일 random 시험으로 전체 rollout이 바이트 동일하다고 주장하면 안 된다.

**import·성능:** `_LoaderBasics`는 CPython 내부 구현이며 wrapper는 다른 모듈의 표준 적재에도 얇은 호출 한 단계를 더한다. finder·audit hook과 추가 파일 I/O도 있다. 대상 모듈의 원래 loader를 호출하는 순서는 보존하지만, 전체 import 순서와 초기화 부작용이 전혀 안 달라진다고 검증하지는 않았다. 실제 학습 iteration overhead·처리량에 대한 같은 조건 A/B는 **미측정**이다. 원본 cfg의 경로 검사보다 random을 먼저 소비하게 되는 실패 경로도 있으므로 ‘결과·성능에 영향 없음’ 대신 ‘현재 경로 기동 확인, 수치·성능 동등성 미검증’으로 적는다.

## 4. 질문 4 · 출력 루트 분리

**확인됨:** shell `21~22`의 `BRO=../out_branch`, `export BRANCH_OUT`과 branch_run의 출력 경로, validator `29`가 같은 새 루트를 사용한다. 로그·guard·slot·체크포인트·attempt 보존·STOP도 그 루트다. N8 시험과 현재 학습 bundle/로그의 실제 위치가 맞는다. 17 §4의 기존 `_eval/out` 불변 요구에 맞는 변경이다.

`unseen_driver_cmdr.py:34,38~41`은 새 출력 `_eval/out_uncr`와 기존 1042 입력 `_eval/out/branch`를 나눴다. 기존 E1 결과는 `290~294`에서 통과·생존 개수 대조용으로 읽는다. 이 코드의 주요 결과 쓰기·재시도·post는 새 출력으로 향한다. 1043 학습 출력과 1042 평가 입력을 혼동한 경로는 확인하지 못했다. **1043을 학습했다고 현재 GPU 1 진단이 1043 결과가 되는 것은 아니다.** GPU 1은 끝까지 1042 off/on 평가다.

경로 이동에 따른 부수 한계는 남는다. unseen의 `--scan_dirs`는 `[ROOT, BR]`, 즉 out_uncr와 옛 out/branch이며 새 out_branch를 직접 훑지 않는다. 공통 registry가 현재 학습 경로를 보완하지만 그것만 믿을 구조는 아니다. 실제 절대 경로 manifest로 참여자를 묶고, 공통 registry도 아래처럼 안전하게 갱신해야 한다.

## 5. 질문 5 · 추가로 놓친 운영·출처 문제

### 공통 registry는 최종 갱신에서 잠금이 없다

**확인됨:** `isaac_slot.py:179`에서 잠금을 푼 뒤 `185~190`이 registry를 다시 읽고 쓴다. 다른 참가자의 변환 잠금 구간과 겹칠 수 있다. `.tmp` 파일명도 공통이다(`110~116`). CPU 사본에서 허용되는 순서를 직접 적용했다.

```text
A 최종 검사: 빈 registry 읽음
B 검사·등록: {'B': 'B.log'} 저장
A 최종 등록: 앞서 읽은 빈 dict에 A만 넣어 저장
최종 registry: {'A': 'A.log'}
```

B 기록이 사라졌다. 실제 두 프로세스에서 이 race가 이미 발생했다는 것은 **미확인**이다. 고유 실제 USD 루트가 현재의 1차 보호이고 registry는 이를 대신할 수 없다. 최종 read/merge/write까지 잠금을 공유하고 고유 임시 파일을 사용해야 한다. basename만 registry key로 쓰는 방식도 바꿔야 한다. 서로 다른 절대 루트라도 날짜·시각·random suffix가 같으면 T3b의 ‘충돌’이 되는데, 그것은 실제 파일 공유와 다르다. 로그 스캔도 `attempts/*.log*`여서 새 `attempts/<tag>.<시각>/`의 하위 로그를 읽지 못한다.

### 수집 코드와 집계 코드의 출처를 섞으면 안 된다

**확인됨:** unseen의 CODE 목록(`48`)은 q_eval_cmdr·q_metrics·slot·isolate·guard·driver 여섯 개다. 하지만 q_eval_cmdr는 실제로 `q_post.py`를 호출해 episodes/cells를 만든다(`640~659`). q_post는 driver stamp에 없다. 현재 실행본 q_post SHA256은 `f90aaa97a50c5347111298b913d7bb948e58f0d1ce3af09808739cfcae1e26dd`이다. 입력 YAML은 경로를 확인하지만 그 내용 해시는 이 validator에서 재대조하지 않는다.

또한 `237`의 code_sha는 실행 후 파일 상태다. 실행 중 파일이 바뀌면 실제 로딩한 코드와 다른 판을 stamp에 적을 수 있다. 현재 핵심 사본 14개는 검사 중 같았지만, 이 사실이 코드의 출처 보장을 완성해 주지는 않는다. 시작 시 입력·코드 manifest를 동결하고 종료 시 재대조하며, 정책 수집과 후처리 버전을 분리해 기록해야 한다. 기존 stamp가 일부 dependency를 안 담았다고 원자료를 곧바로 버릴 필요는 없지만, 출처 미확인인 항목을 ‘모든 코드 고정’이라고 표현하면 안 된다.

## 6. 질문 3 · 아침 보고에서 가능한 주장

**1043 학습:** 두 군 각각 종료·부모/설정·최종 counter·22,000/24,000 pt 내용·실제 USD 경로·bundle을 확인한 뒤에만 ‘E1 20,000에서 시드 1043 off/on 4,000 update 학습 완료’라고 쓸 수 있다. 학습 완료만으로 CMD-R 효과가 재현됐거나 unseen 성능이 개선됐다고 할 수 없다. 1043의 목표·등록 회귀 평가가 따로 필요하다. 이번 GPU 1의 1042 진단이 이를 대신하지 않는다.

**1042 진단:** 유효한 7칸 21실행을 확보하고 실제 지문·판정 구간·측정 정의를 검증한 뒤 ‘학습 시드 1042의 부모 E1 20,000·off/on 24,000을 동일 평가 시드 1000, 난이도 0.5, 각 100판으로 비교한 조건부 회귀 진단’이라고 쓴다. `crossed`는 **낙상 전 몸통의 장애물 구간 끝 통과**이며, 네 발 도착·명령 준수·안전 도착의 인증이 아니다. 지형·명령 칸별로 생존과 통과를 분리하고 무효/보류는 분모와 함께 표시한다.

100 episode를 100개의 독립 학습 반복으로 해석하지 않는다. 이번 표만으로 학습 seed에 일반화된 효과, 전체 10종·모든 명령·v2 대비 우월성을 말할 수 없다. 구 부모와 cross/surv 정수가 같아도 실행·궤적 재현까지 같다는 뜻은 아니다. 지문이 맞아도 ‘기록된 짝 조건이 일치’이지 모든 숨은 물리·난수 상태가 같다는 증명은 아니다.

**유지 조건의 최소 이행 순서:** 현재 수집본 보존 → 수정한 CPU 검증기로 동결 묶음 재검사 → 수집/후처리 버전과 보류 항목을 명시한 진단 보고 → 현재 묶음에 연결된 gate 및 실제 조우 검토 → 그 후 full 여부 결정. 밤에 GPU를 채웠다는 운영 실적을 실험 결론으로 쓰지 않는다.

## 7. 검증 범위·재현·잔여 미확인

의뢰 기준은 `fd12ede5ed2cba34bf6bf5f0dd8d4677b58da795`이다. `night-tools-20261013/SHA256SUMS.txt`의 **14개 전부**에 대해 사본·실행본·명세 SHA256이 일치했고 19:20:49에도 다시 같았다. 기동 해시 파일과 branch_lib의 `3d186c725082367572affced77d064a61d9bfd087a8e0f4629e43a2cb756eafc`도 일치했다. 검사 중 공용 브랜치 HEAD가 다른 작업으로 이동했으므로 HEAD 이름보다 이 파일 해시를 검증 대상으로 고정했다. 기존 변경과 다른 세션의 새 파일은 수정하지 않았다.

| CPU 시험 | 직접 재실행 결과 | 해석 |
|---|---|---|
| `test_usd_isolate.py` | 9/9 | 제공한 import/단일 변환 fixture 범위에서만 통과 |
| `test_isaac_slot.py` | 15/15 | 실제 Isaac 대신 임시 로그를 쓰는 CPU 자식 |
| `test_validate_branch.py` | 22/22 | 실제 1042 pt의 임시 복사본, CPU load |
| `test_night_1043_v3.py` | 원본 7/8, N2 주입 수정 재시험 통과 | 코드 수정 없이 BASH_ENV 함수로 실패를 주입. 잘못된 stub 선택을 확인함 |
| `test_unseen_driver_cmdr.py` | 9/9 | 합성 fixture. 공개 CLI post와 지문/궤적 손상 전체를 보장하지 않음 |
| 독립 반례 | post 빈 결과, NaN x좌표, 빈 지문, 오래된 full gate, 즉시 비표준 적재, 같은 cfg 두 번, 명시 외부 USD, 같은 basename의 혼합 경로, registry 손실 | §2~5의 실패를 직접 재현 |

시험 환경은 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`와 Git Bash다. `PYTHONDONTWRITEBYTECODE=1`을 설정하고 temp의 `_eval/branch` 구조에 사본과 필요한 CPU dependency·1042 체크포인트를 복사했다. 추가 코드는 전부 그 임시 폴더에서 실행했다. full gate 시험의 실제 실행 함수는 호출 기록 stub으로 대체했다. 실제 driver main/post를 운영 출력에 실행하지 않았고, GPU·Isaac·운영 프로세스·STOP·원자료는 변경하지 않았다.

반례 재현 시 특히 구분할 사항은 세 가지다. post는 함수 직접 호출 대신 빈 임시 UNCR_ROOT에서 **CLI `--stages post`**를 사용한다. 비표준 loader 시험은 제공 U9에서 변환 직전 추가한 colorsys import를 없앤다. 두 번 변환 시험은 `cfg=Cfg(); a=AssetConverterBase(cfg); b=AssetConverterBase(cfg)`로 같은 cfg를 재사용하고 다음 random 값을 비교한다. 검증기 손상 시험은 fixture의 `outhash`를 다시 계산해, stamp 이후 변조가 아니라 내용 검증 자체의 누락을 검사한다.

**미확인/미측정:** lead의 변이 시험 11개·18개는 이번에 재실행하지 않았다. 실제 Isaac을 새로 띄운 A/B, USD 최종 stage의 전체 참조·collider, 성능 overhead, 이후 실행 완료와 전체 21건 결과는 이 문서의 중간 관찰만으로 확정하지 않는다. CPU 시험과 실제 기동 기록이 각각 증명하는 범위를 넘어선 승인은 하지 않는다.

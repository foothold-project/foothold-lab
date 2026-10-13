> 분류: A/평가 · 밤 실행 도구 (Isaac 실행 관문 · USD 격리 실행기) v3
> 작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 2026-10-13 20:16 (시험 수 · 시간 최종 확인 23:31)
> 근거: VERIFY-astra-17c.md §2.1 · §2.2 · §3 · §4 마지막 문단 · §5 「공통 registry」 · VERIFY-astra-17d.md §2.6 · v2 원본 (읽기만) · Isaac Lab `asset_converter_base.py` · URDF · MJCF · Mesh 변환기 · `terrain_generator.py` · 이 글의 CPU 시험 · 변이 · 실제 기록 읽기 전용 재연
> 요지: 17c 반례 (같은 basename 혼합 경로 · 늦은 94 · registry 손실 · 하위 attempts 로그 · 같은 cfg 두 번 · 명시 외부 usd_dir · 비표준 loader 즉시 변환 · N2 주입) 와 17d §2.6 (예상 변환 0 · 1) 을 CPU 시험으로 재현하고 v3 에서 막았다. 실제 Isaac 에서의 동작은 미확인이다.
> 상태: CPU 시험 · 변이 통과 · 실제 Isaac · GPU 미실행 · 기동 코드 (night v3 셸 · unseen_driver_cmdr · ce12) 는 아직 v2 를 부른다 (이 판은 아무 기존 파일도 고치지 않았다)

# Isaac 실행 관문 · USD 격리 실행기 v3

v2 (`isaac_slot.py` · `usd_isolate_run.py`) 와 그 시험은 그대로 둔다. 지금 도는 학습과 새벽 재기동이 v2 를 부르기 때문이다. v3 는 옆에 새 파일로 만들었다.

## 1. 만든 파일

모두 `C:/isaac/ext/go2_rl_robotlab/_eval/` 아래다.

| 파일 | 하는 일 |
|---|---|
| `isaac_slot_v3.py` | 실행 관문 v3. v2 와 같은 인자 · 같은 종료 코드 뜻에 선택 인자 `--expect_conversions 0\|1` 하나를 더했다 |
| `usd_isolate_run_v3.py` | USD 격리 실행기 v3. v2 와 같은 쓰임 (`FOOTHOLD_USD_ROOT=... python usd_isolate_run_v3.py <스크립트> ...`) 에 선택 환경 변수 `FOOTHOLD_EXPECT_CONVERSIONS` |
| `test_isaac_slot_v3.py` | slot 시험 43칸. 가짜 자식은 임시 로그와 assigned.jsonl 을 쓰는 CPU 프로세스. E3 ~ E5 는 진짜 v3 실행기와 가짜 isaaclab 변환기를 묶은 통합 시험 |
| `test_usd_isolate_v3.py` | 실행기 시험 27칸 (U1 ~ U26 · U10b) 과 시간 INFO 줄 |
| `mutate_isaac_slot_v3.py` | slot 변이 36개 |
| `mutate_usd_isolate_v3.py` | 실행기 변이 19개 |
| `branch/test_night_1043_v3b.py` | night v3 셸 실패 경로 시험. N2 주입을 BASH_ENV 함수로 바꾸고 호출 표식을 확인 (10칸) |
| `branch/mutate_night_1043_v3b.py` | night 셸 변이 5개 (변이본은 임시 폴더에만 씀) |
| `README-slot-isolate-v3.md` | 이 글 |

시험과 변이는 모든 잠금 · registry · 로그 · 변이본을 시스템 임시 폴더 (`%TEMP%`) 에 만들고 지운다. `_eval/slot/` · `_eval/out*` · `handover*` 에는 쓰지 않는다. 시험 기대값은 손으로 적었다 (경로는 `os.path` 만으로 만들고, 난수 값은 아래 §5 의 손 계산).

## 2. v2 와 달라진 점

### 2.1 slot (`isaac_slot_v3.py`)

1. **루트 안 판정을 경로마다 한다 (17c §2.2).** v2 는 로그 전체 문자열에 `<루트>/isaaclab/usd_<키>` 가 한 번이라도 있는지만 봤다. v3 는 로그에서 `IsaacLab/usd_<날짜>_<시각>_<값>` 을 찾고, 같은 줄에서 그 앞의 경로를 가장 가까운 구분 문자 (공백 · 따옴표 · `@` · `<>` · `|` · 괄호 · `,;=*?` · 드라이브 글자가 아닌 `:`) 까지 붙여 절대 경로로 만든다. 그다음 `normpath` · `normcase` · 구분자 `/` 로 정규화해 정확히 `<루트>/isaaclab/usd_<키>` 와 같아야 루트 안이다. 상대 경로처럼 풀 수 없는 것은 `unresolved:` 로 남기고 밖으로 센다. 드라이브 없는 `/tmp/...` (18:51 실제 형태) 는 slot 프로세스의 현재 드라이브로 푼다.
2. **장면 줄에서 바로 끝낸다 (17c §2.2).** 잠금을 풀기 직전 판정에서 루트 밖 (94) · assigned 미연결 (91) · 충돌 (96) · registry 오류 (90) · 변환 기대 위반 (89) 이 있으면 자식을 그 자리에서 끝낸다. 잠금을 푼 뒤에도 자식이 끝날 때까지 2초마다 로그의 새 바이트만 읽어, 새 폴더가 루트 밖이거나 assigned 에 없으면 끝낸다. assigned.jsonl · isolate_state.json 이 바뀌면 다시 읽어 실행기의 거절 · 차단 기록도 본다. 자식이 끝난 뒤 로그 전체로 최종 재대조는 v2 대로 한다.
3. **assigned.jsonl 과 로그를 잇는다.** 로그의 폴더가 `<usd_root>/assigned.jsonl` 에 없으면 91. assigned 가 비었는데 변환 흔적 (로그 폴더 또는 importer 로그 줄 `[isaacsim.asset.importer.*]` · `[omni.kit.asset_converter]`) 이 있으면 91. assigned 안의 폴더가 루트 밖이면 94.
4. **registry (17c §5).** read · 충돌 확인 · merge · write 를 `<registry>.lock` 잠금 안에서 하고 (장면 줄 판정과 최종 판정 모두), `<registry>.<pid>.<uuid>.tmp` 로 쓴 뒤 `os.replace` 한다. 키는 정규화한 절대 폴더 경로다. 서로 다른 절대 루트의 같은 basename 은 충돌이 아니다. v2 가 남긴 basename 키는 그 값 (로그 경로) 의 로그를 열어 절대 경로로 다시 대조한다. registry 를 읽을 수 없거나 JSON 이 아니면 덮어쓰지 않고 90.
5. **로그 스캔.** `--scan_dirs` 마다 `*.log` · `*.log.prev.*` · `attempts/*.log*` · `attempts/*/*.log*` (unseen driver 의 `attempts/<tag>.<시각>/`) · `_attempts/*.log*` · `_attempts/*/*.log*` (night 셸 배치). 먼저 내 폴더 basename 이 들어 있는 파일만 열어 경로를 뽑는다.
6. **예상 변환 개수 (17d §2.6).** `--expect_conversions 0|1`, 기본 1 (v2 의 「폴더 정확히 하나」). 같은 값을 자식 환경 `FOOTHOLD_EXPECT_CONVERSIONS` 로 넘겨 실행기가 쓰기 전에 막게 한다. 0 이면 장면 줄만으로 잠금을 풀고 폴더 0개가 정상이지만, 변환 시도 흔적 (assigned.jsonl 의 어떤 줄 · 로그 폴더 · importer 줄 · isolate_state.json 의 blocked) 이 하나라도 있으면 89 다. 「폴더 없어도 통과」 로 완화한 것이 아니다. 1 이면 실행기가 둘째 변환을 거절한 줄이 있으면 89, 그 밖은 v2 처럼 폴더 정확히 하나 (95). 어느 값이든 실행기가 막은 일이 있으면 89.
7. **관문 내부 오류.** 자식을 띄운 뒤 관문 코드가 예외로 멈추면 자식을 끝내고 `slot_error` 를 적은 뒤 90. v2 는 이 경우 관문만 죽고 자식이 남을 수 있었다.
8. **기록.** v2 칸을 모두 두되 `usd_final` · `usd_at_release` · `usd_outside_root` · `conflicts` 키는 이제 절대 경로다. v2 식 basename 은 `usd_final_keys`. 새 칸: `expect_conversions` · `usd_unassigned` · `assigned` · `assigned_outside_root` · `convert_hint` · `hint_without_assigned` · `conversion_attempts` · `unexpected_refused` · `launcher_blocked` · `expect_violation` · `killed` (`scene_line` 또는 `after_release`) · `registry_error` · `scan_unreadable` · `legacy_registry_missing_logs` · `isolate_state` · `check_at_release`. 지금 기록을 읽는 검증기 넷 (`branch/validate_branch.py` · `unseen_driver_cmdr.py` · `rand_scenes/rand_lib.py` · `ce12/validate_dump.py`) 은 `usd_final` 의 개수 · `usd_outside_root` 비었음 · `conflicts` 비었음만 보므로 뜻이 같다. 다른 소비자는 미확인.

### 2.2 종료 코드

v2 와 같은 뜻을 유지하고 셋을 더했다. 여럿에 해당하면 이 순서로 앞의 것.

| 코드 | 뜻 | v2 와 |
|---|---|---|
| 98 | 띄우지 않음 (멈춤 파일 · 마감) | 같음 |
| 97 | 변환 상한 안에 장면 줄 없음 | 같음 |
| 94 | 루트 밖 또는 풀 수 없는 USD 폴더 · assigned 안의 루트 밖 폴더. 자식 종료 코드와 상관없이 | 뜻 같음 · v2 는 자식 0 일 때만 · 우선순위가 96 · 95 보다 앞으로 |
| 89 | (새) 변환 시도가 예상 개수를 넘음 · 또는 실행기가 무언가를 막음 (17d §2.6) | 새 코드 |
| 91 | (새) assigned 와 로그가 이어지지 않음 | 새 코드 |
| 96 | 다른 실행과 같은 절대 폴더 (registry · 로그 스캔) | 키가 basename 에서 절대 경로로 |
| 90 | (새) 관문이 판정을 끝내지 못함 (registry 갱신 실패 · 관문 내부 오류) | 새 코드 |
| 95 | 자식 0 인데 USD 폴더 수가 예상 (0 또는 1) 과 다름 | 예상 0 일 때 0개가 정상 |
| 그 밖 | 자식 종료 코드 | 같음 |

90 · 91 · 89 는 `_eval` 안에서 다른 뜻으로 쓰는 slot 코드가 없음을 확인하고 골랐다 (`ce12/run_dump.py` 는 자기 코드로 92 · 93 을 쓴다). unseen driver 는 0 · 98 이 아닌 코드를 모두 재시도로, night 셸은 0 이 아니면 멈춤으로 다루므로 새 코드도 실패로 처리된다.

### 2.3 실행기 (`usd_isolate_run_v3.py`)

1. **cfg 를 바꾸지 않는다 (17c §3).** v2 는 `cfg.usd_dir` 를 영구로 바꿔, 같은 cfg 로 변환기를 두 번 만들면 두 번째가 명시 경로 재사용이 되고 randrange 가 한 번 줄었다. v3 는 `AssetConverterBase` 에 데이터 descriptor `_usd_dir` 를 얹는다. 원래 `__init__` 이 기본 분기에서 `.../IsaacLab/usd_<날짜>_<시각>_<값>` 을 대입하는 순간 같은 이름으로 `<루트>/IsaacLab/usd_<날짜>_<시각>_<값>` 로 바꾸고, 폴더를 만들기 전에 assigned.jsonl 에 적는다. randrange 는 원래 코드가 원래 자리 (`cfg.validate` · asset 검사 뒤) 에서 변환마다 한 번씩 부른다. `config.yaml` 에 적히는 `usd_dir` 도 원래처럼 None 이다. 기본 분기 값이 그 모양이 아니면 (판 변경) 추측하지 않고 예외로 멈춘다.
2. **명시 `cfg.usd_dir` 정책.** 루트 안이면 그대로 쓰고 `kind explicit_inside` 로 적는다. 루트 밖이면 `kind explicit_outside_refused` 로 적고 예외로 멈춘다. 허용 목록은 두지 않았다. 미리 변환한 USD 를 읽기 전용 입력으로 쓰려면 변환기를 거치지 말고 `UsdFileCfg` 처럼 USD 를 직접 읽게 한다 (CE v2 장면이 이 경우다, 17d §2.6). 현재 Go2 경로는 `usd_dir=None` 이므로 이 정책의 영향을 받지 않는다 (실제 assigned 14건 모두 loader 할당, 17c §1).
3. **감싸기 전 변환 차단 (17c §3 비표준 loader).** 감사 hook 이 모든 `os.mkdir` 사건에서 (a) 호출 스택에 `isaaclab/sim/converters/asset_converter_base.py` 의 `__init__` 이 있는데 바로 위 호출자가 이 실행기의 감싼 `__init__` 이 아니면, (b) 또는 만들려는 폴더가 `IsaacLab/usd_<날짜>_<시각>_<값>` 인데 루트 밖이면, 그 mkdir 을 `UsdIsolationError` 로 막는다. 기반 `__init__` 의 첫 쓰기는 `os.makedirs` 이고, makedirs 는 폴더가 이미 있어도 마지막 `mkdir` 을 부르므로 공용 폴더에 아무것도 만들기 전에 멈춘다. 감사 hook 에서 예외를 내면 `os.mkdir` 이 취소되는 것은 이 Python 3.11.15 에서 따로 확인했다. v2 의 늦은 감싸기 (`audit:<사건>`) 도 남겨, 첫 변환은 막고 그 뒤 변환은 감싼다. 같은 모듈이 다시 올라와 새 클래스가 생겨도 loader 가 그 클래스를 감싼다.
4. **예상 변환 개수 (17d §2.6).** `FOOTHOLD_EXPECT_CONVERSIONS=0|1|any` (없으면 any, v2 와 같음 · 다른 값이면 시작하지 않고 2). 감싼 `__init__` 에 들어오는 순간 시도 수를 세어, 0 이면 첫 번째를, 1 이면 두 번째를 random · 폴더 생성 · 변환 전에 예외로 막고 assigned.jsonl 에 `kind refused_unexpected_conversion` (usd_dir null · n) 줄을 남긴다.
5. **지형 cache.** `terrain_generator.py:364~397` 의 `cache_dir/<hash>/mesh.obj · origin.csv · cfg.yaml` 은 **가로채지 않는다.** `TerrainGenerator` 가 `use_cache=True` 로 만들어지면 isolate_state.json 의 `warnings` 와 로그 줄 `[USD-ISOLATE] WARNING ...` 에 cache_dir · 루트 안 여부 · seed 를 남길 뿐이다 (실행은 계속).
6. **재진입 표식을 스레드별로.** v2 의 전역 `busy` 는 한 스레드가 hook 안에 있을 때 다른 스레드의 사건을 건너뛸 수 있었다.

### 2.4 night N2 주입 (`branch/test_night_1043_v3b.py`)

원본 `test_night_1043_v3.py` 는 고치지 않았다. v3b 는 같은 칸에 N2 주입만 바꿨다. `mv` 를 BASH_ENV 로 읽히는 셸 함수로 정의하고, 함수가 불릴 때마다 표식 줄을 쓴다. N2 는 그 표식 (옮기려던 경로 포함) · 「옮기지 못함」 문구 · rc 4 · slot 호출 0 · 이전 시도가 제자리를 모두 요구한다. N2b 는 「성공했다고 답하지만 옮기지 않는 mv」 로 옮긴 뒤 확인 줄을 시험한다. N0 은 그 bash 에서 BASH_ENV 함수가 앞선다는 전제를 잰다.

이 기계에서 잰 사실: PATH 앞에 둔 stub 은 `C:/Program Files/Git/usr/bin/bash.EXE` (Python `shutil.which("bash")` 가 고른 것) 에서는 stub 으로, `C:/Program Files/Git/bin/bash.exe` (감싸개) 에서는 `/usr/bin/mv` 로 풀린다. 즉 원본 N2 의 결과는 어느 bash 가 잡히느냐에 달렸고, ASTRA 의 7/8 과 lead 의 8/8 이 둘 다 나올 수 있다. v3b 는 찾은 Git Bash 둘 모두에서 N0 · N2 · N2b 를 돌린다.

## 3. ASTRA 반례별 처리

「v2 결과」 는 이번에 v3 시험을 v2 원본 (읽기만 · 임시 폴더 실행) 에 걸어 잰 값이다.

| 반례 | v2 결과 | v3 결과 | 시험 |
|---|---|---|---|
| 17c §2.2 같은 basename 의 루트 안 · 밖 혼합 경로 | rc 0 · outside [] · 폴더 1개로 합쳐짐 | 94 · 폴더 2개 · 밖 경로 기록 · 장면 줄에서 끝냄 | A1 |
| 17c §2.2 장면 줄 뒤 밖 경로 즉시 종료 | 94 이지만 30초 자식이 끝까지 돈 뒤 | 장면 줄에서 끝냄 (15초 안) | A2 · A3 |
| 잠금 푼 뒤 늦게 나온 밖 경로 | 95 · 30초 다 돎 | watch 가 끝냄 · 94 | A4 |
| 17c §5 registry 손실 순서 (A 읽음 · B 씀 · A 씀) | (v2 에 함수 없음 · 무잠금 쓰기) | B 가 A 의 잠금을 기다리고 두 기록 모두 남음 | R1 |
| 17c §5 공통 `.tmp` 이름 | (v2 는 공통 이름) | 고유 이름 · 남의 `.tmp` 를 건드리지 않음 | R3 |
| 17c §5 다른 절대 루트의 같은 basename | 둘째가 96 | 둘 다 0 · 절대 경로 키 둘 | T3a |
| 17c §5 `attempts/<tag>.<시각>/` 하위 로그 | 0 (못 읽음) | 96 | T3d · T3e |
| 17c §3 같은 cfg 두 번 (seed 7) | 경로 둘 다 `_5305` · 다음 random 0.9478653606090632 | `_5305` · `_2471` 두 경로 · 0.3948234964231735 · cfg.usd_dir None 유지 | U10 · U10b |
| 17c §3 asset 검사 실패 경로의 random 소비 | 0.9478653606090632 (미리 뽑음) | 0.32383276483316237 (원래와 같음) | U12 |
| 17c §3 명시 외부 usd_dir | 그대로 사용 · assigned 없음 | 기록 후 예외 (일반 폴더 · 기본 모양 폴더 둘 다) | U13 |
| 17c §3 비표준 loader 즉시 변환 (U9 에서 colorsys 줄 제거) | 가짜 /tmp 에 씀 | 첫 mkdir 에서 예외 · 가짜 /tmp 아무것도 안 생김 | U15 |
| 다른 이름으로 다시 올린 변환기 모듈 | 가짜 /tmp 에 씀 | 감싸지지 않은 `__init__` 을 쓰기 전에 막음 | U18 |
| 17c §2.1 N2 주입의 환경 의존 | 원본 N2 는 bash 에 따라 갈림 (위 §2.4) | BASH_ENV 함수 · 표식 확인 · 두 bash 모두 통과 | N0 · N2 · N2b |
| 17d §2.6 예상 0 인데 뜻밖의 변환 | (v2 에 개념 없음 · ce12 는 사후 93) | 변환기 입구에서 예외 · 가짜 /tmp · `<루트>/IsaacLab` 모두 안 생김 · random 안 뽑음 · slot 89 | U23 · E3 |
| 17d §2.6 예상 1 인데 두 번째 변환 | (v2 에 개념 없음 · 재지 않음) | 둘째를 입구에서 거절 · 폴더 하나 · slot 89 | U24 · E5 |
| 17d §2.6 예상 0 · 변환 없음 | (v2 slot 은 폴더를 기다리며 자식이 끝날 때까지 잠금을 쥐고 95 · 코드 읽기로만 확인) | 장면 줄에서 바로 풀고 0 | E1 · U25 |

## 4. 시험 · 변이 결과

실행: `CUDA_VISIBLE_DEVICES=-1 PYTHONDONTWRITEBYTECODE=1 C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B <파일>` (Git Bash). Isaac · GPU 는 띄우지 않았다.

| 대상 | 결과 | 걸린 시간 |
|---|---|---|
| `test_isaac_slot_v3.py` | 43/43 통과 | 약 73초 |
| `mutate_isaac_slot_v3.py` | 36개 ALL CAUGHT | 약 9분 |
| `test_usd_isolate_v3.py` | 27/27 통과 | 약 6초 |
| `mutate_usd_isolate_v3.py` | 19개 ALL CAUGHT | 약 7초 |
| `branch/test_night_1043_v3b.py` | 10/10 통과 (N0 · N2 · N2b 는 Git Bash 둘에서) | 약 6초 |
| `branch/mutate_night_1043_v3b.py` | 5개 ALL CAUGHT | 약 10초 |

변이 시험은 변이마다 이름 붙은 칸만 돌리고 (`SLOT_V3_ONLY` · `USD_V3_ONLY` · `NIGHT_V3B_ONLY`), 그 칸이 전부 FAIL 일 때만 CAUGHT 로 센다 (시험이 예외로 죽어 FAIL 줄이 없으면 MISSED). 첫 회차에서 놓친 변이로 시험 쪽 결함 넷을 찾아 고쳤다: 빈 목록 첨자로 시험이 죽음 (I2 · I7 · I14) · registry 파일이 없을 때 읽다 죽음 (S11) · 기본 모양이 아닌 외부 경로만 쓴 U13 (설정자 쪽 관문이 대신 막아 정책 관문 제거를 못 봄 · 막은 까닭 문구까지 보게 하고 기본 모양 경로를 더함) · finder 가 대신 감싸 버린 U22 (Kit 식 앞 finder 뒤에서 다시 올리게 바꿈).

### 4.1 실제 기록 읽기 전용 재연

`out_uncr` 평가 24건 · `out_smoke/branch` 2건의 `.slot.json` 마다, 그 로그에 v3 경로 추출을 걸고 그 `usd_root` 의 assigned.jsonl 과 이었다 (registry · 스캔 · 쓰기 없음). 26건 모두 v3 가 뽑은 폴더의 basename 이 v2 기록의 `usd_final` 과 같았다. 18:51 smoke (v2 94) 만 루트 밖 1개였고, 나머지 25건은 폴더 1개 · 루트 안 · assigned 연결이었다. 지금 도는 학습 로그 (`out_branch/cmdr_s1043_off_u4000.log`, 20:15 에 13.2 MB) 는 추출 0.31초 · 폴더 1개 · 루트 안 · assigned 연결이었다. 학습 완료 뒤의 전체 로그 크기와 시간은 미측정.

## 5. 손으로 정한 기대값

- seed 7 의 `random.randrange(10000)` 은 5305, 2471 순서다. 뽑지 않고 `random()` 0.32383276483316237, 한 번 뒤 0.9478653606090632, 두 번 뒤 0.3948234964231735 (마지막은 17c 의 값과 같다). 시험과 무관한 표준 라이브러리 한 줄로 잰 값이다.
- 경로 기대값은 `os.path.normcase(os.path.abspath(...))` 에 `\` 를 `/` 로 바꾼 것.

## 6. 남은 한계

1. **로그 경로 추출.** 경로 안에 공백 · `@` · 따옴표 · 괄호 · `,;=` 가 있으면 잘려서 밖 (94) 또는 `unresolved` 로 판정된다 (막는 쪽으로 틀린다). 지금 루트 (`C:/isaac/ext/go2_rl_robotlab/_eval/...`) 에는 그런 글자가 없다. 드라이브 없는 경로는 slot 프로세스의 현재 드라이브로 푼다.
2. **잠금 뒤 감시는 사후다.** 2초 간격으로 새 줄을 읽고 끝내므로, 밖 경로가 로그에 찍힌 뒤 최대 몇 초는 자식이 계속 돈다. 쓰기 자체를 막는 것은 실행기의 mkdir · 입구 차단뿐이다.
3. **registry 를 v2 와 섞을 때.** v3 끼리는 `<registry>.lock` 으로 손실이 없지만, v2 참가자는 잠금 없이 공통 `.tmp` 로 쓰므로 같은 registry 를 쓰면 v2 의 마지막 쓰기가 v3 기록을 지울 수 있다. 기본 `--registry` 는 CLI 를 같게 하려고 v2 와 같은 파일로 두었다. 모든 호출자를 한 번에 v3 로 바꾸거나, 섞이는 동안은 v3 에 다른 registry 경로를 넘기고 `--scan_dirs` 로 서로의 로그를 보게 할 것. registry 는 보조이고, 1차 보호는 실행마다 다른 절대 루트다 (17c §5).
4. **스캔에서 읽지 못한 파일은 실패로 치지 않는다** (`scan_unreadable` 에 기록만). v2 basename 항목의 로그가 없어졌으면 `legacy_registry_missing_logs` 에 기록만.
5. **importer 흔적** 은 `[isaacsim.asset.importer.*]` · `[omni.kit.asset_converter]` 두 채널만 본다. 다른 변환은 로그 폴더나 assigned 줄로만 보인다. 예상 0 실행에서 importer 확장이 변환과 무관한 줄을 같은 채널로 찍으면 89 로 오판할 수 있다 (막는 쪽).
6. **실행기가 지키는 범위.** `AssetConverterBase` 를 거치는 변환 (URDF · MJCF · Mesh 변환기는 base 초기화를 호출함을 원본에서 확인) 과, 루트 밖에 `IsaacLab/usd_<날짜>_<시각>_<값>` 폴더를 새로 만드는 Python `os.mkdir` 이다. Kit 의 C++ 변환 · base 를 거치지 않는 변환기 · 이미 있는 공용 폴더에 mkdir 없이 파일만 여는 코드 · 다른 이름 규칙의 공용 폴더는 막지 못한다. 기반 `__init__` 은 파일 경로 끝 `isaaclab/sim/converters/asset_converter_base.py` 와 이름 `__init__` 으로 알아보므로, 설치 배치가 다르거나 컴파일된 판이면 미확인이다. U21 (기본 폴더가 descriptor 를 거치지 않고 정해진 경우) 은 변환이 끝난 뒤에야 멈춘다 (사후).
7. **CPython 내부 의존.** `importlib._bootstrap_external._LoaderBasics.exec_module` 감싸기 (v2 와 같음) · 감사 사건 `os.mkdir` 에서 예외를 내면 mkdir 이 취소된다는 동작 (Python 3.11.15 CPU 에서 확인 · Kit 안에서는 미확인).
8. **예상 변환 개수의 셈.** 감싼 `__init__` 에 들어온 횟수다. 명시 폴더의 lazy 재사용 (변환 생략) 도 한 번으로 센다. 감싸지 못한 호출은 셈에 들지 않고 §2.3 의 3번 (mkdir 차단) 으로 멈춘다. ce12 기록기 (`ce12/run_dump.py`) 는 여전히 v2 흐름 (slot 없이 띄우고 사후 93) 이다. 17d §2.6 을 실제로 적용하려면 그 실행을 `isaac_slot_v3.py --expect_conversions 0` 과 `usd_isolate_run_v3.py` 로 띄우게 바꿔야 하며, 이 판에서는 기존 파일을 고치지 않아 하지 않았다.
9. **난수 불변성** 은 Python `random` 에 대해 「단일 변환 · 같은 cfg 두 번 · 서로 다른 cfg 둘 · asset 없음」 네 경우만 확인했다. NumPy · Torch · 물리 난수와 전체 rollout 동일성은 미확인.
10. **성능.** 가짜 변환기 CPU 측정 (세 번): 변환 1회 1.08 ~ 1.33 ms → 1.79 ~ 2.25 ms, `open()` 1회 56.7 ~ 61.0 µs → 61.7 ~ 65.5 µs (감사 hook 이 모든 사건에 붙음). 시간 INFO 줄의 「단일 · 같은 cfg 두 번 · 서로 다른 cfg」 도 가짜 변환기 값이다. 실제 Isaac 학습의 iteration 처리량 차이는 미측정.
11. **스레드별 재진입 표식** 은 동시 스레드 시험을 하지 않았다.
12. **지형 cache** 는 경고뿐이다. 17c 가 본 q_eval_cmdr 의 `use_cache=false` 외에, 학습 설정의 use_cache 값은 이 판에서 확인하지 않았다 (미확인).

## 7. 실제 Isaac 에서 확인해야 할 것

1. Kit 안에서 loader 감싸기가 걸리고 (`patched_by loader`), 실제 `UrdfConverter` 가 descriptor 를 거쳐 `<루트>/IsaacLab/usd_*` 에 `go2.usd` 와 `configuration/go2_{base,physics,robot,sensor}.usd` 를 만드는지. `config.yaml` 의 `usd_dir` 가 None 인지. assigned 한 줄이 로그의 폴더와 같은지.
2. 감사 hook 의 예외가 Kit 안에서도 `os.mkdir` 을 취소하고 삼켜지지 않는지 (비표준 적재를 일부러 만든 짧은 실행 · 예상 0 실행).
3. 실제 학습 · 평가에서 호출 스택 검사가 오판 (base `__init__` 이 다른 길로 불림) 하지 않는지. blocked 가 비어야 한다.
4. CE v2 장면 (`UsdFileCfg` · `GroundPlaneCfg`) 을 `--expect_conversions 0` 으로 띄우면 변환기 진입 0 · assigned 없음 · blocked 없음 · 장면 줄에서 바로 잠금 해제 · rc 0 인지.
5. 같은 조건 A/B 로 학습 iteration 처리량과 평가 시간 차이.
6. 학습이 끝난 뒤 큰 로그 전체에 대한 최종 재대조 시간.
7. 지형을 `use_cache=True` 로 쓰는 설정이 있는지와 그때의 경고 줄.

## 8. 바꿔 쓸 때

지금 기동 코드는 v2 를 부른다. v3 로 바꾸는 것은 별도 결정이다. 바꿀 때는 `isaac_slot.py` → `isaac_slot_v3.py`, `usd_isolate_run.py` → `usd_isolate_run_v3.py` 로 함께 바꾸고 (v3 slot 은 v2 실행기와도 동작하지만 사전 차단 · 예상 개수는 v3 실행기에만 있다), 변환이 없어야 하는 실행에는 `--expect_conversions 0` 을 준다. registry 섞임은 §6.3 을 볼 것.

# CE12 v2 A1 서명 경로 표기 후보 수정 보고서
> 분류: A/평가
> 작성: Codex Worker · 2026-10-14
> 근거: 실제 v2 08:52 기록 사본, CE12 코드와 r2 도장 사본, CPU 대조·회귀·변이 로그
> 요지: 기록기의 env.yaml 경로를 파싱 직후 정규화하는 한 줄 후보가 A1 경로 불일치를 없앤다
> 상태: 후보 및 CPU 시험 완료 · ASTRA 검증과 lead 채택 전 · GPU 재기록 미확인
> 판: B4 후보 1

## 격리와 대상

첫 쓰기 전 경로 단언 출력은 `B4_ISOLATION_OK C:\Users\AI-WS01\.claude\jobs\09bbf294\tmp\codexB4`였다. 후보·fixture·격리 시험·로그·변이·보고서·SHA256SUMS 경로를 모두 이 루트 아래로 확인했다. 이후 시험 진입점의 `B4_TEST_PATHS_OK`와 기존 시험의 `ISOLATION_PATHS`도 출력했다. `_eval/ce12/` 원본 55개 파일을 `ce12_candidate/`에 통째 복사하고, 수정 전 55/55 해시 일치를 확인했다. 실제 v2 `signature.json`, `meta.json`, `native.npz`, 모델 `foothold-v2.env.yaml`은 `fixture_real/`에 복사했다. 시험에서 파일 내용을 읽는 함수는 B4 복사본으로 연결했고 원본 실자료를 쓰기 인자로 넘기지 않았다. r2 도장과 참조 파일 17개도 B4 `fixture_r2/`에 복사했다. 원본 도장과 서명은 수정하지 않았다.

해석기와 적재 파일을 시험 시작에 출력하고 예상 절대경로·해시가 다르면 `환경 불일치`로 멈춘다. 새 경로 시험은 `isaac311-moects`와 `isaac311`에서 각각 실행해 **4/4, rc 0**이었다. 두 환경의 `python.exe` SHA256은 모두 `0562f573871cb16a2fb8de16e3d486e3dfd74bb83c7e87db265561917d05ad1a`이나 RSL-RL runner는 서로 다르다. moects의 `source/rsl_rl/.../on_policy_runner.py`는 `bc79dd28613c7f8cc587fcbdf7274ade148cbec15ac2df22b4fecd5827f83782`, isaac311의 설치본은 `6ffaee7e154a49ae55eebf53a7b1549f0461a1742d92dd34af5bb4b785d19cf2`다. 적재된 B4 `adapters.py`는 `ce12_candidate/adapters.py`, SHA256 `39c1a2930a5992a65229529c49d8e5c278b202c12c534461f24c7ec26dea00c6`이었다.

## D1 · 실제 원인과 경로 전수

`v2_run_17n/v2_run2.txt`의 기록 실행은 rc 0, `run.json.output_problem`은 빈 문자열이었다. `v2_approve.txt`는 수집 `COLLECTED` 뒤 A1만 `FAIL ... 다른 칸 ['signature_sha256', 'source']`로 기록하고 `REJECTED`로 끝났다. 복사한 실제 `signature.json`의 YAML 내용 SHA256은 `a5ef31d626f8cabe850de37bae0aa26782e14e9db3ba61d678dd1210105323e7`이다. 경로 문자열은 `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab\models\foothold-v2.env.yaml`, 서명 SHA256은 `2f1b0c2b011442c790749f2d21121df3ebbb9e6e1389d2c79fc5d64702814805`다. 승인기가 현재 adapter로 다시 만든 서명은 전부 슬래시인 경로와 SHA256 `dfc1410feaa60af791abca5d9118f6cb90bbfeb03e526281dc03304ebc748996`이다.

경로 생성은 `dump_native_v2.py:49`의 슬래시형 `LAB`와 61행 `os.path.join(LAB, "models", "foothold-v2.env.yaml")`에서 섞인다. 328행이 그 `args.env_yaml`을 `V2Adapter.from_env_yaml`에 전달하고 `adapters.py:747`이 `source.path`에 입력 문자열을 그대로 넣는다. 반면 `adapters.py:44`와 `validate_dump.py:77`의 기본 `V2_ENV_YAML`은 슬래시 상수이며, `validate_dump.py:263~269`의 `_sig_now`는 그 기본값으로 서명을 만든다. `validate_dump.py:330~337`의 A1은 JSON 전체를 정확히 비교한다. `adapters.py:337~338`의 서명 해시도 경로 문자열을 포함한 JSON에서 계산한다. 따라서 내용이 같은 파일인데도 두 칸이 다르다.

판별식은 **signature 또는 meta 안의 경로 문자열 가운데 `_sig_now`가 다시 만들거나 승인기가 직접 비교하는 값**이다. 복사한 실제 `meta.json`과 `signature.json`의 절대경로 문자열을 전수 열거했다.

| 값 | 실제 기록 표기 | 승인 대조 및 영향 |
|---|---|---|
| `signature.source.foothold-v2.env.yaml.path` | 혼합 구분자 | `_sig_now`의 슬래시 경로와 A1에서 정확 비교. 유일한 직접 경로 불일치 |
| `signature.signature_sha256` | `2f1b0c2b…` | 경로 문자열을 포함해 계산하므로 A1의 두 번째 불일치 |
| `meta.args.env_yaml`, `meta.env_yaml` | 같은 혼합 구분자 | A4는 `meta.env_yaml`을 `same_path`로 비교해 통과. A6은 비교 보고서의 설정 경로와 해시를 `normcase(abspath)`로 대조. `meta.args.env_yaml` 자체의 정확 문자열 비교는 없음 |
| `meta.args.checkpoint` | 슬래시 | 기록기 원 인자. `meta.checkpoint`와 별개이며 A1의 입력이 아님 |
| `meta.checkpoint` | 역슬래시 | M1이 요청 checkpoint와 `same_path` 및 내용 SHA256으로 확인. A1과 무관 |
| `meta.args.outdir` | 슬래시 | A4가 `same_path`로 출력 루트와 비교 |
| `meta.lab_files_sha256` | 세 파일 이름을 키로 한 내용 해시 | 절대경로 문자열은 없고 다시 만든 서명 경로가 아님 |

`same_path`는 `validate_dump.py:89~90`의 `normcase(abspath)` 비교다. `compare_native.py:132~140`은 설정 경로를 절대 슬래시로 기록하고 내용 해시를 싣는다. `run.json`의 checkpoint·명령 경로는 실행기 출처 검사 대상이나 기록기 `signature.source`를 다시 만드는 값은 아니다. 이 범위에서 A1과 같은 **다른 정확 문자열 경로 불일치는 찾지 못했다**.

## D2 · 후보 비교와 r2 영향

| 후보 | 코드 조각과 변경 파일 | CTS r2 `--check_approval`의 추가 영향 |
|---|---|---|
| A · 기록기 인자 정규화 | `dump_native_v2.py`의 `args = parser.parse_args()` 바로 뒤 `args.env_yaml = os.path.abspath(args.env_yaml).replace("\\", "/")` 한 줄 | 도장의 코드 파일 목록에 v2 기록기가 없음. **추가 변경 0개** |
| B · adapter 서명 경로 정규화 | `adapters.py:747`의 `"path": os.path.abspath(path).replace("\\", "/")` | 도장의 `code_adapters.py` 해시가 달라져 **추가 변경 1개** |

B4의 수정하지 않은 r2 도장 사본과 도장이 가리키는 파일 사본을 실제 `validate_dump.main(..., --check_approval)` 분기에 넣었다. 도장 안의 원래 경로 문자열은 유지하고 읽기만 B4 복사본으로 매핑했다 (`check_r2_candidates.py`, `logs/r2_candidates.log`). 현재 코드의 기준 결과부터 rc 1, `APPROVAL INVALID`이며 기존 차이 `code_compare_native.py`, `code_validate_dump.py`, `code_run_dump.py` 3개가 있다. 후보 A도 **동일한 3개**, 후보 B는 거기에 `code_adapters.py`가 더해진 **4개**였다. 그러므로 후보 A가 r2를 `STILL VALID`로 만든다는 뜻은 아니다. 이미 있는 세 코드 차이를 숨기지 않고 추가 영향만 비교했다. 도장의 `code_dump_native_cts.py`는 A에서 달라지지 않는다. 작은 후보 A만 `ce12_candidate/`에 구현했고 B는 `mutants/candidate_B_adapter_path.py` 코드 조각으로 보관했다.

후보의 기존 파일 변경은 `dump_native_v2.py` 한 줄이다. 원본 SHA256 `251220254fc70b7b0adf1bbd2dd85d998c0218a38595c9c598ef3d626015be82`, 후보 SHA256 `a3da62b8185f4a28aa8623997094c245f603f8cdec7820efaa57ba194ff97c16`. 신규 시험 `test_v2_signature_path.py` SHA256은 `f4c7ea4c7dec098d0ddefe9262e30faf02e47200ca6c8dacc0e9a8786afba5f8`이다. 후보 전체의 `ce12_candidate/SHA256SUMS.txt`는 **56개 항목 전부 재해시 일치**, 파일 자체 SHA256 `2bcaab236e55d891df621c8e52127705c1ef502ade5506d171e1ddcce895b705`다.

## D3 · CPU 시험과 변이

모든 지정 실행은 절대 해석기, `CUDA_VISIBLE_DEVICES=-1`, `PYTHONDONTWRITEBYTECODE=1`, `-B`를 사용했다. 기존 시험은 `eval/`의 격리 사본에서 가짜 자식과 B4 안의 원자료 사본을 사용했고 임시 결과는 삭제하지 않고 B4 `retained/`에 보관했다. `run_dump.py` 자체를 호출한 것은 기존 회귀 시험의 격리 fake child 경로뿐이며 운영 기록기는 호출하지 않았다.

새 시험은 기록기의 실제 `--env_yaml` 기본식과 파싱 후 대입식을 AST로 추출해 실제 `LAB`로 평가한다. YAML을 파싱하고 SHA256을 계산할 때에는 B4 복사본만 읽되, 서명에 남기는 경로 문자열은 실제 기록 당시의 문자열이다. 실제 `native.npz`의 관절 이름과 기록된 `signature.json`을 사용한다. 손으로 고정한 내용 SHA, 기록 서명 SHA, 승인기 서명 SHA와 경로를 확인한다.

| 검사 | 정상 기대와 반례 | 수정 전 | 최종 후보 |
|---|---|---|---|
| P1 | 실제 기본식의 혼합 경로가 승인기의 슬래시 서명과 같아져야 함 | FAIL | PASS |
| P2 | 실제 08:52 서명은 `source`, `signature_sha256`만 다르고 후보 서명은 승인기와 같아야 함 | FAIL | PASS |
| P3 | 슬래시·역슬래시·혼합 입력 모두 같은 서명과 같은 canonical path | FAIL | PASS |
| P4 | 같은 경로 문자열에서 YAML 내용만 바꾼 복사본은 서로 다른 SHA와 서명 | PASS | PASS |

첫 실행은 `logs/path_red.log` **1/4, rc 1**, 수정 뒤 `logs/path_final_moects.log`와 `path_final_isaac311.log`는 각각 **4/4, rc 0**이다. 정상판을 다시 통과시킨 뒤 지정 변이 세 개를 검사했다 (`logs/mutations_requested_final.log`). (a) 한 줄 되돌림은 `failed [P1,P2,P3] want [P1,P2,P3]`, (b) 기록기 정규화를 빼고 adapter `source.normalized_path`만 통일하며 `source.path`를 그대로 두면 같은 위치, (c) YAML 내용 해시 재계산을 고정값으로 바꾸면 `failed [P4] want [P4]`였다. 모두 rc 1, import·module·구문 오류·환경 불일치·예상 밖 traceback 0으로 **3/3 CAUGHT**다. 첫 (b) 변이는 지정한 `source`가 아니라 `args.checkpoint`에 값을 넣은 것이어서 `mutants/b_wrong_field.py`와 `logs/mutations_final2.log`에 남기되 지정 분모에서 제외했다. 지정 형태를 `mutants/b_source_wrong_field/`로 다시 만들고 정상판부터 재실행했다.

| 기존 지정 시험 | 예정 | 실행 | skip · hold | 종료 코드 |
|---|---:|---:|---:|---:|
| `test_adapters.py` · moects | 23 | 23 PASS | 0 · 0 | 0 |
| `test_run_dump.py` · moects | 139 | 139 PASS | 0 · 0 | 0 |
| `mutate_adapters.py` · moects | 24 | 24 CAUGHT | 0 · 0 | 0 |
| `mutate_run_dump.py` · moects | 65 | 65 CAUGHT | 0 · 0 | 0 |
| `mutate_17i.py` · moects | 11 | 11 CAUGHT | 0 · 0 | 0 |
| `test_v2_load_device.py` · isaac311 | 1 | 1 PASS | 0 · 0 | 0 |

기존 변이 로그에는 `MISSED`, `ImportError`, `ModuleNotFoundError`가 0개였다. `test_v2_load_device.py`는 지정된 isaac311에서 실제 runner 경로로 통과했다. 추가로 moects에서도 돌린 첫 시도는 **rc 1**, 그 환경의 다른 RSL-RL `OnPolicyRunner.load`가 시험용 러너 객체의 `alg_cfg`를 요구해 `AttributeError`였다 (`logs/test_v2_load_device_moects.log`). 이것을 지정된 1/1에 섞지 않는다. 새 경로 시험 P1~P4는 두 환경 모두 도는 것으로 실측했다.

첫 격리 단언을 Python `-c`로 호출할 때 PowerShell 인용으로 SyntaxError가 났다. **어떤 쓰기도 하기 전에** PowerShell 경로 단언으로 다시 실행해 `B4_ISOLATION_OK`를 얻었다. 한 소스 읽기 명령도 잘못된 작업 디렉터리 문자열로 실패했으며 올바른 경로에서 다시 읽었다. 이들은 시험 결함 검출이나 통과 분모가 아니다. 실제 기록의 A1 거절과 r2 기준의 3개 변경도 성공 숫자에 섞지 않았다.

## lead가 다시 돌릴 명령 · 미확인

아래는 **ASTRA 독립 판정 후 lead가 후보 한 줄을 운영 CE12에 채택하고, 보호 조건과 GPU 1 상태를 새로 확인한 경우**의 동일 조건 재기록 명령이다. 이 Worker는 실행하지 않았다. 이전 17n의 셀·reset·전환·checkpoint 조건을 유지하고 tag만 새로 만든다. `--deadline 0`은 마감 없음이므로 lead의 새 운영 마감으로 바꿔야 한다.

```powershell
$tag = 'v2_native_a1path_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$py = 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$runner = 'C:/isaac/ext/go2_rl_robotlab/_eval/ce12/run_dump.py'
$ckpt = 'C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.pt'
& $py $runner --which v2 --checkpoint $ckpt --tag $tag --gpu 1 --min_free_mib 4096 --deadline 0 --dry_run -- --cells stand,fwd03,yawL05 --envs_per_cell 4 --steps 60 --reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03
& $py $runner --which v2 --checkpoint $ckpt --tag $tag --gpu 1 --min_free_mib 4096 --deadline 0 -- --cells stand,fwd03,yawL05 --envs_per_cell 4 --steps 60 --reset_envs 1,6 --reset_step 30 --switch_env 0 --switch_step 40 --switch_cell fwd03
```

새 tag의 기록 성공, A1 전체 승인, compare 보고서와 다른 A 검사, GPU/Isaac 실제 동작은 **미확인**이다. 후보는 원본 `_eval/ce12/`에 반영되지 않았다. 최종 대조에서 원본 55개와 후보의 공통 파일은 `dump_native_v2.py`만 달랐고, 신규 시험과 SHA256SUMS는 B4 후보에만 있었다. **이 작업자가 `_eval` 안에 만든 파일 목록은 0개**다. `_eval/out*`, slot, branch, s2, handover, rand_scenes에 쓰지 않았고 파일 삭제·커밋·GPU·Isaac 실행도 하지 않았다.

## 이력

| 판 | 일시 | 내용 |
|---|---|---|
| B4 후보 1 | 2026-10-14 | v2 기록기 경로 한 줄 후보와 실제 서명·r2 영향·CPU 회귀 및 변이 |

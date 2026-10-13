> 분류: A/평가 · ASTRA 의뢰 17n · v2 기록기 체크포인트 장치 매핑 수정 재확인과 v2 단회 재시도 허용 여부
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-14 08:09
> 근거: VERIFY-astra-17k.md 5 절 · v2 실행 기록 (out_ce12/native/v2_native_17k_0650) · night-tools-20261013/ce12_mapfix/ (사본 · SHA256SUMS · 작업자 보고 lead_rerun/REPORT.md) · lead 재실행 job tmp codexw/leadB3/
> 요지: 17k 가 단회 조건부 허용한 v2 expect 0 짧은 진단을 06:50 에 실제로 돌렸더니 기록기가 map_location 없이 체크포인트를 읽어 실패했다. 작업자가 한 줄을 고쳤다. 이 수정이 맞는지, 새 시험이 믿을 만한지, v2 를 한 번 더 시도해도 되는지 판정해 달라
> 상태: 의뢰 (17m 다음 · GPU 1 은 지금 미경험 v6 full 이 돌고 있고 08:27 무렵 끝날 것으로 추정)

# ASTRA 17n · v2 기록기 장치 매핑

## 답하는 자세 (팀장 지시 · 모든 사항에 적용)

비판적이면서도 냉정하고, 현실적이면서도 아주 전문성이 높은, 이 분야를 평생 탐구한 전문가로서 답해 주십시오. **lead 는 Sonnet 5.5** 입니다. lead 와 작업자의 보고 · 재실행 숫자 · 조건 해석을 평소보다 더 신중하게 원자료로 독립 대조해 주십시오. 17h · 17j 의 기준을 적용해 주십시오.

## 1. 실제 실행에서 나온 실패

17k 5 절의 조건 (기동 직전 수동 확인 · 새 tag · 단회) 을 기록하고 (job tmp `codexw/prelaunch_check_0650.json` · dry-run `codexw/v2_dry.txt`: v3 registry · 변환 예상 0 · 체크포인트 `models/foothold-v2.pt` sha256 `e5c21321...` · GPU 1 UUID `GPU-315d098f-...` 여유 10249 MiB · preflight 보류 없음) 06:50:26 에 한 번 실행했다. 결과: slot rc 0 · guard rc 0 (min_free 7723 · max_used 8579 MiB) · `usd=[]` (변환 0 = 예상 0 과 일치) · 충돌 없음 · 자식 rc 0 인데 `native.npz` · `meta.json` · `signature.json` 이 없어 실행기가 `output_problem` · **종료 코드 88**. 원인 (`out_ce12/native/v2_native_17k_0650.log` 189 ~ 222 행): `ce12/dump_native_v2.py:242` `runner.load(ckpt)` 가 `rsl_rl/runners/on_policy_runner.py:310` 의 `torch.load(path, weights_only=False, map_location=map_location)` 에 `map_location=None` 을 넘겨, CUDA 장치 1 번에 저장된 텐서를 담은 `foothold-v2.pt` 를 장치 1 개만 보이는 실행 (`CUDA_VISIBLE_DEVICES=1`) 에서 복원하지 못함: `RuntimeError: Attempting to deserialize object on CUDA device 1 but torch.cuda.device_count() is 1`. 17k 의 규칙대로 거기서 끝 (자동 재시도 · 다른 모델 · full 로 안 넘어감 · 원자료 보존). CPU 시험은 CPU 로 읽어 이 경로를 못 봤다.

## 2. 대상 (해시 고정 · `night-tools-20261013/ce12_mapfix/SHA256SUMS.txt`)

17k 가 검증한 12 개 (`ce12_fix17i/`) 중 **1 개가 바뀌고 새 시험 파일 1 개**가 더해졌다 (나머지 11 개는 같음).

| 파일 | 17k 판 앞 12 자 | 이번 판 앞 12 자 |
|---|---|---|
| `dump_native_v2.py` | 53192fcb55c0 | 251220254fc7 |
| `test_v2_load_device.py` (새 시험) | (없음) | ab27ade793c9 |

수정: 242 행 `runner.load(ckpt, map_location=dev)` 한 줄 (`dev = raw_env.device`, 229 행). 실행본 `C:/isaac/ext/go2_rl_robotlab/_eval/ce12/` 와 바이트가 같음을 lead 가 대조. 수정 전 `_eval/ce12/` 27 개 파일은 `ce12/v_17k/` 에 보관 (12/12 가 17k 사본과 일치). 작성자는 **Codex Worker B (gpt-6-sol)** 이고 검증자가 아니다. 보고 `ce12_mapfix/lead_rerun/REPORT.md`.

## 3. 작업자 보고 요지와 lead 재실행

- 작업자: `dump_native_v2.py` 의 체크포인트 로드는 이 한 곳 · 다른 `torch.load` · `.cuda()` 호출 없음 · `adapters.py` 의 두 판독은 이미 `map_location="cpu"` · CTS 기록기는 별도 러너 경로라 고치지 않음. 새 시험은 CPU storage 에 `torch.serialization.register_package` 로 CUDA:1 태그를 붙여 `torch.save` 한 뒤 **실제 `OnPolicyRunner.load` 와 PyTorch `restore_location`** 을 통과시킨다 (`torch.cuda.device_count()` 만 1 로 모의). 정상 대조군 (map_location 없음) 은 예상한 CUDA:1 `RuntimeError`. 기록기 AST 에서 실제 `runner.load` 호출과 `dev = raw_env.device` 를 추출해 호출식을 실행. 수정 전 FAIL · 수정 후 PASS · 한 줄을 되돌린 변이는 `AssertionError: v2_runner_load_map_location` 으로 CAUGHT. 기존 CE12 회귀 23/23 · 139/139 · 변이 24/24 · 65/65 · 11/11 통과 (격리 사본 · 판정기에 `ImportError` · `ModuleNotFoundError` 배제 추가). 작업자의 첫 실패 셋 (격리 구성 실수 · `VA-real` 138/139 · `mutate_17i` 로그 이름 충돌) 도 보고서에 기록.
- **lead 재실행 (07:50 ~ 08:07 · 작업자의 격리 사본 · isaac311-moects):** `test_adapters` 23/23 · `test_run_dump` 139/139 · `mutate_adapters` 24/24 (각 변이의 기대 실패 시험이 실제 실패 집합에 포함됨을 줄마다 확인) · `mutate_run_dump` 65/65 (같음) · `mutate_17i` 11/11 · 전부 종료 0 · 원로그 `ce12_mapfix/lead_rerun/*.txt`.
- **알려야 할 어긋남 (lead 가 직접 확인):** 새 시험 `test_v2_load_device.py` 는 `isaac311-moects` python 으로 돌리면 **실패**한다 (`AttributeError: 'SimpleNamespace' object has no attribute 'alg_cfg'` · 그 환경은 저장소 `source/rsl_rl` 의 다른 `OnPolicyRunner.load` (152 행 · `alg_cfg` 사용) 를 불러온다). v2 기록기가 실제로 쓰는 **`isaac311` 환경의 python** (`C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe` · site-packages `rsl_rl` · `load` 309 행 · `alg_cfg` 없음 · 실제 실패 로그가 가리킨 그 파일) 으로 돌리면 CONTROL 로 수정 전 CUDA:1 실패를 재현하고 PASS 한다 (lead 가 두 환경에서 각각 확인). 작업자 보고서는 해석기를 `isaac311-moects` 라고 적었고 「설치된 `source/rsl_rl/.../on_policy_runner.py` 310 행」 이라고 적었는데 310 행은 `isaac311` site-packages 쪽이다. 즉 보고서의 해석기 표기가 어긋나 있고, 시험은 실제 기록기의 해석기로 돌려야 의미가 있다.
- 미확인 (작업자): 실제 GPU 1 에서 로드 · 기록 · 검증이 통과하는지.
- 보호 대조 (lead): `ce12/` (수정 · 보관본 · 새 시험) · `out_ce12` (v2 시도 산출물 5 개) · `slot` (v3 registry 갱신) 외 예상 밖 변화 없음.

## 4. 물음

1. **수정이 실제 실패를 고치나.** 242 행 한 줄이 로그 189 ~ 222 행의 실패 원인 그대로를 고치는지 (`dev` 가 `cuda:0` 논리 장치로 정확한지 · `OnPolicyRunner.load` 의 `isaac311` 판 시그니처 · 다른 장치 의존이 이 기록기 경로에 더 있는지). 
2. **새 시험이 믿을 만한가.** 실제 `restore_location` 경로를 타는 것이 맞는지 · 해석기 의존 (위 어긋남) 을 어떻게 처리해야 하는지 (시험이 해석기를 검사하게 하거나 이름으로 구분) · 변이가 정상 소스의 같은 시험 통과와 의도한 실패 위치로 확인됐는지.
3. **v2 단회 재시도 허용.** 17k 5 절의 조건 (기동 직전 수동 확인 · 새 tag · 고정 코드 해시 · 공통 변환 lock · v3 registry · attempt 별 USD 루트 · expect 0 · 명시적 미래 deadline · 시험용 `CE12_*` 없음 · 성공 뒤 COLLECTED → CPU `--recompute_action` → A1 ~ A9 승인 → 재확인 · 비정상이면 거기서 끝) 을 이 판에도 그대로 적용하면 되나. 승인용 코드 묶음 (`--code_bundle`) 은 이 판의 해시로 새로 만들어야 하나 (lead 계획: 이 판의 `ce12` 7 개 실행 파일 + slot v3 + isolate v3 + gpu_guard 의 기동 직전 해시). 작업자가 준 명령에는 `--deadline 0` 이 있었는데 lead 는 명시적 미래 epoch 로 바꿔 쓴다. 허용이면 최종 명령과 사전 확인 목록을 적어 달라. GPU 1 의 미경험 v6 full 이 끝난 뒤에 한다.
4. 결과 보고에 남길 미확인 (v2 기록의 첫 실제 증거가 될 것이므로).

## 결과

- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17n.md` 한 파일. 첫 줄은 한 문장 판정. 표기: 확인됨 · 추정 · 미확인.
- 코드 수정 · GPU · Isaac · 커밋은 하지 마십시오. `_eval/out*` · `handover_*` · `handover-1635` · `slot/` 에는 쓰지 마십시오. 지금 GPU 1 에서 미경험 v6 full 이 돌고 있으니 GPU 를 건드리지 마십시오. em dash 를 쓰지 마십시오.

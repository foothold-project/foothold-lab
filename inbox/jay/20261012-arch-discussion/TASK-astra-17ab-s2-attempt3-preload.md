> 분류: A/정책학습 · ASTRA 의뢰 17ab · S2 첫 수집 세 번째 시도 허용 여부 (진단 파일 한 곳: Kit 보다 먼저 불러오기)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 14:31
> 근거: 17aa 조건 · 두 번째 시도 증거 `night-tools-20261013/s2_stage0_first_collection/attempt2_20261015_1427/` · 수정 diff `.../s2_stage0_first_collection/A31_diag_preload.diff` · 작업 중인 드라이버들의 같은 우회 3 곳
> 요지: 두 번째 시도(14:27)는 EULA 를 지나 Kit 가 떴고 **GPU 0 장치 결박이 실제로 통과**했다. 그 뒤 `IsaacProvider` 가 `tensordict` 를 Kit 시작 **뒤에** 불러오다 접근 위반으로 죽었다. 이 저장소의 동작하는 드라이버는 모두 `h5py` · `torch` · `tensordict` 를 Kit 보다 먼저 불러온다(Windows DLL 선적재). A3 의 진단 파일 한 곳에 같은 세 줄을 넣었다(A3.1). 세 번째 시도를 허용하는지 매우 좁게 판정해 달라
> 상태: 의뢰 (GPU 둘 다 계산 0 · 팀장은 채팅에 있고 시도마다 새 동의를 받음 · 승인 json 없음)

# ASTRA 17ab

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 분량 `VERIFY-astra-17ab.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지. 17aa 에서 닫힌 것은 다시 보지 말고 아래만 봐 주세요.

## 사실 (직접 읽을 것)

1. **두 번째 시도(chain `s2-stage0-a3-live-20261015-142719`) 결과: 시작 실패(수집 0 행), 단 첫 시도보다 훨씬 멀리 갔다.** EULA 통과 → Kit 7.7 초에 기동(`child.log`) → **장치 결박 통과**: `out/device_binding.json` 에 `torch_uuid` = `c08e23b0-62b6-a4f2-8eb2-11151c6a8c7b`(= 기대 UUID), `str(props.uuid)` 가 UUID 문자열이고 `repr` 는 `<torch._C._CUuuid object>` 라는 점, Kit 관찰 `/physics/cudaDevice=0` · `/renderer/activeGpu=0` → `verified`. 감독기 영수증 exit `3221225477`(0xC0000005), 가족 0, 총 16 초.
2. **죽은 자리:** `child.log` 의 `Windows fatal exception: access violation` 의 Python 스택 맨 위가 `tensordict/utils.py:44 from tensordict._C import ...`(네이티브 확장 적재)이고 `tensordict/base.py` → `_datasets` → `_td` 로 올라간다. 호출자는 `IsaacProvider.__init__` 의 `from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper` 쪽(Kit 시작 뒤)이다. 이 기계에는 같은 종류의 Kit 크래시 덤프가 10/12~10/13 에도 있다.
3. **이 저장소의 선례 3 곳:** `C:/isaac/ext/go2_rl_robotlab/_eval/q_eval.py:24-25`(`import h5py` · `import tensordict` 를 `AppLauncher` 앞에, 주석 「Windows DLL preload」), `_eval/ce12/dump_native_v2.py:32-33`(`import torch` · `from tensordict import TensorDict`, 주석 「Windows 우회 · Kit 보다 먼저」), `_eval/branch/branch_run.py:45-46`. 안 한 쪽(S2 진단)만 죽었다.
4. **수정(A3.1):** `s2_connect_diag_17v.py` 의 `_main_capture` 안, `from isaaclab.app import AppLauncher` **앞**에 `import h5py` · `import torch` · `import tensordict` 세 줄과 주석(6 줄 추가, diff 파일). 모듈 최상단이 아니라 main 경로라 「Import is CPU-only」 는 유지. A3 나머지 46 파일은 바이트 그대로, `SHA256SUMS.txt` 는 한 줄 갱신(새 목록 SHA256 `089f6f16a52f40f5b351a3e14eb38567b3320a8ea0a00da8f76aabfca6527df2`), 기동 도구의 핀(`LIST_SHA`)도 같이 갱신. 기동 도구의 나머지(17aa 조건 · 환경 변수 두 개 · 동의 파일 필수)는 그대로.
5. **lead 가 한 것:** A3 CPU 전체 시험을 A3.1 바이트로 다시 돌리는 중(결과는 이 파일 뒤에 덧붙임). lead 는 `h5py` 가 이 인터프리터에 있고 `import h5py; import torch; import tensordict` 가 Kit 없이 CPU 에서 문제없이 되는지는 아직 재지 않았다(Kit 앞 순서 효과는 실기동에서만 보임).

## 물음 (셋)

1. **17aa 의 조건(새 승인 · 팀장의 매번 새 EULA/참석/한 번 실행 확인 · 입력 그대로 · 중단/보고 문구)으로 세 번째 시도를 허용하는가.** 한 파일 6 줄 수정이 A3 의 검증 범위를 어떻게 바꾸는지(어느 시험을 다시 봐야 하는지).
2. **더 있어야 할 선적재가 있는가.** 선례 3 곳이 Kit 앞에서 불러오는 모듈(`h5py` · `torch` · `tensordict`, 일부는 `rsl_rl.runners`)과 S2 경로가 Kit 뒤에 불러오는 것(`gymnasium` · `isaaclab_rl.rsl_rl` · `isaaclab_tasks` · `warp` 등)을 대조해, 같은 접근 위반을 낼 만한 다른 네이티브 확장이 보이면 지금 한꺼번에 알려 달라(또 한 번 죽는 일을 줄이려는 것). 못 본 것은 「미확인」.
3. **장치 UUID 표기 항목 17y 4 번의 「실제 형식 미확인」 은 이 실측으로 닫힌 것으로 보는가**(`str` 은 UUID, `repr` 은 객체).

## 결과
- `inbox/jay/20261012-arch-discussion/VERIFY-astra-17ab.md` 한 파일. 표기: 확인됨 · 추정 · 미확인.

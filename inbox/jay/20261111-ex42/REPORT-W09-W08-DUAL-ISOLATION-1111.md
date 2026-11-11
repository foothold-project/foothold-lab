# EX-42 W09·W08 두 GPU 자식 격리
> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11 17:10
> 근거: #691 후속 · 10/13 USD 임시 폴더 충돌 기록
> 요지: 두 Kit 자식의 임시 폴더와 캐시를 분리하고 시작 간격을 둔다.
> 상태: CPU 확인됨 · Kit 미실행

각 회차의 `flag_one` · `flag_four` 자식은 산출 폴더 아래 `kit_runtime/cuda_0` 또는 `cuda_1` 의 개별 `tmp` · `cache` 를 쓴다. 자식 환경의 `TMPDIR` · `TEMP` · `TMP` · `XDG_RUNTIME_DIR` 는 개별 `tmp`, `XDG_CACHE_HOME` 과 Kit `localCachePath` 는 개별 `cache` 다. 실행 영수증에 두 실제 경로를 남기고 DRY 명령도 개별 캐시 경로를 보여 준다.

GPU0 첫 Kit 자식 호출 직전에 신호를 내고 GPU1 첫 호출 전 30초 쉰다. CPU 시험은 두 그룹 동시 실행과 30초 지연 호출을 확인했고, cuda:1 자식이 cuda:0 신원을 보고하면 HOLD가 되는 반례를 확인했다. `test_ex42_flag_baseline_chain_cpu.py` + `test_ex42_e1f_flag_cpu.py`: 27 passed. 실제 두 Kit 프로세스의 임시 경로 사용과 시작 시각은 미측정이다.

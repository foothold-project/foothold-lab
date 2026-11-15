> 분류: 실험 기록 (E0 환경 준비)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-12
> 근거: 한글 경로 사본 `인공지능사관학교/ext/go2_rl_robotlab/_smoke/` (10/10) 에만 있던 기록
> 요지: MoE-CTS 재현 env `isaac311-moects` 를 만든 과정(conda 복제 · pip 설치 · 설치 전후 패키지 목록 · 첫 연기 시험 · 한글 경로 URDF 변환 진단). 한글 경로 사본을 지우기 전에 옮겼다
> 상태: 보존

- `01`~`05`: env 복제 · pip dry-run · 설치 · 설치 전후 `pip freeze` 와 차이 · `pip check`
- `06`~`08`: 한글 경로에서의 첫 연기 시험 선언 · 실행 로그 · GPU 표본
- `09-diag-urdf-A.log`: 한글 경로에서 Isaac URDF 변환이 빈 USD 를 내고 종료 0 이던 진단 (B 판 350 KB 는 `C:/isaac/ext/go2_rl_robotlab/_smoke/env-setup-korean-path/` 에만 둠)
- `SMOKE-korean-path.md`: 그때의 기록. 영문 경로로 옮긴 뒤의 기록은 `C:/isaac/ext/go2_rl_robotlab/_smoke/SMOKE.md`

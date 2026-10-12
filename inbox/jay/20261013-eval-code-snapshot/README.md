> 분류: A/정책학습 · 코드 사본 (Linux 이전 전 조건)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 00:50
> 근거: super 런북 7 절 「이전 전 조건」 (정본이 git 밖인 채로 이사하지 않기) · 팀장 10/12 23:55 「실험은 foothold-lab 에서 · 최종본은 foothold-go2」
> 요지: lab 밖 `C:/isaac/ext/go2_rl_robotlab/_eval/` 의 우리 평가 · 분기 · RoboGauge 도구 코드 191 개 (py · sh · md · yaml · json · txt, 1 MB 미만, out · __pycache__ 제외) 를 10/13 00:50 시점 그대로 옮긴 사본과 sha256 목록
> 상태: 사본 (정본 이전은 Linux 이사 때 `sim/eval/` · `sim/policy/` 로 · 실행 중 도구라 이 시각 뒤 바뀐 파일은 다음 사본에서 다시 대조)

- `SHA256SUMS.txt` 의 경로는 `_eval/` 기준이다. 이사 직전에 같은 명령으로 다시 만들어 이 목록과 대조하고, 다른 파일만 새로 커밋한다.
- 결과물 (`out/` 74 GB) · 체크포인트 (`logs/`) 는 git 이 아니라 NAS 백업 대상이다 (매니페스트 1 절).

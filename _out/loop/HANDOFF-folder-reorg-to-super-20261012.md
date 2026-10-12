# lead → super 인계 · 폴더 정리 (한글 경로 없애기 · Linux 이전 준비)

> 분류: 운영 · 인계
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-12
> 근거: 팀장 10/12 lead 채팅 「폴더 정리는 super 에게 넘겨」 · 「mai/project/foothold-lab 이런 식으로 폴더 정리」 · lead 실측 (아래)
> 요지: 한글 경로(`인공지능사관학교`)가 Isaac URDF 변환을 깨뜨렸다. 폴더 재배치는 시스템 일이라 super 가 맡는다. lead 쪽에서 경로에 묶인 것을 실측해 넘긴다
> 상태: 인계 (super 가 팀장과 범위 확인 뒤 진행)

## 왜

- 10/10 E0: 한글 경로(`Desktop/jay/인공지능사관학교/ext/...`)에서 Isaac URDF importer 가 **빈 USD 를 내고 종료 0** 이었다. 영문 경로 `C:/isaac/ext/go2_rl_robotlab` 로 옮겨서 풀었다 (기록 `inbox/jay/20261008-546-design/e0-env-setup/`).
- 팀장 10/12: Ubuntu 멀티부트(새 SSD)로 넘어가도 작업이 끊기지 않게 작업 · 폴더 · 파일 · 경로 · 에이전트를 정리.

## lead 쪽에서 경로에 묶인 것 (10/12 실측)

| 무엇 | 자리 | 옮길 때 |
|---|---|---|
| 프로젝트 저장소 | `C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab` (브랜치 `feature/verify-v2-mvp-jay`) · 옆에 `foothold-site` | 저장소 안 **코드 · 설정 48 개 · 문서 23 개**가 이 절대경로를 적고 있다 (`git grep -l "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교"`) |
| Claude 프로젝트 메모 | `C:/Users/AI-WS01/.claude/projects/C--Users-AI-WS01-Desktop-jay----------foothold-lab/memory/` (62 개) | **폴더 이름이 작업 경로에서 만들어진다.** 저장소를 옮기면 새 경로의 메모 폴더가 비어 있다. 옮겨 붙이기 필요 |
| RL 실험 코드 · 결과 | `C:/isaac/ext/go2_rl_robotlab` (MoE-CTS · 28b4516d) · `logs/` 2.2 GB · `_eval/out/` 21 GB · `_runs/` · `_smoke/` | 저장소 밖 · NAS 백업 없음. 문서 · 코드 · 요약표 사본만 저장소 `inbox/jay/20261008-546-design/eval-*/` 에 있다 |
| Isaac Lab · conda | `C:/isaac/IsaacLab` · env `isaac311` (원본) · `isaac311-moects` (MoE-CTS) | Linux 에서는 다시 만든다. 설치 전후 `pip freeze` 는 `e0-env-setup/` 에 있다 |
| 이전 RL 결과 | `C:/isaac/IsaacLab/logs/rsl_rl/...` (foothold-v2 등) | 저장소 밖 |
| NAS 거울 | NAS `01_AI_WORK/인공지능사관학교` = 데스크톱 SyncSpace 거울 (메모 `nas-layout-and-access`) | 데스크톱 폴더를 옮기면 거울 경로도 바뀐다 |
| Orca 작업공간 | `C:/Users/AI-WS01/orca/workspaces/foothold-lab/...` | 저장소 경로를 가리킨다 |
| 세션 상태 | `C:/Users/AI-WS01/.mai/sessions/*.json` · `units/` 의 `cwd` | |

## lead 가 따로 할 것 (RL 쪽)

- RL 실험 인벤토리 · 재현 매니페스트 (코드 SHA · env · 체크포인트 · 명령 · 데이터 자리) · Linux 에서 다시 세울 기준선 목록. #546 에 둔다.
- 지금 돌고 있는 것: E2 (GPU 0 · 10/12 12:50 쯤 끝) → E2 평가 (GPU 1) → **학습 중단** (팀장 10/12).

## 확인할 것

- 새 자리 이름 (`mai/project/foothold-lab` 은 팀장 예시) · Windows 쪽을 먼저 옮길지, Linux 에서 새로 시작할지
- 옮기는 동안 다른 세션(rl-v2-command-restore 등)이 같은 저장소를 쓰는지

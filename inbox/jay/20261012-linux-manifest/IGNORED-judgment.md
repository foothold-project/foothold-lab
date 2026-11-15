> 분류: A/정책학습 · 운영 · Linux 이전 매니페스트 (저장소 안 ignored 자료)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 14:24
> 근거: `git status --ignored` (13:4x 실측 · 항목 1,548 · 파일 91,809 · 66.6 GB) · 폴더별 du · vfxpedia/mai-os#34 R04 「저장소 안 ignored 자료를 백업 / 재생성 / 제외로 판정하는 목록이 빠져 있다」
> 요지: foothold-lab 안의 git 이 안 담는 자료 66.6 GB 를 묶음 27 개로 나눠, 무엇을 NAS 로 옮기고 (백업), 무엇은 명령으로 다시 만들고 (재생성), 무엇은 버려도 되는지 (제외) 초안을 적는다
> 상태: 초안 · 팀장 · super 확인 전 · 아무것도 옮기거나 지우지 않음

# foothold-lab ignored 자료 판정 (초안)

**판정의 뜻**
- **백업:** 다시 만들 수 없거나 다시 만들면 비싼 것. NAS 로 옮긴다. 원본 영상, 유료 생성물, 몇 시간 걸린 GPU 결과가 여기 든다.
- **재생성:** 저장소 안의 코드와 백업한 원본으로 다시 만들 수 있는 것. 만드는 명령만 남긴다.
- **제외:** 다시 받을 수 있는 도구와 캐시. 판 번호만 남긴다.
- **확인:** lead 가 혼자 정하면 안 되는 것.

| 묶음 | 크기 | 판정 | 까닭 |
|---|---:|---|---|
| `inbox/jay/20260916-3dgs-test/IMG_*.MOV` (셋) | 0.63 GB | **백업** | 3DGS 의 원본 촬영 영상. 다시 찍을 수 없다 |
| 같은 폴더 `_frames/` | 0.34 GB | 재생성 | MOV 에서 ffmpeg 로 뽑은 프레임 |
| 같은 폴더 `_out/tools/` | 2.6 GB | 제외 | 받은 도구. 판 번호만 남긴다 |
| 같은 폴더 `_out/` 의 나머지 (shot2pipe 12 · mixcond 7.2 · adonly 2.2 · colmap 1.3 · colmap_loop 1.3 · shot2 1.1 · nurec 0.8 · baselines 0.8 · splat 0.7 GB) | 28.8 GB | **확인** | 최종 결과 (nurec USDZ · splat) 는 백업이 맞다. 중간 결과 (COLMAP · 학습 중간) 는 몇 시간짜리 GPU 결과라 다시 만들기가 비싸다. 무엇을 남길지는 팀장 판단 |
| `inbox/jay/20261013-go2-app-study/astra10/tools/` | 약 14.9 GB | 제외 | Android SDK 4.5 · 에뮬레이터 이미지 2.8 · JDK 0.3 · python 0.2 · frida 0.1 GB. 다시 받을 수 있다. 판 번호를 ASTRA 10 문서에서 옮겨 적는다 |
| 같은 폴더 `evidence/` · `logs/` | 작음 | **백업** | 공식 페이지 · 약관 · wasm 을 그 시각에 받아 둔 증거. 나중에 같은 것을 다시 못 받을 수 있다 |
| 같은 폴더 `rea-worker-input/` | 작음 | 확인 | 다른 세션이 쓴 입력. 소유 세션 확인 |
| `sim/eval/results/` (실험 결과 1,259 항목) | 14.2 GB | **백업** | 사이트 · 문서가 이 결과를 가리킨다. 다시 만들려면 GPU 로 수십 시간 |
| `inbox/jay/20260930-mvp-brand/_out/` (launch_render 1.1 · review 0.9 · seedance_out 0.3 · img_out 0.3 · analysis 0.2 GB) | 3.15 GB | **백업** | 유료 생성물 (Seedance · 이미지) 과 Cycles 렌더. 다시 만들면 크레딧과 시간이 든다 |
| `inbox/jay/20260904-launch/library/` | 0.33 GB | **백업** | 유료 생성 영상 · 이미지 |
| `inbox/jay/20260929-mvp-submission/output/FOOTHOLD-MVP-submission.zip` | 0.11 GB | **백업** | 제출본 |
| 같은 폴더 `tmp/` 와 나머지 | 0.23 GB | 제외 | 만드는 중의 임시 파일 |
| `inbox/jay/20260929-mvp-presentation/output/FOOTHOLD-MVP-review.pdf` · `assets/fire-demand-official.pdf` | 작음 | **백업** | 발표본과 받은 공식 자료 |
| 같은 폴더 `_out/` | 0.11 GB | 재생성 | 빌드 스크립트 산출 |
| `_out/loop/gallery-v2-draft/` | 0.64 GB | 재생성 | 갤러리 초안 빌드 |
| `_out/loop/verdict-*.json` · `audit3.log` 등 | 작음 | **백업** | 실험 판정 기록 |
| `web/assets/mvp-deck/` | 0.29 GB | 재생성 | 덱 빌드 산출 |
| `inbox/jay/20260929-mvp-submission` 외 `__pycache__/` · `.pytest_cache/` · `sim/**/__pycache__/` · `tools/__pycache__/` | 작음 | 제외 | 파이썬 캐시 |
| `.claude/worktrees/` | 0.02 GB | 제외 | 지난 worktree 흔적 |
| `deliverables/plan/_deck/deck.artifact.html` · `preview.html` | 0.02 GB | 재생성 | 덱 빌드 산출 |
| `_ready_to_del/` | 작음 | 확인 | 이름은 지워도 된다지만 누가 무엇을 두었는지 미확인 |
| `inbox/lim/20260901-프로젝트기획서-초안.pdf` | 작음 | **백업** | 팀원 자료. lead 가 판정할 것이 아니므로 그대로 옮긴다 |
| `.claude/settings.local.json` | 작음 | 확인 (비밀값 경로) | 내용을 열지 않았다. 인증 값이 들 수 있으므로 일반 백업에 섞지 않고 런북의 비밀값 절차를 따른다 |

**합계 (근사).**
- 백업: 약 19 GB. 3DGS 확인분 28.8 GB 를 더하면 최대 약 48 GB.
- 재생성: 약 1.4 GB.
- 제외: 약 17.7 GB.

**하지 않은 것.**
- 파일을 옮기거나 지우지 않았다.
- 크기는 du 기준이고, 같은 내용의 중복은 세지 않았다.
- 「재생성」 의 명령이 지금도 그대로 도는지는 시험하지 않았다 (미확인).

**다음.**
- 팀장 · super 가 「확인」 네 줄을 정한다.
- 백업 묶음은 NAS 전송 목록에 넣는다 (`_eval/out` 은 저장소 밖이라 별도, vfxpedia/mai-os#34 6138847601).

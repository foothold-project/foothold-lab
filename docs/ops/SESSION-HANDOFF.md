# 세션 이관 가이드: 다른 기계·리눅스에서 이어받기

> 분류: 운영
> 작성: 오흥재 · 2026-08-27 22:09
> 근거: 본인 노트
> 요지: 새 세션이 이어받을 때 읽는 저장소 지도와 절차.
> 상태: 확정
> 판: v1.0

> 작성 2026-08-20 (노트북 세션) · 대상: 새 OS·새 기계·새 세션에서 이 프로젝트의 자동화·웹·기록 계통을 이어받는 나(또는 다른 세션)
> 원칙: **이 문서 하나로 제로베이스에서 재구성 가능해야 한다.** 안 되는 부분이 발견되면 이 문서를 고친다.

## 0. 먼저 읽는 순서

1. `docs/LEDGER.md`: 지금 어디까지 왔나 (진행 현황)
2. 이 문서: 어떻게 이어받나
3. `MAI_UNIVERSE/00_STATE.md`: 프로젝트 전체 축 (WS 재기획 포함)
4. `docs/DECISIONS.md`: 왜 그렇게 했나

## 1. 저장소 지도 (클론 4 + 볼트 1)

| 저장소 | 공개 | 역할 | 로컬 위치 관례 |
|---|---|---|---|
| `foothold-project/foothold-lab` | 비공개 | 팀 문서·inbox·워크플로 (**두뇌**) | `인공지능사관학교/foothold-lab` |
| `foothold-project/foothold-go2` | 공개 | 코드·실험 (`sim/` `nav/` `common/`) | `인공지능사관학교/foothold-go2` |
| `foothold-project/foothold-site` | 공개 | 웹 미러 (**직접 수정 금지**, 빌드 산출물) | `인공지능사관학교/foothold-site` |
| `foothold-project/foothold-brand` | 공개 | 브랜드 정본 (Codex 관리) | `인공지능사관학교/foothold-brand` |
| `vfxpedia/mai-universe` | 비공개 | 개인 볼트. 웹 원본(`03_PROJECTS/doyak-final/05_deliverables`)이 여기 산다 | `인공지능사관학교/MAI_UNIVERSE` |

★ 세션 임시 클론(스크래치패드)은 **세션이 끝나면 사라진다.** 영속 작업은 위 관례 위치의 클론에서 한다.
★ 노트북에는 볼트 옆 `foothold-lab` 클론(빌드가 읽는 것)과 세션 임시 클론이 **둘 다** 있었다.
  빌드의 문서 수집은 모든 후보를 훑어 최신본을 고르므로(2026-08-13 수정) 어느 쪽이 최신이어도 안전하다.

## 2. 웹 빌드·배포 (사람이 하는 유일한 정기 작업)

빌드는 GitHub Actions 가 아니라 **로컬**에서 돈다 (볼트가 비공개 로컬에 있기 때문).

```
cd MAI_UNIVERSE/03_PROJECTS/doyak-final/05_deliverables
python _build/build.py --check     # 필요 시 --verify (외부 사실 검증)
```

절차 (충돌 사고 2회로 확정된 순서):
1. **pull 먼저**: lab · 볼트 · site 전부 원격 최신으로 (WS 세션이 먼저 밀었을 수 있다)
2. 빌드 (관문 자동 실행: 토큰색·문구·ASCII·다크모드·파비콘·NEW·em dash·민감정보 17종·sync-conflict)
3. 볼트 커밋·push → site 커밋·push (site push 가 Vercel 배포 + 디스코드 알림 트리거)
4. 생성물(html) 충돌 시: **skip/reset 후 재빌드**가 정답. 손 병합 금지.

★ 리눅스 이관 시 첫 작업: `_build/*.py` 의 경로 후보(`LAB_CANDIDATES` 등)가 전부 Windows 경로다.
  `os.environ.get('FOOTHOLD_LAB_DIR')` 식 env 오버라이드를 후보 맨 앞에 추가할 것
  (대상: build.py `_find_site` · docs_pages · flow_page · collab_page · voicecheck · tokencheck · brandmark · secure_docs).

## 3. 자동화 전체 (GitHub Actions, 기계 무관하게 돈다)

lab 11종: 이슈 자동처리(보드·날짜·담당) · 갈래 sub-issue 연결 · 실적 종료일 · 디스코드 알림(docs)
· inbox 감지(디스코드+검토이슈+**텔레그램 자동검토**) · 승격(`/승격` 코멘트) · 마감 알림(평일 9시)
· 주간 리포트(월 9시) · 공지 발송(수동) · main 감시 · 보드 뷰 정리(수동)
rl 4종: 이슈 자동처리 · 갈래 연결 · 실적 종료일 · 디스코드 알림. main 은 룰셋 강제(PR only).

규칙: 날짜는 전부 KST · 워크플로 YAML 은 검증 통과 후 커밋 · 이벤트 자동화는 자기 출력에 반응 금지(봇/접두어 2중 가드).

## 4. 시크릿·자격 지도 (값은 절대 여기 안 적는다)

| 무엇 | 어디 | 리눅스에서 |
|---|---|---|
| `PROJECT_TOKEN` `DISCORD_WEBHOOK` `DISCORD_NOTICE_WEBHOOK` `TELEGRAM_BOT_TOKEN` `TELEGRAM_CHAT_ID` | lab **레포 시크릿** (rl 은 org `DISCORD_WEBHOOK` 사용) | 그대로 (기계 무관) |
| GitHub 로컬 인증 | Windows: Git Credential Manager | `gh auth login` 또는 credential helper 재설정 |
| 텔레그램 로컬 발송 | `~/.mai/telegram_token.txt` · `telegram_chat_id.txt` · `tg_send.py` | **~/.mai 를 복사**하면 즉시 동작 (python 표준lib만 사용) |
| GIST V100 계정 | 디스코드 #foothold-resource | 교육장 IP 에서만 접속 |
| 팀원 권한 | lab·rl write / site·brand read / org 기본 read | 설정은 GitHub 에 있음, 기계 무관 |

## 5. 이관 체크리스트 (리눅스 새 기계)

- [ ] 클론 5개를 §1 관례 위치에 (`git clone` ×4 + 볼트)
- [ ] `gh auth login` (repo·project 스코프) 또는 PAT
- [ ] `~/.mai/` 복사 (텔레그램)
- [ ] `_build` 경로 env 오버라이드 추가 (§2 ★) 후 `build.py --check` 가 끝까지 도는지
- [ ] ffmpeg·pypdf·pynacl·pyyaml 등 로컬 도구 (빌드 자체는 표준lib 위주)
- [ ] NAS 동기화 클라이언트 (볼트 미디어 원본은 git 밖, NAS 가 원본)
- [ ] 검증: 테스트 이슈 1개 생성→갈래 부모 연결→닫기→실적일, inbox 테스트 1건→3중 알림

## 6. 증발 방지 규칙 (요약)

채팅은 휘발이다. 결정→`DECISIONS.md`, 상태→`LEDGER.md`, 검증→`ops/VERIFIED.md`,
사양→`ROBOT-SPEC.md`, 회의→`meetings/`(전사가 정본, 녹음은 NAS), 팀원 제출→`inbox/`.
세션 규칙 9개는 Claude 영속 메모리(`foothold-session-rules`)에 있고 기기 간 공유되지 않으므로,
**새 기계의 Claude 에는 이 문서와 LEDGER 를 먼저 읽혀라.**

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-08-20 | 처음 씀 | 이전 이력은 git 에 |

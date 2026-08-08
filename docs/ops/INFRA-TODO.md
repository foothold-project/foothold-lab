# 인프라 구축 체크리스트 — 반드시 한다 (팀장 확정 2026-08-09)

> 워크스테이션 Tailscale 세팅과 **같은 날 묶어서** 진행한다. 전부 같은 망 작업이다.

## 1. NAS 회의 오디오 폴더

- [ ] UGREEN 공유폴더 `foothold/meetings/` 생성, 팀 계정 읽기/쓰기 권한
- [ ] 규칙: 파일명 `YYMMDD_제목.m4a` — 회의 직후 업로드
- [ ] (Phase 2) 워크스테이션이 이 폴더를 감시 → MOSS 전사 → lab `docs/meetings/` 보고서 자동 커밋

## 2. NAS Vaultwarden (팀 비밀 금고)

- [ ] UGREEN Docker 앱 → 이미지 `vaultwarden/server:latest`
- [ ] 볼륨: NAS 폴더 → 컨테이너 `/data` 매핑 · 포트 지정 (예: 8100)
- [ ] **HTTPS 필수** (브라우저 암호화 API 요구) → `tailscale cert` 로 인증서 발급이 가장 깔끔
- [ ] 관리자 계정 → 팀원 5명 초대 → 공유 컬렉션 "FOOTHOLD"
- [ ] 이관: RunPod 계정 · PAT · 웹후크 URL 등 → 등록 후 디스코드 임시 공유분 삭제
- ⚠️ UGREEN 모델의 Docker 지원 여부 사전 확인 (UGOS Pro 필요)

## 3. 디스코드 #resources 채널 (단기 — 지금 바로 가능)

- [ ] 비공개 채널 신설, 권한 = 팀 5인만
- [ ] 올리는 것: 팀 공용 계정(RunPod id/pw) · NAS 경로 · 접속 안내
- [ ] 올리지 않는 것: **토큰·API 키·웹후크 URL** (Vaultwarden 전까지 불가피하면 임시 + 분기 회전)
- [ ] 규칙 고정 메시지로 박기

## 4. 다크 모드 수리 (사이트)

- 실측(2026-08-09): **brief · encyclopedia · index · setup · team-intro 5개 페이지에 다크 CSS 없음**
  (curriculum · plan · team-access 는 지원). WS 처럼 다크 기본 OS 에서 절반이 눈부심.
- [ ] 5개 페이지에 다크 팔레트 블록 추가 — 이슈 #5

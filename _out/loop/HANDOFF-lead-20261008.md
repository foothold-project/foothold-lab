# lead 인계 · 2026-10-08

> 분류: 운영
> 작성: 오흥재 · 2026-10-08 20:55
> 근거: 이 세션 실행 기록 · 커밋 · 이슈 댓글
> 요지: 10/7~10/8 lead 세션이 한 일과 남은 일. 다음 lead 는 이 파일과 #546 부터 읽는다.
> 상태: 인계
> 판: v1.0

`HANDOFF-precompact.md` 는 PreCompact 훅이 다시 쓰므로 거기에 덧붙인 줄은 다음 압축 때 사라진다. 이 파일은 손으로 쓴 인계라 훅이 건드리지 않는다.

## 1. 다음에 바로 할 일 (#546 · 팀장 지시 10/8)

super 가 정리한 MVP 이후 설계 논의를 lead 가 팀장과 진행한다. #546 에 받았다고 남겼고 보드 In Progress.

| 칸 | 무엇 | 상태 |
|---|---|---|
| A | 라현 · 민우 · 현민 보고를 **각각** 웹 문서로. 링크 자료는 전부 열어 문서 안에 담는다(링크만 금지). 통합 진행 상황 문서 따로. 게시 순서: 정리 → 텔레그램 예고 → 팀장 컨펌 → 게시 → 공지 | 착수 전 · 근거 PR #542(민우) #543 · #545(라현) #544(현민) |
| B | 이음매 셋: 앱 ↔ 게이트웨이 · **Nav2 ↔ 보행 정책(갈림길: 속도 명령 vs 목표 위치)** · 정책 ↔ 실기. 현민 RL(목표형 교사)과 석헌 정책학습의 소유 · 분담 | 논의 전 · AME-2 보고서 10절에 인터페이스 차이 정리돼 있음 |
| C | 방향 점검 · 놓친 것 찾기 · 팀장 피드백(라현: 가비지 스플랫 → SuperSplat 정리 먼저)도 점검 | 논의 전 |
| D | RL 아키텍처 Top-down · 논문 각각 deep-research · astra 와 논의 · «발을 놓을 곳을 안다» | 논의 전 · 근거 `docs/research/20260929-locomotion-direction.md` · star 논문 메모리 |
| E | 브랜드 G · F 영상 남은 일 파악만(우선순위 낮음). MVP-brand · brand-launch-video 세션은 닫는다 | 파악만 |

## 2. 10/7~10/8 에 끝낸 것

| 일 | 결과 | 어디 |
|---|---|---|
| 석헌 AME-2 v1~v6 보고서 | RunPod 공유 볼륨을 직접 읽어 정리 · 숫자 전부 일치 · v6 은 정면 목표 + 거리 승급 두 요인 · 그림 일곱 장 · 자료 CSV | `docs/research/20261007-ame2-go2-v1-v6.md` · #532 #533 · 웹 게시 |
| 라현 서비스 방향 검토 | 근거 부록을 7~10절로 합본 · 묶음 조사·비교 고정 · 옛 부록 주소는 합본으로 307 | `docs/research/20261007-underground-recon-service-review.md` · #535 |
| 연구 페이지 | 한 목록 · 여섯 묶음 · 묶음 안 날짜 최신순 하나 | `web/_build/hub3.py` · #538 #539 |
| #511 영상 NAS | 1~3단계 끝. 영상 345개 · PDF 7개 NAS 에서 나감. 배포본 892 → 201 MB | 아래 3절 |
| 경량화 | 큰 PNG 77장 WebP (80.4 → 20.2 MB) | `web/_build/image_slim.py` · #541 |
| 도메인 조사 | 6개 이름 × 9개 뒤 이름 · 판별기 시험 · Cloudflare 화면가 | `_out/nas-migration/DOMAIN-all-20261008.md` · 아티팩트 https://claude.ai/artifact/N6KTt6WXJkKkwRdQ7sfBb5 |
| super 요청 | 덱 폴더 커밋(2befcb98) · brand 명부 자동 등재 경로 분석 → super #537 | #537 |
| Star 정리 | mai-os `research/starred-repos/` 로 이동 | #529 · mai-os 7c58181 |

## 3. 영상 · PDF 가 나가는 길 (#511)

```
방문자 → foothold-project.vercel.app (페이지 · 그림)
          └ /...mp4 · /...pdf 요청 → vercel.json 307 → https://ai-nas01.tail025053.ts.net/...
                                       └ Tailscale Funnel (NAS 컨테이너 ai-nas01-tailscale)
                                          └ Caddy 컨테이너 foothold-media 127.0.0.1:8090
                                             └ /volume1/foothold/media/site (읽기 전용)
```

- 빌드 `[3.05] media_offload.py`: 배포본의 영상 · PDF 를 NAS 와 sha256 대조 → 없으면 올림 → 배포본에서 뺌. **NAS 에 못 닿으면 배포가 막힌다.** 워크스테이션 재부팅 뒤에는 별도 PowerShell 창에서 `net use N: \\100.80.160.84\foothold /user:VFXPEDIA * /persistent:no` 를 다시 한다.
- 빌드 `[3.06] image_slim.py`: 200 KB 넘는 PNG → WebP(투명 무손실 · 사진형 품질 90, 평균 차이 2/255 넘으면 무손실).
- **Tailscale 이 켜진 기기(팀장 기기)는 Chrome 이 «로컬 네트워크 접근» 허용을 물은 뒤에야 영상 · PDF 가 열린다.** 사이트마다 한 번. 외부 방문자는 해당 없음.
- NAS 쪽 되돌리기: `sudo docker exec ai-nas01-tailscale tailscale funnel reset` · `sudo docker rm -f foothold-media`.

## 4. 팀장 결정 대기 · 팀장 손이 필요한 것

- ~~Vercel 보관 기간 7일~~ **10/8 팀장 설정 완료**: Production · Pre-Production 1 week · Canceled · Errored 1 day (위치는 아래 5절).
- Vercel Fast Data Transfer 117 GB / 100 GB 초과 (10/8 화면). 영상 · PDF 를 NAS 로 넘겼으니 앞으로는 줄어든다. 남은 큰 것은 제출본 HTML 두 장(31.8 MB · 9.6 MB, 그림이 안에 박힘). 이것도 NAS 로 돌릴지 결정 필요.
- 도메인 구매: 프로젝트 `foothold-project.dev` 1년 · 개인 `mai-universe.dev` 또는 `vfxpedia.dev`. `vfxpedia.com` 이 팀장 것인지 확인 필요(2006 Gandi · Blackmagic Fusion 페이지로 넘어감).
- #520 석헌 칸 체크 여부.

## 5. Vercel 보관 기간 바꾸는 곳

Vercel 대시보드 → 프로젝트 **foothold** → **Settings** → 왼쪽 **Build and Deployment** → 맨 아래 **Deployment Retention Policy** → 상태별(Canceled · Errored · Pre-Production · Production) 기간을 고르고 **Save**. 고를 수 있는 값은 30 days · 2 weeks · 1 week · 1 day 이고, 10/8 21:40 현재 넷 다 30 days 다(팀장 화면에서 lead 가 읽기만 함).

- **Vercel 공식 문서(9/16 갱신)는 Settings → Security 라고 적지만 실제 화면에는 없다.** 10/8 팀장이 Security 화면을 찍어 지적했고, Chrome 으로 확인한 실제 자리는 위와 같다.
- 팀 전체 기본값은 팀 **Settings → Build and Deployment → Deployment Retention Policy** 에 따로 있다. 「Apply this policy to all existing projects」를 켜면 hire-sift · mood-lens-ai 에도 들어간다.
- 예외로 남는 것(Hobby): 최근 배포 3개 · Ready 운영 배포 3개 · 운영 주소가 붙은 배포. 9/16 부터 팀이 10 GB 를 넘으면 예외 밖 배포는 30일을 안 기다리고 바로 지워진다(Vercel 변경 기록).

## 6. 이 세션이 배운 것 (메모리에 있음)

- `site-build-gates-before-writing` · 문서를 올리기 전에 맞출 빌드 관문 다섯.
- `nas-layout-and-access` · NAS 폴더 지도 · tailscaled 는 Docker · Chrome 로컬 네트워크 접근.
- 관문이 «명부를 갱신했다, 다시 빌드하면 통과» 하는 구조가 둘(brand · emptycheck) 있다. 명부 자동 등재 줄은 되돌리고 원인을 고친다(#537).

## 판 이력

| 판 | 날짜 | 무엇 | 왜 |
|---|---|---|---|
| v1.0 | 2026-10-08 | 처음 씀 | 팀장 「핸드오프 정리해줘」 |

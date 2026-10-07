# 사이트 영상 NAS 이전 계획 (#511)

> 분류: 계획
> 작성: 오흥재 · 2026-10-06 19:10 · 고침 2026-10-07
> 근거: foothold-site 미러 실측 · GitHub deployments API · Tailscale 상태
> 요지: 배포 한 건에 영상 580 MiB 가 실려 Vercel 배포 저장소가 찼다. 영상은 NAS 를 원본으로 두고 NAS 주소에서 서빙하며, 웹 화면은 바꾸지 않는다.
> 상태: 1단계 끝 · 2단계 서빙 경로 팀장 결정 대기
> 판: v0.3

## 실측 (2026-10-06)

| 항목 | 값 |
|---|---|
| 미러 작업 트리 | 858 MB (단위 미확인 · 다시 잴 것) |
| 그중 영상 | 345개 · 580.5 MiB (= 608.7 MB) |
| 영상 원본이 lab 에 있는 것 | 153개 · 251.3 MiB (빌드가 다시 구움) |
| 영상 원본이 site 에만 있는 것 | 192개 · 328.4 MiB (갤러리 클립 · v0.1 때 **유일본** · 10/7 NAS 복사로 두 곳) |
| 어디서도 이름이 안 불리는 영상 | 4개 · 2.0 MiB |
| GitHub 에 기록된 Vercel 배포 | Production 311건 (8월 158 · 9월 129 · 10월 24) |
| site 저장소 git | 커밋 330 · pack 4.30 GiB |
| NAS | `ai-nas01` · Tailscale 100.80.160.84 · SMB 445 · HTTPS 443 응답 · 공유 폴더 `foothold` 를 10/7 팀장이 N: 로 붙임(비지속) |

전수 목록: `media-inventory.csv` (경로 · 바이트 · sha256 · 원본 위치 · 참조 수). 만든 스크립트: `_out/tools/nas_media_inventory.py`.

폴더별(MiB): gallery/v1/clips 244.4 · assets/mvp-deck/media 154.1 · gallery/v2/clips 84.0 · assets/video/v2 75.4 · 나머지 22.

v0.1 은 이 값들을 «MB» 로 적었으나 스크립트는 2^20 으로 나눴다. v0.2 에서 MiB 로 고쳤다.

## 원인은 두 층이다

1. **배포 한 건이 무겁다.** 영상이 미러에 들어 있어 배포마다 858 MB 가 올라간다.
2. **옛 배포가 남아 있다.** 311건이 쌓였다. 영상을 빼도 옛 배포가 차지한 저장소는 Vercel 쪽에서 지워야 줄어든다. 배포별 용량과 보존 설정은 Vercel 대시보드에서만 보인다(이 워크스테이션에는 Vercel CLI·토큰이 없다).

## 목표 상태

- 사용자가 보는 화면은 그대로. 영상 주소만 `https://<NAS 공개 주소>/foothold-media/...` 로 바뀐다.
- NAS `foothold/media/site/` 가 영상 원본. 미러에는 영상이 없다(빌드 관문으로 막는다).
- 미러 크기 목표 300 MB 이하.

## 영상 경로가 들어 있는 모양 (미러 실측)

| 모양 | 수 | 예 | 바꾸는 법 |
|---|---|---|---|
| 루트 절대 `/assets/...mp4` | 275 | 갤러리 · 문서 페이지 | 빌드 끝에서 접두어 교체 |
| 파일 기준 상대 `media/x.mp4` | 592 | 덱(`assets/mvp-deck/index.html`) | 파일 위치로 풀어 절대화한 뒤 교체 |
| 사이트 기준 `assets/...mp4` | 69 | 루트 페이지 | 접두어 교체 |
| 갤러리 런타임 | (색인 json 의 `clips/x.mp4`) | `G.at(folder + '/' + clip.file)` | `gallery.js` 에 영상 전용 뿌리 `G.media` 를 두고 클립만 그쪽으로 |

## 서빙 경로 (팀장 결정 필요)

| 안 | 무엇 | 장점 | 확인할 것 |
|---|---|---|---|
| **A. Tailscale Funnel (권장)** | NAS 의 Tailscale 에서 한 경로만 공개 HTTPS 로 연다 | 이미 쓰는 Tailscale · 공유기 포트 개방 없음 · 인증서 자동 · 비용 0 | 관리 화면 세 가지(공식 문서 kb/1223): 정책 파일 `funnel` nodeAttr · HTTPS 인증서 켜기(10/7 꺼져 있음) · MagicDNS. 그다음 NAS 에서 `tailscale funnel` 실행 · 가정 회선 업로드 속도와 NAS 가동률이 곧 영상 가용성 · 문서에 «Funnel 트래픽은 조절할 수 없는 대역폭 제한을 받는다»(수치 없음) · 포트는 443 · 8443 · 10000 만 |
| B. Cloudflare Tunnel | NAS 도커에 cloudflared | 캐시가 앞에 붙어 회선 부담이 준다 | 도메인이 Cloudflare 에 있어야 함 · 10/7 현재 우리 도메인 없음(foothold-project.vercel.app 뿐) |

둘 다 서버 쪽에 **Range 요청(영상 탐색)과 CORS(다른 주소에서 재생)** 가 되어야 한다. 켜면 첫 단계에서 이 둘을 실측한다.

## 단계와 관문

1. **복사** · NAS 공유 폴더를 붙이고 `foothold/media/site/` 로 345개를 복사 → sha256 전수 대조(목록과 다르면 멈춤). 갤러리 유일본 192개가 여기서 처음으로 두 곳에 있게 된다.
   - **결과 (10/7):** `_out/tools/nas_media_copy.py` 로 345/345 복사 · 580.5 MiB · 276 초. 복사본마다 sha256 을 목록과 대조해 불일치 0 · 원본 변경 0 · 원본 없음 0. 다른 구현(`sha256sum -c MANIFEST.sha256`)으로 NAS 에서 다시 읽어 345개 전부 일치. 목록은 `N:/media/site/MANIFEST.sha256`, 보고는 `copy-report.json`.
   - 관문 시험: 일부러 틀린 sha256 한 행 → 종료 코드 1 · 다시 돌리면 건너뜀 · 복사본 한 개를 훼손 → 그 한 개만 다시 복사. 세 경우 다 기대대로. 복사 중 불일치(`dest_mismatch`) 경로는 일부러 만들지 못해 시험하지 않았다.
2. **서빙** · 안 A 또는 B 를 켜고 영상 하나로 Range·CORS·속도 실측.
3. **빌드** · `MEDIA_BASE` 상수 하나. 비어 있으면 지금과 똑같이 동작(되돌리기 = 상수 비우기). 채우면 위 네 모양을 교체하고 미러에서 영상을 뺀다. 관문: 미러에 영상 0개 · 교체한 주소가 전부 NAS 목록(sha256)에 있음.
4. **검증** · 실제 서빙 주소에서 덱·갤러리·문서 페이지 영상 재생 확인(로컬 시험만으로 통과시키지 않는다).
5. **Vercel 정리** · 대시보드에서 배포 보존 기간을 줄이거나 옛 배포 삭제(팀장 계정 작업). 이것을 해야 10 GB 가 실제로 내려간다.
6. site 저장소 git 4.3 GiB 의 옛 영상 이력 정리는 별도 판단(이력 재작성이라 팀장 결정).

## 10/7 밤 실측과 조사 (v0.3)

**영상 크기** · 345개 · 중앙값 1.28 MiB · 90 % 가 2.64 MiB 이하 · 5 MiB 넘는 것 3개(덱 원본 74.2 · 17.3 · 11.7 MiB). 10 GB 가 찬 까닭은 한 벌이 커서가 아니라 배포마다 858 MB 가 통째로 보관돼 쌓여서다. site 저장소는 브랜치 1개 · 배포 전부 Production 이라 «브랜치 preview 가 주범» 가설은 해당 없음(조사 문서 1절의 미확인 가설).

**속도 (워크스테이션에서 잼 · 우리 회선이 양쪽 다 상한일 수 있음)**

| 경로 | 74.2 MiB 한 파일 | 작은 클립 |
|---|---|---|
| Vercel 지금 | 12.5 초 · 약 50 Mbit/s · 첫 바이트 3.2 초 | 4.1 MiB 0.56 초 · 1.3 MiB 0.94 초 · Range 206 |
| NAS 직접(SMB 무버퍼) | 9.3 초 · 약 67 Mbit/s | (345개 연속 평균 3.9 MiB/s) |
| Funnel | **미측정** · 켜야 잴 수 있음 · 한도 비공개 | |

**NAS 사실** · Tailscale 직결(DERP 아님) 9 ms · NAS 는 다른 공인 IP(다른 장소). Tailscale 은 UGOS 안에 격리돼 SSH 계정(sudo 없음 · docker 권한 없음)으로는 `tailscale funnel` 을 못 부른다. 공유 `foothold`(= /volume1/foothold) 와 별개로 `/volume1/01_AI_WORK/인공지능사관학교/` 는 워크스테이션 바탕화면의 SyncSpace 동기본이라 foothold-site 영상 345개가 이미 있지만, 3단계에서 사이트가 영상을 빼면 같이 사라지므로 원본 자리로 못 쓴다.

**조사 요약** (`RESEARCH-hosting-domain-20261007.md` · 출처 전부 10/7)
- Vercel 10 GB = Hobby Deployment Storage(8/21 신설). 넘으면 «배포가 막힐 수 있다». 10/7 배포는 성공.
- Funnel: HTTPS 인증서 켜면 기기 이름 · tailnet 이름이 공개 CT 로그에 영구히 남는다(접근 통제는 그대로). 정책 `funnel` nodeAttr 는 권한만 준다. 한도 비공개 · *.ts.net 주소만.
- B Cloudflare Tunnel 은 도메인이 필요하고, 무료 CDN 으로 영상을 내보내는 것은 Cloudflare 약관이 제한한다. 차선은 도메인 없이 GitHub Pages 영상 전용 저장소(서울 엣지 · Range · CORS 실측 · 1 GB 한도), 도메인을 사면 Cloudflare R2 + media.<도메인>.
- foothold.dev 는 이미 등록됨(다른 업체). 빈 후보 footholdlab.dev · foothold-project.dev · foothold.kr. 원화 증빙은 가비아(.dev 31,900원/년 VAT 포함).

**다음** · 팀장 결정 둘(원본 자리 · Funnel 켜기) → Funnel 실측 관문(외부 LTE 에서 5 MB 클립 단일 속도 · 20개 동시 완료 시간 · 오류 수 · Vercel 값과 비교) → 통과하면 3단계.

## 판 이력

| 판 | 날짜 | 무엇 | 왜 |
|---|---|---|---|
| v0.1 | 2026-10-06 | 실측·원인·단계 초안 | Vercel 배포 저장소 10 GB 100 % 메일 |
| v0.3 | 2026-10-07 | 속도 실측 · NAS 사실 · 호스팅 · 도메인 조사 | 팀장 질문(Funnel 설정 · 속도 · 대안 · 도메인 · 경로) |
| v0.2 | 2026-10-07 | 1단계 결과 · 단위 MB→MiB 정정 · Funnel 조건 | 팀장이 #511 을 lead 에 맡기고 NAS 를 붙임 |

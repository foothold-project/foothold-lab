> 분류: 조사 (M2 · 영상 · PDF 미디어 서버를 NAS Funnel 에서 Cloudflare 로 옮기는 안)
> 작성: 오흥재 · 2026-10-09 00:30 (lead 하위 조사 · pages.dev ICN 은 lead 가 재확인)
> 근거: Cloudflare · Vercel · GitHub · bunny.net · Backblaze 공식 문서 (2026-10-09 00:07~00:29 열람, 문서마다 «Last updated» 병기) + 사무실 KT 망(AS4766) curl 실측 + NAS 원본 파일 실측
> 요지: R2 는 우리 규모에서 월 $0. 카드(또는 PayPal) 등록은 사실상 필요, 도메인은 필요 없다. 권장은 R2 + Pages Function(pages.dev). KT 망에서 pages.dev 만 서울(ICN)로 들어가고 workers.dev · r2.dev 는 미국으로 갔다.
> 상태: 조사 끝 · 결정 대기. 아무 계정도 만들지 않았고 로그인 · 결제 화면에 들어가지 않았다.

## 요약 (팀장용)

**팀장이 해야 할 것**
1. Cloudflare 계정 1개 (이메일 인증). Workers · Pages 무료 사용 자체는 카드가 필요 없다 [S8][S42].
2. R2 켜기: 대시보드에서 R2 구독 checkout 을 직접 마친다 [S20]. 공식 문서에 «카드 필수» 문장은 없지만, 무료 범위만 써도 결제수단을 넣어야 했다는 보고가 일관된다 [S40]. 받는 수단은 Visa · Mastercard · AmEx · Discover · UnionPay 카드, PayPal, Apple Pay, Google Pay, Link [S21]. 국내전용 카드 가능 여부는 미확인이라 해외결제 카드나 PayPal 을 준비한다.
3. 업로드 권한은 팀장 PC 에서 직접: `wrangler login --use-keyring` (브라우저 OAuth, Windows 자격 증명 관리자 보관) 또는 버킷 하나로 묶은 R2 API token 을 만들어 `rclone config` 에 넣는다. 값은 채팅에 쓰지 않는다 [S28][S29][S30].
4. 도메인: 권장 경로에는 필요 없다. 사면 .dev 첫해 $8.20 · 갱신 $12.20/년, .com $10.46/년 (Cloudflare 공식 검색 화면 10/9 00:13) [S26].

**우리 규모 월 비용: $0** (도메인 제외)
5. 저장 0.63 GB (무료 10 GB-month) · 첫 업로드 PUT 약 352회 (무료 Class A 월 100만) · 재생 GET 월 약 7만~33만 추정 (무료 Class B 월 1,000만) · egress 무료 [S1][M1]. 추정 근거는 1절.
6. Worker 나 Pages Function 을 앞에 두면 요청이 일 약 2천~1.1만 (무료 일 10만, 00:00 UTC 초기화) [S7][S17].

**도메인 없이 되는가: 된다.** 세 갈래 (3절)
7. r2.dev: 문서가 non-production · rate-limited 로 못 박고 캐시도 없다 [S2][S3]. 시험용.
8. Worker(workers.dev) + R2 binding: 정식 경로지만 KT 망에서 workers.dev 는 미국(PDX · LAX · SEA)으로 들어갔다 [M3].
9. Pages Function(pages.dev) + R2 binding: 같은 코드인데 KT 망에서 pages.dev 는 서울(ICN)로 들어갔다 [M2].

**권장 경로 하나: R2 (Standard, location hint apac) + Pages Function (pages.dev) + vercel.json 307 한 줄 교체**
10. 속도: KT 망에서 pages.dev 대역만 ICN (TCP 연결 15 ms, 정적 mp4 첫 바이트 0.11~0.16 s, 6~7 MB/s). workers.dev · r2.dev 대역은 미국 (TCP 132~169 ms, r2.dev 첫 바이트 0.6~0.9 s, 2.3 MB/s) [M2][M3][M4][M8].
11. 비용 · 조건: 도메인 없이 $0. R2 Class B 는 무료 범위의 1~3 %, Function 요청은 일 한도의 2~11 % 추정 (위 5 · 6).
12. Range: Function 이 R2 `get(key, {range: request.headers})` 로 필요한 바이트만 읽고 206 + Content-Range 를 직접 만든다 [S9]. 공식 예제는 Range 요청에도 200 을 돌려주므로 그대로 쓰면 안 된다 [S10]. iOS Safari 는 byte-range 지원이 필수다 [S38].
13. 약관: R2 에 둔 영상은 2023 개정 뒤 CDN 영상 제한의 예외로 명시된 경로다 [S22][S24].
14. 위험: (a) Cloudflare 는 새 프로젝트를 Workers 로 시작하라고 권한다(Pages 는 유지) [S17]. (b) pages.dev 이름은 Cloudflare 가 1주 예고로 바꿀 수 있다 [S23]. (c) SKB · LGU+ · 모바일 망은 안 쟀다. (d) Function + R2 의 실제 첫 바이트는 계정이 없어 못 쟀다 (미확인). 첫 배포 뒤 `/cdn-cgi/trace` 와 `curl -r` 로 재고 확정한다.
15. 버린 길: 영상을 Pages · Workers 정적 자산으로 바로 올리기. 파일당 25 MiB 한도(FULL_v6.mp4 77.8 MB 1개 초과)이고 [S7][S16], pages.dev 정적 mp4 가 Range 를 무시하고 200 전체를 보냈다 [M5].
16. 차선: 카드를 못 쓰면 GitHub Pages ($0 · ICN · 206 실측, 단 사이트 1 GB · 월 100 GB soft · 공개 저장소) [S36][M6]. 코드 없이 가장 단순한 유료는 bunny.net (월 약 $1~3.5, 선불 $10, 서울 PoP 실측) [S34][M7].
17. 도메인을 사서 R2 custom domain 에 붙이는 길은 코드가 없고 캐시가 되지만, 무료 zone 이 받는 IP 대역이 KT 망에서 미국으로 가면 지금보다 빠르다고 단정 못 한다 (미확인) [S2][M4].

---

## 0. 우리 조건 재측정 [M1]

NAS `\\100.80.160.84\foothold\media\site` 를 읽기만 해서 쟀다 (2026-10-09 00:10~00:21).

| 항목 | 값 |
|---|---|
| mp4 | 345개 · 608.7 MB (580.5 MiB) · 중앙 1.34 MB · 90 % 2.75 MB · 최대 77.8 MB (`assets/mvp-deck/media/FULL_v6.mp4`) |
| PDF | 7개 · 19.6 MB |
| 합계 | 352개 · 628.3 MB |
| 25 MiB 넘는 파일 | 1개 (FULL_v6.mp4, 74.2 MiB) |
| mp4 재생 시간 합 | 2,802.7 s = 46.7 분 (ffprobe, 실패 0) · 중앙 5.6 s · 최대 83.6 s |
| moov 위치 | 앞(faststart) 247개 · 뒤 98개. 다른 세션의 10/8 `moov_end_list.txt` 도 98개였다 |
| 페이지의 `<video>` | axis2 페이지 3개 모두 `preload="none"` · autoplay 없음 · `crossorigin` 없음 (Chrome 에서 DOM 확인) |

## 1. R2 요금 · 무료 범위 · 우리 월 비용

공식 요금 [S1] (Last updated Oct 1, 2026):

| | Standard | Infrequent Access |
|---|---|---|
| 저장 | $0.015 / GB-month | $0.01 / GB-month |
| Class A (PutObject · ListObjects · CreateMultipartUpload · UploadPart · CompleteMultipartUpload 등) | $4.50 / 100만 | $9.00 / 100만 |
| Class B (GetObject · HeadObject 등) | $0.36 / 100만 | $0.90 / 100만 |
| 꺼낼 때 처리비 | 없음 | $0.01 / GB |
| egress | 무료 (Workers API · S3 API · r2.dev 모두) | 무료 |

- 무료 범위 (매월): 저장 10 GB-month, Class A 100만, Class B 1,000만. **Standard 에만 적용**, Infrequent Access 는 무료 범위 없음 [S1].
- 단위는 올림: 100만 1건이면 200만으로 청구, 1.1 GB-month 면 2 GB-month [S1].
- 저장량은 «하루 최대치의 30일 평균» [S1].
- 권한 없는 요청(401)은 과금하지 않는다 [S1].

**우리 월 비용 계산**
- 저장: 0.63 GB → 올림 1 GB-month < 무료 10 → $0 [S1][M1]. 지금 속도로 늘어도 10 GB 까지 여유 약 16배.
- Class A: 첫 업로드 352 PUT + 목록 조회 몇 번. 100 MB 안팎은 단일 PUT 이 권장이라 [S31] 대부분 1건씩. → 무료 100만의 0.04 % → $0.
- Class B (재생): 근거와 추정.
  - 지난달 Vercel Fast Data Transfer 117 GB (영상이 주 원인, 팀장 제공). mp4 평균 1.764 MB 로 나누면 «파일 한 벌 전송» 약 6.6만 회/월. HTML 도 섞인 숫자라 위쪽 한계로 쓴다.
  - 1회 재생당 GET: Chrome 은 보통 `Range: bytes=0-` 한 번으로 받아 내려가고, moov 가 뒤에 있는 98개는 끝부분을 한 번 더 읽는다. Safari 는 `bytes=0-1` 로 먼저 묻고 다시 받는다 [S43]. 탐색(seek)마다 1회 더. 그래서 1~5 GET 로 잡았다. **브라우저로 직접 세지는 못했다** (Chrome 확장이 미디어 요청을 잡지 못함). 미확인.
  - 6.6만 × 1~5 = 월 약 7만~33만 GET → 무료 1,000만의 0.7~3.3 %. 10배로 틀려도 33 % → $0.
- egress: 무료 [S1].
- **합계 $0/월.** 넘으면 Class B 100만당 $0.36 [S1].

## 2. 결제수단이 꼭 필요한가

- 공식 Get started 는 «R2 구독이 있는 계정이 필요하고, 없으면 대시보드에서 checkout 을 마쳐 R2 구독을 추가하라», «무료 사용분이 포함되어 있고 사용량은 월별 청구» 라고만 적는다 [S20]. 카드 «필수» 문장은 공식 문서에서 못 찾았다 (미확인).
- 실제 사용자 보고는 일관되게 «무료여도 카드 요구»: r/CloudFlare 2026-03-27 글 [S40], 2025-10-23 R2 입문 글 «결제 정보 추가» 단계 [S40]. 10/7 다른 세션 조사도 같은 판단(공식 미확인)이었다.
- 받는 결제수단 [S21]: Visa · Mastercard · American Express · Discover · UnionPay · PayPal · Apple Pay · Google Pay · Stripe Link. 선불 · 기프트 카드는 거절될 수 있다. 3D Secure 를 요구하는 지역 카드는 발급사 인증 단계가 뜬다.
- 한국 카드: 위 브랜드의 해외결제 카드면 목록상 가능. 국내전용 카드 · 한국 PayPal 계정의 실제 통과 여부는 미확인.
- 알아 둘 것 [S21]: 사용량 과금 서비스는 Cloudflare 가 청구 주기 중 카드를 임시 승인(preauthorize)할 수 있다. 결제수단이 실패하면 R2 버킷 접근이 막히고(요청이 오류), 30일 안에 안 고치면 데이터가 지워질 수 있다.
- Workers · Pages 는 기본이 Free 플랜이라 카드 없이 쓴다 [S8]. Cloudflare 제품 페이지 하단 문구도 «무료 시작에 카드 불필요» [S42]. **카드는 R2 때문에만 필요하다.**

## 3. 공개 주소 방법별 조건

### 3a. r2.dev (도메인 없이, 코드 없이)
- 문서 [S2] (Sep 25, 2026): r2.dev 는 Cloudflare 가 관리하는 개발용 주소이고 non-production 트래픽용이라고 적는다. rate limit 이 걸리고 개발 목적으로만 쓰라고 한다. 캐시 · WAF · 접근 제어 · bot management 는 r2.dev 에서 안 된다. r2.dev 로 CNAME 을 거는 것은 지원하지 않는 경로라고 한다.
- 한도 [S3] (Jun 8, 2026): 가변 rate limit. 초당 수백 요청을 넘으면 429, 대역(throughput)도 조일 수 있다.
- 캐시: 없음 [S19]. 요청마다 버킷까지 간다.
- 실측 [M8]: 남의 공개 r2.dev 버킷 2개, KT 망에서 colo=LAX, TCP 133~146 ms, 첫 바이트 0.61~0.86 s (1회 1.73 s), 5 MB 구간 2.3 MB/s, Range 206 정상. 버킷 위치는 모른다.
- 판단: 우리 트래픽은 rate limit 에 안 닿겠지만 문서가 운영용이 아니라고 명시. 1차 시험 주소로만.

### 3b. 사용자 도메인 (R2 custom domain)
- 도메인은 **R2 버킷과 같은 계정의 zone** 이어야 한다 [S2].
- Cloudflare 가 관리하지 않는 도메인이면 문서는 partial(CNAME) setup 을 쓰라고 한다 [S2]. 그런데 partial 은 **Business · Enterprise 만**(Free · Pro 불가)이고, Cloudflare Registrar 도메인에는 지원되지 않는다 [S4]. Free · Pro 는 full(primary) setup 만 된다 [S5].
- 그래서 무료 플랜에서는 **네임서버를 Cloudflare 로 옮기는 full setup 이 필수**다. Registrar 에서 사면 처음부터 Cloudflare 네임서버다 [S6][S25].
- 얻는 것: 캐시 (mp4 · pdf 는 기본 캐시 확장자, Free 의 캐시 가능 파일 크기 512 MB) [S19], Smart Tiered Cache 가 Free 에서도 된다 [S19], Range 는 캐시가 처리한다 [S19]. 코드 없음.
- 모르는 것: 무료 zone 이 받는 IP 대역과 그 대역의 KT 망 경로. 같은 Cloudflare 라도 대역마다 ICN · 미국이 갈렸다 [M4]. 사기 전에는 잴 수 없다 (미확인).

### 3c. 도메인 없이: Worker (workers.dev) + R2 binding
- 무료 한도 [S7] (Sep 5, 2026): 요청 일 10만 (00:00 UTC = 09:00 KST 초기화, 넘으면 Error 1027) · 요청당 CPU 10 ms (네트워크 대기는 CPU 시간에 안 셈) · 메모리 128 MB · subrequest 50 · 응답 본문 크기 제한 없음.
- 요금 [S8] (Oct 2, 2026): Free 는 일 10만 요청. Paid 는 계정당 월 최소 $5, 월 1,000만 요청 포함.
- workers.dev 는 Free 웹사이트로 취급되고, 문서는 운영 Worker 는 route 나 custom domain 에 두라고 권한다 [S14].
- Range: R2 `get()` 의 `range` 옵션은 offset · length · suffix 또는 요청 Headers 를 그대로 받는다 [S9]. 돌려받은 객체의 `range` 와 `size` 로 206 · Content-Range 를 직접 만들어야 한다. 공식 사용 예제는 이걸 안 하고 200 으로 돌려준다 [S10].
- Cache API [S11][S12]: 객체 최대 512 MB, Free 는 요청당 호출 50회. 데이터센터 안에서만 저장되고 tiered cache 와 안 맞는다. `cache.put` 은 206 응답을 거부하고, `cache.match` 는 전체 응답(Content-Length 있음)을 저장해 두면 Range 요청에 206 을 만들어 준다. 문서는 custom domain 의 Worker 와 Pages Functions(pages.dev 포함)에서 «동작한다» 고만 적는다. **workers.dev 에서의 동작은 미확인.**
- Workers Cache (2026-10-03 문서, 새 기능) [S13]: Worker 응답을 Cloudflare 가 캐시하고, Range 요청은 Range 를 떼고 Worker 에서 전체 200 을 받아 저장한 뒤 206 으로 잘라 준다. tiered 가 기본. 다만 캐시 적중도 Worker 요청 1건으로 센다. **Free 플랜에서 쓸 수 있는지는 문서에 없다 (미확인).**
- 실측 [M3]: 남의 workers.dev 3개, KT 망에서 colo=PDX · LAX · SEA, TCP 141~155 ms, 첫 바이트 0.50~0.75 s.

### 3d. 도메인 없이: Pages Function (pages.dev) + R2 binding (권장)
- Pages Functions 는 R2 binding 을 지원한다 [S17]. 요청은 Workers 요청으로 세고 Free 는 Workers 와 합쳐 일 10만 [S17]. 정적 자산 요청은 무료 · 무제한 [S17].
- Cache API 가 pages.dev 에서도 동작한다고 문서가 적는다 [S11].
- Pages 개요 문서는 새 프로젝트를 Workers 로 시작하라고 권한다(Pages 폐지는 아님) [S17].
- 실측 [M2]: 남의 pages.dev 3개, KT 망에서 colo=ICN, TCP 15~19 ms, 2.68 MB 정적 mp4 첫 바이트 0.11~0.16 s, 5.9~7.0 MB/s.
- 같은 Function 코드가 ICN 에서 돌고 거기서 R2 버킷까지 읽으러 간다. 버킷이 어느 도시에 생기는지는 문서에 없다 (3절 8 참고, 미확인).
- 코드 뼈대 (미시험): `[[path]].js` 에서 `env.MEDIA.get(key, {range: request.headers})` → `obj.writeHttpMetadata(h)` · `accept-ranges: bytes` · Range 가 있으면 `content-range: bytes {offset}-{offset+length-1}/{size}` 와 206, 없으면 200. Content-Type 은 업로드 때 넣은 값이 그대로 나간다 [S9].

### 3e. 버린 길: 정적 자산에 영상 직접
- 파일당 25 MiB (Pages · Workers static assets 둘 다), Free 파일 수 20,000 [S7][S16]. FULL_v6.mp4 하나가 넘는다 [M1].
- Range: 남의 pages.dev mp4 3개에 `Range: bytes=0-1` 을 보냈더니 모두 200 전체 (Accept-Ranges 없음) [M5]. Workers static assets 는 직접 못 쟀지만 같은 asset-worker 소스에 Range 처리 코드가 없다 [S41] (미확인). iOS Safari 는 byte-range 필수라 [S38] 못 쓴다.

## 4. 약관: Cloudflare 가 CDN 으로 «영상» 을 언제 막는가

- 현행 Service-Specific Terms, «Content Delivery Network (Free, Pro, or Business)» 항 [S22] (Last updated: September 28, 2026). Enterprise 가 아니면 영상과 큰 파일을 CDN 으로 내보낼 때 Cloudflare 의 특정 유료 서비스를 쓰라고 한다. 그 서비스는 원문으로 "Paid Services (e.g., the Developer Platform, Images, and Stream) that you must use" 다. 그런 서비스 없이 영상이나 지나친 비율의 큰 파일을 내보내면(또는 그렇다고 의심되면) CDN 사용을 끄거나 제한할 수 있고, 통지는 «합리적 노력» 수준이다.
- 2023-05-16 개정 블로그 [S24]: 예전 Self-Serve Subscription Agreement 2.8 조를 없애고 이 제한을 CDN 전용 조항으로 옮겼다. 제한은 CDN 에만 적용된다. Stream · Images · **R2** 처럼 Cloudflare 가 직접 호스팅하는 콘텐츠면 CDN 으로 영상 · 큰 파일을 내보내도 된다고 밝혔다. Cloudflare 밖에 둔 영상은 여전히 제한.
- Developer Platform 조항 [S23] (Workers · Pages · R2 등 포함): 네트워크에 과한 부담이면 저장 · 요청을 일시 제한할 수 있다. Developer Platform 은 콘텐츠 호스팅에 쓸 수 있다고 명시. workers.dev · pages.dev 이름은 Cloudflare 가 바꿀 수 있고 최소 1주 전 통지를 «시도» 한다(custom domain 은 해당 없음).
- 우리 경로에 대입:
  - R2 + custom domain · R2 + Worker · R2 + Pages Function: 영상이 R2 에 있으므로 블로그가 명시한 허용 경로. 위험 낮음.
  - NAS 를 Cloudflare Tunnel 로 · B2 + Cloudflare CDN: Cloudflare 밖에 둔 영상 → 제한 대상. 위험 있음.
  - «무료 범위만 쓰는 R2» 가 조항의 «Paid Services» 에 드는지는 문구상 분명하지 않다 (미확인). 블로그는 유료 여부를 따지지 않고 «R2 가 호스팅하면» 이라고 썼다.

## 5. Cloudflare Registrar

- 원가 판매: 등록처(registry)와 ICANN 이 받는 값만 받고 마진 없음 [S25].
- 가격 (Cloudflare 공식 검색 화면 `www.cloudflare.com/domains/search?q=foothold-project`, 2026-10-09 00:13 KST, 로그인 없이 열람) [S26]:
  - .dev: 첫해 $8.20, 갱신 $12.20/년
  - .com: $10.46/년 (갱신 같음)
  - 참고 .app 첫해 $8.20 · 갱신 $14.20
  - 같은 값을 제3자 집계(cfdomainpricing.com, Updated 2026-10-08)도 보여 준다 [S27].
  - 이 검색에서 foothold-project.dev · .com 은 «Buy now» 로 떴다. 문서상 확정 가용성 검사는 구매 단계에서 다시 한다 [S25] (미확인).
- 네임서버: Registrar 도메인은 자동으로 Cloudflare 네임서버를 쓰고, Registrar 에 있는 동안 다른 DNS 로 바꿀 수 없다 [S25]. partial setup 도 안 된다 [S4].
- 살 때 필요한 것 [S25]: 인증된 계정 이메일, ASCII 연락처(영문 주소), 결제수단, 약관 동의. 등록 뒤 ICANN 등록자 이메일 인증을 안 하면 도메인이 hold 되고 네임서버가 주차용으로 바뀐다.
- 다른 곳에서 사면 [S6]: Cloudflare 에 zone 추가(Free) → 받은 네임서버 2개를 등록처에 입력 → DNSSEC 가 켜져 있으면 먼저 끔 → 최대 24시간 대기 → zone Active 뒤 R2 custom domain 연결. 10/7 다른 세션 조사에 가비아 .dev 31,900원/년(VAT 포함)이 있으나 오늘 다시 재지 않았다 (미확인).

## 6. 올리는 방법 · 키 관리 · CORS

| 방법 | 345+7개 일괄 | 인증 | 판단 |
|---|---|---|---|
| `wrangler r2 object put <bucket>/<key> --file <path> --remote` | 명령 한 번에 객체 하나 (디렉터리 · 일괄 옵션 없음) [S28] | `wrangler login` 브라우저 OAuth. `--use-keyring` 이면 Windows 자격 증명 관리자에 키를 두고 토큰은 암호화 파일 [S28] | 키를 아예 안 만진다. 352번 반복 스크립트 필요. `--content-type` 를 직접 준다 |
| rclone (`rclone copy` · `rclone sync`) | 동시 업로드 [S29], 바뀐 것만 다시 올림 | R2 API token 의 Access Key ID · Secret. Secret 은 만들 때 한 번만 보인다 [S30]. 권한은 «Object Read & Write» 를 특정 버킷 하나로 [S30] | **일괄 · 증분에 가장 맞다.** rclone v1.59 이상 [S29] |
| S3 API (aws cli · boto3) | 됨, multipart 자동 [S31] | rclone 과 같은 키 | rclone 과 같은 급. 따로 쓸 이유 없음 |
| 대시보드 끌어다 놓기 | 됨 [S31] | 로그인 | 첫 시험 몇 개용 |

- 키를 채팅에 안 쓰는 법: 팀장이 대시보드에서 버킷 한정 토큰을 만들고, 팀장 PC 에서 `rclone config` 대화형 입력으로 넣는다. rclone.conf 는 기본이 평문이라 `rclone config` 의 «Set configuration password» 로 암호를 걸 수 있다 [S29]. 또는 `wrangler login --use-keyring` 만 쓰면 Access Key 자체가 없다 [S28].
- 재생 쪽 CORS: `<video>` 에 `crossorigin` 속성이 없으면 CORS 요청 없이 받아 오므로 필요 없다 (canvas 에 그릴 때만 필요) [S32]. 우리 페이지는 속성이 없고 [M1], 저장소에서 mp4 · pdf 를 `fetch()` 하는 코드도 못 찾았다(보안 문서 `.enc` 는 돌림 대상 아님). 지금도 307 로 다른 출처(NAS)에 보내 재생 중이다. 나중에 fetch · canvas 가 생기면 버킷 CORS 정책이나 Function 응답 헤더에 넣는다 [S32].
- 할 일 하나: 지금 빌드 관문(`web/_build/media_offload.py`)은 NAS 의 sha256 으로 «올라갔는지» 를 본다. R2 로 가면 같은 관문을 R2 기준으로 다시 짜야 한다.

## 7. 대안 비교

월 비용은 지난달 117 GB 를 영상 전송 위쪽 한계로 썼다. 속도는 사무실 KT 망 실측 [M#], 안 잰 칸은 미확인.

| 방식 | 월 비용 | 필요한 것 | 속도 (KT 망) | 한도 | 약관 위험 |
|---|---|---|---|---|---|
| R2 + Pages Function (pages.dev) **권장** | $0 [S1][S17] | 계정 · 카드/PayPal · 도메인 불필요 · 코드 약간 | 입구 ICN, TCP 15 ms [M2]. Function+R2 첫 바이트 미확인 | 일 10만 요청 · CPU 10 ms · R2 무료 범위 [S7][S1] | 낮음 [S24]. pages.dev 이름 변경 가능 [S23] |
| R2 + Worker (workers.dev) | $0 | 위와 같음 | 입구 미국 (PDX · LAX · SEA), TCP 141~155 ms [M3] | 위와 같음 | 낮음. workers.dev 는 운영용 비권장 [S14] |
| R2 + 사용자 도메인 | $0 + 도메인 $8.20~12.20/년(.dev) [S26] | 계정 · 카드 · 도메인 · 네임서버 이전 | 무료 zone 대역 경로 미확인. 비슷한 대역은 미국 [M4] | 캐시 512 MB/파일 [S19] | 낮음 [S24] |
| R2 r2.dev | $0 | 계정 · 카드 | LAX, 첫 바이트 0.6~0.9 s, 2.3 MB/s [M8] | rate limit · 캐시 없음 [S3] | 운영 사용 비권장 [S2] |
| Cloudflare Stream | 약 $5 + 재생 분 $1/1,000분 → 최대 약 $14 [S33] | 계정 · 카드 · 페이지 수정 (영상 ID 기반 주소) | 미확인 | 저장은 1,000분 단위 선불 [S33] | 낮음 |
| bunny.net (b-cdn.net) | 최소 $1, 아시아 $0.03/GB × 최대 117 GB ≈ $3.5. 저장 $0.01/GB [S34] | 계정 · 선불 $10 이상 (카드 · PayPal) · 도메인 불필요 [S34] | KR PoP, TCP 15~53 ms, 206 [M7]. 캐시 MISS 첫 바이트 0.27~1.36 s | 잔액 0 이하면 계정 정지, 60일 뒤 데이터 삭제 [S34] | 낮음 (CDN 이 본업) |
| Backblaze B2 + Cloudflare | 저장 10 GB 무료, CDN 경유 egress 무료 [S35] | B2 계정 · Cloudflare zone(도메인) | B2 지역은 미국 · 유럽 · 캐나다뿐 [S35]. 미확인 | B2 직접은 egress 저장량 3배까지 무료 [S35] | **있음**: Cloudflare 밖 영상 [S22][S24] |
| GitHub Pages (영상 전용 저장소) | $0 | GitHub 계정 · 공개 저장소(Free) · 카드 · 도메인 불필요 [S36] | Fastly ICN, TCP 14~24 ms, 206 [M6] | 사이트 1 GB (여유 약 370 MB) · 월 100 GB soft · 파일 100 MiB [S36] | 상업 금지 조항만. 저장소가 공개라 파일 목록이 다 보인다 |
| Vercel 로 되돌리기 | Hobby $0 / Pro $20 (1 TB 포함) [S37] | Pro 면 카드 | icn1, 첫 바이트 59~80 ms [M9] | Hobby 는 넘으면 «대개 30일 지나야 다시 사용» [S37]. 배포 저장소 10 GB 문제(오프로드 이유)도 그대로 | Hobby 는 비상업 · 개인 용도 [S37] |

## 8. 한국 · 일본 PoP 와 첫 바이트

- Cloudflare 네트워크 페이지: 한국 서울, 일본 도쿄 · 오사카 · 후쿠오카 · 나하 [S39].
- 그러나 **어느 PoP 로 들어가는지는 IP 대역과 ISP 경로가 정한다.** 사무실 KT 망(AS4766, IPv4)에서 IP 를 직접 지정해 `/cdn-cgi/trace` 를 3번씩 찍었다 [M4]:

| 대역 (어디서 본 IP) | colo | TCP 연결 |
|---|---|---|
| 172.66.x (pages.dev) | ICN · ICN · ICN | 9 ms |
| 162.159.140.x (1회만) | ICN | 8 ms |
| 172.67.x (workers.dev) | LAX · PDX · DFW | 132~169 ms |
| 104.21.x (workers.dev) | LAX · LAX · PDX (다른 호스트는 SEA) | 132~139 ms |
| 104.18.x (r2.dev) | LAX · LAX · LAX | 133~139 ms |
| 188.114.96.x | DFW · DFW · PDX | 136~167 ms |

- 요금제별 경로 정책을 밝힌 공식 문서는 못 찾았다 (미확인). 위 표는 KT 한 곳, 한 시점이다.
- R2 버킷 위치: 기본 Automatic (만드는 요청과 가까운 지역), 또는 location hint `apac` (Asia-Pacific). 도시는 문서에 없다. hint 는 버킷을 처음 만들 때만 먹고 최선 노력이다 [S18]. **버킷을 만들 때 `apac` 을 고른다.**
- 캐시는 버킷과 별개: r2.dev 는 캐시 없음 [S19]. custom domain 은 들어온 PoP 에 캐시하고 Smart Tiered Cache 가 버킷 가까운 상위 PoP 를 고른다 [S19]. Worker · Function 은 들어온 PoP 에서 돌고 R2 binding 읽기는 버킷까지 간다. Cache API 는 그 PoP 안에만 저장 [S12].
- 첫 바이트 기대치 (실측만): pages.dev 정적 0.11~0.16 s [M2] · r2.dev(LAX) 0.61~0.86 s [M8] · workers.dev(미국) HTML 0.50~0.75 s [M3] · GitHub Pages 적중 0.04 s [M6] · Vercel 0.06~0.08 s [M9] · 현재 NAS Funnel 바깥 0.3~4 s (팀장 제공). **Pages Function + R2(apac) 의 첫 바이트는 미확인**: ICN 입구 + ICN 에서 버킷까지 왕복이 더해진다. 신뢰할 만한 공개 실측은 못 찾았다.
- 참고: 사무실에서 잰 NAS Funnel (4~8 MB/s, 첫 바이트 0.05~0.17 s) 은 같은 건물 경로라 바깥 실측과 달라 비교에서 뺐다.

## 9. 권장 경로로 갈 때 순서 (승인 뒤)

팀장 (계정 · 결제 · 키):
1. Cloudflare 가입, 이메일 인증.
2. R2 checkout (카드 또는 PayPal).
3. 버킷 생성: 이름 정하고 Location 에서 Asia-Pacific(`apac`) 선택. 나중에 못 바꾼다 [S18].
4. 키: `npx wrangler login --use-keyring` 또는 버킷 한정 «Object Read & Write» 토큰 → `rclone config` (설정 암호 권장).
5. Pages 프로젝트 이름 결정 (= `<이름>.pages.dev`).

세션 (팀장 PC 의 인증을 빌려 실행, 키 값은 보지 않음):
6. NAS 의 `media/site` 를 같은 경로 키로 rclone sync. Content-Type 이 mp4 · pdf 로 들어갔는지 HEAD 로 확인 (rclone 의 확장자 추정 동작은 미확인).
7. Function 작성 · 배포. 관문: `curl -r 0-1` 이 206 + `Content-Range: bytes 0-1/<크기>`, 없는 키 404, `/cdn-cgi/trace` 가 ICN, FULL_v6.mp4 중간 구간 탐색.
8. 재생 시험: Chrome · iOS Safari 실제 기기.
9. 통과하면 `web/vercel.json` 의 영상 돌림 목적지와 `media_offload.py` 의 `MEDIA_BASE` 를 같이 바꾼다 (두 값이 다르면 관문이 막는다). 관문을 R2 기준으로 고친다.
10. 한 달 뒤 대시보드에서 Class B · Functions 요청 수를 보고 1절 추정을 고친다.

## 10. 확인 못 한 것 (미확인)

- R2 결제수단 «필수» 의 공식 문장. 국내전용 카드 · 한국 PayPal 통과 여부.
- Pages Function + R2(apac) 의 실제 첫 바이트 · 전송 속도. apac 버킷의 실제 도시.
- KT 외 망(SKB · LGU+ · 모바일 3사)에서 pages.dev · workers.dev · 무료 zone 대역의 경로.
- 무료 zone 이 받는 IP 대역.
- workers.dev 에서 Cache API 동작 여부. Workers Cache 의 Free 플랜 제공 여부.
- Workers static assets 의 Range 처리 (pages.dev 만 쟀다).
- 1회 재생당 GET 수 (브라우저로 못 셌다).
- 무료 범위만 쓰는 R2 가 약관의 «Paid Services» 에 드는지.
- Pages Function 이 일 10만을 넘었을 때의 정확한 응답 (Workers 는 Error 1027 [S7]).
- rclone 이 R2 에 Content-Type 을 확장자로 넣는지.

## 11. 측정 방법 [M]

- 때 · 곳: 2026-10-09 00:07~00:29 KST, 사무실 워크스테이션, KT (AS4766), IPv4 (IPv6 경로 없음).
- 남의 공개 주소에는 작은 Range GET 만 보냈다 (최대 5 MB 1회 × 2).
- [M1] NAS 파일: `find -printf %s` · `ffprobe format=duration` · mp4 최상위 atom 순서 파싱 (읽기 전용). 페이지 DOM 은 Chrome 탭에서 `document.querySelectorAll('video')` 로 확인.
- [M2] pages.dev: hono · localtubemanager · kuhnpohl-media `.pages.dev` 의 `/cdn-cgi/trace` → 모두 ICN. `localtubemanager.pages.dev/videos/import-export.mp4` (2.68 MB) 전체 GET 3회.
- [M3] workers.dev: static-links-page.signalnerve · pride-badges.pony · cute-cat-avatars.laosing-cors `.workers.dev` → PDX · PDX · PDX, 다시 잴 때 LAX · SEA.
- [M4] `curl --resolve demo.pages.dev:443:<IP> https://demo.pages.dev/cdn-cgi/trace` 를 IP 마다 3회. colo 는 IP 경로로 정해진다.
- [M5] 남의 pages.dev mp4 3개 (`video/mp4` 1개, SPA 폴백 2개)와 `demo.pages.dev` JS 1개에 `-r 0-1` · `-r 0-1023` → 전부 200 · 전체 크기.
- [M6] `https://pages.github.com/images/logo.svg` `-r 0-99` 3회 → 206, `x-served-by: cache-icn…`.
- [M7] `https://mdbcdn.b-cdn.net/img/video/Agua-natural.mp4` `-r 0-1023` 3회 → 206, `server: BunnyCDN-KR1-…`, `cdn-cache: MISS`.
- [M8] r2.dev: `pub-dd72…` 이미지 `-r 0-1023` 5회, `pub-969f…` ISO `-r 0-5242879` 2회, `pub-c713…` trace → 모두 LAX.
- [M9] `https://foothold-project.vercel.app/` 2회 → `x-vercel-id: icn1::…`. 영상 주소는 지금 307 → `ai-nas01.tail025053.ts.net`.
- [M10] `domains.cloudflare.com` 은 curl · WebFetch 에 403 이라 Chrome 으로 공개 검색 화면만 읽었다 (로그인 없음, 구매 버튼 안 누름).

## 12. 출처 (2026-10-09 열람)

- [S1] R2 Pricing · https://developers.cloudflare.com/r2/pricing/ (Oct 1, 2026)
- [S2] R2 Public buckets · https://developers.cloudflare.com/r2/buckets/public-buckets/ (Sep 25, 2026)
- [S3] R2 Limits · https://developers.cloudflare.com/r2/platform/limits/ (Jun 8, 2026)
- [S4] CNAME setup (Partial) · https://developers.cloudflare.com/dns/zone-setups/partial-setup/ (Aug 14, 2026)
- [S5] DNS setups · https://developers.cloudflare.com/dns/zone-setups/ (Aug 25, 2026)
- [S6] Full setup · https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/ (Jul 29, 2026)
- [S7] Workers Limits · https://developers.cloudflare.com/workers/platform/limits/ (Sep 5, 2026)
- [S8] Workers Pricing · https://developers.cloudflare.com/workers/platform/pricing/ (Oct 2, 2026)
- [S9] R2 Workers API reference · https://developers.cloudflare.com/r2/api/workers/workers-api-reference/ (Jul 31, 2026)
- [S10] Use R2 from Workers · https://developers.cloudflare.com/r2/api/workers/workers-api-usage/ (Aug 25, 2026)
- [S11] Cache API · https://developers.cloudflare.com/workers/runtime-apis/cache/ (Aug 14, 2026)
- [S12] How the Cache works · https://developers.cloudflare.com/workers/reference/how-the-cache-works/ (Jul 6, 2026)
- [S13] Workers Cache · https://developers.cloudflare.com/workers/cache/ · https://developers.cloudflare.com/workers/cache/configuration/ (둘 다 Oct 3, 2026)
- [S14] workers.dev · https://developers.cloudflare.com/workers/configuration/routing/workers-dev/ (Sep 22, 2026)
- [S15] Static assets billing · https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/ (Apr 23, 2026)
- [S16] Pages Limits · https://developers.cloudflare.com/pages/platform/limits/ (Sep 5, 2026)
- [S17] Pages Functions pricing · https://developers.cloudflare.com/pages/functions/pricing/ (Sep 8, 2026) · Pages Functions bindings · https://developers.cloudflare.com/pages/functions/bindings/ (Jun 25, 2026) · Pages 개요 · https://developers.cloudflare.com/pages/ (Aug 25, 2026)
- [S18] R2 Data location · https://developers.cloudflare.com/r2/reference/data-location/ (Aug 19, 2026)
- [S19] Enable cache in an R2 bucket · https://developers.cloudflare.com/cache/interaction-cloudflare-products/r2/ (May 7, 2026) · Tiered Cache · https://developers.cloudflare.com/cache/how-to/tiered-cache/ (Sep 29, 2026) · Default cache behavior · https://developers.cloudflare.com/cache/concepts/default-cache-behavior/ (Sep 14, 2026) · Range request behavior · https://developers.cloudflare.com/cache/reference/range-requests/ (Sep 14, 2026)
- [S20] R2 Get started · https://developers.cloudflare.com/r2/get-started/ (Apr 21, 2026)
- [S21] Billing policy · https://developers.cloudflare.com/billing/understand/billing-policy/ · Update billing information · https://developers.cloudflare.com/billing/get-started/update-billing-info/ (둘 다 May 29, 2026)
- [S22] Service-Specific Terms, Application Services (CDN 항) · https://www.cloudflare.com/service-specific-terms-application-services/ (Last updated: September 28, 2026)
- [S23] Service-Specific Terms, Developer Platform · https://www.cloudflare.com/service-specific-terms-developer-platform/ (September 28, 2026)
- [S24] Cloudflare 블로그 2023-05-16 «Goodbye, section 2.8» · https://blog.cloudflare.com/updated-tos/
- [S25] Cloudflare Registrar · https://developers.cloudflare.com/registrar/ · Register a new domain · https://developers.cloudflare.com/registrar/get-started/register-domain/ (둘 다 Apr 24, 2026)
- [S26] Cloudflare 공식 도메인 검색 · https://www.cloudflare.com/domains/search?q=foothold-project (2026-10-09 00:13 KST)
- [S27] cfdomainpricing.com (NameBeta 운영, 제3자) · https://cfdomainpricing.com/ (Updated 2026-10-08)
- [S28] Wrangler R2 commands · https://developers.cloudflare.com/workers/wrangler/commands/r2/ (Oct 1, 2026) · Wrangler general (login) · https://developers.cloudflare.com/workers/wrangler/commands/general/ (Sep 2, 2026)
- [S29] R2 rclone · https://developers.cloudflare.com/r2/examples/rclone/ (Apr 21, 2026) · rclone Configuration encryption · https://rclone.org/docs/#configuration-encryption
- [S30] R2 Authentication (API tokens) · https://developers.cloudflare.com/r2/api/tokens/ (Oct 1, 2026)
- [S31] R2 Upload objects · https://developers.cloudflare.com/r2/objects/upload-objects/ (Jul 29, 2026)
- [S32] R2 CORS · https://developers.cloudflare.com/r2/buckets/cors/ (Sep 23, 2026) · MDN `<video>` crossorigin · https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/video
- [S33] Stream Pricing · https://developers.cloudflare.com/stream/pricing/ (Sep 8, 2026)
- [S34] bunny.net · https://bunny.net/pricing/ · https://bunny.net/pricing/storage/ · https://bunny.net/network/ (Seoul 표기) · https://bunny.net/docs/billing/add-funds · b-cdn.net 기본 호스트명은 https://bunny.net/docs/cdn/quickstart (검색 요약으로만 확인)
- [S35] Backblaze B2 · https://www.backblaze.com/cloud-storage/pricing · 지역 https://www.backblaze.com/docs/cloud-storage-data-regions (검색 요약으로 확인)
- [S36] GitHub Pages limits · https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits · Large files · https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github
- [S37] Vercel Hobby · https://vercel.com/docs/plans/hobby (2026-09-14) · Vercel Pro · https://vercel.com/docs/plans/pro-plan (2026-09-15)
- [S38] Apple Safari Web Content Guide (보관 문서): iOS 미디어 서버는 byte-range 지원 필수 · https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/CreatingVideoforSafarioniPhone/CreatingVideoforSafarioniPhone.html
- [S39] Cloudflare Network · https://www.cloudflare.com/network/
- [S40] 사용자 보고: r/CloudFlare 2026-03-27 (보관본) · https://reddit.sentinel-team.org/posts/1s4bdml/snapshots/2026-03-27T05%3A28%3A13.67957Z · dev.to 2025-10-23 · https://dev.to/leonwong282/the-complete-beginners-guide-to-cloudflare-r2-image-hosting-2025-2g4k
- [S41] workers-sdk asset-worker 소스 · https://github.com/cloudflare/workers-sdk/tree/main/packages/workers-shared/asset-worker/src (handler.ts 마지막 커밋 2026-09-23)
- [S42] Cloudflare Registrar 제품 페이지 하단 문구 · https://www.cloudflare.com/domains/
- [S43] Safari 의 `bytes=0-1` 선행 요청 사례 · https://forum.gitlab.com/t/embedded-mp4-videos-no-longer-work-in-safari-on-gitlab-pages/44691

이전 조사와의 관계: 10/7 다른 세션의 `domain_hosting_research.md` 는 «R2 + 사용자 도메인» 의 한국 경로를 «서울 PoP 경유 (미확인 실측)» 로 적었다. 오늘 대역 실측 [M4] 으로는 무료 계열로 보이는 대역이 KT 망에서 미국으로 갔으므로 그 가정은 도메인을 산 뒤 다시 재야 한다. GitHub Pages 의 ICN · 206 은 오늘도 같았다 [M6].

# FOOTHOLD 영상 호스팅 · 도메인 조사

조사일 2026-10-07. 출처는 모두 이날 읽었다 (맨 아래 [번호] 목록). 확인 못 한 것은 「미확인」으로 적었다.
아무것도 구매·가입·신청하지 않았다. RDAP 조회와 공개 페이지 열람, 공개 파일 내려받기 시험만 했다.

## 요약

1. Vercel 「10 GB」는 Hobby 의 **Deployment Storage** 한도일 가능성이 가장 높다. 넘으면 배포가 막힐 수 있다고 Vercel 이 적었다 [V3]. 처방은 영상 580 MiB 를 배포물에서 빼는 것이다. 보호되는 preview 배포 수도 같이 본다.
2. 권장 경로: **A (Funnel) 를 무료로 먼저 켜고, 실측 관문을 통과할 때만 사이트 영상 주소를 바꾼다.** Funnel 대역 한도는 비공개이고 CDN 도 없다. 관문을 못 넘으면 도메인 없이 되는 **GitHub Pages 영상 전용 저장소** (서울 엣지·Range·CORS 실측 확인), 도메인을 사면 **Cloudflare R2 + media.<도메인>** 이 다음이다. 영상을 Cloudflare 무료 CDN(Tunnel 포함)으로 내보내는 것은 약관 조항 때문에 권하지 않는다 [C1].
3. Tailscale 관리 콘솔에서 할 일 셋. (1) Machines: NAS 이름 `ai-nas01` 확인. 이 이름은 공개 CT 로그에 영구히 남는다. (2) DNS: tailnet DNS 이름을 먼저 확정하고 **HTTPS Certificates → Enable HTTPS**, 공개 원장 동의. (3) Access controls: `funnel` nodeAttr 확인·추가. target 은 NAS 로 좁힌다. 그다음 NAS 에서 `tailscale funnel --bg --set-path=/media <영상 폴더 절대경로>`.
4. **foothold.dev 는 살 수 없다.** 2026-04-07 Porkbun 에서 등록됐고 다른 업체 사이트가 돌고 있다. RDAP 상 미등록 대안: footholdlab.dev, foothold-project.dev, foothold.kr, foothold.co.kr 등.
5. 등록처: 원화 세금계산서·현금영수증이 필요하면 **가비아** (.dev 31,900원/년 VAT 포함, 2년 63,800원 · .kr 23,100원/년). 해외 카드 영수증이 정산에 인정되면 **Cloudflare Registrar** (.dev 갱신 $12.20, 2년 약 2.7~3.3만원, 네임서버가 처음부터 Cloudflare). 어느 쪽이든 증빙 규정을 행정 담당에게 먼저 확인한다.

## 1. Vercel Hobby 의 10 GB

**어느 한도인가.** Hobby 에서 10 GB 인 항목은 둘이다.
- Deployment Storage: "Hobby teams include up to 10 GB" (2026-08-21 신설) [V2]. 빌드 출력과 정적 자산을 배포별로 보관하는 저장소다 [V4].
- Fast Origin Transfer: Hobby "First 10 GB" [V5]. CDN 과 Functions·Middleware·Blob·ISR 사이 전송이라 [V6] 정적 사이트는 거의 안 쓴다.
- 그래서 Deployment Storage 가 유력하다. 확정은 메일 본문의 자원 이름과 대시보드 Usage > Deployment Storage 로 한다 (미확인).

**넘으면 어떻게 되나.**
- 2026-09-16 공지: "going over the limit can block you from deploying until you free some up." [V3]
- 같은 공지: 10 GB 를 넘은 팀은 예외 밖 배포를 "deleted immediately instead of after 30 days." [V3]
- Hobby 일반 규칙: 한도를 넘으면 대개 30일 지나야 그 기능을 다시 쓴다 [V7].
- 사용량 초과로 사이트가 503 DEPLOYMENT_PAUSED 로 멈출 수 있다는 KB 는 있다 [V8]. Deployment Storage 초과만으로 사이트가 멈춘다는 문구는 못 찾았다 (미확인).

**지우면 풀리나.**
- "Retained deployment output contributes to Deployment Storage while Vercel stores it." [V1]
- 지운 배포는 30일 복구 기간에 들어간다 (Settings > Security > Recently Deleted) [V1]. 복구 기간 중인 배포가 저장량에 잡히는지는 문서에 없다 (미확인).
- 계량은 GB-month 다. 프로젝트별 하루 최대 저장량을 청구 기간 동안 더한다 [V4]. Hobby 10 GB 가 순간값인지 GB-month 인지는 문서가 구분하지 않는다 (미확인). 반영 시점도 "After Usage refreshes" 로만 적혀 있다 [V9].

**Retention 설정이 Hobby 에 있나.** 있다. "available on all plans" [V1]. 프로젝트 Settings > Security > Deployment Retention Policy. Hobby 는 2026-04-29 부터 최대 30일 [V10].
- 기간이 지나도 남는 예외 (Hobby): 마지막 배포 3개, Ready 상태 production 3개 [V1].
- 모든 플랜 공통 예외: production alias 배포, **활성 브랜치의 최신 preview** (브랜치가 안 지워졌고 PR 이 merge/close 안 됨) [V1].

**우리 숫자로 보면.** 보호 배포 6개 × 858 MB ≈ 5.1 GB 라 이것만으로는 10 GB 가 안 찬다. 그런데 origin 원격 브랜치가 126개다 (`git branch -r`). 브랜치마다 preview 가 빌드됐다면 활성 브랜치 최신 preview 가 각각 보호돼 주범일 수 있다 (미확인. Deployments 화면의 Preview 수로 확인). 브랜치별 빌드를 끄는 설정은 vercel.json `git.deploymentEnabled` 다 [V11].

**처방 순서.** 영상을 빼면 배포 1개가 약 250 MB (858 MB 에서 580 MiB ≈ 608 MB 를 뺀 값) 로 준다 · 머지된 브랜치 삭제 · 불필요한 preview 빌드 끄기. Vercel 도 "Do not package large videos ... into each deployment" 라고 적었다 [V9].

## 2. Tailscale

### 2a. HTTPS Certificates 를 켜면
- 하는 일: tailnet 기기에 공인 CA(Let's Encrypt) TLS 인증서를 발급할 수 있게 한다. 순서는 DNS 페이지 → MagicDNS 확인 → "Enable HTTPS" → 공개 원장 동의 [T1].
- 부작용 1: 인증서는 공개 Certificate Transparency 로그에 기록된다. **기기 이름과 tailnet DNS 이름**이 공개된다. "Do not enable the HTTPS feature if any of your machine names contain sensitive information." [T1]
- 단, 인증서를 실제로 받은 기기만 원장에 오른다. 접근 통제는 그대로다 [T1].
- 부작용 2: tailnet 이름은 기본 이름과 무작위 이름 사이에서만 바꿀 수 있다. 인증서는 tailnet 이름 기준이다 [T1]. 그래서 이름을 먼저 정한다.
- 부작용 3: 인증서를 자주 다시 받으면 Let's Encrypt 한도에 걸려 34시간 기다릴 수 있다 [T1].
- 되돌리기: DNS 페이지에서 Disable HTTPS 가능. 그러나 HTTPS 링크가 모두 깨진다. 발급된 인증서는 폐기(revoke)되지 않는다 [T1]. CT 로그는 추가 전용이라 기록은 남는다.

### 2b. `funnel` nodeAttr
- 정체: 정책 파일 `nodeAttrs` 의 속성이다. "This attribute tells Tailscale which tailnet users can use Funnel." [T2]
- 기본 모양: `{"target": ["autogroup:member"], "attr": ["funnel"]}` [T2][T3].
- 기본 정책에 이미 있나: 문서의 기본 정책(allow all) 예시에는 `acls` 와 `ssh` 만 있고 `nodeAttrs` 는 없다 [T4]. CLI 로 `tailscale funnel` 을 처음 실행하면 승인 화면을 거쳐 자동으로 추가된다. 콘솔 Access controls 의 "Add Funnel to policy" 로도 넣는다 [T2]. 우리 tailnet 정책에 이미 들어 있는지는 미확인. 콘솔에서 본다.
- 허용 범위: target 에 걸린 기기에서 `tailscale funnel` 을 쓸 권한이다. autogroup:member 는 직접 구성원의 기기 전체다 [T3]. 즉 구성원 누구나 자기 기기를 공개할 수 있게 된다. NAS 하나로 좁히는 편이 낫다.
- 주의: NAS 가 태그 기기라면 사용자 기기가 아니어서 autogroup:member 에 안 걸릴 수 있다 (미확인). 그때는 target 에 그 tag 를 넣는다.
- 이것만으로 노출되나: 아니다. 권한만 준다. 공개는 기기에서 funnel 명령을 실행해야 시작된다. 같은 포트에 마지막으로 serve 를 걸었으면 비공개, funnel 을 걸었으면 공개다 [T2].

### 2c. Funnel 대역과 위치
- 공식 문구: "Traffic sent over a Funnel is subject to non-configurable bandwidth limits." [T2] 숫자는 공개하지 않는다.
- Tailscale 직원 (HN, 2023-03-30): "there is a bandwidth limit, it's a funnel, not a hose. We don't announce what the bandwidth limit is" [T5].
- 실측 수치: 믿을 만한 공개 측정값을 못 찾았다 (미확인). 2026-09-28 글도 "no figure in megabits per second" 라고 적었다 [T6].
- 릴레이 위치: "ingress servers we operate around the world" 라고만 했다 [T5]. 아시아·한국 위치는 비공개 (미확인). DERP 서버 위치와 같은지도 미확인.
- 기타 제약: 베타 기능, Tailscale v1.38.3 이상, 포트 443·8443·10000 만, TLS 만, **tailnet 도메인(*.ts.net) 이름만** [T2]. 즉 media.<우리 도메인> 아래에 Funnel 을 둘 수 없다. 공개 DNS 반영에 최대 10분 [T2].
- 적합성 판단: 클립 345개 평균 1.7 MiB. 한국 시청자 수십 명이 동시에 여러 클립을 열면 수백 MiB 단위가 한꺼번에 나간다. 한도 비공개 + CDN 없음 + NAS 회선 업로드 한계 때문에 **문서만으로는 적합하다고 말할 수 없다.** 실측 관문을 둔다. 예: 외부 LTE 단말에서 5 MB 클립 단일 속도, 그리고 20개 병렬 내려받기의 완료 시간과 오류 수를 잰다.

### 2d. 디렉터리 직접 서빙과 Range
- 된다. funnel/serve 대상은 프록시·파일·디렉터리·텍스트 넷 중 하나다. 디렉터리를 주면 목록 페이지를 보여 준다 [T7][T8]. `--set-path` 로 경로 아래에 붙인다.
- Range: 소스 `ipn/ipnlocal/serve.go` 의 `serveFileOrDirectory` 가 Go 의 `http.ServeContent`(파일) 와 `http.FileServer`(디렉터리) 를 쓴다 [T9]. 둘 다 Range 요청을 처리한다. 그래서 탐색(seek) 은 될 것이다. 실제 206 응답은 켠 뒤 `curl -I -H "Range: bytes=0-1023"` 로 확인한다 (미확인).
- CORS: 파일 서버가 CORS 헤더를 붙이는 코드는 못 봤다. 일반 `<video src>` 재생은 CORS 가 필요 없다. fetch·canvas·`crossorigin` 속성을 쓰면 필요하다.
- 주의: 디렉터리 목록이 공개된다. 공개할 파일만 든 폴더를 가리킨다.
- UGREEN NAS: Tailscale 을 Docker 로 돌리는 안내가 있다 [T10]. 그러면 명령은 컨테이너 안에서 실행하고 영상 폴더를 볼륨으로 붙여야 한다. 우리 NAS 의 설치 방식은 미확인.

## 3. 대안 비교 (영상 0.6~2 GB, 월 수십 GB 수준 전송 가정)

| 방식 | 월 비용 | 도메인 | 한국 속도 | Range / CORS | 묶임 |
|---|---|---|---|---|---|
| Tailscale Funnel (NAS) | $0 | 불필요 (*.ts.net 만 가능) | 미확인 (한도·릴레이 비공개) | Range 코드상 됨 / 기본 없음 | 낮음 |
| Cloudflare Tunnel (NAS) + 무료 CDN | $0 + 도메인 | 필요 (Cloudflare 네임서버) | Cloudflare 서울(ICN) PoP 운영 [C6] | 됨 / 원본이 정함 | 낮음. 단 약관 위험 |
| Cloudflare R2 + 사용자 도메인 | $0 (10 GB-month·Class B 1천만 건 무료, 이그레스 무료) | 필요 (같은 계정 zone) | 서울 PoP 경유 (미확인 실측) | S3 GET 이라 됨 / 버킷 CORS 설정 | 낮음 (S3 API) |
| Backblaze B2 + Cloudflare | 10 GB 까지 무료, 이후 $6.95/TB | Cloudflare 를 거치려면 필요 | 미확인 | 됨 / 설정 | 낮음. Cloudflare 경유 시 약관 위험 같음 |
| Bunny Storage + CDN | 최소 $1/월 (아시아 $0.03/GB) | 불필요 (기본 *.b-cdn.net 주소, 문서 미확인) | 미확인 | 미확인 | 낮음 |
| Hugging Face dataset | $0 | 불필요 | 실측 약 3 MB/s, 첫 바이트 약 1 s | 206 확인 / `*` 확인 | 낮음 |
| GitHub Pages (영상 전용 저장소) | $0 | 불필요 | 서울 엣지 응답 확인 | 206 확인 / `*` 확인 | 낮음 |
| GitHub Releases | $0 | 불필요 | 미확인 | 206 확인 / CORS 없음 | 정식 용도 아님 |

근거와 단서.
- Cloudflare CDN 약관: Enterprise 가 아니면 영상·대용량 파일은 Developer Platform·Images·Stream 같은 유료 서비스로 내보내야 한다. 아니면 CDN 사용을 제한할 수 있다 [C1]. Tunnel 로 NAS 영상을 내보내도 CDN 을 거치므로 같은 조항에 걸린다. R2 는 Developer Platform 이라 허용 경로로 읽힌다. 무료 한도 사용분도 「Paid Services」 에 드는지는 문구상 미확인.
- R2 가격·무료 한도 [C2]. r2.dev 주소는 "rate-limited and should only be used for development purposes" [C3]. 사용자 도메인은 같은 계정의 zone 이어야 한다 [C3]. CNAME(partial) 설정은 Business 이상이라 [C4] 무료로는 네임서버를 Cloudflare 로 옮겨야 한다. R2 를 켜려면 결제수단 등록이 필요하다는 글이 많다 (공식 문서로는 미확인).
- Quick Tunnel(trycloudflare.com) 은 계정·도메인 없이 되지만 테스트용이고 동시 200 요청 한도다 [C5].
- B2: 첫 10 GB 무료, $6.95/TB/월, 저장량 3배까지 이그레스 무료, Cloudflare·bunny.net 등으로는 무료 [B1].
- Bunny: Storage $0.01/GB/지역, CDN 아시아·오세아니아 $0.03/GB, 월 최소 $1, 14일 시험 [B2][B3].
- Hugging Face: resolve 주소는 302 로 CDN 서명 주소에 넘긴다. 이 워크스테이션에서 7.3 MB 파일을 두 번 받았다. 2.2 s·2.5 s, 약 2.9~3.3 MB/s, 응답 IP 54.254.163.78. 익명 resolver 한도는 IP 당 5분 3,000건 [H1].
- GitHub Pages: 사이트 1 GB 이하, 월 100 GB 소프트 한도, 상업 서비스 금지 [G1]. 시험 응답 `X-Served-By: cache-icn...` (서울 엣지), 206, `Access-Control-Allow-Origin: *`. 현재 580 MiB 는 들어가지만 2 GB 로 늘면 못 쓴다.
- GitHub Releases: 파일당 2 GiB 미만, 총량·대역 한도 없음 [G2]. 시험 응답은 `application/octet-stream` + `attachment`, CORS 없음. `<video>` 재생 여부 미확인.
- 도메인이 있으면 영상 주소를 media.<도메인> 으로 고정할 수 있다. 뒤쪽 저장소를 바꿔도 페이지를 다시 안 고친다. 이것이 도메인의 실익이다.

## 4. 도메인

### 4a. foothold.dev 조회 (Google Registry RDAP [D1])
- HTTP 200. 등록처 Porkbun LLC. 등록 2026-04-07, 만료 2027-04-07. 네임서버 alexa·julio.ns.cloudflare.com. 상태 client delete/transfer prohibited.
- https://foothold.dev 는 200 으로 열리고 제목은 "Websites for Lancaster County Businesses & Organizations | Foothold". 운영 중인 다른 업체 도메인이다. **신규 등록 불가.**
- 다른 이름 RDAP 결과 (404 = 레지스트리에 등록 기록 없음. 예약·프리미엄 여부는 등록처 검색에서 다시 본다):

| 이름 | 결과 |
|---|---|
| footholdlab.dev · foothold-lab.dev · footholdproject.dev · foothold-project.dev · teamfoothold.dev | 404 (미등록) |
| foothold.kr · foothold.co.kr · footholdlab.kr (KISA RDAP) | 404 (미등록) |
| foothold.app | 2020-09-27 등록 (Cloudflare) |
| foothold.com | 1996-03-07 등록 |
| footholdlab.com | 2026-09-21 등록 (호스팅케이알 검색에도 「이미 사용중」) |
| foothold.io | 미확인 (rdap.org 응답 없음) |

- 검증: 같은 RDAP 에 google.dev, kisa.or.kr, naver.kr 는 200 이 나왔다. Squarespace 검색도 footholdlab.dev 를 "Exact match" 가격과 함께 보여 줬다.

### 4b. .dev 특성
- TLD 전체가 HSTS preload 목록에 있다. 모든 .dev 사이트는 HTTPS 만 된다 [D2]. 서브도메인도 같다. NAS 를 http 로 직접 물리면 안 열린다. Vercel·Cloudflare 는 인증서를 자동으로 준다.
- 등록 자격 제한 없음. "anyone can register a .dev domain" [D3].

### 4c. 가격 (1년 기준, 2026-10-07 화면 값. 할인은 「할인」 표시)

| 등록처 | .dev 첫해 | .dev 갱신 | .com | .kr | 통화·VAT | WHOIS 비공개 | 네임서버를 Cloudflare 로 | 증빙 |
|---|---|---|---|---|---|---|---|---|
| Cloudflare [D4][D5][D6] | $8.20 [D6] 또는 $12.20 [D5] | $12.20 | $10.46 | 목록에 없음 | USD. 한국 VAT 부과 여부 미확인 [D7] | 무료 | 자동. 다른 네임서버로는 못 바꾼다 | 대시보드 인보이스 (영문·USD). 세금계산서 아님 |
| Porkbun [D8] | $8.75 | $12.87 | $11.08 | 취급 안 함 | USD | 미확인 | 가능 (미확인) | 카드·PayPal 등 [D9]. 영수증 형식 미확인 |
| Namecheap [D10] | $10.98 (할인, 정가 $15.98) + ICANN $0.20 | $20.98 | $10.98 (할인, 정가 $14.98) | 미확인 | USD | 무료 | 가능 (미확인) | 미확인 |
| Squarespace [D11] | ₩42,653 | 미확인 | ₩28,435 (첫해 할인 ₩14,218) | ₩43,058 | 원화 표시. 실제 결제 통화·VAT 미확인 | 무료 | 미확인 | 미확인 |
| 가비아 [K1] | 31,900원 | 미확인 (등록비와 같을 것으로 추정) | 26,400원 | 23,100원 (.co.kr 같음) | 원화, VAT 포함 | 미확인 | 미확인 (네임서버 변경은 일반 기능) | 「세금계산서 정보」·「결제/증빙 조회」 메뉴 확인 [K2] |
| 후이즈 [K3] | 미확인 (주문 단계에서만 표시) | 미확인 | 미확인 | 미확인 | 원화 | 미확인 | 「등록정보 / 네임서버 변경」 메뉴 있음 | 「세금계산서 / 현금영수증 / 카드매출전표」 메뉴 있음 |
| 호스팅케이알 [K4] | **취급 안 함** (「dev 유효하지 않은 도메인 확장자(TLD)입니다」) | 없음 | 18,000원 (할인 배너) | 정가 20,000원, 할인 14,000원 (.co.kr 같음) | 원화. VAT 포함 여부 미확인 | 미확인 | 미확인 | 미확인 |
| 카페24 [K5] | 목록에 없음 (New gTLD > IT/전자. 판매 여부 미확인) | 없음 | 미확인 | 44,000원/2년, 할인 37,400원/2년 (2026-10-31 까지, 첫해 30%) | 원화 | 미확인 | 미확인 | 미확인 |

- .dev 2년 합계 (환율 1 USD = 1,339원, open.er-api.com 2026-10-07 값. 해외 결제 수수료 별도): Cloudflare $20.40~24.40 (약 27,300~32,700원) · Porkbun $21.62 (약 28,900원) · Namecheap $32.36 (약 43,300원) · 가비아 63,800원.
- Cloudflare 가격은 로그인한 대시보드에서만 보인다. 위 값은 제3자 집계 둘이며 첫해 값이 서로 다르다 (미확인).
- 레지스트리 도매가가 모든 등록처에 같다는 설명이 있다 [D6]. 그래서 갱신가 차이는 등록처 마진이다.

### 4d. 추천
- 먼저 이름을 정한다. foothold.dev 는 불가다. 후보: footholdlab.dev · foothold-project.dev (.dev) 또는 foothold.kr · foothold.co.kr (.kr).
- 정산에 **국내 증빙(세금계산서·현금영수증)** 이 필요하면 **가비아**. 원화·VAT 포함 가격이 공개돼 있고 증빙 메뉴가 있다. 2년 63,800원으로 Cloudflare 보다 약 3만원 비싸다. 산 뒤 네임서버를 Cloudflare 로 바꾸면 R2·Tunnel·Vercel 을 모두 붙일 수 있다.
- **해외 카드 결제 영수증·영문 인보이스가 인정**되면 **Cloudflare Registrar**. 도매가라 2년 합계가 가장 낮은 축이고, 네임서버 옮기는 단계가 없고, WHOIS 비공개가 무료다. 단 다른 DNS 로는 못 옮긴다 (옮기려면 등록처 이전) [D4].
- Porkbun 은 첫해가 싸지만 2년 합계가 Cloudflare 와 비슷하고 네임서버를 따로 바꿔야 한다. Namecheap 은 갱신가 $20.98 가 높다. 호스팅케이알·카페24 는 확인한 범위에서 .dev 를 팔지 않는다.
- .kr 을 고르면 해외 등록처는 못 쓴다. 가비아 23,100원/년, 호스팅케이알 할인 첫해 14,000원.

## 5. 도메인 하나로 여러 서비스 붙이기

| 주소 (예: footholdlab.dev) | 무엇 | 어디 | 메모 |
|---|---|---|---|
| 루트 · www | 지금의 정적 사이트 | Vercel | Cloudflare DNS 에 Vercel 레코드. 인증서 발급을 위해 Cloudflare 는 "DNS only" 권장 [V12] |
| app. | 웹앱 | Vercel 별도 프로젝트 | Hobby 는 프로젝트당 도메인 50개, 비상업만 [V7][V5] |
| dashboard. | 대시보드 | Vercel, 또는 NAS·워크스테이션 서비스를 Cloudflare Tunnel 로 | Tunnel 은 영상이 아닌 웹 화면에는 약관 문제 없음 |
| media. | 영상 | R2 사용자 도메인 (또는 NAS Tunnel) | R2 는 같은 계정 zone 필요 [C3]. Funnel 은 여기에 못 둔다 [T2] |
| api. | 로봇 서비스 API | Tunnel → NAS·서버, 또는 클라우드 서버 | .dev 라 HTTPS 강제 |

DNS 레코드만 다르게 두면 된다. 각 서브도메인은 독립이라 뒤쪽 서비스를 따로 바꿀 수 있다.

**실제 모바일 앱에서 도메인이 쓰이는 곳.**
- API 주소: 앱이 부르는 HTTPS 엔드포인트 (api.<도메인>).
- Android App Links: `https://<호스트>/.well-known/assetlinks.json`. HTTPS 만, `application/json`, 리다이렉트 금지, 그 도메인을 소유해야 한다 [M1].
- iOS Universal Links: `apple-app-site-association` 파일을 "https:// with a valid certificate and with no redirects" 로 둔다 [M2].
- 개인정보처리방침 URL: Google Play 는 Play Console 지정 칸과 앱 안 모두에 필요. 공개·작동·지역 차단 없는 URL, PDF 불가 [M3]. App Store 는 App Store Connect 메타데이터와 앱 안 모두에 링크 필요 (5.1.1(i)) [M4].
- 설치 자체에는 도메인이 필요 없다. APK 직접 설치·TestFlight·스토어 배포 모두 도메인과 무관하다. 방침 URL 도 vercel.app 페이지로 채울 수 있다. 도메인은 링크 연동과 주소 안정성을 위해 쓴다. 로봇(Go2)과 같은 망에서 직접 통신하는 기능도 도메인이 필요 없다.

## 출처 (모두 2026-10-07 읽음)

- [V1] https://vercel.com/docs/deployment-retention
- [V2] https://vercel.com/changelog/deployment-storage-keeps-your-deployments-rollback-ready
- [V3] https://vercel.com/changelog/hobby-projects-now-retain-fewer-deployments-to-free-up-storage
- [V4] https://vercel.com/docs/deployment-storage
- [V5] https://vercel.com/docs/limits/fair-use-guidelines
- [V6] https://vercel.com/docs/manage-cdn-usage
- [V7] https://vercel.com/docs/plans/hobby
- [V8] https://vercel.com/kb/guide/why-is-my-account-deployment-blocked
- [V9] https://vercel.com/docs/deployment-storage/optimize
- [V10] https://vercel.com/changelog/hobby-projects-now-default-to-30-day-deployment-retention
- [V11] https://vercel.com/docs/project-configuration/git-configuration
- [V12] https://vercel.com/docs/domains/troubleshooting
- [T1] https://tailscale.com/kb/1153/enabling-https
- [T2] https://tailscale.com/kb/1223/funnel
- [T3] https://tailscale.com/docs/reference/syntax/policy-file
- [T4] https://tailscale.com/docs/reference/examples/acls
- [T5] https://news.ycombinator.com/item?id=35374302 (직원 댓글 item?id=35375794)
- [T6] https://www.ssdnodes.com/learn/tailscale-funnel-limits-and-ports
- [T7] https://tailscale.com/kb/1311/tailscale-funnel
- [T8] https://tailscale.com/kb/1242/tailscale-serve
- [T9] https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go
- [T10] https://ai.ugreen.com/blogs/how-to/ugreen-nas-remote-access
- [C1] https://www.cloudflare.com/service-specific-terms-application-services/
- [C2] https://developers.cloudflare.com/r2/pricing/
- [C3] https://developers.cloudflare.com/r2/buckets/public-buckets/
- [C4] https://developers.cloudflare.com/dns/zone-setups/partial-setup/
- [C5] https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
- [C6] https://www.cloudflarestatus.com/api/v2/components.json ("Seoul, South Korea - (ICN)")
- [B1] https://www.backblaze.com/cloud-storage/pricing
- [B2] https://bunny.net/pricing/
- [B3] https://bunny.net/pricing/storage/
- [H1] https://huggingface.co/docs/hub/rate-limits
- [G1] https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits
- [G2] https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- [D1] https://pubapi.registry.google/rdap/domain/foothold.dev (KR 은 https://rdap.nic.or.kr, 그 밖은 https://rdap.org)
- [D2] https://www.registry.google/domains/dev/
- [D3] https://www.cloudflare.com/application-services/products/registrar/buy-dev-domains/
- [D4] https://developers.cloudflare.com/registrar/faq/ , https://developers.cloudflare.com/registrar/get-started/register-domain/
- [D5] https://cfdomainpricing.com/ (제3자, NameBeta)
- [D6] https://tld-list.com/tld/dev (제3자)
- [D7] https://developers.cloudflare.com/billing/understand/sales-tax/ (한국 항목 없음)
- [D8] https://api.porkbun.com/api/json/v3/pricing/get (Porkbun 공개 가격 API)
- [D9] https://porkbun.com/support/payment_options
- [D10] https://www.namecheap.com/domains/registration/gtld/dev/
- [D11] https://domains.squarespace.com/domain-search?query=footholdlab.dev
- [K1] https://domain.gabia.com/regist/regist_domain (신규 도메인·KR·주요 도메인 탭)
- [K2] https://customer.gabia.com/
- [K3] https://domain.whois.co.kr/regist/dom.php
- [K4] https://www.hosting.kr/domain/search?q=footholdlab.dev
- [K5] https://hosting.cafe24.com/?controller=new_domain_search
- [M1] https://developer.android.com/training/app-links/verify-android-applinks
- [M2] https://developer.apple.com/documentation/xcode/supporting-associated-domains
- [M3] https://support.google.com/googleplay/android-developer/answer/10144311
- [M4] https://developer.apple.com/app-store/review/guidelines/

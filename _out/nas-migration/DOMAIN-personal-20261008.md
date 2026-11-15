# 개인·프로젝트 도메인 조사 (사용계획서용)

조사 시각: 2026-10-08 00:09~00:18 KST. 읽기만 했다. 로그인·장바구니·구매는 하지 않았다.
원자료: `C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/work/` (RDAP JSON, Porkbun 가격 JSON, 환율 JSON).

## 1. 등록 여부 (레지스트리 RDAP)

.ai 의 RDAP 주소는 IANA 부트스트랩(2026-09-30 발행)에서 찾았다: `rdap.identitydigital.services/rdap/`.

| 도메인 | RDAP 응답 | 상태 | 판매처(registrar) | 생성일 | 만료일 | 비고 |
|---|---|---|---|---|---|---|
| iammai.dev | 200 | 등록됨 | Name.com | 2025-03-14 | 2027-03-14 | 네임서버 Vercel. 사이트는 Vercel "DEPLOYMENT_NOT_FOUND" |
| iammai.app | 200 | 등록됨 | Porkbun | 2025-10-03 | 2027-10-03 | 10/03 자동 연장됨 |
| iammai.ai | 200 | 등록됨 | GoDaddy | 2026-03-24 | 2028-03-24 | 소유자 비공개(Domains By Proxy). GoDaddy 무료 파킹 화면 |
| iammai.com | 200 | 등록됨 | GoDaddy | 1999-06-21 | 2027-06-21 | 파킹 화면에 "This domain may be for sale" 표시 |
| mai.dev | 200 | 등록됨 | Squarespace Domains | 2019-02-28 | 2027-02-28 | 호스팅 기본 페이지. 판매 표시 없음 |
| mai.app | 200 | 등록됨 | GoDaddy | 2023-07-21 | 2027-07-21 | 파킹 화면에 "GoDaddy 경매에서 구매할 수 있습니다" 표시 |
| mai.ai | 200 | 등록됨 | 101domain | 2017-12-16 | 2027-01-07 | 회사(Augmented Intelligence, LLC)가 실제 서비스 중 |
| foothold-project.dev | 404 | **미등록** | | | | 구매 가능 |
| mai-universe.dev | 404 | **미등록** | | | | 구매 가능 |

참고로 같은 이름의 다른 TLD 도 봤다. mai-universe.app · .ai · .com 모두 404(미등록).

**결론: 요청한 개인 후보 중 지금 살 수 있는 것은 mai-universe.dev 하나다.**
iammai 네 개(.dev .app .ai .com)는 모두 남이 갖고 있다. mai.dev · mai.app · mai.ai 도 마찬가지다.
등록된 도메인은 소유자가 팔지 않으면 살 수 없다. 중개 매물 가격은 조사하지 않았다.
iammai.dev 는 Vercel 네임서버를 쓴다. 혹시 팀장 본인이 예전에 산 것이 아닌지 Name.com 계정을 한 번 확인해 주십시오.

### 하위 도메인(서브도메인)은 어떻게 되나

- universe.mai.dev, os.mai.dev, vfxpedia.mai.dev, foothold.mai.dev 는 **mai.dev 주인만** 만들 수 있다. 우리는 mai.dev 를 살 수 없으므로 이 주소들은 쓸 수 없다.
- 도메인 하나를 사면 그 아래 하위 도메인은 **추가 구매 없이** 마음대로 만든다. DNS 기록 한 줄씩이다.
  예: mai-universe.dev 를 사면 os.mai-universe.dev, vfxpedia.mai-universe.dev, foothold.mai-universe.dev 가 공짜다.
- iammai.dev 였다면 universe.iammai.dev 등도 같은 방식이었겠지만, 이미 남의 것이라 불가.
- 실제 한도: Cloudflare 무료 요금제는 2024-09-01 이후 만든 영역에 DNS 기록 200개까지다(developers.cloudflare.com/dns/manage-dns-records). 하위 도메인 몇 개에는 충분하다.

### 프리미엄 여부

Cloudflare 검색 결과에 "Premium" 표시가 없었다. 값도 같은 TLD 의 일반 가격과 같았다.
Porkbun 검색 화면에서도 foothold-project.dev · mai-universe.dev 는 "1st Year Sale!" "At Cost" 표시뿐이었다. 프리미엄 아님.

## 2. 가격 (Cloudflare Registrar, 판매처 화면 그대로)

출처: `https://www.cloudflare.com/domains/search?q=<이름>` (로그인 없이 공개, 00:11~00:15 KST).
값은 화면 숫자와 버튼 설명문(aria-label)을 둘 다 읽어 맞췄다.

| 도메인 | 첫 결제 | 연장(1년) | 최소 기간 | 화면 문구 |
|---|---|---|---|---|
| foothold-project.dev | $8.20 (정가 $12.20 취소선) | $12.20 | 표시 없음(1년) | "for $8.20. Renews at $12.20 per year." |
| mai-universe.dev | $8.20 (정가 $12.20 취소선) | $12.20 | 표시 없음(1년) | 위와 같음 |
| mai-universe.app | $8.20 (정가 $14.20 취소선) | $14.20 | 표시 없음(1년) | "for $8.20. Renews at $14.20 per year." |
| mai-universe.ai | **$160.00 (2년치)** | $80.00 | **2년** ("2-year minimum") | "for $160.00 per 2 years. Renews at $80.00 per year." |
| mai-universe.com | $10.46 | $10.46 | 표시 없음(1년) | "for $10.46. Renews at $10.46 per year." |
| iammai.dev · .app · .ai · .com | 가격 없음 | | | "Unavailable" |

Cloudflare 원가 판매 공식 문구:
- 판매 페이지 `https://www.cloudflare.com/domains/` : "Never pay more than we do". 등록·이전·연장 가격이 레지스트리와 ICANN 청구액 이하라고 적는다.
- 공식 문서 `https://developers.cloudflare.com/registrar/faq/` : 레지스트리와 ICANN 정가를 마크업 없이 받는다고 적는다. 같은 곳에 **환불 불가**도 적혀 있다(오타·TLD 착오 포함).

### 교차 확인: Porkbun 공식 가격 API

`POST https://api.porkbun.com/api/json/v3/pricing/get` (00:10 KST, 인증 없이 응답 200).

| TLD | Cloudflare 첫해 / 연장 | Porkbun 첫해 / 연장 | 차이 |
|---|---|---|---|
| .dev | $8.20 / $12.20 | $8.75 / $12.87 | Porkbun 이 $0.55~0.67 비쌈 |
| .app | $8.20 / $14.20 | $8.75 / $14.93 | Porkbun 이 $0.55~0.73 비쌈 |
| .ai | $80.00/년 (2년 $160) | $82.70/년 | API 에 최소 기간 정보 없음(미확인) |
| .com | $10.46 / $10.46 | $11.08 / $11.08 | Porkbun 이 $0.62 비쌈 |

두 판매처 모두 .dev · .app 에 첫해 할인이 붙어 있다. 레지스트리 쪽 할인으로 보이나 근거 문서는 확인하지 못했다(미확인).

## 3. 원화 환산

- 적용 환율: **1,339.20원/USD**. 서울외국환중개 매매기준율, 2026-10-08 고시분(www.smbs.biz 오늘의 환율, 00:14 KST 경 열람).
- 대조: open.er-api.com 1,338.92원/USD (마지막 갱신 2026-10-07 00:02 UTC). 차이 0.28원. 아래 금액에 영향 거의 없음.
- 원 단위 반올림.

카드 결제 주의:
- Cloudflare 는 USD 로 청구한다. 해외 결제라 카드사 해외 이용 수수료가 붙는다. 보통 1% 남짓이며 카드마다 다르다.
- 카드 명세서의 원화 금액은 카드사 정산일 환율로 바뀐다. 아래 금액과 조금 다르게 찍힌다.
- Cloudflare 세금 문서(2026-05-29 갱신)의 부과 국가 목록에 한국은 없다. 결제 화면의 최종 합계는 구매 단계라 보지 않았다(미확인).
- 해외 업체라 국내 세금계산서는 나오지 않는다. 증빙은 카드 매출전표와 Cloudflare 청구 내역이다.

## 4. 사용계획서 붙여넣기용 표

환율 1,339.20원/USD (서울외국환중개 매매기준율, 2026-10-08 고시). 가격 확인 2026-10-08 00:11~00:15 KST.

| 항목 | 도메인 | 기간 | 금액(USD) | 금액(원, 1,339.20원/$ · 10/08 고시) | 판매처 | 결제 | 증빙(카드 매출전표) |
|---|---|---|---|---|---|---|---|
| 프로젝트 도메인 | foothold-project.dev | 1년 | $8.20 | 10,981원 | Cloudflare Registrar | 해외 신용카드(USD) | 카드 매출전표 + Cloudflare 청구 내역 |
| 개인 도메인 후보 | mai-universe.dev | 1년 | $8.20 | 10,981원 | Cloudflare Registrar | 해외 신용카드(USD) | 카드 매출전표 + Cloudflare 청구 내역 |
| 개인 도메인 후보 | mai-universe.dev | 3년 합계 | $32.60 | 43,658원 | Cloudflare Registrar | 해외 신용카드(USD) | 연도별 매출전표 |
| 개인 도메인 후보 | iammai.dev | 해당 없음 | 구매 불가 | 구매 불가 | (Name.com 에 등록됨) | | |
| 개인 도메인 후보 | iammai.app | 해당 없음 | 구매 불가 | 구매 불가 | (Porkbun 에 등록됨) | | |
| 개인 도메인 후보 | iammai.ai | 해당 없음 | 구매 불가 | 구매 불가 | (GoDaddy 에 등록됨) | | |
| 개인 도메인 후보 | iammai.com | 해당 없음 | 구매 불가 | 구매 불가 | (GoDaddy 에 등록됨, 매물 표시) | | |

참고(같은 이름, 다른 TLD. 모두 미등록):

| 도메인 | 첫해(또는 최소 기간) | 원 | 3년 합계 | 원 |
|---|---|---|---|---|
| mai-universe.app | $8.20 | 10,981원 | $36.60 | 49,015원 |
| mai-universe.com | $10.46 | 14,008원 | $31.38 | 42,024원 |
| mai-universe.ai | $160.00 (2년 최소) | 214,272원 | $240.00 | 321,408원 |

3년 합계 계산: 첫 결제 + 오늘 화면의 연장가 x 남은 연수. 예: .dev = 8.20 + 12.20 x 2.
연장가는 레지스트리가 올리면 같이 오른다. 3년 합계는 견적이 아니라 계산값이다.
foothold-project.dev 의 2년차 연장은 $12.20 (16,338원)이다.

## 5. 권고 (하위 도메인 universe. os. vfxpedia. foothold. 을 둘 개인 도메인)

1. **mai-universe.dev 를 권한다.** 요청 후보 중 유일하게 살 수 있다. 첫해 10,981원, 3년 43,658원.
2. **.ai 는 권하지 않는다.** 최소 2년 선결제 $160(214,272원), 연장 $80/년. .dev 연장가의 약 6.6배.
3. 3년 비용만 보면 mai-universe.com($31.38)이 .dev($32.60)보다 $1.22 싸다. 첫해 할인이 없고 매년 같은 값이다. 이름의 느낌으로 고르면 된다.
4. .dev · .app 은 HTTPS 만 열린다. Vercel 과 Cloudflare 가 인증서를 자동 발급하므로 문제없다.
5. Cloudflare 에서 산 도메인은 Cloudflare 네임서버만 쓸 수 있다(공식 FAQ). 각 하위 도메인을 Vercel 로 보낼 때는 Cloudflare DNS 에 CNAME 한 줄씩 넣으면 된다.
6. 이름 관찰: mai-universe.dev 아래 universe.mai-universe.dev 는 "universe" 가 겹친다. universe 는 최상위 주소(mai-universe.dev) 자체로 두는 방법도 있다.
7. 환불이 안 되므로 철자를 결제 전에 한 번 더 확인한다.

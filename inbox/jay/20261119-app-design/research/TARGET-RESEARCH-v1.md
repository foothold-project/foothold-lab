> 분류: 리서치
> 작성: app-design-lx 하위 조사
> 근거: 조사 메모 4편 (korea_field_problems · market_size · value_numbers · competitors_segments, 2026-11-21) · 선행 검토 foothold-lab docs/research/20261007-underground-recon-service-review.md v1.1 (읽기만) · 각 수치 옆 공개 출처 URL
> 요지: 첫 타깃은 「위험 첫 진입 실증 과제를 맡은 로봇 개발·통합팀」이고, 시장은 IDC 실측 1.8억 달러(2024)와 국내 공공 예산 신호로만 말하며, 예행의 가치는 외부 수치가 없어 우리가 직접 잴 지표로 제시한다
> 상태: v1 초안 보존본 (팀장 11/21 「없어지면 안 됨」) · 팀장 검토 중 · 핵심 숫자 3 (KOSHA 2026 가이드 154건·315명·41.9%·132명 중 30명 · IDC 1.8억 달러·약 2만 대 · 노컷 2027 예산안 4족 40대 160억) app-design-lx 원문 대조 일치 (11/21 03:30) · 나머지 수치 미대조

# 사람보다 먼저 보낼 로봇을 먼저 걸려 보기

「시뮬에서 되는 것이 실기에서도 된다」는 기술 주장에 사업 가치를 붙이려면 그 확인이 누구의 어떤 손실을 막는지 말해야 한다. 공개 자료로 가장 단단한 답은 이렇다. 한국 밀폐공간 질식은 **재해자 열 명 중 네 명이 죽는 사고(치명률 41.9%)**이고, 10년간 사망자 132명 중 **30명이 구조하러 들어갔다가 숨졌다** 「사실 (KOSHA 2026 가이드)」. 공공 부문은 이 문제에 사족 로봇으로 답하기 시작했다. 서울소방은 공동구 등 진입 곤란 현장에 사족 로봇 선제 투입을 계획했고, 소방청 2027 예산안에는 **4족보행로봇 40대·160억원**이 들어 있다 「사실 (서울시 2026 · 노컷뉴스 2026, 예산안 단계)」. 그러나 지도 작성·경로 반복·다기체 관제·디지털 트윈은 Spot/Orbit, ANYmal, Deep Robotics가 이미 판다. 공개 자료에서 찾지 못한 것은 「현장 스캔 위에서 같은 임무를 물리 시뮬로 먼저 걸려 보고, 그 임무를 그대로 실기에 보내는」 결합뿐이다 「추정 · 부재 증명 아님」. 그래서 첫 타깃은 로봇을 사는 기관 자체가 아니라, 그 기관의 실증 과제를 수행하며 **현장 전에 실패를 줄여야 하는 개발·통합팀**으로 두고, 선행 검토의 결론(개발·통합팀 우선)을 유지한다. 시장 규모는 측정에 가까운 IDC 세계 사족 로봇 **1.8억 달러·약 2만 대(2024)**를 기준으로 쓰고 20~35억 달러대 조사기관 전망은 정의가 넓은 범위로만 소개한다. 시뮬 예행이 현장 실패를 몇 % 줄였다는 공개 측정은 찾지 못했으므로, 발표에서는 그 빈칸을 숨기지 말고 「첫 실행 성공률·현장 개입 횟수·현장 체류 시간」을 우리가 잴 가치 지표로 내놓는 편이 방어 가능하다. 끝으로 선행 검토의 규칙을 그대로 따른다. **참고 사례와 기관 계획은 우리 플랫폼 수요나 우리 정책의 현장 효과를 증명하지 않는다.**

표기: 「사실 (출처)」는 원문에서 확인한 값, 「사실 (출처 · 요약)」은 검색 요약이나 2차 보도에서만 확인해 발표 전 원문 대조가 필요한 값, 「추정」은 이 보고서나 원자료의 계산·추론, 「미확인」은 근거를 찾지 못한 것. 공급사 사례 수치는 「공급사 발표」를 함께 적는다. 사고·시설 수는 시장 규모로 바꾸지 않는다.

## 1. 현장 문제: 질식 치명률 41.9%, 사망자 넷 중 하나는 구조 진입자

### 밀폐공간은 들어가는 순간이 가장 위험하다

선행 검토 부록 C4가 이미 정리한 핵심 숫자는 원문으로 다시 확인됐다. 고용노동부·안전보건공단 2026 가이드는 2016~2025년 **154건·재해자 315명·사망 132명**, 그중 **구조하러 들어갔다 사망 30명**을 적는다 「사실 ([KOSHA 2026 가이드](https://info.cak.or.kr/download.do?uuid=08d223c3-5233-436a-8427-0ddbf304da60.pdf), 2026)」. 같은 가이드는 질식 치명률 **41.9%**를 2025년 전체 사고재해자 치명률 0.77%와 비교해 **「약 54배」**라고 쓴다 「사실 (같은 가이드 13쪽)」. 이 54배는 서로 다른 모집단(10년 밀폐공간 재해자 대 2025년 전체 사고재해자)을 비교한 가이드의 표현이므로 다시 계산하지 말고 그대로 인용한다 「추정」. 30/132는 사망자 중 구조 진입자의 비율(22.7%)이지 구조하러 들어간 사람의 사망 확률이 아니다(선행 검토 C4).

새로 확인된 분포는 시나리오 설계에 쓸 만하다. 업종별로는 **건설업 55건(35.7%)**, 제조업 42건, 서비스업 32건이고, 원인물질은 **황화수소 61건(39.6%)**, 일산화탄소 34건, 산소결핍 31건이다. 건설업은 겨울 콘크리트 양생(갈탄 일산화탄소)으로 1월, 서비스업은 정화조·맨홀(황화수소)로 6~8월에 몰린다 「사실 ([KOSHA 2026 가이드 15~16쪽](https://info.cak.or.kr/download.do?uuid=08d223c3-5233-436a-8427-0ddbf304da60.pdf#page=15), 2026)」. 따라서 시연 로봇의 가스 탑재 구성은 H2S·CO·O2 동시 측정이 기본이 된다 「추정」. 산업안전보건기준에 관한 규칙은 밀폐공간을 18개 유형(케이블·가스관 지하 암거·맨홀·피트, 정화조·탱크 등)으로 정의한다 「사실 (같은 가이드 10~11쪽)」. 장소별(맨홀·정화조·탱크) 건수 표는 가이드에 없다 「미확인」.

### 공동구는 불이 나면 사람이 접근하지 못한다

전국 공동구 개수·총연장 공식 집계는 찾지 못했다 「미확인」. 서울은 **8개소**이며 연장은 자료에 따라 **74,770 m**(서울시 2026 도로시설물 현황, 2025-12-31 기준) 「사실 ([서울시 안전분야 누리집](https://news.seoul.go.kr/safe/?p=45739), 2026)」와 **36.45 km**(2023 보도) 「사실 ([보안뉴스](https://m.boannews.com/html/detail.html?idx=117441), 2023 · 요약)」로 다르다. 측정 기준 차이로 보이나 근거가 없어 둘 다 출처와 함께 적는다 「추정」. 설치 30년이 지난 5개소(여의도·목동·상계·가락·개포) 점검에 국토부·산업부·과기정통부·환경부·소방·국토안전관리원이 함께 들어갔다 「사실 (보안뉴스, 2023 · 요약)」.

점검 주기는 공동구 전용 조문을 확인하지 못했다. 국토계획법 시행령의 공동구 안전점검 주기 문구는 「미확인」이므로 쓰지 않는다. 일반 시설물안전법 기준으로는 정기안전점검 반기 1회 이상, 정밀안전점검 A등급 3년·B·C등급 2년·D·E등급 1년에 1회 이상이다 「사실 ([서울시 안전분야 누리집](https://news.seoul.go.kr/safe/archives/327), 연도 미표기 · 공동구 전용 아님)」. 공동구 점검 인력·순회 빈도·연간 관리비는 공개 수치가 없다 「미확인」.

화재 사례는 문제 정의에 쓸 수 있다. 2000년 여의도 공동구 화재는 재산피해 추정 **32억5천만원**이고 케이블 연소 유독가스로 소방 접근이 어려웠다 「사실 ([한국화재보험협회](https://kfpa.or.kr/mem/pdf_file/B/10/B10_1-5.pdf), 연도 미표기 · [서울신문](https://m.seoul.co.kr/news/2000/02/21/20000221027004), 2000)」. 2018년 KT 아현 통신구 화재는 **79 m** 소실에 요금 감면 대상 약 80만 명, 소상공인 보상 약 62억원이 보도됐다 「사실 ([비즈니스워치](https://news.bizwatch.co.kr/article/mobile/2018/12/28/0016), 2018 · [아주경제](https://www.ajunews.com/view/20191121102312646), 2019 · 요약)」. 두 화재 모두 「사람이 접근하기 어려웠다」는 공통점이 있지만, 로봇이 진압이나 복구를 앞당겼을 것이라는 주장은 근거가 없다 「추정」.

### 플랜트·건설·재난: 정비와 수색 진입에서 사람이 죽는다

2025년 재해조사 대상 사고사망자는 **605명**이고 그중 **건설업 286명**이다 「사실 ([헤럴드경제](https://www.heraldk.com/article/2026033019000041446), 2026 · 고용노동부 부가통계 보도)」. 석유화학에서는 2022년 여천NCC 열교환기 내부 청소 뒤 기밀시험 폭발로 4명 사망 「사실 ([세계일보](https://www.segye.com/newsView/20220211517187), 2022)」, 2025년 울산 SK에너지 정기보수 중 수소배관 폭발로 2명 사망 「사실 ([경향신문](https://www.khan.co.kr/article/202510231358001/), 2025)」이 보도됐다. 사고가 정비 기간 내부 진입·시험 단계에 몰리지만, 로봇의 쓰임은 진입 전 가스·내부 상태 확인이지 폭발 예방이 아니다 「추정」. 소방 쪽에서는 2022년 평택 냉동창고 신축 공사장 화재 때 **인명 수색에 들어간 구조대원 3명이 순직**했다 「사실 ([서울신문](https://m.seoul.co.kr/news/2022/01/06/20220106500095), 2022)」. 「찾으러 들어가는 사람이 위험하다」는 구조가 산업 밀폐공간과 소방 현장에 함께 있다는 점이 FOOTHOLD의 「사람보다 먼저」 목표와 직접 맞닿는다 「추정」.

### 정부 계획과 예산: 2027년이 공공 실증의 문턱

가장 직접적인 숫자는 소방청 **2027년도 예산안 3,713억원** 안의 **무인소방로봇 9대 108억원, 4족보행로봇 40대 160억원**이다 「사실 ([노컷뉴스](https://nocutnews.co.kr/news/6572990), 2026 · [파이낸셜뉴스](https://www.fnnews.com/news/202609041550528147), 2026)」. 국회 확정 전 예산안이며 대당 단가는 기사에 없다. 160억/40대를 대당 4억원으로 인용하지 않는다 「추정」. 소방장비관리법 개정으로 로봇·드론 첨단소방장비 실증체계가 생기고 시행일은 **2026년 12월**이다 「사실 ([국민참여입법센터](https://opinion.lawmaking.go.kr/lmSts/govLm/2000000330366/detailRP?yType=I), 2026 · 요약)」. 서울소방은 2026 업무계획에서 「지하 공동구 등 유해가스와 농연으로 진입이 어려운 현장에 4족 보행 로봇 선제 투입」, 라이다·8종 가스 측정기, 통신 음영 대응 Private 5G를 밝혔고 「사실 ([서울시 안전분야 누리집](https://news.seoul.go.kr/safe/archives/517409), 2026)」, 2026-02-26 시연에서는 사족 로봇이 연기 찬 지하철 역사에서 시민 2명을 찾았다 「사실 ([서울신문](https://m.seoul.co.kr/news/2026/02/26/20260226500254), 2026)」. 선행 검토 C4가 이미 서울시 2025 예산안의 순찰 2대·사족 1대 시범 사업 합계 3억원과 서울시 밀폐공간 2,399개를 정리했다.

산업부 제4차 지능형로봇 기본계획(2024~2028)은 민관 **3조원 이상** 투자와 2030년 로봇 100만 대 보급을 내세운다 「사실 ([정책브리핑](https://m.korea.kr/news/policyNewsView.do?newsId=148924862), 2024)」. 국토부 2025 공간정보 정책사업은 1,209개·약 **5,838억원**이고 디지털 트윈 국토와 지하공간통합지도 고도화가 핵심이다 「사실 ([스마트시티 누리집](https://smartcity.go.kr/2025/05/02/25년-5800억-원-규모-공간정보-정책사업-공간정보-인/), 2025)」. 「예산의 68%가 디지털 트윈」은 요약 수준이다 「사실 ([매일신문](https://www.imaeil.com/page/view/2025050211044571882), 2025 · 요약)」. 우리 스캔 자산이 국가 지하공간통합지도에 들어가는 경로는 확인하지 않았다 「미확인」. 고용노동부 로봇 안전 사업 예산, 공동구에 로봇을 쓰는 조달 공고도 찾지 못했다 「미확인」.

## 2. 타깃 후보: 기관은 탐지 장비를 사고, 예행이 필요한 사람은 통합팀이다

공개 구매 신호가 가장 구체적인 곳은 소방과 공동구 관리 쪽이다. 하지만 그 기관들이 공개 문서에 적은 요구는 라이다·가스 측정·영상 전송이며 **시뮬 예행을 요구한 문서는 없다** 「사실 (서울시 2026 원문 확인) · 추정 (해석)」. 시뮬 예행 자체가 구매 이유가 되는 쪽은 그 장비를 현장에 실제로 걸려야 하고, 실패하면 과제 일정과 기체를 잃는 개발·통합팀이다. 아래 표의 구매자·사용자·고충은 모두 「추정」이고, 현재 대안 열만 출처에 기댄다.

| 순위 | 고객군 | 구매자 · 사용자 (추정) | 고충 (추정) | 현재 대안 (사실) | 사족 + 시뮬 예행이 맞는 이유 | 안 맞는 이유 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 위험 첫 진입 실증 과제를 수행하는 로봇 개발·통합팀 (연구기관·통합사업자, 소방·지하 시설 과제 포함) | 과제 책임자·기술 책임자 · 제어·자율 개발자, 시험 운용자 | 실기 시험 비용·낙상·기체 손상, 현장 접근 허가가 드묾, 시뮬 장면 수작업 | Isaac Sim·Lab·NuRec·Gazebo를 직접 조립, 실기 반복 시험 ([NVIDIA](https://developer.nvidia.com/omniverse/nurec)) | 예행이 곧 그들의 일. 조달·인증 장벽이 낮음. Go2 사용자 자체가 대상. 2027 공공 실증 물량이 이들을 거쳐 감 | 시장이 작고 개발자가 직접 조립할 수 있음. 지불 의사·가격대 미확인 |
| 2 | 공동구·지하 시설 관리기관 (지자체·공사) | 시설·재난안전 부서 · 점검 인력, 관제실 | 유해가스 공간 진입, 긴 구간 반복 점검 | 사람 순회, 고정 센서, 은평공동구 천장 레일 관측장비 약 2.4 km 시범 ([서울시](https://news.seoul.go.kr/safe/?p=501376), 2019), 궤도·바퀴형 | 계단·단차에 다리가 유리. 구조가 고정되어 한 번 스캔한 자산이 오래 감 | 레일이 깔린 곳은 레일이 이김. 예행이 조달 요구 항목인지 미확인. Deep Robotics가 공동구 트윈 솔루션을 이미 판매 |
| 3 | 소방·재난 대응 기관 | 소방본부 장비 부서 · 구조대·현장 지휘 | 농연·가스 속 정찰, 통신 음영, 구조 진입 순직 | 사람 진입, 6륜 무인소방로봇 ([현대차그룹](https://www.hyundaimotorgroup.com/ko/story/unmanned-firefighting-robot-physical-ai), 2026), 드론, 계획 단계의 사족 로봇 | 계단·잔해에 다리가 유리. 2027 예산안 40대라는 가장 큰 공공 신호 | 재난 현장은 미리 스캔된 지도가 없을 가능성이 큼. 평시 대상물 사전 스캔·훈련용으로만 예행이 성립 |
| 4 | 플랜트·발전·화학 사업장 안전 부서 | 설비 보전 부서 · 순회 점검원 | 반복 순회, 위험 구역, 기록 표준화 | Spot·ANYmal·X30 + 트윈·데이터 플랫폼 ([ANYbotics](https://www.anybotics.com/photorealistic-digital-twin/), 2023) | 다리 적합 높음. 정비 기간 내부 진입 위험이 큼 | 경쟁사가 트윈·임무 계획까지 이미 제공. Go2의 방폭 대응 미확인 |

건설 현장은 순위에서 뺐다. 현장이 매일 바뀌어 스캔 자산이 빨리 낡고, 건설업 질식의 큰 몫인 겨울 양생 공간은 진입 전 측정·환기 문제이기 때문이다 「추정」.

**첫 타깃 추천은 1위, 그중에서도 2027년 공공 사족 로봇 실증(소방·공동구)을 맡을 통합사업자·연구기관이다** 「추정」. 이유는 세 가지다. 첫째, 시뮬 예행이 그들의 실제 업무와 같은 단어다. 둘째, 소방청 예산안과 실증체계 시행(2026-12)이 맞물리면 실증 현장이 늘 가능성이 있고 「추정」, 그 실증을 수행하는 쪽은 「처음 가 보는 현장에서 기체를 넘어뜨리지 않는 것」이 일정과 직결된다. 셋째, 국내 순찰 사족 로봇이 이미 제조사(레인보우로보틱스)와 관제 SW(도구공간) 조합으로 공공·플랜트를 노린다 「사실 ([보안뉴스](https://m.boannews.com/html/detail.html?idx=139003), 2025 · 요약)」. 우리는 그 조합과 정면으로 겨루기보다 그들 앞 단계의 「출동 전 확인」 도구로 서는 편이 차별 여지가 크다 「추정」. 이 경로로 2·3위 기관에 간접으로 닿는다.

주의할 점이 둘 있다. 서울소방 계획과 소방청 예산은 **사족 로봇 수요의 신호이지 우리 플랫폼 수요의 증거가 아니다**(선행 검토와 같은 경고). 또 사람 진입을 줄여야 한다는 필요만으로 다리나 Go2가 선택되지 않는다. EU-OSHA 사례는 압력 탱크에 검사 암과 자석 바퀴 로봇을 썼고, NASA/JPL은 바퀴·궤도·다리·비행 기체를 환경에 맞춰 골랐다(선행 검토 5.3).

## 3. 시장 규모: 측정값 1.8억 달러와 전망값 35억 달러 사이

### 세계 사족 로봇: 기관끼리 10배 넘게 어긋난다

| 발행처 · 연도 | 기준 값 | 전망 값 · CAGR | 범위 · 표기 |
| --- | --- | --- | --- |
| IDC (2025-06) | 2024년 1.8억 달러 초과, 출하 약 2만 대 | 전망 없음 | 공급사 출하 매출. 소비자형이 대수의 72.1%. 「사실 ([IDC](https://www.idc.com/resource-center/press-releases/%e4%b8%ad%e5%9b%bd%e5%8e%82%e5%95%86%e9%a2%86%e8%b7%91%ef%bc%8c%e5%a4%9a%e5%85%83%e5%ba%94%e7%94%a8%e8%b5%b7%e8%88%aa-idc%e5%8f%91%e5%b8%83%e5%85%a8%e7%90%83%e5%9b%9b%e8%b6%b3/), 2025)」 |
| Bosson Research (2025) | 2024년 1.96억 달러 | CAGR 35.23% | 「사실 ([marketresearch.com](https://www.marketresearch.com/Bosson-Research-v4252/Global-Quadruped-Robot-Research-Status-43405598), 2025 · 요약)」 |
| TechSci Research (2025 무렵) | 2024년 22.0억 달러 | 2030년 119.6억 달러 · 18.41% | 「사실 ([TechSci](https://www.techsciresearch.com/news/23753-quadruped-robot-market.html) · 요약)」. 같은 회사 다른 판은 2031년 67.4억 달러 · 19.28%로 어긋남 |
| MarketsandMarkets (2026 무렵) | 2026년 35.4억 달러 | 2032년 104.8억 달러 · 18.0% | 「사실 ([MarketsandMarkets](https://www.marketsandmarkets.com/Market-Reports/quadruped-robot-market-186625495.html) · 요약)」. 원문 403, 범위 미확인 |
| Precedence Research (2026 무렵) | 2025년 31.2억 달러 | 2035년 175.3억 달러 | 「사실 ([Precedence](https://www.precedenceresearch.com/table-of-content/7836) · 요약)」 |
| Global Info Research (2025) | 2024년 6.99억 달러 (보행 로봇 전체) | 2031년 17.23억 달러 | 「사실 ([marketresearch.com](https://www.marketresearch.com/GlobalInfoResearch-v4117/Global-Legged-Robot-Manufacturers-Regions-42309904), 2025 · 요약)」. 범위가 더 넓은데 TechSci 사족 값의 1/3 |

어긋남의 원인은 정의와 방법론이다. 2024년 세계 출하가 약 2만 대이고 그 72.1%가 저가 소비자형이라면 20억 달러대는 하드웨어 출하 매출로 설명되지 않는다. 군수 계약·소프트웨어·서비스 포함, 하향식 모형, 연구용 단가 적용 같은 차이로 보인다 「추정」. 「보행 로봇 전체」가 「사족만」보다 작게 나오는 역전도 정의보다 방법론 차이가 크다는 신호다 「추정」. CAGR은 대부분 18% 안팎으로 모이지만 기준값이 10배 다르면 전망도 10배 다르다.

측정값 쪽의 교차 확인도 있다. Unitree 상장 서류는 **2023~2025년 사족 로봇 33,294대** 판매와 매출 1.59억 위안(2023)에서 **17.0억 위안(2025)** 증가를 적는다 「사실 ([상하이증권거래소 영문판](https://english.sse.com.cn/news/newsrelease/voice/c/c_20260811_10828578.shtml), 2026)」. 2025년 1~9월 핵심 매출의 사족 비중은 42.3%다 「사실 ([The Robot Report](https://www.therobotreport.com/unitree-ipo-shows-a-real-hardware-business-the-humanoid-case-is-still-early/), 2026)」. 17.0억 위안에 42.3%를 곱하면 사족 매출 약 7억 위안(약 1억 달러)이고, 세계 1위 업체 하나가 이 정도라면 세계 하드웨어 시장을 수억 달러 규모로 보는 것이 IDC와 일관된다 「추정」. Boston Dynamics는 Spot 약 **2,000대 가동**을 말했고 고객 다수는 제조·전력 산업이다 「사실 ([The Star 재게재 Bloomberg](https://www.thestar.com.my/tech/tech-news/2025/11/21/a-us100000-robot-dog-is-becoming-standard-in-policing---and-raising-ethical-alarms), 2025 · 요약)」. 반면 GGII는 2023년 세계 판매를 약 3.4만 대로 잡아 IDC와도 어긋난다 「사실 ([前瞻产业研究院](https://www.qianzhan.com/analyst/detail/220/251022-4f4338c7.html) · 요약)」.

### 점검 로봇과 디지털 트윈: 사족이 들어갈 상위 시장일 뿐이다

세계 점검 로봇 시장은 배관 크롤러·드론·고정형·수중형을 모두 넣어 2024~2025년 기준 **27.8억 달러**(Credence, CAGR 13.7%) 「사실 ([Credence](https://www.credenceresearch.com/report/inspection-robots-market) · 요약)」, **30억 달러**(Global Market Insights 2025, 2035년 115억 달러, 14.7%) 「사실 ([GMI](https://www.gminsights.com/industry-analysis/inspection-robots-market) · 요약)」, **67.2억 달러**(360iResearch 2025, 이동형+고정형) 「사실 ([marketresearch.com](https://www.marketresearch.com/360iResearch-v4164/Inspection-Robots-Type-Mobile-Stationary-43423003) · 요약)」로 벌어진다. IFR은 2024년 전문 서비스 로봇 세계 판매 약 20만 대(+9%)를 집계했고 「사실 ([IFR](https://ifr.org/ifr-press-releases/news/service-robots-see-global-growth-boom), 2025)」, 2025년 점검·정비 응용군이 강하게 성장했다고 적는다 「사실 ([IFR WR 2026 요약](https://ifr.org/img/worldrobotics/Executive_Summary_WR_2026_-_Service_Robots.pdf), 2026 · 요약)」. 이 시장들은 「사족 점검 시장」으로 바꿔 부르지 않는다.

디지털 트윈은 MarketsandMarkets 최신 판이 2025년 **211.4억 달러에서 2030년 1,498.1억 달러(CAGR 47.9%)** 「사실 ([MarketsandMarkets](https://www.marketsandmarkets.com/Market-Reports/digital-twin-market-225269522.html) · 요약)」를 내지만, 같은 회사가 2023년 판에서는 2028년 1,101억 달러·61.3%를 냈다 「사실 ([MarketsandMarkets 보도자료](https://www.marketsandmarkets.com/PressReleases/digital-twin.asp), 2023 · 요약)」. 판마다 크게 바뀌는 전 산업 수치이므로 「점검 데이터가 흘러가는 인접 시장」으로 한 줄만 쓴다 「추정」. 인프라 전용 트윈 수치는 찾지 못했다 「미확인」.

### 한국: 사족 로봇 시장 금액은 공개 통계가 없다

국내 로봇산업 매출은 **2024년 6조 1,695억원(+3.2%)** 「사실 ([Invest Korea](https://www.investkorea.org/ik-kr/cntnts/i-3021/web.do), 한국로봇산업협회 실태조사 인용)」이 확인된 공식 집계이고, 분야별 매출과 사족 로봇 국내 시장 금액은 찾지 못했다 「미확인」. 공개된 국내 사족 도입은 수 대 단위다. LS일렉트릭 부산 사업장 Spot 2대 정식 운용 「사실 ([CEO스코어데일리](https://ceoscoredaily.com/page/view/2026092209291721332), 2026 · 요약)」, 세종시 이응다리 Spot 순찰 「사실 ([스마트시티 종합포털](https://smartcity.go.kr/2023/09/20/인공지능-자율주행-순찰로봇-이응다리-지킨다/), 2023 · 요약)」, 한국지역난방공사 현장의 레인보우로보틱스 사족 순찰 실증 「사실 ([레인보우로보틱스](https://rainbow-robotics.com/%eb%a0%88%ec%9d%b8%eb%b3%b4%ec%9a%b0%eb%a1%9c%eb%b3%b4%ed%8b%b1%ec%8a%a4-%eb%94%94%ec%8a%a4%ed%8e%99%ed%84%b0%ec%99%80-%ec%88%9c%ec%b0%b0%eb%a1%9c%eb%b4%87-%ec%82%ac%ec%97%85-%eb%a7%9e%ec%86%90/) · 요약)」가 그 예다. 「2030년 국내 20조원」 목표는 원문에서 확인되지 않아 쓰지 않는다 「미확인」.

### 발표에서 쓸 숫자와 SAM 좁히기

발표에서 방어 가능한 시장 문장은 세 층이다. 첫 층은 측정값이다. 「세계 사족 로봇은 2024년 약 2만 대·1.8억 달러가 팔렸고(IDC, 2025), 1위 Unitree는 3년간 33,294대를 팔았다(상장 서류, 2026).」 둘째 층은 범위다. 「조사기관들은 소프트웨어·서비스를 넣은 넓은 정의로 20~35억 달러, 연 18% 안팎 성장을 전망하지만 기관 사이 차이가 10배를 넘는다.」 셋째 층은 국내 공공 지출 신호다. 「소방청 2027 예산안에 4족보행로봇 40대 160억원(국회 확정 전).」 이 160억원은 로봇 구매 예산안이지 시장 규모가 아니고, 서울시 2025 예산안 3억원(시범 사업 합계)과 대상·연도가 달라 더하지 않는다.

SAM은 위에서 아래로 나누지 말고 아래에서 위로 쌓는다. IDC의 「상업형 약 28%」는 **대수** 비중이어서 금액(1.8억 달러)에 곱하면 틀린다(IDC는 금액은 상업형이 더 크다고 적는다). 대신 우리 SAM을 「국내 공공 위험 진입 사족 로봇 도입에 붙는 임무 계획·예행 소프트웨어」로 정의하고, 「소방청 2027 예산안 160억원 × 소프트웨어·예행 몫 가정 5% / 10% / 20% = 8억 / 16억 / 32억원」을 **민감도 예시**로만 보여 준다 「추정 · 몫 비율은 공개 근거 없음」. 공동구 관리기관·플랜트 실증 물량은 조달 공고를 찾지 못해 더하지 않는다 「미확인」. 사고 건수·밀폐공간 수·공동구 연장을 대수나 금액으로 바꾸는 계산은 하지 않는다.

## 4. 가치 숫자: 공급사 ROI는 많고 예행 효과의 측정은 없다

### Spot·ANYmal 공개 ROI는 공급사 발표다

가장 자세한 사례는 Boston Dynamics의 AB InBev Leuven 양조장이다. Spot이 10개 포장 라인에서 주당 개별 검사 **1,800건**, 첫 6개월 이상 약 150건 발견, 평균 수리 기간이 「몇 달에서 13일」로 줄었다고 하고, 50·40개 검사점짜리 임무 작성이 **1시간 미만**, 조작 교육 15분 미만이라고 적는다. 회수 기간 「첫해 안」은 담당자의 기대다 「사실 · 공급사 발표 ([Boston Dynamics](https://bostondynamics.com/case-studies/energy-savings-predictive-maintenance-at-ab-inbevs-largest-european-brewery/), 2024 무렵 게시)」. 호흡 장비가 필요하던 CO2 구역에서 Spot이 20분 안에 누설 2곳을 찾은 장면은 「사람 대신 들어간다」의 가장 가까운 공개 예다 「사실 · 공급사 발표 (같은 사례)」.

ANYbotics 블로그는 그리스 시멘트 공장 연 에너지 절감 **10만 달러 초과**와 계획 외 정지 회피 12개월 **30만 달러 초과**, 해상풍력 Equans의 **8개월 안 회수**(3년 ROI 250% 초과는 원문 스스로 projected), 화학 공장 Grace의 12개월 ROI 190% 초과를 적는다 「사실 · 공급사 발표 ([ANYbotics](https://www.anybotics.com/news/why-the-future-of-industrial-inspection-is-automated/), 2025)」. 어느 사례도 기준선·대조군·계산 방법을 공개하지 않는다. 반복되는 가치 축은 사람 시간 대체보다 점검 빈도 증가(월 1회에서 매일), 이상 조기 발견으로 계획 외 정지 회피, 위험 구역 진입 회피다 「추정」. 선행 검토 C1의 UKPN(47개 터널·연 160회 초과 점검·유지비 연 £100만 초과, 절감은 예상)과 AutoInspect(검사 동작 571/653)도 같은 성격의 참고다. 「POSCO 연 운영비 4.8만 달러」류 블로그 수치는 원 출처가 없어 쓰지 않는다 「미확인」.

### 수동 점검과 사고의 비용

국내 비교 기준선은 한국엔지니어링협회 2025 임금 실태 조사의 기술자 하루 평균임금 **309,345원**(월평균 근무 20.3일)이다 「사실 ([토큰포스트 보도](https://www.tokenpost.kr/news/economy/311649), 2025)」. 곱하면 기술자 1인 월 직접 인건비 약 628만원이지만 제경비·기술료를 뺀 값이고, 로봇 1대가 순회 1인을 대신한다는 근거는 없다 「추정」. 밀폐공간 진입 1건 800~15,000달러 같은 해외 수치는 판매사 블로그뿐이라 기준값으로 못 쓴다 「미확인」. 국내 진입 비용은 감시인·가스 측정·환기·구조 장비 항목을 직접 쌓는 편이 낫다 「추정」.

사고 비용은 사회 비용이다. NSC는 2024년 업무상 사망 1건 약 **154만 달러**, 총 1,814억 달러로 추정한다 「미확인 ([NSC](https://injuryfacts.nsc.org/work/costs/work-injury-costs/), 원문 403 · 요약)」. 한국 2023년 산재 경제적 손실 추정 **약 36.42조원**은 산재보상금에 「간접손실 = 직접손실 × 4」를 곱한 값이다 「미확인 ([더나은미래](https://www.futurechosun.com/archives/101006), 국회의원실 보도)」. 로봇 1대가 사고 몇 건을 막는다는 공개 측정이 없으므로, 이 값들은 위험의 크기를 보여 주는 맥락으로만 쓰고 절감액으로 곱하지 않는다 「추정」.

계획 외 정지는 점검 가치의 맥락이다. Siemens 2024 보고서는 대형 공장 정지 1시간 비용을 FMCG **3.6만 달러**에서 자동차 **230만 달러**로, 대형 공장 평균 월 27시간 손실로 추정한다(설문 181건 기반) 「사실 ([Siemens TCOD 2024](https://assets.new.siemens.com/siemens/assets/api/uuid:1b43afb5-2d07-47f7-9eb7-893fe7d0bc59/TCOD-2024_original.pdf), 2024)」. 대형 공장 평균이므로 국내 중소 현장이나 공동구에 곱하면 크게 부풀려진다 「추정」.

### 시뮬 예행으로 피할 현장 실패: 숫자는 우리가 만들어야 한다

「시뮬레이션이 현장 시험 횟수나 로봇 파손을 몇 % 줄였다」를 통제 비교로 잰 공개 수치는 찾지 못했다 「미확인」. 정성 근거는 있다. 로봇 개발자 인터뷰·설문 연구에서 현장 시험은 「시간이 많이 들고 비싸며 확장되지 않고 위험할 수 있다」고 답했다 「사실 ([Afzal 외](https://afsafzal.github.io/materials/AfzalSimulation21.pdf), 2021)」. 2026 조사 논문도 실세계 시험이 충실도는 높지만 비싸고 재현성이 낮다고 정리한다 「사실 ([arXiv 2602.02293](https://arxiv.org/pdf/2602.02293), 2026)」. McKinsey의 「디지털 트윈 20~30% 개선 잠재력」은 측정 방법이 없는 컨설팅 주장이다 「미확인 ([McKinsey](https://www.mckinsey.com/industries/public-sector/our-insights/digital-twins-boosting-roi-of-government-infrastructure-investments), 2025)」. 현장 실패의 실제 모습은 선행 검토 C4의 F1~F8(레일 걸림·거친 지형 낙상·지형 오판·라이다 단절 등)과 Dominion 시범에서 좁은 입구에 가끔 걸린 Spot 「사실 · 공급사 발표 ([Boston Dynamics](https://bostondynamics.com/case-studies/dominion-energy/) · 요약)」에 있다. 그중 보행·접촉 실패만 예행 대상이고, 센서 고장·관측 누락은 예행이 직접 막지 않는다.

팀 자체 기록은 예행이 무엇을 보여 주는지의 예로 쓸 수 있다. 미학습 지형 8종 시뮬 평가에서 v2 종합 성공은 **2,123/2,400회(88.46%)**지만, 좁은 디딤돌은 시드 다섯 개에서 **0~24/100회**였다 「사실 (선행 검토 2.2·2.3, 팀 시뮬 실측, 시드 42 등 조건 한정)」. 평균이 높아도 특정 바닥 조건에서는 대부분 실패한다는 뜻이고, 현장 스캔 위 예행의 쓰임은 「이 현장에 그런 조건이 있는가」를 출동 전에 묻는 것이다 「추정」. 이 수치는 실제 터널의 성공 확률이 아니다.

따라서 발표에서 내놓을 가치 숫자는 빌려 온 외부 ROI가 아니라 **우리가 잴 지표**다 「추정」. 같은 임무를 예행 있음과 없음으로 실기에 올렸을 때의 첫 실행 성공률, 현장 개입(사람이 손으로 잡거나 조종을 넘겨받은) 횟수, 현장 체류 시간이다. 비용은 「(기술자 일 단가 309,345원 × 인원 × 일수) + 출장·운송 + 현장 허가·감시인」으로 조립해 현장 하루를 줄인 값으로 말할 수 있다 「추정」. 12/10 전에 실내 시설 장면 하나라도 이 비교를 재면 「미확인」 칸 하나가 「사실 (팀 측정)」로 바뀐다.

## 5. 경쟁사와 대안: 지도·관제·트윈은 이미 팔린다

Boston Dynamics Spot + Orbit은 Autowalk 경로 기록·반복, 다지점 대시보드와 다기체 OTA, 온프레미스·클라우드 배치, 레이저 스캐닝 현실 캡처, Orbit 5.0(2025-05)의 360° 영상 시설 이력 Site View를 제공한다 「사실 ([Boston Dynamics 블로그](https://bostondynamics.com/blog/see-your-facility/) · [Digital Twin 솔루션](https://bostondynamics.com/solutions/digital-twin/), 연도 미표기 · [The Robot Report](https://www.therobotreport.com/orbit-5-0-adds-features-boston-dynamics-spot-quadruped-robot/), 2025)」. 두 공식 원문에는 임무의 시뮬 예행이 나오지 않는다 「사실 (원문 열람)」. 다만 Isaac Sim은 Spot을 내장 자산으로 주고 NVIDIA는 Isaac Lab 학습 정책을 Spot SDK로 실기에 올린 글을 냈다 「사실 ([NVIDIA 블로그](https://developer.nvidia.com/blog/closing-the-sim-to-real-gap-training-spot-quadruped-locomotion-with-nvidia-isaac-lab/) · 요약)」. Orbit 안의 예행 기능 유무는 영업 확인 전까지 「미확인」이다.

ANYbotics ANYmal은 Framence 실사 디지털 트윈에서 발전소 검사 임무를 계획·수정·실행했고 「검사 임무 시뮬레이션 정확도 향상」이라는 문구가 있으나 다리 동역학 시뮬은 설명되지 않는다 「사실 ([ANYbotics](https://www.anybotics.com/photorealistic-digital-twin/), 2023)」. Data Navigator는 검사 자료 분석·일정·망분리 배치를 지원한다 「사실 ([ANYbotics](https://anybotics.com/solutions/data-navigator) · 요약)」. Cognite InRobot은 Spot·ANYmal 임무를 3D 모델 위에서 계획한다 「사실 ([Cognite](https://docs.cognite.com/cdf/inrobot) · 요약)」. Unitree Go2·B2 순정 앱은 L1 라이다 점군 지도와 경로 지정 자율 순찰을 설명한다 「사실 ([Unitree Go2](https://www.unitree.com/go2/) · 요약)」. Deep Robotics는 공동구 점검 솔루션과 디지털 트윈 플랫폼을 내걸고, X30이 SP Group과 싱가포르 **40 km 지하 송전 터널**을 순찰하며, X30과 바퀴다리형 LYNX M20의 다기체 터널 점검 체계를 발표했다 「사실 ([Robotics 24/7](https://www.robotics247.com/article/deep_robotics_deploys_x30_robot_dog_to_inspect_singapore_power_cable_tunnel), 2025 · [Deep Robotics](https://deeprobotics.cn/en/index/electric) · 요약)」. 국내 공동구 시장에 들어오면 가장 직접적인 저가 경쟁자가 된다 「추정」. Formant는 다기체 단일 화면 관제와 Isaac 시뮬레이터 연동을 내세운다 「사실 ([Formant](https://formant.io/?p=19144) · 요약)」.

국내에서는 레인보우로보틱스 RBQ가 험지·위험 환경 순찰·점검을 내세우고 도구공간과 순찰로봇을 공동 개발한다 「사실 ([레인보우로보틱스](https://rainbow-robotics.com/%EC%A0%9C%ED%92%88%EC%86%94%EB%A3%A8%EC%85%98/%EC%82%AC%EC%A1%B1%EB%B3%B4%ED%96%89-%EB%A1%9C%EB%B4%87/), 2025 · [보안뉴스](https://m.boannews.com/html/detail.html?idx=139003), 2025 · 요약)」. 현대차그룹은 Spot 기반 공장 순찰을 운영하고 「사실 ([노컷뉴스](https://nocutnews.co.kr/news/5626841), 2021 · [뉴시스](https://www.newsis.com/view/NISX20260713_0003706330), 2026 · 요약)」 6륜 무인소방로봇 4대를 기증했다 「사실 ([현대차그룹](https://www.hyundaimotorgroup.com/ko/story/unmanned-firefighting-robot-physical-ai), 2026)」. 에이딘로보틱스·KAIST·KIRO 등은 1차 자료를 확보하지 못했다 「미확인」.

실사 스캔을 시뮬로 옮기는 도구도 이미 있다. NVIDIA Omniverse NuRec은 센서 자료를 3D 가우시안 스플래팅으로 재구성해 OpenUSD로 Isaac Sim에 넣고 「사실 ([NVIDIA NuRec](https://developer.nvidia.com/omniverse/nurec) · 요약)」, Niantic Scaniverse는 스플랫과 충돌 메시를 Isaac Sim에 넣어 Isaac Lab으로 정책을 학습하는 real2sim·sim2real 흐름을 보여 준다 「사실 ([Niantic](https://www.nianticspatial.com/campaigns/flexion-nvidia-humanoid-real2sim-sim2real) · 요약)」.

그러므로 **독자 기능으로 주장하면 안 되는 것**은 라이다 3D 지도 작성, 지도 위 경로·경유점 임무 계획, 기록 경로 반복, 다기체·다지점 관제, 트윈에서 실기로 임무 지시, 실사 스캔의 Isaac Sim 자산화, 학습 보행 자체다 「추정 (위 사실들에서)」. 공개 자료에서 찾지 못한 것은 (a) 스캔 자산을 물리 시뮬 장면으로 바꾸고 (b) 같은 임무 정의를 자체 험지 RL 정책 또는 순정 보행으로 예행하고 (c) 그 임무를 수정 없이 실기 Go2로 보내며 (d) 관제 화면에서 기체마다 실기·시뮬을 표시하는 **결합**이다 「추정 · 검색으로 부재를 증명할 수 없음」. 각 부품은 이미 존재하므로 차이는 기술이 아니라 「부품 결합과 Go2 대상 통합」이다.

한 가지 범위 주의가 있다. 선행 검토 시점(2026-08 결정)에는 **자체 학습 정책의 실기 이전이 목표에서 제외**됐다 「사실 (선행 검토 1절·B1)」. **팀장 정정 (11/21 18:3x): 이것은 초기 제외였고, 지금은 START · AME-2 를 실기에 입히는 중이다. 시뮬은 lead-lx 와 진행 중이며 1차 teacher 배포만 됐고 실기용은 진행 중.** 실기에서 실제로 도는지는 아직 재지 않았다 「미확인 · lead-lx 에 문의함」. 확인 전에는 「같은 임무 입력이 실기를 움직인다」까지만 말하고 「우리 정책이 현장에서 더 잘 걷는다」고 말하지 않는다.

## 6. 한 줄 메시지 후보

첫째, **「사람이 먼저 들어가 죽는 자리에 로봇을 먼저 보내고, 그 로봇이 그 현장을 걸을 수 있는지는 출동 전에 확인한다.」** 근거는 질식 치명률 41.9%와 사망자 132명 중 구조 진입 30명(KOSHA 2026), 평택 수색 진입 순직 3명(2022)이다. 「출동 전에 확인」은 우리 측정이 나오기 전까지 기능 설명이지 효과 주장이 아니다.

둘째, **「2027년 소방청은 4족보행로봇 40대를 사려 한다. 우리는 그 로봇이 처음 들어갈 현장을 먼저 걸어 보는 도구다.」** 근거는 소방청 2027 예산안 160억원(국회 확정 전)과 소방장비관리법 실증체계(2026-12 시행), 서울소방의 공동구 선제 투입 계획이다. 수요 신호는 사족 로봇에 대한 것이며 우리 플랫폼 수요가 아니라는 단서를 붙인다.

셋째, **「평균 88%가 숨기는 디딤돌 0~24%. 현장 지도 위 예행은 그 현장의 약한 조건을 실기 전에 드러낸다.」** 근거는 팀 시뮬 실측(v2 2,123/2,400회, 디딤돌 시드별 0~24/100회, 선행 검토 2.2·2.3)과 현장 시험이 비싸고 위험하다는 개발자 연구(Afzal 2021). 실제 현장 성공률이 아님을 함께 말한다.

넷째, **「지도와 관제는 이미 있다. 우리는 그 지도 위에서 같은 임무를 먼저 걸어 보고, 같은 입력으로 실기를 보낸다.」** 근거는 Orbit·ANYmal·Deep Robotics가 지도·관제·트윈을 이미 판다는 사실과, 공개 자료에서 물리 예행과 실기 전송의 결합을 찾지 못했다는 조사 결과다. 경쟁사를 깎지 않고 빈칸에 서는 문장이라 질문에 가장 덜 흔들린다.

다섯째, **「현장 한 번 스캔, 실패는 시뮬에서, 현장 하루를 아낀다.」** 근거는 기술자 일 평균임금 309,345원(2025)과 현장 시험의 비용·위험(Afzal 2021)이지만, 「하루를 아낀다」는 아직 「추정」이다. 발표 전 첫 실행 성공률·현장 개입 횟수·체류 시간을 예행 있음과 없음으로 한 번이라도 재야 쓸 수 있다.

## 맺음

이번 조사로 「so what?」에 대한 답의 모양이 바뀌었다. 시장 크기로 설득하려 하면 1.8억 달러와 35억 달러 사이에서 질문을 받고, 공급사 ROI를 빌려 오면 「그건 Spot의 숫자」라는 반문을 받는다. 공개 자료가 단단하게 받쳐 주는 것은 두 가지뿐이다. 위험 첫 진입은 실제로 사람이 죽는 문제이고, 한국 공공 부문은 2027년을 전후해 사족 로봇 실증으로 그 문제에 돈을 쓰기 시작했다. 그 사이에 비어 있는 것이 「처음 가는 현장에서 그 로봇이 실패하지 않을지 미리 아는 방법」이고, 그 효과를 잰 숫자는 아무도 공개하지 않았다. 따라서 FOOTHOLD가 발표에서 가장 강하게 설 자리는 남의 숫자를 인용하는 쪽이 아니라 그 빈칸의 첫 측정값을 내놓는 쪽이다.

남은 빈칸은 분명하다. 전국 공동구 총연장과 법정 점검 주기, 국회 확정 소방청 예산, 통합사업자의 지불 의사와 가격대, Orbit 안의 예행 기능 유무, 실기에서 자체 정책이 도는지 여부다. 앞의 셋은 공문서 확인으로, 넷째는 영업 문의로, 다섯째는 팀 안에서 바로 닫을 수 있다.

## 출처 목록

국내 현장·정책

- 고용노동부·안전보건공단, 밀폐공간 질식재해예방 안전작업 가이드 (2026) · https://info.cak.or.kr/download.do?uuid=08d223c3-5233-436a-8427-0ddbf304da60.pdf
- 고용노동부, 질식 재해 고위험사업장 집중점검 (2025) · https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=17829
- 매일신문, 대구지방고용노동청 밀폐공간 사업장 (2026) · https://www.imaeil.com/page/view/2026080510390699105
- 서울시 안전분야 누리집, 2026 도로시설물 현황 (2026) · https://news.seoul.go.kr/safe/?p=45739
- 보안뉴스, 서울 공동구 안전점검 (2023) · https://m.boannews.com/html/detail.html?idx=117441
- 서울시 안전분야 누리집, 시설물 안전점검 주기 (연도 미표기) · https://news.seoul.go.kr/safe/archives/327
- 한국화재보험협회, 여의도 공동구 화재 자료 (연도 미표기) · https://kfpa.or.kr/mem/pdf_file/B/10/B10_1-5.pdf
- 서울신문, 여의도 공동구 화재 (2000) · https://m.seoul.co.kr/news/2000/02/21/20000221027004
- 비즈니스워치, KT 아현 화재 보상 (2018) · https://news.bizwatch.co.kr/article/mobile/2018/12/28/0016
- 아주경제, KT 아현 화재 1년 (2019) · https://www.ajunews.com/view/20191121102312646
- 노컷뉴스, 소방청 2027 예산안 (2026) · https://nocutnews.co.kr/news/6572990
- 파이낸셜뉴스, 소방청 2027 예산안 (2026) · https://www.fnnews.com/news/202609041550528147
- 국민참여입법센터, 소방장비관리법 개정 (2026) · https://opinion.lawmaking.go.kr/lmSts/govLm/2000000330366/detailRP?yType=I
- 서울시 안전분야 누리집, 서울소방 2026 업무계획 (2026) · https://news.seoul.go.kr/safe/archives/517409
- 서울신문, 서울소방 사족 로봇 시연 (2026) · https://m.seoul.co.kr/news/2026/02/26/20260226500254
- 서울시 안전분야 누리집, 은평공동구 레일 관측장비 (2019) · https://news.seoul.go.kr/safe/?p=501376
- 정책브리핑, 제4차 지능형로봇 기본계획 (2024) · https://m.korea.kr/news/policyNewsView.do?newsId=148924862
- 헤럴드경제, 2025 산업재해 부가통계 (2026) · https://www.heraldk.com/article/2026033019000041446
- 세계일보, 여천NCC 폭발 (2022) · https://www.segye.com/newsView/20220211517187
- 경향신문, 울산 SK에너지 폭발 (2025) · https://www.khan.co.kr/article/202510231358001/
- 서울신문, 평택 냉동창고 화재 순직 (2022) · https://m.seoul.co.kr/news/2022/01/06/20220106500095
- 스마트시티 누리집, 2025 공간정보 정책사업 (2025) · https://smartcity.go.kr/2025/05/02/25년-5800억-원-규모-공간정보-정책사업-공간정보-인/
- 매일신문, 디지털 트윈 비중 (2025) · https://www.imaeil.com/page/view/2025050211044571882

시장 규모

- IDC, 세계 사족 로봇 시장 (2025) · https://www.idc.com/resource-center/press-releases/%e4%b8%ad%e5%9b%bd%e5%8e%82%e5%95%86%e9%a2%86%e8%b7%91%ef%bc%8c%e5%a4%9a%e5%85%83%e5%ba%94%e7%94%a8%e8%b5%b7%e8%88%aa-idc%e5%8f%91%e5%b8%83%e5%85%a8%e7%90%83%e5%9b%9b%e8%b6%b3/
- TechSci Research, Quadruped Robot Market (2025 무렵) · https://www.techsciresearch.com/news/23753-quadruped-robot-market.html
- TechSci Research, 다른 판 (연도 미상) · https://www.techsciresearch.com/report/quadruped-robot-market/28841.html
- MarketsandMarkets, Quadruped Robot Market (2026 무렵) · https://www.marketsandmarkets.com/Market-Reports/quadruped-robot-market-186625495.html
- Precedence Research, Quadruped Robot (2026 무렵) · https://www.precedenceresearch.com/table-of-content/7836
- Bosson Research, Global Quadruped Robot (2025) · https://www.marketresearch.com/Bosson-Research-v4252/Global-Quadruped-Robot-Research-Status-43405598
- Global Info Research, Global Legged Robot (2025) · https://www.marketresearch.com/GlobalInfoResearch-v4117/Global-Legged-Robot-Manufacturers-Regions-42309904
- 상하이증권거래소 영문판, Unitree 상장 서류 (2026) · https://english.sse.com.cn/news/newsrelease/voice/c/c_20260811_10828578.shtml
- The Robot Report, Unitree IPO (2026) · https://www.therobotreport.com/unitree-ipo-shows-a-real-hardware-business-the-humanoid-case-is-still-early/
- The Star (Bloomberg 재게재), Spot 가동 대수 (2025) · https://www.thestar.com.my/tech/tech-news/2025/11/21/a-us100000-robot-dog-is-becoming-standard-in-policing---and-raising-ethical-alarms
- 前瞻产业研究院 (GGII 인용), 사족 로봇 판매 (2025) · https://www.qianzhan.com/analyst/detail/220/251022-4f4338c7.html
- Credence Research, Inspection Robots (연도 미상) · https://www.credenceresearch.com/report/inspection-robots-market
- Global Market Insights, Inspection Robots (2025~2026) · https://www.gminsights.com/industry-analysis/inspection-robots-market
- 360iResearch, Inspection Robots (2025~2026) · https://www.marketresearch.com/360iResearch-v4164/Inspection-Robots-Type-Mobile-Stationary-43423003
- IFR, Service robots see global growth boom (2025) · https://ifr.org/ifr-press-releases/news/service-robots-see-global-growth-boom
- IFR, World Robotics 2026 Service Robots 요약 (2026) · https://ifr.org/img/worldrobotics/Executive_Summary_WR_2026_-_Service_Robots.pdf
- MarketsandMarkets, Digital Twin Market (2025 무렵) · https://www.marketsandmarkets.com/Market-Reports/digital-twin-market-225269522.html
- MarketsandMarkets, Digital Twin 보도자료 (2023) · https://www.marketsandmarkets.com/PressReleases/digital-twin.asp
- Invest Korea, 국내 로봇산업 (2025~2026 게시) · https://www.investkorea.org/ik-kr/cntnts/i-3021/web.do
- CEO스코어데일리, LS일렉트릭 Spot (2026) · https://ceoscoredaily.com/page/view/2026092209291721332
- 스마트시티 종합포털, 세종 이응다리 Spot (2023) · https://smartcity.go.kr/2023/09/20/인공지능-자율주행-순찰로봇-이응다리-지킨다/
- 레인보우로보틱스, 지역난방공사 순찰 실증 (연도 미표기) · https://rainbow-robotics.com/%eb%a0%88%ec%9d%b8%eb%b3%b4%ec%9a%b0%eb%a1%9c%eb%b3%b4%ed%8b%b1%ec%8a%a4-%eb%94%94%ec%8a%a4%ed%8e%99%ed%84%b0%ec%99%80-%ec%88%9c%ec%b0%b0%eb%a1%9c%eb%b4%87-%ec%82%ac%ec%97%85-%eb%a7%9e%ec%86%90/

가치 숫자

- Boston Dynamics, AB InBev 사례 (2024 무렵) · https://bostondynamics.com/case-studies/energy-savings-predictive-maintenance-at-ab-inbevs-largest-european-brewery/
- ANYbotics, Why the future of industrial inspection is automated (2025) · https://www.anybotics.com/news/why-the-future-of-industrial-inspection-is-automated/
- Boston Dynamics, Dominion Energy 사례 (연도 미표기) · https://bostondynamics.com/case-studies/dominion-energy/
- 토큰포스트, 2025 엔지니어링 임금 실태 조사 (2025) · https://www.tokenpost.kr/news/economy/311649
- NSC Injury Facts, Work Injury Costs (2024 자료) · https://injuryfacts.nsc.org/work/costs/work-injury-costs/
- 더나은미래, 산재 경제적 손실 (연도 미상, 2023 값) · https://www.futurechosun.com/archives/101006
- Siemens, The True Cost of Downtime 2024 (2024) · https://assets.new.siemens.com/siemens/assets/api/uuid:1b43afb5-2d07-47f7-9eb7-893fe7d0bc59/TCOD-2024_original.pdf
- Afzal 외, Simulation for Robotics Test Automation (2021) · https://afsafzal.github.io/materials/AfzalSimulation21.pdf
- arXiv 2602.02293, 로봇 시험 조사 논문 (2026) · https://arxiv.org/pdf/2602.02293
- McKinsey, Digital twins for government infrastructure (2025) · https://www.mckinsey.com/industries/public-sector/our-insights/digital-twins-boosting-roi-of-government-infrastructure-investments

경쟁사·대안

- Boston Dynamics, See your facility (연도 미표기) · https://bostondynamics.com/blog/see-your-facility/
- Boston Dynamics, Digital Twin 솔루션 (연도 미표기) · https://bostondynamics.com/solutions/digital-twin/
- The Robot Report, Orbit 5.0 (2025) · https://www.therobotreport.com/orbit-5-0-adds-features-boston-dynamics-spot-quadruped-robot/
- NVIDIA, Spot Isaac Lab sim-to-real (연도 미표기) · https://developer.nvidia.com/blog/closing-the-sim-to-real-gap-training-spot-quadruped-locomotion-with-nvidia-isaac-lab/
- ANYbotics, Photorealistic digital twin (2023) · https://www.anybotics.com/photorealistic-digital-twin/
- ANYbotics, Data Navigator (연도 미표기) · https://anybotics.com/solutions/data-navigator
- Cognite, InRobot 문서 (연도 미표기) · https://docs.cognite.com/cdf/inrobot
- Unitree, Go2 (연도 미표기) · https://www.unitree.com/go2/
- Deep Robotics, Energy & Power (연도 미표기) · https://deeprobotics.cn/en/index/electric
- Robotics 24/7, Deep Robotics 싱가포르 케이블 터널 (2025) · https://www.robotics247.com/article/deep_robotics_deploys_x30_robot_dog_to_inspect_singapore_power_cable_tunnel
- Formant, Unleash Spot (연도 미표기) · https://formant.io/?p=19144
- NVIDIA, Omniverse NuRec (연도 미표기) · https://developer.nvidia.com/omniverse/nurec
- Niantic Spatial, Flexion NVIDIA real2sim (연도 미표기) · https://www.nianticspatial.com/campaigns/flexion-nvidia-humanoid-real2sim-sim2real
- 레인보우로보틱스, 사족보행 로봇 (2025) · https://rainbow-robotics.com/%EC%A0%9C%ED%92%88%EC%86%94%EB%A3%A8%EC%85%98/%EC%82%AC%EC%A1%B1%EB%B3%B4%ED%96%89-%EB%A1%9C%EB%B4%87/
- 보안뉴스, 레인보우로보틱스·도구공간 협력 (2025) · https://m.boannews.com/html/detail.html?idx=139003
- 노컷뉴스, 기아 오토랜드 광명 Spot (2021) · https://nocutnews.co.kr/news/5626841
- 뉴시스, 현대차 울산 공장 순찰 (2026) · https://www.newsis.com/view/NISX20260713_0003706330
- 현대차그룹, 무인소방로봇 (2026) · https://www.hyundaimotorgroup.com/ko/story/unmanned-firefighting-robot-physical-ai

선행 검토

- 맹라현, 서비스 방향 검토: 성과에서 활용 방향까지 v1.1 (2026-10-07) · foothold-lab docs/research/20261007-underground-recon-service-review.md

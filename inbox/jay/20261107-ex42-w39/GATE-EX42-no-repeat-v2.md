> 분류: A/평가 · EX-42 출발 관문 재감사
> 작성: analyst · 2026-11-07
> 근거: W34 33행 · runner 5e0c37a1 · I36 1d382122 · W35 a8381f8a · 영상 진단 b07b4089 · 원자료/CPU 재계산
> 요지: 남은 막음은 예행 대기만이 아니다. 실행 구현·소비 연결과 재현된 코드 결함이 남아 있다.
> 상태: v2.0 · W39 감사 완료 · 출발 막음 26행 유지 · GPU/Kit/운영 원장 변경 없음

# EX-42 반복 실수 방지 출발표 재감사 · W39

**현재 확인한 고정 코드로는 EX-42 출발 불가다.** 준비 단계의 방어 코드가 많이 생겼지만 실제 학습·평가·영상·보고 연결은 완성되지 않았다. 새 자료 세 건을 반영해도 남은 막음을 모두 “예행만 하면 됨”으로 부를 수 없다.

W34의 **33행 중 출발 막음 26행은 유지**한다. 나머지 7행은 기존 코드 또는 운영 규칙이 확인된 행이다. 7행도 EX-42 전체 실행을 완료했다는 뜻은 아니다. 이번 범위 CPU **56 PASS**와 추가 반례 **3건 재현**을 따로 센다. 같은 문제를 새 번호로 부풀리지 않고 기존 G01·G11·G25에 넣었다.

## 1. 먼저 결정할 수 있는 결론

| 질문 | 재감사 결론 | 직접 확인한 근거 |
|---|---|---|
| 남은 막음이 예행 대기뿐인가 | **아니오** | `EX42Runtime`은 아직 준비 전용이며 시작 경로가 본학습을 거절한다. W35 다섯 모듈도 runner의 비시험 코드에서 호출을 찾지 못했다. E01·E02 |
| I36으로 점수 대기 재발이 막혔나 | **30분 정체 탐지는 구현됨. 사전 예방과 EX-42 연결은 별도** | 최근 출력 OK, 31분 무출력·CPU 정체 FAIL을 포함한 19시험 재실행. 다음 점수가 가까울 때 긴 P2 진입을 막는 장치의 증거는 없다. E03 |
| W35 다섯 행을 닫아도 되나 | **아니오** | 16시험은 통과. 반복 측정의 지형을 바꿔도 반복 폭으로 허용하는 추가 반례가 PASS. 나머지 생산자·소비자 연결과 실측도 남음. E04 |
| 검은 영상 원인이 고쳐졌나 | **아니오** | 진단 추가 후 실제 queue 827도 rc1. 원자료 119행·검은 PNG 47개를 직접 다시 세고 SHA·픽셀을 확인. E05 |
| Linux 설치 뒤 필요한 것만 남았나 | **아니오** | native 장치·렌더 검증은 설치 날 해야 하지만 런타임, 전체 관문 소비, 증거 검증, 알림 중복 방지 연결은 설치 전 CPU로 준비할 수 있다. E01·E06 |

**보고 문장도 고쳐야 한다.** “CPU 준비 완료·예행 대기”는 모듈 단위 시험에만 해당한다. 프로젝트 출발 행은 `구현/결함 수정 → 실제 소비 연결 → 같은 최종 HEAD의 예행` 중 어디에 있는지 구별해야 한다. 코드가 존재한다는 이유로 뒤의 두 단계를 생략하지 않는다.

### 감사 기준과 범위

- 직접 재확인: 지정 네 고정 HEAD의 clean 상태, 시험 네 묶음, 코드 소비 검색, 답을 아는 반례 셋, 검은 RGB 원자료. 모두 CPU와 읽기만 사용했다.
- 탐색 범위: runner `runner-ex42-v016` 5e0c37a1, W35 `scripter-ex42-gates` a8381f8a, I36 `scripter-ops-check-i36` 1d382122, 영상 `stagevideo-darkdiag-1107` b07b4089. 다른 브랜치에 더 새 미전달 구현이 있을 가능성까지 부정하지 않는다. 새 고정 HEAD가 오면 해당 행과 호출부만 재감사한다.
- pipeline의 장비·WSL 수치는 그 보고서를 읽은 범위다. 이번 감사에서 native Linux 설치·속도·GPU·Telegram 수신을 재측정한 것으로 합산하지 않았다.
- 각 행의 “없음 · 막음”은 **해당 출발 조건을 완성한 증거가 없음**이다. 이미 생긴 부분 코드까지 없다는 뜻이 아니다. “연결 전”은 예행 미실행과 다르다.
- 원래 R·M·I·PM의 전수 대응표와 재발 피해는 [W34 보존본](archive/W34-v1.md)에 남겼다. 이번 표는 동일한 G01~G33을 재판정하고 I34~I38을 기존 원인에 추가한다. 행을 삭제하거나 평가 범위를 줄이지 않았다.

### 최신 결정 정정

W34의 “D183을 바꾼다”는 표현은 **폐기**한다. 11/06 21:2x 결정은 D183의 쉬운 것부터·이전 학습 유지·분석 뒤 다음 과제 원칙이 **이어진다**고 정정했다. 어려운 미션은 20,000 뒤가 기본 순서이고 실제 선행 능력이 진입을 결정한다. 10,000 블록 끝에 승인 대기로 학습을 멈추지 않는다.

11/07 08:5x에는 v5의 미달 `deferred`, 선행을 갖춘 다른 과제로 이동, 40,000 예약표, 유지 미회복 때 복습 원칙을 승인했다. 재도전은 개선 추세·원인 처치 근거에 따라 우선순위를 올린다. [decisions.tsv 174·183·198·199·217행](<D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/decisions.tsv:217>)을 대조했다. 반면 감사한 runner YAML은 정본 v0.16·D182와 준비 전용 상태다. 따라서 G02는 최신 결정→정본→실행 YAML→소비 코드 대조가 필요하다. 이 문서가 새 수치나 보상 조정 권한을 승인하지 않는다.

## 2. 33행 처분표

판정 칸은 기존 검사와 연결할 수 있도록 다섯째 열에 두었다. 다만 현재 검사기의 기본 대상은 아홉 행뿐이므로 §3.1 고침 없이 이 표를 읽었다고 전체 33행을 검증했다고 말하면 안 된다.

| 관문 · 추가 출처 | 재발 피해 | 이번에 확인한 장치 | 아직 필요한 일 · 닫는 증거 | 판정 | 담당 |
|---|---|---|---|---|---|
| G01 · R6/R20 | 일부 시험만 통과하고 긴 학습 중 새 가지가 처음 실패 | E01 준비 전용 출발 거절, E02 관문 표 읽기, runner 18 PASS | 실제 런타임·사슬 구현. 전체 필수 관문 ID를 읽도록 §3.1 수정. 모든 단계·재개·실패 가지를 최종 HEAD로 예행 | 없음 · 막음: 구현·검사 범위 결함·예행 | runner · verifier · lead |
| G02 · R3/R16 · 최신 결정 | 옛 규칙으로 다른 실험을 실행 | v5 승인 기록 확인, 기존 단일축 검증 함수 있음 | D183 정정·40,000 셈·시간 상자·선행표·복습/재도전·블록 끝 계속을 정본/YAML/소비자/시험에 동기화. v0.16 준비표는 대체 못 함 | 없음 · 막음: 정본·설정·구현 정합 | planner · runner · lead |
| G03 · 고정 HEAD | 예행과 다른 코드로 본학습 | E02 `audit_locked_checkout` 임시 git·읽기 전용·SHA 반례 PASS | 실제 실행 파일·설정까지 보호 목록 고정, 시작기가 함수를 호출, 원격/실행 HEAD·dirty·writable 실증. 현재 정의 외 호출 없음 | 없음 · 막음: 연결·고정 사본 예행 | runner |
| G04 · 단일 장비 | GPU 충돌·Windows/Linux 병렬 착각 | E06 Windows 장비 표, E01 machine profile 코드 있음 | 실제 EX-42 profile 소비, native Linux GPU UUID·driver·메모리·속도·촬영 동시성. WSL CPU는 대체 불가 | 없음 · 막음: 연결·설치 날 실측 | pipeline · runner · super2 |
| G05 · 실제 parser | CLI/import/출력 경로 오류로 첫 실행 실패 | E01 파서·기기 경로 검사, 미설치 때 JSON rc2; 설치일 import 시험 분리 | 최종 native 환경에서 지정 Python/rsl/Isaac 실제 import·argv·새 산출 SHA. 이번 CPU PASS가 설치 성공을 뜻하지 않음 | 없음 · 막음: 설치 날 예행 | runner · pipeline |
| G06 · 실행 권한 | 과도한 종료 또는 불필요한 재승인 대기 | 기존 승인/PID 확인 규칙 유지 | 출발 카드에 허용 범위 기록. 이번 감사는 GPU·종료 권한을 추가하지 않음 | 있음 · 규칙: 기존 범위 유지 | lead |
| G07 · 학습 상태 재개 | optimizer·RNG·성과창·예산 상태 손실 | EX-41 상태 시험은 기존 근거 | EX-42 시간 상자·노출·연장·복습·미션/10,000 블록 상태 재개 구현과 중간/경계 동일성 시험 | 없음 · 막음: EX-42 상태 구현·예행 | runner · analyst |
| G08 · 상태 파일 | reader 충돌로 저장/학습 실패 또는 unknown을 0으로 소비 | E02 Windows 열린 핸들에서 bounded unknown→재시도 시험 PASS; E06 겹침 조사 | `ex42_status` writer와 실제 관리판·감시기 reader 연결. 검색상 운영 호출 없음. 최종 파일/호출부로 동시 저장·읽기 | 없음 · 막음: 연결·실파일 예행 | runner · pipeline |
| G09 · I36/I37/I38 | 긴 작업 뒤 P1 지연·빈 GPU·수동 큐 손상 | I36 사후 탐지, G11 P1 marker 함수 CPU시험, 기존 잠금 | 다음 점수 30분 이내 P2 진입 방지와 단위 사이 양보 연결, 저장본 도착 시 영상 독립 등록, 필수 큐 키 보존·board 재독. 실제 EX-42 큐 영수증 | 없음 · 막음: 예방 장치·소비 연결·예행 | lead · runner |
| G10 · I36 | watcher가 살아만 있고 점수를 못 냄 | E03 I36 30분 무출력·CPU 정체 FAIL, 19 PASS | EX-42 watcher/PID/HEAD/heartbeat 목록, detector 소비·경보·복구 연결. I36 탐지는 자동 복구 또는 출발 완료 아님 | 없음 · 막음: EX-42 감시 연결·예행 | runner · lead |
| G11 · I24/I36 | W78 조각이 다른 시험지를 재거나 P1을 막음 | E04 full/unit 지형 동일성 검사와 16 PASS 묶음 | 반복 자료에도 지형·phase identity 검사(§3.2), 같은 코드 full/unit·반복 폭·실제 분할 큐 양보, 최종 runtime 연결 | 없음 · 막음: 재현 결함·연결·실측 | scripter · runner |
| G12 · I31/I33/I38 | queue 손상·취소를 완료로 오기 | 기존 잠금·고유 tmp·cancelled 분리 코드 유지 | I38 수동 writer의 필수 키 누락은 G09·G25에서 열어 둠. 큐 라이브러리 존재로 전체 연결까지 닫지 않음 | 있음 · 부분 코드: 연결은 G01/G09 | runner |
| G13 · 점수 상태/회차 | 측정 실패를 성적 미달로 오인·과거 PASS 사용 | E02 model_N/SHA와 stale·corrupt 구별 CPU시험 | `validate_score_pair`를 실제 EX-42 producer/retry/판정에 연결, 시간 상자와 측정 RETRY 분리. 정확한 N 계약 예행 | 없음 · 막음: 점수 생산·소비 연결 | runner · verifier |
| G14 · 수치/영상 분리 | 영상 실패 한 편이 유효 숫자를 무효화 | E04 immutable component receipt와 supersession CPU시험 | 실제 숫자 PASS·영상 FAIL→재시도에서 숫자 바이트 보존. EX-42 생산자 연결 없음 | 없음 · 막음: 연결·실자료 영수증 | runner · scripter |
| G15 · 지도 셋 | 복원/끔 누락으로 실패를 놓침 | E02 정확한 mode×command 집합 거절 시험 | 실제 13명령×3모드 점수 producer와 보고 소비 양쪽 연결. 함수는 정의 외 호출 없음. 단계별 추가 축도 명시 | 없음 · 막음: 점수·보고 연결 | runner · analyst |
| G16 · 지표/분모 | 다른 단위·표본을 합쳐 잘못 승급 | W10·W18에서 명령 투영 비, 속도 오차, 생존 분리 재검산. v5 결과 전 기준 구조 있음 | EX-42 최종 기준표 SHA·종류/레벨/명령별 반복 폭·가정 목록과 실제 판정 함수 일치. 미측정 값을 완료로 채우지 않음 | 없음 · 막음: 기준표·반복 폭·소비 | analyst · planner · verifier |
| G17 · 실제 학습 조건 | 주석/요청값을 실제 처방으로 착각 | E02 저장 env/agent에서 관측값만 추출하는 함수 CPU시험 | n0와 모든 경계의 실제 명령/지도/DR/보상/레벨 값 연결, requested/realized 차이 검증. 정의 외 호출 없음 | 없음 · 막음: 기록 생산·소비 연결 | runner · planner |
| G18 · 자동 규칙 | 승인된 보정이 한 번도 작동하지 않음 | E02 decision ID·허용값·경계 검증 함수 | v5 허용 자동 행동만 실제 단계에 연결. 승급·복습·보류·재도전 true/false 입력과 적용 영수증. 함수 단독 PASS로 부족 | 없음 · 막음: runtime 연결 | runner · verifier |
| G19 · 정식 분석 | lr 바닥·망각을 늦게 발견 | EX-41 단계 보고서·W78 m3750 원자료 보충 완료 | EX-42 단계/10,000 블록 자동 호출, 곡선·KL/lr/std·위상·W57/W78·CMP·1x 판독 누락 계약. EX-41 보고서는 대체 아님 | 없음 · 막음: EX-42 보고 연결 | analyst · runner · lead |
| G20 · 지형 식별 | flat/rough·env ID 혼동 | E04 종류/레벨 선택·flat 존재·raw/video identity CPU시험 | 새 recorder의 NPZ 필드를 EX-42 촬영·측정에 연결. 실제 타일 manifest와 장면·raw tick 대조 | 없음 · 막음: 연결·새 촬영 실증 | scripter · runner |
| G21 · I34 | 공통 로더/화풍이 달라 영상 전체 재촬영 | E04 loader/composer/style/frame audit/lead review SHA 관문 | 최종 producer 연결, 첫 한 편 전 프레임·팀장 판독. E05 검은 RGB의 유효 수집/결측·재시도 처분을 검증해야 함 | 없음 · 막음: 연결·렌더 실패·판독 | scripter · runner · lead |
| G22 · I34/I37 | 실패/없는 영상도 playlist 완료 | E04 고정 요청 ID·영수증·playlist 집합 시험 | 실제 EX-42 전량 요청과 playlist 연결. 실패·누락을 완료로 세지 않고 숫자 상태와 분리. 검은 화면 진단은 성공 영상 아님 | 없음 · 막음: 연결·렌더 실패·전량 예행 | scripter · runner |
| G23 · 무한 재시도 | 같은 실패로 GPU 시간을 소진 | 기존 bounded retry·stdin DEVNULL·새 attempt 코드 | 근본 원인 미해결을 retry 완료로 바꾸지 않음. 전체 호출부 실증은 G01/G10/G22 | 있음 · 부분 코드: 재발 원인은 별도 | runner |
| G24 · 전달 | 결과가 폴더에만 남거나 중복 발송 | E06 Windows lead 도착 한 통의 보고 존재 | EX-42 event ID 영속 중복 방지·producer/wrapper 연결은 미구현 증거. native 알림·폰 수신은 승인 뒤 설치 날 | 없음 · 막음: 연결·설치 날 전달 | pipeline · super2 · runner |
| G25 · 완료 증거/I38 | done만 보고 거짓 완료·작업자 대기 | WORKLIST 자동 읽기는 존재 | §3.3 done+없는 파일 반례 여전. done도 근거 SHA·필수 산출 수·수신/검수까지 검증. 큐 writer는 공통 schema로 | 없음 · 막음: 재현 결함·완료 검증 | lead · pipeline |
| G26 · 정본 동기화 | 다음 세션이 옛 결정으로 실행 | WORKLIST에 W39 등록, 결정·보고 원장 있음 | W41 열린 문구와 08:5x 승인 기록, v5 승인 전 표현, 실행 YAML v0.16 차이를 결정별로 정리. 카드·계보·일정 동기화 | 없음 · 막음: 최신판 동기화 | lead · planner |
| G27 · 세션 전달 | 입력 덮기·잘못된 창·중복 의뢰 | orchestration status·현재 handle 확인 규칙 유지 | 이번 보고도 한 번만 mailbox로. 실제 Linux 도착은 G24 | 있음 · 규칙 | lead · pipeline |
| G28 · 시각/한도/맥락 | 잘못된 시각·예측값으로 결정 | date·limits_now·검증된 인계 규칙 유지 | 이번 보고는 사용 한도를 추정하지 않음. native 재개 장치 시험은 G24 | 있음 · 규칙/도구 | 각 세션 · pipeline |
| G29 · 원자료 검증 | 타 세션 결론을 사실로 중계 | 이번 고정 HEAD·56 CPU시험·반례3·RGB SHA/픽셀 직접 재확인 | 미측정 native 항목은 한계와 닫는 증거를 명시 | 있음 · 검증 규칙 | analyst · verifier |
| G30 · 표/링크 | 보고서를 읽거나 재현할 수 없음 | 기존 Markdown 검사·원자료·GitHub 링크 규칙 | 이 판의 표·반례 파일·원격 산출을 확인. 이후 EX-42 보고에도 반복 적용 | 있음 · 도구/규칙 | analyst · scripter |
| G31 · 디스크/이사 | 설치 디스크 오인·원자료 손실 | super2 0a76038 런북 L-17 식별·복구 절차 확인, E06 장비 기록 | 설치 대상 고유 ID 재대조·40,000 출력 예산·백업 SHA 복원 영수증·native 세션 재개. 런북 작성 완료와 실제 복구 완료는 다름 | 없음 · 막음: 설치·복구 실증 | super2 · pipeline |
| G32 · 지형 성과 확대 | 실제 노출/레벨이 설계와 다름 | 기존 terrain manifest/단일축 검증·v5 선행 구조 | 실제 sampler·mesh·sensor·종류별 env/레벨 분포·경계당 +1·유지 하락·deferred/재도전 소비. EX42 runtime 미구현 | 없음 · 막음: runtime·관측값 연결 | runner · analyst · planner |
| G33 · 수치 격리 | 불량 전이가 PPO를 오염 | E02 score batch의 혼합/all-invalid/reset-failure CPU시험 | **점수 행 검사와 PPO 전이 격리는 별개.** 새 관측/보상과 유효 mask·GAE/손실/KL 연결, 전역/부분 reset 경보를 실제 예행에서 검증 | 없음 · 막음: 학습 경로 연결·예행 | runner · scripter |

## 3. 직접 재현한 코드 빈틈 셋

### 3.1 전체 관문 중 아홉 행만 읽는다 · G01

[5e0c37a1 ex42_gate_checks.py:13](https://github.com/foothold-project/foothold-lab/blob/5e0c37a1/foothold_s2/ex42_gate_checks.py#L13)의 `REQUIRED_GATE_ROWS`는 G01/G03/G05/G08/G13/G15/G17/G18/G33이다. 33행을 가진 시험 표에서 **G11만 “예행 대기”**, 나머지를 완료로 놓았다.

- 기대: G11을 출발 막음으로 반환.
- 실제 기본 호출: `[]`.
- 같은 함수에 33개 ID를 명시: `['G11']`.

[고정 입력](evidence/fixture-g11-open.md), [재계산](recheck.py). 지금은 다른 준비용 차단이 있으므로 실제 본학습이 잘못 시작됐다는 뜻은 아니다. **향후 런타임 구현 후에도 이 소비 범위 그대로면 다른 담당 관문을 건너뛸 수 있다.** 전체 필수 ID를 정본 schema에 고정하고 누락·미등록 상태도 차단해야 한다. 자유 문장에 특정 토큰이 있는지만 보는 방식도 완료 영수증 검증을 대신하면 안 된다.

### 3.2 반복 폭을 재는 자료의 지형은 검사하지 않는다 · G11

[a8381f8a ex42_w78_gate.py:82](https://github.com/foothold-project/foothold-lab/blob/a8381f8a/foothold_s2/eval/ex42_w78_gate.py#L82)는 full/unit의 `ROW_IDENTITY`를 대조한다. 그러나 [101행](https://github.com/foothold-project/foothold-lab/blob/a8381f8a/foothold_s2/eval/ex42_w78_gate.py#L101) 이후 반복 자료는 상위 코드·저장본·seed·level 목록만 검사한다.

답을 아는 입력: full 거리 1.0, unit 1.1, 반복 1.04/1.20. 같은 지형일 때는 측정 폭 안이라 PASS다. **반복 둘의 terrain_assignment_sha256을 바꾸고 실제 terrain_tiles level을 2→9로 바꿔도 PASS**다. 기대는 HOLD다. 다른 지형의 변동을 허용 오차로 쓰면 full/unit의 오류를 숨길 수 있다. 이는 실측 보행 값이 아니라 코드 반례용 가상 값이다.

[입력 JSON](evidence/fixture-repeat-wrong-terrain.json), [실제 출력](evidence/recheck.json). 고침: 반복 자료도 해당 셀의 종류·배치 SHA·tile·phase_steps·분모를 동일하게 검증하고 결측/불일치는 HOLD. 고친 뒤 이 반례와 같은 코드의 실제 full/unit·반복 측정을 각각 확인한다. 기존 16 PASS를 반복할 뿐 아니라 이 반례가 거절되는 것을 봐야 한다.

### 3.3 완료로 표시하면 증거가 없어도 건너뛴다 · G25

[1d382122 ops_check.py:308](https://github.com/foothold-project/foothold-lab/blob/1d382122/_out/tools/ex41/ops_check.py#L308)의 worklist는 `status != open`을 바로 건너뛴다. 없는 증거 파일을 가리키는 `done` 한 행을 넣으면 **`OK · W next · 0 open`**이며 FAIL이 없다. W34 반례가 최신 I36 소스에서도 그대로 재현됐다.

[고정 입력](evidence/fixture-done-missing.tsv). 고침: done 행도 형식·정본 산출·SHA·요구 개수·검수 영수증을 확인해야 한다. 단순 파일 존재나 본문 marker는 산출 내용이 옳거나 받는 사람이 읽었다는 증거가 아니다. I36은 점수 대기 탐지를 추가했으며 이 완료 판정 결함을 고친 커밋이 아니다.

## 4. 새 운영 사고와 영상 원자료

I34~I38은 [EX41R-INCIDENTS 41~45행](<D:/mai-wt/foothold-lab/lead-worklist-1103/inbox/jay/20261104-ex41-restart/EX41R-INCIDENTS.md:41>)에서 읽었다. 새로운 G행으로 중복 등록하지 않았다.

| 사고 | 기존 G행 | 이번 판정 |
|---|---|---|
| I34 검은 RGB 반복 | G21·G22·G23 | 진단기는 원자료를 남기며 실패를 정상 영상으로 발표하지 않는다. 근본 원인과 완료 영상은 미해결 |
| I35 GPU0 대기 감시 누락 | G09·G10 | ops 시험에 GPU0 대기·실행0 FAIL 있음. 이는 채울 다음 일을 자동으로 만드는 장치와 다름 |
| I36 긴 W78 뒤 점수 정체 | G09·G10·G11 | 30분 사후 탐지 확인. 다음 점수 30분 안 긴 P2 기동 금지와 실제 조각 사이 양보는 미완료 |
| I37 학습 끝 GPU0 공백·영상 등록이 점수에 종속 | G09·G22·G25 | 저장본 생성→영상 독립 등록과 후속 작업 재고 필요. 현재 검증한 EX-42 연결 없음 |
| I38 손 복사 큐가 start/end 키 삭제 | G09·G12·G25 | 임시 수선 보고를 공통 writer 검증으로 부르지 않음. schema 검증·board 재독을 쓰는 모든 경로에 적용해야 함 |

**b07b4089는 수리 커밋이 아니라 계측 커밋이다.** [원자료](<D:/mai-tmp/runner/ex41_dark_diag_1107/capture/attempts/6929329c023ea3d97c6e7d59d5013be0a167b57ac7991f31198ec519fdd8fcb6/01/dark_render_diagnostics/render_samples.jsonl>)를 CPU로 다시 셌다.

| 원자료 항목 | 독립 재계산 |
|---|---|
| 렌더 샘플 / 어두운 PNG | 119 / 47. PNG 47개 SHA 일치 및 모든 RGB 픽셀 0 확인 |
| 프레임17 · physics tick34 | 17행 중 처음16행 밝기0, retry16에서 평균 밝기104.995. 전후 물리 상태 동일 |
| 프레임72 · physics tick144 | 31행 전부 밝기0, retry0~30. 전후 물리 상태 동일 |
| queue827 | 원 결과 JSON rc1·failed. 완료 영상 증거가 아님 |

이를 로봇 보행 붕괴나 정책 실패로 해석하지 않는다. 반대로 물리 상태가 같다는 사실만으로 renderer/readback 원인을 확정하지도 않는다. runner의 CPU 메시 가림 재구성은 추가 원인 분석 자료이며, 이번 W39에서는 그 기하를 다시 재구성하지 않았다. 촬영 품질 결측과 수치 평가의 유효성을 분리해야 한다.

## 5. 시험과 출처 고정

| 묶음 | 고정 HEAD | 이번 직접 재실행 | 한계 |
|---|---|---|---|
| runner 관문/ops 두 파일 | 5e0c37a1 | 18 PASS | 설치일 실환경 import 시험은 별도 파일이며 이번에는 미실행. 준비용 거절 성공은 런타임 성공이 아님 |
| W35 다섯 파일 | a8381f8a | 16 PASS | §3.2 추가 반례는 여전히 PASS이므로 G11 미해제 |
| I36 ops 전체 파일 | 1d382122 | 19 PASS | 실제 EX-42 연결·P2 사전 방지·자동 복구를 증명하지 않음 |
| 검은 RGB 계측 파일 | b07b4089 | 3 PASS | 모의 RGB 계측 시험. 새 GPU 촬영을 한 것이 아님 |
| 추가 CPU 감사 | 위 HEAD | 반례3 재현, 실제 PNG47개 SHA·픽셀 대조 | 반례 재현을 제품 PASS에 더하지 않음 |

실행기는 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`. CUDA_VISIBLE_DEVICES 비움, PYTHONDONTWRITEBYTECODE=1, TMP/TEMP·pytest basetemp는 D:, cacheprovider 끔. [시험 로그](evidence/runner-tests.txt), [W35](evidence/w35-tests.txt), [I36](evidence/i36-tests.txt), [영상](evidence/dark-tests.txt). 원래 소스와 운영 프로세스는 변경하지 않았다.

| 증거 ID | 코드·산출·줄 | 이번 사용 범위 |
|---|---|---|
| E01 | [runner EX42Runtime:156](https://github.com/foothold-project/foothold-lab/blob/5e0c37a1/foothold_s2/curriculum/ex42_runtime.py#L156) · [등록부](https://github.com/foothold-project/foothold-lab/blob/5e0c37a1/experiments/EX-42.yaml) · [ops:173](https://github.com/foothold-project/foothold-lab/blob/5e0c37a1/foothold_s2/scripts/ex42_ops.py#L173) | 준비전용, operations_enabled=false, score_config/baseline/video_source null, 실제 시작 미구현. transition helper 존재는 전체 runtime 구현과 다름 |
| E02 | [gate_checks](https://github.com/foothold-project/foothold-lab/blob/5e0c37a1/foothold_s2/ex42_gate_checks.py) · [상태 저장기](https://github.com/foothold-project/foothold-lab/blob/5e0c37a1/foothold_s2/ex42_status.py) · [runner 보고](<D:/mai-tmp/runner/REPORT-gate-runner-1107.md>) | 실제 호출 검색은 [recheck.json](evidence/recheck.json)의 runner_call_search. W35 모듈·status 호출0, 다섯 검증 함수는 정의만 발견 |
| E03 | [I36 ops_check:76](https://github.com/foothold-project/foothold-lab/blob/1d382122/_out/tools/ex41/ops_check.py#L76) · [시험](https://github.com/foothold-project/foothold-lab/blob/1d382122/_out/tools/ex41/test_ops_check.py) | I36 탐지19시험·G25 반례. 실운영 전체 상태를 이 감사가 정상 판정한 것은 아님 |
| E04 | [W35 보고](<D:/mai-tmp/scripter/REPORT-gate-scripter-1107.md>) · [고정 코드](https://github.com/foothold-project/foothold-lab/tree/a8381f8a/foothold_s2/eval) | 5모듈·16시험·G11 반례·연결 누락. 다른 코드로 측정한 과거 full/unit 차이를 수치 동등성 근거로 쓰지 않음 |
| E05 | [영상 진단 보고](<D:/mai-tmp/runner/REPORT-dark-render-diagnostic-1107.md>) · [queue827 원결과](<D:/mai-tmp/gpu/results/item_827.json>) | 원자료119행·PNG47 SHA/픽셀 독립 계산, rc1 직접 확인 |
| E06 | [pipeline G04/G08/G24](<C:/mai/wt/mai-os/pipeline/os/reports/20261106-ex42-g04-g08-g24.md>) · [WSL R4](<C:/mai/wt/mai-os/pipeline/os/reports/20261106-w32-r4.md>) | 문서·미완료 계약 확인. 과거 WSL 6PASS2FAIL은 후속 시험 분리 전에 나온 결과로, 이번 Windows18PASS와 섞지 않음 |
| E07 | [W34 보존본](archive/W34-v1.md) · [원래 출처 색인](evidence/w34-source-inventory.json) · [당시 범위](evidence/w34-coverage.json) | 기존 R/M/I01~I33/PM 대응 유지. 최신 결정·I34~I38은 이번 판으로 보완 |

원자료 재계산 명령:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:CUDA_VISIBLE_DEVICES=''
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' inbox/jay/20261107-ex42-w39/recheck.py --out D:/mai-tmp/analyst/w39-evidence
```

G31 런북은 mai-os 고정 `0a76038`의 [L-17 원문 발췌](evidence/G31-L17-source.txt)를 직접 읽었다. 확인 명령과 기대 답을 적은 문서이며 실제 설치·복원 수행 영수증은 아니다.

## 6. 다음 순서와 닫는 조건

1. **설치 전에 고칠 것:** G01 전체 관문 소비, G11 반복 자료 동일성, G25 완료 증거 판정. 같은 고정 후속본에 각각의 반례를 넣고 해당 범위만 재검증한다.
2. **설치 전에 연결할 것:** v5 승인 목록을 실행 설정으로 동기화하고 EX42Runtime·score producer·W35 다섯 모듈·status·알림·단계/블록 보고를 실제 사슬에 연결한다. 새 함수를 만든 뒤 호출0인 상태를 완료로 보고하지 않는다. 최신 EX-41 T0′ 부모 선택도 실제 저장본 SHA로 고정한다. 준비 등록부의 EX-40 m6000 SHA를 그대로 실제 부모라고 취급하지 않는다.
3. **같은 최종 HEAD로 예행할 것:** 기본/최종 단계, 중간/블록 재개, 미달·유지 하락·측정 실패, 숫자 PASS+영상 FAIL, P1 대기·조각 양보, 세 지도 전체 누락 검출을 실제 산출 경로까지 본다. 그림자 평가 실패와 학습 중단 여부는 승인 계약을 그대로 따른다.
4. **설치 날 확인할 것:** native Linux 장치·runtime·경로·백업 복구·저장/읽기·알림·실제 속도·메모리. 한 대의 Windows와 Linux를 동시에 쓴다는 일정은 만들지 않는다.
5. **출발 판단:** 26개 열린 G행의 최종 소비자+시험+영수증을 행별로 대조한다. 이 보고는 11/07 고정 스냅샷이며 11/08 18:00의 최종 HEAD가 달라지면 변경된 행만 보완한다. W39 보고 작성 완료와 EX-42 출발 승인 완료를 구분한다.

W18은 m3750 보충을 완료했고, m12000 W78은 최종 산출 도착 뒤 해당 칸만 갱신한다. 이 감사가 대기 중인 평가를 재실행하거나 GPU 큐에 끼어들지는 않았다.

## 판 이력

| 판 | 변경 |
|---|---|
| v1.0 · W34 | 과거 실패 전수 대응 33행, 막음26행. 당시 고정 코드와 반례 보존 |
| v2.0 · W39 | 최신 I36/W35/영상 진단과 runner 후속 코드 재감사. D183 정정, I34~I38 대응, 직접 시험56PASS·반례3·RGB47개 검증. 구현/연결/예행 구분 |

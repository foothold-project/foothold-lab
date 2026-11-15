고칠 것: 17r의 주요 반례는 닫혔지만 진단의 원본 결과 검증과 실행 시간·승인별 예산 강제가 불완전하므로, 현재 후보의 GPU 진단 기동은 보류하고 승인 JSON은 발급하지 않는다.

> 분류: A/평가 · 독립 검증
> 작성: 오흥재 (ASTRA 검증) · 2026-10-14
> 근거: TASK-astra-17s 전문 · SHA256SUMS 25개 · 등록 입력 38개 · 독립 CPU 재실행 · 실제 q 원본 결과 사본
> 요지: 제공 시험 6개는 재현됐지만 가짜 결과 검증이 첫 진단의 실패를 가렸다
> 상태: 수정 필요 · GPU·Isaac·운영 코드 변경·커밋 없음

# ASTRA 17s

이하 C는 night-tools-20261013/cmdr1043_eval_cand_17r/, M·D·F·P는 각각 그 안의 s1043_manifest.py·cmdr_eval_driver_s1043.py·frozen_exec_s1043.py·cmdr_post_s1043.py다. 고정 파일 25개와 등록 입력 38개는 모두 해시가 맞았다. C의 Python 바이트를 그대로 개인 Temp에 복사하고 manifest의 배치·출력 경로와 그 계약 해시만 옮겼다. 원자료는 읽거나 사본으로 시험했다.

## 1. 수정 경로와 새 결함

**판정: 기존 여섯 P1의 지정 반례는 해소됐으나, 진단 기동을 허용할 상태는 아니다.**

| 항목 | 근거 · 확인됨 |
|---|---|
| GPU·타입·승인 | 정수 GPU 0/1은 통과, bool·float·문자열은 거절됐다. scalar 해시·문자열 확인값·코드 digest 변조·승인 뒤 마감 변경도 거절됐다. 외부 승인 파일 digest와 reviewed 대조가 추가됐다. |
| 시작 시험·argv | 등록 원본 q 경로를 해시한다. 9개 시작 시험 suffix의 정상 전체 argv가 통과하고 중복 옵션은 거절된다. 시작 시험 조건을 삭제한 해결이 아니다. |
| lock·자식 | 대소문자 별칭의 동일 lock은 거절된다. 실제 CPU wrapper가 먼저 끝나도 관찰된 손자의 자연 종료까지 기다렸다. 서로 다른 실행 lease와 변환 lock의 OS 잠금도 재현됐다. 모든 자식·모든 운영 실행기의 통합 보장은 별도다. |
| 장치·자료 | 물리 GPU 1·논리 CUDA 0인 post CLI가 45 valid를 냈다. MAE 한 건 NaN이면 CLI가 실패하고 완성 보고서를 내지 않았다. 다른 manifest의 OUT과 전체 USD 경로를 구분하며 reset XY ±9 m는 거절한다. |
| 배치·단계 | cand/ 없는 평평한 사본의 driver/F CLI가 통과한다. 진단의 A 태그 거절·진단 뒤 A 미호출을 재현했다. |

새로 확인된 사항:

- **P1 · D:995, 1478 부근. 원본 q의 정상 결과를 거절한다.** main_diagnostic()은 원본·반복 원본에도 validate(..., need_iter=True)를 적용한다. 고정된 q_eval.py에는 loaded_iter 기록이 없다. 실제 out/cq_test_8d384fcb_g0t141025p134176_ka_orig/meta.json도 없다. 그 결과 사본에서 경로·guard·slot 경계만 시험용으로 바꾸고 검증하면 loaded_iter None, need_iter=False면 오류 없음이었다. 메타데이터에 20000을 추가한 양성 대조도 통과했고, checkpoint 해시 변조는 계속 거절됐다. **원본 q에 한정해 필드 유무를 처리하고 checkpoint 해시·원본 소스·나머지 검사를 유지해야 한다.** 모든 평가기의 iteration 검사를 끄면 안 된다. 원본 반복에도 같은 수정이 필요하다.
- **P1 · D:620,664,845. max_wall_s는 실행 중 상한이 아니다.** 실제 gate와 실제 CPU 자식을 연결하되 GPU probe·slot만 대체한 시험에서 한도 2초, 4초 수면 자식이 전체 5.813초 뒤 guarded rc=0으로 반환됐다. wait_child_tree()에는 마감·STOP·벽시계 검사나 중단 집행이 없다. 등록된 slot도 acquire 때 마감/STOP을 보지만 실행 중 run/watch는 이를 지속 집행하지 않는다. 따라서 “상한 안에 종료”는 틀리다. 시작 금지 시각과 강제 종료 시각을 구분해 승인받고, 강제 상한을 택하면 소유한 자식 트리에 실제 적용하고 종료 확인 전 lease를 풀지 않아야 한다. 이번 감사는 프로세스를 종료하지 않았다.
- **승인 한 묶음의 예산 결박 미완성 · M:72, D:190,225.** 같은 승인 파일·외부 digest로 execution.attempt만 바꿔도 오류 0이다. D는 이 값을 쓰지 않고 새 ATTEMPT를 만들며 launch 수를 프로세스마다 0으로 시작한다. 현재 max_child_launches는 **한 프로세스의 상한**이지 같은 승인으로 여러 번 시작한 누적 상한이 아니다. “진단 한 묶음” 승인을 내려면 승인 ID·실제 attempt·로그를 묶고 재시작 시 소비된 횟수를 이어받거나 재사용을 거절해야 한다. 단순 문서상의 단회 약속과 코드 강제를 혼동하지 않는다.
- **P2 · M:239. 재시도 0회를 표현할 수 없다.** 모든 risk 값에 >0을 요구한다. 새로 결박한 정상 승인에서도 max_retries_per_run=0은 거절됐다. launch·wall은 양수, retry는 0 이상으로 구분해야 한다. 현재 정상 진단은 기본 tries=4를 사용하므로 “재시도 없음”을 코드 계약으로 표현하지 못한다.

**남길 미확인:** 실제 GPU 연쇄, 공통 lease의 운영 적용, 관찰 전에 사라진 부모·자식 및 접근 불가/PID 재사용 경계. 관찰된 고아 자식 시험 통과를 모든 트리의 완전한 소유권 증명으로 확대하지 않는다.

## 2. 시험의 신뢰 범위

**판정: CPU 연결 증거는 개선됐지만 실제 진단 결과 검증은 시험하지 않았다.**

ASTRA의 격리 재실행은 b·c·d·e·post·mutants 모두 종료 0이었다. 각각 3.94·1.27·0.45·26.06·3.47·0.30초였다. 작업자·lead의 저장된 로그에서도 여섯 종료 0과 12개 want 일치를 확인했다. 시간은 이번 실행과 과거 로그를 구분한다.

- e는 실제 D의 start→tests→guarded를 지나 실제 CPU 자식인 가짜 slot과 실제 F CLI로 간다. 그러나 ready, GPU/프로세스 탐지, **validate와 fingerprint를 성공 함수로 교체**한다. 가짜 slot은 F에 --cpu_fixture를 삽입한다. F는 실제 GPU probe·전체 launch 승인 재검을 생략하고 fixture 입력을 확인한 뒤 READY_CPU_NO_CHILD로 끝난다. guard·isolate·q·Isaac은 실행하지 않는다. 잘못된 YAML 거절도 가짜 slot이 문구를 만들어 낸다.
- e의 정상 연결은 8 try다. 등록 suffix 9개 중 비결정성 때만 쓰는 ka_orig2는 일반 연결에서 빠진다. 뒤의 고아 자식 시험에서는 그 태그를 별도 사용한다. c는 9개 argv 모두를 함수로 검사한다.
- 참 on-only는 off 결과 경로를 없는 파일로 바꿔 training_done()이 off 결손을 거절한 시험이다. 실제 on-only GPU 학습이 아니다. 같은 경로의 로그 잠금·변환 잠금·실행 lease를 다른 OS 핸들로 열어 실패하는 시험은 실제다. registry는 가짜 slot의 간단한 JSON이며 운영 slot registry 검증을 대체하지 않는다.
- slot 대기 뒤 변경은 가짜 slot이 실제 변환 lock을 보유한 채 release marker를 기다리고, sentinel 변경 후 F가 92를 내는 실제 CPU 경계 시험이다. 다만 운영 checkpoint 변경이나 승인 변경을 실제 slot 대기 중 주입한 시험은 아니다.
- **12개는 이름이 다른 입력 변조 12종이다. 코드 검사를 하나씩 끈 mutant 12종이 아니다.** launch/argv 정상 대조와 의도한 오류 문구는 확인했다. 여러 검사가 함께 실패한 사례도 있어 “각 검사만 제거하면 같은 반례가 살아남는다”는 증거는 없다. 17r의 코드 변이 6종과 합쳐 18종의 동일 수준 검증이라고 세지 않는다.

**남길 미확인:** 실제 slot·guard·isolate·Kit의 연결, 메모리 peak, 물리 버퍼 동등성. 정상 원본 결과를 새 validator에 넣는 시험, 소유 트리의 시간/STOP 집행, 승인 재사용과 재시도 0의 정상·반례가 필요하다. 제공된 시험 6개를 또 통과시키는 것만으로는 1절 결함이 닫히지 않는다.

## 3. 진단 계약

**판정: 세 별도 실행과 단계 분리는 맞지만 정상 원본 검증과 비교·보고 규칙을 보완해야 한다.**

계약은 부모 p20000, flat/stop03, seed 1000, 100 episodes, student, noise on이다. q 원본 작은 버퍼 → q_cmdr 작은 버퍼 → q_cmdr 기본 버퍼를 각각 guarded로 실행한다. 같은 Isaac 프로세스를 재사용하는 설계가 아니다. 진단은 stage=diagnostic이고 완료·불일치 모두 A를 호출하지 않았다. 반복 원본은 사전 bool이 true일 때만 호출된다. 다만 현재는 1절의 원본 필드 오류로 첫 run에서 held_incomplete가 예상된다.

D:1512는 JSON 의미·JSON 파일 SHA·traj 파일 SHA를 **모두** 요구한다. 의미와 trajectory 바이트가 같고 JSON 공백·키 순서만 다른 CPU 대조도 held_mismatch/3이었다. 보수적 보류 자체는 가능하지만 이것을 물리 비결정성으로 설명하면 틀리다. byte-only 차이는 별도 원인으로 표시하고, 의미·배열 동등성과 파일 바이트 동일성 중 무엇을 통과선으로 삼을지 사전에 정한다. 원본 한 번의 재실행으로 비결정성의 분포나 복사 오류의 원인을 확정할 수도 없다.

기본 세 run 보고에는 시간·guard peak/여유·지문·버퍼·입력이 들어간다. 추가 orig_repeat에는 같은 수준의 peak·preflight·reset·지문·tries 항목이 빠져 있다. report의 peak는 장치 전체 값이며 이 작업의 전용 사용량이 아니다. 진단 비교에서 지문을 기록하는 것과 모든 초기 상태·DR·terrain 지문을 실제 대조하는 것도 구분해야 한다.

과학 기준은 계약의 evaluation.ci_boundary에 세 하한 >0 및 세 칸 동일 가중 평균 ≥10 %p로, selection_boundary에 ≤−5 %p로 들어 있고 계약 해시와 승인에 묶인다. 진단 비용으로 A의 시간 예산을 갱신하는 것은 가능하나 성능을 보고 이 기준을 바꾸면 다른 실험이다. stage를 바꿔 A로 진행하려면 기존 진단 승인과 reviewed가 달라져 재승인이 필요하다.

**남길 미확인:** 현재 장치의 세 run 동등성·원본 반복·공통 지문·peak·A 처리량. 원본 반복 및 실패 run까지 같은 보고 항목으로 남기고 미실행·보류를 분리해야 한다.

## 4. 미정 값과 승인 발급

**판정: 지금은 발급 조건이 충족되지 않았다. 다른 세션이 전한 팀장 승인도 결정 근거로 대체하지 않는다.**

| 담당 | 채울 내용 |
|---|---|
| lead 측정 | 실제 물리 UUID/index·여유, Python/NumPy/torch/Isaac 판과 경로, 고정 코드·38개 입력 해시, 양 군 종료·SAME 보고, canonical lock/lease/registry와 참가 실행기의 사용 증거. 번호 측정과 사용할 GPU 선택은 별개다. |
| 팀장 결정 | GPU 배정·독점 시간창과 참여 범위, 시작/종료 마감의 의미, 최대 launch·retry·벽시계와 중단 방식, 원본 반복 예산, 한 승인으로 허용할 재기동 범위. |
| ASTRA 판단 | 수정된 정확한 바이트·실행 결정·측정·시험에 대한 제한된 진단 기술 승인. 지금은 보류다. |

현 M이 실제 검사하는 승인 파일의 정확한 구조는 다음과 같다. **양식 설명이며 승인 파일이 아니다.**

{approved: true, by: 검증자, approved_at: 승인시각, reviewed: B}

B의 키는 정확히 experiment, train_seed(1043), contract_sha256, stage, candidate_hashes, comparison_report_sha256, gpu_index, gpu_uuid, CUDA_VISIBLE_DEVICES, diagnostic_repeat_original, deadline_epoch, risk_limit, convert_lock, run_lease, registry, python이다. risk는 max_child_launches, max_retries_per_run, max_wall_s. candidate_hashes는 M·비교기·D·P·F **5개 Python 파일**의 SHA256이다. 경로·runtime·원자료 38개·과학 기준은 canonical contract SHA256을 통해 묶인다. 비교 보고서는 파일 바이트 SHA256이다. 승인 JSON 파일 바이트 SHA256을 execution.approval_sha256과 호출자의 --approved_digest 양쪽에 넣고 대조한다. manifest 전체 바이트 해시가 승인 B에 직접 들어가는 구조는 아니다.

순서는 결함 수정 및 해당 정상·반례 재검 → 배치·입력·런타임·공통 잠금 측정 → 팀장의 실행 결정 → contract 동결 → 실제 등록 번들 사본 비교와 SAME 파일 동결 → 5개 코드 digest·실행 B 검토 → 진단 승인 파일 작성·digest 외부 전달 → 기동 직전 불변성/자원 재확인이다. 1절의 승인 재사용 결함을 고치면 B에 승인 ID·실제 attempt·로그 및 누적 예산 범위를 추가하고 **새 스키마 그대로** 재검해야 한다. 현 양식을 충분한 단회 승인 계약이라고 채워 발급하지 않는다. run_lease_participants_confirmed=true라는 자기 선언만으로 공유 증거가 생기지도 않는다.

**남길 미확인:** 팀장의 최종 배정·마감·위험 결정, 실제 측정값, 수정된 승인 스키마. 현재 JSON은 이 값들을 UNDECIDED로 유지하고 있다.

## 5. 반영 및 첫 GPU 진단 순서

**판정: 수정 뒤 별도 새 묶음으로 반영한다. 이번 감사에서는 배치하거나 기동하지 않았다.**

배치안은 candidate_dir=C:/isaac/ext/go2_rl_robotlab/_eval/cmdr1043_eval_17s_fixed/에 M·비교기·D·P·F와 확정 manifest를 한 층에 두는 것이다. source_eval=C:/isaac/ext/go2_rl_robotlab/_eval, write_root=C:/isaac/ext/go2_rl_robotlab/_audit_cmdr1043/로 분리한다. 뒤 경로의 한 실행 디렉터리에 data/reports/work/attempts/logs/STOP을 두고, 승인된 공통 lock/lease/registry도 write_root 안에서 명시한다. **현 M은 모든 WRITE_KEYS가 source_eval 밖이어야 하므로 _eval/slot 같은 기존 공통 경로를 그대로 넣으면 거절된다.** 이 배치안 자체도 아직 결정이 아니다. 공통 경로를 바꾸면 실제 참가 도구에 적용하거나 기존 경로를 명시적 allowlist로 허용하는 수정이 필요하다. 격리 검사 전체를 제거하면 안 된다.

1. 구판 v37·post v10·원자료를 보존한다. 후보 코드와 manifest를 동결하고, 출력 경로·자기 경로·원본 38개·양 군 종료를 CPU 재검한다. 비교기는 번들 두 개를 write_root 아래로 **바이트 그대로 복사**한 뒤 실행해야 한다. ASTRA는 이 절차로 SAME/0 → seed1042 변조 DIFFERENT/1 → 원상복구 SAME/0을 확인했다.
2. 코드 5개·비교 보고·실행 계약·독립 승인 digest를 대조한다. 단회 사용·재기동 예산, 별도 lease/변환 lock, 미참가 실행 차단을 실제 배치 경로에서 확인한다.
3. 기동 직전 물리 UUID/index·논리 CUDA 0·최저 여유 4096 MiB·동시 실행·입력·STOP·마감을 다시 확인한다. “현재 GPU가 비었다”는 의뢰문 주장은 이번 감사에서 측정하지 않았다.
4. 종료/시간/guard/USD/입력·장치 변조/traceback/불완전 결과/동등성 불일치면 보류한다. 실패 자동 재시도·원본 반복은 승인된 조건과 누적 예산 안에서만 허용한다. 자식 잔류 시 lease 해제나 다음 run 시작으로 넘어가면 안 된다.
5. 세 진단 결과를 검토한 뒤 A를 따로 결정한다. A 기동 시 기본 시작 시험 8회, 조건부 원본 반복 1회와 A 45회까지 launch 예산에 포함한다. 현재 A는 시작 시험을 재사용하지 않고 다시 돌린다. A 45만 세면 예산이 부족하다.

보고 문구는 “등록 후보로 부모 진단 3회 중 실행 n·유효 n·보류 n, A 0회, 실제 장치 전체 peak/최저 여유 및 시간, 의미/바이트/지문 비교 결과”처럼 쓴다. A가 끝나도 학습 seed 1043의 목표 세 칸 결과이며 나머지 96칸·22,000·정책 채택의 결론은 아니다.

**남길 미확인:** 새 배치의 실제 기동, 참가 도구의 공통 잠금 사용, 시작 시험 및 A 예산. CPU 비교기 첫 호출은 ASTRA가 원본 경로를 직접 넘겨 격리 검사에서 거절됐고, 사본 경로로 바로잡아 위 결과를 얻었다. 이 호출 오류를 제품 결함으로 세지 않았다.

## 6. 견적과 근거

**판정: 작업자 고침 시간을 기존 견적에서 기계적으로 빼면 안 된다. 현재 임계 경로는 새로 확인된 결함과 결정·측정이다.**

**추정이며 보장 아님:** 원본 validator·0 retry·시간/단회 예산 수정과 CPU 대조 1~3시간, 바뀐 경로 독립 재검 0.5~1시간, 운영 경로·런타임 측정과 배치 동결 0.25~0.5시간. GPU 진단 시작까지 약 **1.75~4.5시간 + 팀장 결정 대기**를 계획 참고값으로 둔다. 전역 실행기 통합이나 자식 소유권 재설계가 필요하면 이 범위를 넘는다. 여섯 시험 실행 자체는 이번에 합계 35.49초였지만 코드 검토·반례 구성 시간을 나타내지 않는다.

진단은 Isaac 세 번이다. 17q가 기록한 과거 110 try 평균 75.3초를 기계적으로 대입하면 3분 45.9초지만, 현재 후보의 기본 버퍼 비용과 별도 준비·공통 잠금 대기를 검증한 값은 아니다. D start의 60초 안정성 관찰 두 번과 checkpoint 안정성 대기도 있다. **승인 후 진단 한 묶음은 10~20분의 임시 작업창**으로 계획하되 실패·원본 반복·재시도는 별도 예산으로 둔다. A 45회의 56분 28.5초도 같은 과거 평균의 단순 추정일 뿐이며 시작 시험 최소 8회와 대기를 더해야 한다. GPU 진단 후 예상을 다시 산출한다.

**남길 미확인:** 실제 수정·검토 소요, 팀장 결정 시각, 현재 GPU 성능·peak·배치 소요. 12:12~12:54는 작업자 작업 시간 보고이지 준비 완료의 실측이 아니다.

재현 자료는 C:/Users/AI-WS01/AppData/Local/Temp/astra17s_cpu_730c1a0003/의 sources-before.json, evidence_17r/run_20261014_215838_143348/, audit_independent.py, independent-results.json, comparator-results.json, final-source-check.json이다. 실제 원본 meta SHA256은 4c4bed8364cf6cc1c873585dc895ec1fee99ab1bc699cf71bed9c19a834bb093. 원본·시험 후보를 고치지 않고 Temp의 시험 fixture만 썼다. 모든 새 CPU 자식은 자연 종료했으며 운영 프로세스·GPU·Isaac·slot·동결 폴더는 건드리지 않았다. 저장소 산출물은 이 파일 하나다.


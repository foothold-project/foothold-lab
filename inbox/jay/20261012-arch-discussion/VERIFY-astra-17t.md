고칠 것: 진단 기동은 보류하며, PID 재사용 시 무관한 자식을 종료하는 경로·미결정 통과선의 승인 관문 통과·필수 지문 누락을 valid로 남기는 경로를 고친 뒤 해당 정상·반례를 재검해야 한다.
> 분류: A/평가 · ASTRA 17t 독립 검증
> 작성: 오흥재 (ASTRA 검증 세션) · 2026-10-15
> 근거: TASK-astra-17t 전문 · cmdr1043_eval_cand_17s 고정 31개 파일 · 등록 입력 38개 · 독립 CPU 재실행과 반례
> 요지: 기존 네 결함의 기본 재현은 닫혔지만 새 경계 결함 세 건이 남아 진단 승인 조건을 충족하지 못했다
> 상태: 검증 완료 · GPU 진단 보류 · 승인 JSON 발급 없음

# ASTRA 17t

이하 M은 s1043_manifest.py, D는 cmdr_eval_driver_s1043.py이며 줄 번호는 의뢰의 cmdr1043_eval_cand_17s 사본 기준이다. 저장소 산출물은 이 파일 하나다. 코드·원자료·운영 slot·GPU·Isaac·기존 프로세스를 변경하거나 기동하지 않았다. CPU 시험은 별도 Temp 사본에서 수행했다.

## 1. 기존 네 결함과 새 결함

**판정: 원본 필드·0 retry·단회 예약은 지정된 범위에서 고쳐졌다. 실행 중 시간상한의 기본 반례도 닫혔다. 그러나 종료 대상의 소유권 판단이 안전하지 않아 기동은 막는다.**

**근거 · 확인됨:**

- 원본 q의 loaded_iter 누락은 D:1072에서 need_iter=False일 때만 허용한다. 진단 원본·원본 반복 호출만 이 값을 준다(D:1611,1630). 실제 원본 meta의 SHA256은 4c4bed8364cf6cc1c873585dc895ec1fee99ab1bc699cf71bed9c19a834bb093. 같은 입력으로 누락·명시 20000은 통과하고, 명시 19999·checkpoint SHA 변조·cmdr의 누락은 거절됐다. 원본 코드 고정·checkpoint·cmdr 검사를 통째로 끈 해결은 아니다.
- guarded의 2초 한도와 4초 CPU 자식 시험은 rc 124·wall_limit·held로 끝났다. 정상 자식·관찰된 손자·STOP도 제공 시험에서 통과했다. deadline_epoch는 새 실행을 막는 시각이고, max_wall_s는 ATTEMPT_START부터의 누적 실행 예산이다. 매 run마다 새 2초를 주는 구조가 아니다.
- 승인 장부의 디렉터리 원자 생성은 별도 CPU 프로세스 둘을 동시에 출발시켜도 claimed 1건·already used 1건이었다. 승자 종료 후 세 번째 프로세스도 거절됐다. 제공 시험의 attempt만 변경·두 번째 시작·동시 스레드 예약도 통과했다. 새 여섯 필드를 승인 이후 바꾸면 각각 approval contract mismatch가 발생했다.
- claim 하나를 start()에서 소비하고, 같은 프로세스의 세 q 실행·승인된 재시도·조건부 반복이 누적 launch/wall을 함께 쓰는 설계는 맞다. 실패해도 이미 쓴 승인이다. 새 프로세스 재개는 새 승인 ID와 잔여 작업·새 예산을 검토해야 하며 장부 삭제로 되살리면 안 된다.
- retry=0은 관문을 통과하고 guarded의 실제 launch가 1회였다. −1·문자열·bool은 거절됐다.

**기동 차단 결함 1 · D:711~720,753~766, PID 재사용.** 감시기는 새 자식의 ppid가 과거 known에 있다는 이유로 등록한다. 그 부모 PID가 지금도 같은 생성 시각의 프로세스인지는 확인하지 않는다. 독립 시험에서 우리 루트 100은 유지하고, 관찰했던 중간 자식 110이 종료된 뒤 다른 프로세스가 PID 110을 재사용하며 새 자식 300을 낳게 했다. 감시기는 110의 생성 시각 불일치는 알아차려 110을 종료하지 않았지만, **무관한 300은 새로 known에 넣고 kill을 호출했다.** 300 자신의 생성 시각이 맞아도 우리 자식이라는 증거는 아니다.

이는 실제 타 프로세스를 죽인 실험이 아니라, 후보 함수 본문 그대로에 psutil 프로세스 표·시계만 대체한 결정적 반례다. 같은 시험의 정상 부모 대조군은 정상 트리를 정리했다. 부모 PID+생성 시각을 확인하지 못하면 새 자식을 소유했다고 판단해서는 안 된다. 관찰 간격 사이의 부모 종료까지 보장하려면 프로세스 핸들·OS 소유 집합 등으로 생명주기를 묶는 방안도 검토해야 한다. 종료 직전 자식 시각 비교만으로 해결됐다고 쓰면 틀리다.

**기동 차단 결함 2 · M:232~340, D:1590~1591.** comparison_pass_rule은 B에 들어가지만 값 검사가 없다. 독립적으로 다른 필드를 정상화하고 CPU용 승인 digest를 다시 계산했을 때, 엄격 규칙·UNDECIDED·ignore_all_differences·false·null 모두 launch_errors(require_files=True)==[]였다. D는 승인값과 무관하게 엄격한 세 비교를 적용한다. 승인 해시를 우회한 것이 아니라, **미결정 또는 실행과 다른 규칙을 유효한 결정으로 받아들이는 결함**이다. 현 미결정 manifest 전체가 기동 가능하다는 뜻은 아니다. 다른 미정 값들은 현재 기동을 막는다. approval_id·log_name의 UNDECIDED도 각각 통과하므로 예약어를 명시적으로 거절해야 한다. 허용 규칙과 적용 규칙을 동일하게 검사하고, 미정·미지원 값은 승인 전 거절해야 한다.

새 필수 지문 누락 결함은 3절에 적었다. 장부의 경로 제한과 allowlist는 정상 경로 및 제공 경계 시험에서 유지됐다. 다만 source_eval 내부의 아무 파일이나 승인할 이유는 없다. allowlist는 운영 공통 파일의 정확한 경로만 허용하는 결정이어야 한다.

**남길 미확인:** 실제 Kit 자식 생성·종료의 전 구간, PID 재사용 빈도, 접근 거부·재분기·관찰 전 사라진 부모의 자식 전체. 접근 거부 반례에서는 알 수 없는 자식에 신호를 보내지 않고 계속 대기했다. 따라서 “상한까지 종료가 보장됨”도 “모든 자식이 없어야만 lease 해제됨”도 전역 보증으로 쓰지 않는다. 정상 관찰 경로에서의 CPU 확인과 구분한다. 알 수 없는 자식이 남으면 예산 만료 뒤에도 보류와 운영자 인계가 필요하다.

## 2. 시험의 신뢰 범위

**판정: 재실행 성적은 재현됐지만, ‘코드 검사를 끈 변이 6종’은 부정확한 분류이며 10개 통과는 GPU 기동 안전성의 증명이 아니다.**

**근거 · 확인됨:** 고정 31개 파일·등록 입력 38개는 모두 해시가 일치했다. 작업자 전체 목록 SHA256 ac97c2a1a2068dfbfb8e8fa1fbb883cde207b59fb575ab7ce71ab54a57849db9 및 실제 목록 159/159도 대조했다. ASTRA 사본에서 10개 시험을 한 번 순서대로 실행해 전부 exit 0, 하위 시험 실행시간 합계 79.70초였다. skip·hold는 이 10개 실행에 없었다. 내부 변이 시험의 시간은 이미 합계에 들어 있으므로 별도 합산하지 않는다. 작업자의 과거 실패를 이 성공 실행의 분모에 섞지 않는다.

입력 변조는 로그의 want/got를 직접 읽어 12건 확인했다. 코드 변이는 생성된 소스·해시·원본과의 차이·정상/변이 로그를 모두 대조했다. 모두 한 곳을 바꿨고 정상 exit 0, 변이 exit 1, 최초 FAIL과 AssertionError가 지정 want와 일치했다. 분류는 다음과 같다.

| 변이 | 실제 바뀐 의미 |
|---|---|
| original_field | 원본의 누락 허용을 없애 정상 원본까지 거절하는 회귀 |
| wall_enforcement | 활성 자식 시간상한 비활성화 |
| approval_ledger | 기존 claim 디렉터리를 허용해 단회 예약 무력화 |
| retry_zero | 0 retry를 다시 거절하는 회귀 |
| byte_only_reason | byte-only 사유를 semantic_mismatch로 오표기 |
| common_allowlist | 정확한 key/path 허용 조건 제거 |

즉 **입력 변조 12건과 코드 변이 6건**이다. 뒤 6건 모두를 안전검사 비활성화라고 부르면 안 된다.

test_17s_original은 실제 validate 본문과 원본 결과 파일을 읽는다. 그러나 “slot 경계만 대체”했다는 설명은 틀렸다. 50~52줄에서 log_done·usd_check·py_traceback도 성공 함수로 바꿨다. 원본 필드 수정의 시험으로는 유효하지만 실제 로그·USD·traceback까지 통과했다는 근거는 아니다. test_17r_e:98~99의 validate·fingerprint 성공 대체도 그대로다. runtime의 guarded 시험 역시 gate·preflight 등을 대체하며 실제 slot 연결 시험이 아니다. 접근 거부·PID 재사용은 제공 10개 밖에서 ASTRA가 별도로 시험했다.

**남길 미확인:** 실제 GPU slot v3·guard·isolate·Kit 연결, 물리 버퍼·장치 peak, 모든 참가 실행기의 공통 lease 사용. CPU 환경은 isaac311-moects Python, -B, CUDA_VISIBLE_DEVICES=-1이다. GPU 판정을 얻는 시험은 예정하지도 실행하지도 않았다. 이전 백업 154개 전체의 생성 당시 동일성은 이번에 재측정하지 않았다.

## 3. 진단 계약과 보고

**판정: 세 실행 분리·A 자동 진행 금지는 유지된다. 보고 형식은 개선됐지만 필수 증거 누락을 valid로 남기므로 완료 판단은 아직 신뢰할 수 없다.**

**근거 · 확인됨:** orig/small/default는 별도 q 실행이며 진단 경로는 A를 호출하지 않는다. 원본 반복은 세 run이 유효하고 비교가 어긋났을 때만 승인된 bool에 따라 추가된다. 반복을 한다고 처음 불일치를 completed로 뒤집지도 않는다. 의미·JSON 바이트·traj 바이트와 사유 코드가 분리됐고, JSON 재서식만 다른 시험은 byte_only_json으로 보류됐다. 이 사유는 물리 비결정성 증거가 아니다. trajectory_bytes_mismatch 또한 내용 차이와 파일 직렬화 차이를 분리한 검증은 아니므로 물리 원인을 확정하지 않는다.

**기동 차단 결함 3 · D:1522~1557.** diagnostic_record는 지문 계산의 OSError·ValueError·KeyError 등을 삼키고 먼저 정한 status=valid를 유지한다. 실제 원본 결과의 Temp 복사본으로 정상 대조군의 validate 통과와 fingerprint 생성을 확인한 뒤, env_origins.npy만 보존용 이름으로 옮겼다. 같은 validate는 여전히 통과했고 보고는 **status=valid, fingerprint=null**이었다. 파일 복구 후 정상 결과로 돌아왔다. 슬롯·로그 경계는 2절과 같은 대체를 썼고 validate·fingerprint 본문은 실제 코드다. D:1616~1643의 최종 완료 조건도 이 지문 누락을 보지 않는다. 완전한 실행이 정상적으로 지문을 내는 것과, 누락을 조용히 성공으로 처리하는 것은 다른 문제다.

실패 run의 없는 증거를 null로 남기는 것은 맞다. 그러나 유효 run의 필수 fingerprint·지형/배치 증거를 계산하지 못하면 why를 남기고 held로 내려야 한다. 기본·반복에 같은 필수 조건을 적용한다. 세 run이 같은 물리 조건이었는지는 계약상 의도된 차이를 제외한 공통 지문으로 별도 대조해야 한다. 없는 자료를 정상 완료의 근거로 삼지 않는다.

형식 자체는 기본·반복·실패에 동일한 시간·tries·preflight·장치 전체 peak/여유·지문·버퍼·입력·reset 필드를 쓴다. 다만 wall_s는 마지막 try 시간이고 전체 비용은 try_records와 준비·대기까지 합쳐야 한다. failed(rc 비정상), held(결과 검증 실패), not_run을 구별한다. 승인된 조건부 반복이 실제 실행되지 않았다면 그 여부·사유도 명시하는 것이 정직하다.

통과선은 **실행 전에 확정하고 구현과 일치시켜야** 한다. 미결정 문자열을 해시에 묶었다고 사전 확정이 된 것은 아니다. A의 과학 기준은 계약에 있는 세 칸 각각 95% 구간 하한 >0 및 동일 가중 평균 ≥10%p를 유지한다. 진단의 비용 측정 뒤 시간 예산을 갱신하는 것과, 성능을 본 뒤 채택선을 바꾸는 것을 구분한다.

**남길 미확인:** 실제 세 run의 물리 동등성·유효 지문·반복 결과·전체 소요. 현재 보류는 성능 불량 판정이 아니라 실행 안전성과 증거 완결성에 대한 판정이다.

## 4. 승인 구조·책임·권고값

**판정: 승인 B는 정확히 22키다. 새 값 검사를 보완하고 실측·팀장 결정을 채우기 전에는 승인 JSON을 발급하지 않는다.**

**근거 · 확인됨:** 외형은 {approved:true, by:검증자, approved_at:시각, reviewed:B}다. B는 M:83~105가 만드는 다음 키 전체이며 이 표기는 양식 설명이지 승인이다.

experiment, train_seed, contract_sha256, stage, approval_id, attempt, log_name, restart_scope, termination_policy, comparison_pass_rule, candidate_hashes, comparison_report_sha256, gpu_index, gpu_uuid, CUDA_VISIBLE_DEVICES, diagnostic_repeat_original, deadline_epoch, risk_limit, convert_lock, run_lease, registry, python.

train_seed=1043, 진단 stage=diagnostic. candidate_hashes는 M·비교기·D·post·frozen 실행기 다섯 Python 파일의 바이트 SHA256이다. 경로·allowlist·등록 입력 38개·runtime·과학 기준은 canonical contract SHA256에 포함된다. 비교 보고와 승인 JSON은 각각 파일 바이트 해시다. 승인 해시는 execution.approval_sha256과 외부 --approved_digest 양쪽에 들어간다. manifest 전체 파일 해시가 B에 직접 들어가는 구조는 아니므로 실행 시 manifest 바이트도 pins로 보존한다.

| 새 필드 | 누가 무엇을 정하는가 |
|---|---|
| approval_id·attempt·log_name | lead가 충돌 없는 새 이름과 미사용 장부·로그를 확인해 제안, ASTRA가 그 정확한 이름을 승인에 결박. 팀장이 매번 이름을 만들 필요는 없다. 미정 예약어 금지, 영숫자·_·- 사용, log는 CLI 제한에 맞춰 50자 이하로 둔다. |
| restart_scope | 팀장이 단회 기동 정책을 결정. 권고 single_start_no_reuse. 프로세스 종료·실패 뒤 자동 재개 금지, 잔여 작업은 새 승인. |
| termination_policy | 팀장이 종료 위험을 결정. 권고 partial_result=held, terminate_grace_s=5~10초. 현재 Windows terminate를 애플리케이션의 정상 저장 종료라고 간주하지 않는다. 소유권이 불확실하면 신호 금지·lease 보류·운영자 인계. |
| comparison_pass_rule | ASTRA가 기술적으로 지원되는 규칙을 제시하고 팀장이 채택, lead가 실행 전 고정. 현재 권고는 semantic_and_json_bytes_and_traj_bytes 하나뿐. 다른 기준은 구현·사전 계약 검토 없이 넣지 않는다. |

**아래 수치는 추정 권고이며 승인값이 아니다.** 최초 진단은 팀장이 실제 비어 있는 GPU 0 또는 1 중 하나를 배정하고, 참가 Isaac 실행 전체와 공통 lease를 지키는 20~30분 작업창을 확보한다. 어느 GPU가 지금 비었는지는 이번에 측정하지 않았다.

- 첫 묶음은 launch=3, retry=0, 원본 반복=false를 권고한다. 같은 승인에 불일치 원인용 반복까지 원하면 사전에 launch=4, repeat=true로 선택한다. 반복·재시도에 별도 무상 예산은 없다.
- max_wall_s=1200~1800초를 초기 범위로 두되 준비·안정성 관찰·대기가 포함된다. deadline_epoch는 정한 창의 새 자식 시작 마감이며, 20~30분 뒤의 구체 시각으로 확정한다. 실행 중 이미 시작한 자식은 별도 wall 감시가 관리한다. 접근 불가 자식 때문에 lease가 남는 상황까지 이 시간 안에 해결된다는 보장은 없다.
- 물리 UUID/index·CUDA 매핑·최저 여유·Python/NumPy/torch/Isaac 버전·공통 경로와 실제 참가자는 lead 측정 대상이다. 팀장 배정과 실측은 다르다. 공유 확인 bool만 true로 적는 것은 증거가 아니다.

순서는 세 결함 수정 및 해당 정상·반례 재검 → 실제 배치와 공통 경로·runtime·원자료 측정 → 팀장 결정 → contract 동결 → 실제 번들 사본 SAME 보고 동결 → 코드 다섯 해시와 B 검토 → 제한된 진단 승인과 외부 digest 전달 → 기동 직전 불변성·장치·미사용 claim 재확인이다. 새 이름만 붙여 재기동을 반복하는 것은 새 예산 검토를 대체하지 못한다.

**남길 미확인:** 최종 배정·작업창·위험값·반복 결정·소유권 수정·운영 실측. 이 보고서는 다른 세션이 전한 승인을 팀장 결정으로 인정하지 않는다.

## 5. 배치와 첫 GPU 진단

**판정: 이전 배치안은 allowlist로 구체화할 수 있다. 그러나 지금 반영하거나 기동할 상태는 아니다.**

**근거 및 권고:**

candidate_dir=C:/isaac/ext/go2_rl_robotlab/_eval/cmdr1043_eval_17s_fixed/, source_eval=C:/isaac/ext/go2_rl_robotlab/_eval, write_root=C:/isaac/ext/go2_rl_robotlab/_audit_cmdr1043/의 분리를 유지한다. 데이터·보고·작업·시도·로그·STOP·승인 장부는 write_root 아래에 둔다. approval_ledger는 한 승인에서 바꾸지 않고 지우지 않는다.

**공통 잠금은 검증된 기존 경로를 정확한 allowlist로 재사용하는 편을 권고한다.** 기존 도구가 다른 lease를 쓰는데 새 write_root에 우리 lease만 만들면 서로 막지 못한다. lead가 실제 참가 명령에서 registry·convert_lock·run_lease의 canonical 경로를 찾아 확인하고, 그 세 키만 key/path 쌍으로 등록한다. 변환 lock과 전체 실행 lease는 서로 다른 파일이어야 한다. 모든 참가자를 새 공통 경로로 동시에 옮겨 검증할 수 있을 때만 새 경로를 택한다. allowlist를 source_eval 전체의 쓰기 허가로 넓히지 않는다. 이번 감사는 실제 운영 파일에 allowlist 시험을 쓰지 않았다.

1. 원본 38개·양 군 end/guard/slot/stamp·후보 경로·runtime·자기 해시와 출력 격리를 CPU로 확인한다. 실제 등록 번들을 write_root 아래에 바이트 복사해 비교한다. 이번 Temp 대조는 SAME/0 → on seed1042 변조 DIFFERENT/1 → 복구 SAME/0이었다. 배치 후 바뀐 계약 해시로 다시 해야 한다.
2. 배치된 코드로 잘못된 통과선·누락 지문·PID 재사용 반례와 정상 대조를 재검한다. 단회 claim·사용된 ID·동시 기동·경로 별칭·장부 탈출·lease 경합도 실제 배치 경로에 연결해 확인한다.
3. 첫 자식 직전 등록 바이트·승인 digest·STOP·마감·미사용 claim·물리 UUID/index·논리 CUDA 0·여유 4096 MiB 이상·동시 Isaac·공통 lease를 확인한다. CPU 시험의 가짜 GPU 값은 사용하지 않는다.
4. 소유권 불명·한도·STOP·guard·USD 참조/충돌·traceback·입력 변경·불완전 지문·비교 불일치에서 보류한다. 잔류 자식이 있으면 다음 run이나 lease 해제로 진행하지 않는다. 원자료를 실패 원인별로 보존하고 허용 없는 자동 재기동은 하지 않는다.
5. 진단 보고는 “3회 중 실행/유효/보류/실패/미실행, 조건부 반복 여부, A 0회, 전체 시간·각 try·장치 전체 peak/최저 여유, 의미/바이트/공통 지문”으로 작성한다. peak를 해당 작업만의 VRAM으로 표현하지 않는다.

진단 한 묶음은 임시로 10~20분을 계획하되 첫 실측으로 갱신한다. 과거 평균 75.3초 ×3=3분45.9초는 현재 후보 실측이 아니고 준비·대기·기본 버퍼 비용을 보장하지 않는다. A는 별도 승인이다. **현재 A 경로는 시작 시험 8회+45회=53 launch, 조건부 원본 재시험까지 고려하면 54**를 세야 한다. 진단 3회를 이미 했다고 이 8회를 빼면 안 된다. retry를 허용하면 그 추가 launch까지 상한에 명시한다. A의 초기 시간창 90~120분은 진단 후 갱신할 추정일 뿐이다. 목표 세 칸의 결과를 나머지 96칸·22,000 checkpoint·정책 전체 채택으로 확대하지 않는다.

**남길 미확인:** 운영 경로 참가자 전수·배치 후 관문·현재 GPU·실제 진단 비용과 A 비용. 옛 CPU PID 175820는 조회·종료하지 않았다.

## 6. 지금부터의 견적과 재현 자료

**판정: 기존 1.75~4.5시간에서 작업자 소요를 빼지 않는다. 새로 확인된 종료 소유권·승인값·증거 누락이 임계 경로다.**

**추정:** 세 결함 수정과 작업자 정상·반례 0.75~2시간, 수정 영향 독립 재검 0.5~1시간, 배치·실측·동결 0.25~0.5시간으로 **GPU 진단 시작까지 1.5~3.5시간+팀장 결정 대기**를 계획 참고값으로 둔다. 소유권을 OS 수준으로 다시 설계하거나 공통 lease 참가 도구를 변경해야 하면 이 범위를 넘는다. 팀장 결정은 수정 중 병행해 기다림을 줄일 수 있지만 수정된 바이트의 검증을 생략하지 않는다. CPU 10개 실행의 79.70초는 검토·반례 구성·배치 시간을 뜻하지 않는다. 작업자 22:50~23:15와 lead 23:50은 보고된 작업 시각이며 준비 완료 측정값이 아니다.

**확인됨 · 재현 경로:** C:/Users/AI-WS01/AppData/Local/Temp/astra17t_cpu__tityzhh/

- sources-before.json: 후보 31개·입력 38개와 시작 상태.
- evidence_17s/run_20261015_000004_76084/: 10개 재실행, 입력 12건, 코드 변이 6건의 정상/변이 로그·소스.
- independent_17t.py · independent-results.json: 미결정 통과선·새 필드 결박·가상 PID 재사용/접근 거부·별도 프로세스 claim 경쟁.
- fingerprint_probe.py · fingerprint-results.json: 실제 원본 사본의 정상·지문 파일 누락·복구.
- evidence-audit.json · compare_raw/: 159개 목록 대조·변이 실제 diff·정상/seed1042/복구 번들 비교.
- final-source-check.json: 보고서 작성 뒤 고정 바이트·입력·작업 상태 재확인.

시험 후보 코드는 원본 그대로 복사했고 manifest의 시험 출력 경로만 Temp로 재등록했다. 승인 fixture는 CPU 시험용이며 실행 승인 파일이 아니다. ASTRA 집계 보조 명령은 처음 summary의 키를 records로 잘못 읽어 중단됐고 results로 바로잡았다. 제품 실패나 시험 재실패로 세지 않았다. 새로 만든 CPU 시험 자식만 실행·회수했고 운영 프로세스는 건드리지 않았다.

**남길 미확인:** 실제 수정 난이도·결정 대기시간·운영 자원·배치와 GPU 시간. 위 세 결함이 남아 있는 한 “진단 허용”으로 옮기면 이 판정을 잘못 읽은 것이다.


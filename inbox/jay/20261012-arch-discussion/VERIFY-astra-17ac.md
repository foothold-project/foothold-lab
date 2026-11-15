판정: 3차는 수집 완료·0단계 HOLD이며, A3.2 정보 수집과 0단계 전 배관 smoke는 아래 조건으로 설계할 수 있지만 현재 미동결 A3.2와 코드 없는 200-update·두 arm의 기동을 승인한 것은 아니다.
> 분류: A/정책학습 · ASTRA 17ac 독립 검증
> 작성: 오흥재 (ASTRA 세션 검증) · 2026-10-15
> 근거: 의뢰문 전문·추가 정정 · attempt3 capture·영수증·최종 cfg · c3307646의 실행 당시 검사기 · 설치 RayCaster 소스
> 요지: 13개 HOLD를 재현했으며 집계 분류·낙하 시점·센서 프레임을 정정하고, 진단과 학습 배관 시험의 허용 범위를 구분한다
> 상태: 원자료 CPU 확인 완료 · A3.2 방향 검토 · 코드 수정·GPU·Isaac·커밋 없음

# ASTRA 17ac

## 1. 3차 판독: 수집 완료는 맞고, 10+3 분류는 틀리다

**확인됨.** 이하 `R`은 `night-tools-20261013/s2_stage0_first_collection/attempt3_20261015_1506/`, `A3`는 `night-tools-20261013/s2_step4a3/`다. 변경 중인 검사기를 실행하지 않고 `git show c3307646:…/s2_connect_check_17v.py`와 같은 커밋의 순수 CPU oracle을 메모리에 읽어 재계산했다. 저장된 `R/out/check.json`과 사유 13개·counts·criteria가 모두 일치했다. NumPy CPU만 사용했다.

- `capture.npz` SHA256: `ce3ece986e149629e808ecbb978c308d991cd5bbedb972cedd81cfb565a93f22`.
- 재계산에 쓴 검사기 SHA256: `a052829950b13ab721dcbf138f573af74e6681fac26a7291447ed459abbab1d4`.
- `stage0.receipt.json`의 artifact 9개를 사본 바이트와 대조하여 9/9 일치. 최종 cfg 내부 문자열 해시도 meta와 일치했다.
- 배열은 256행·8환경·187광선, 완료 기록은 captured 256·last_valid_step 255, 로그의 Python Traceback 표식은 0이다. 영수증의 자식 exit 0·가족 0, 상태 기록의 HOLD_INFORMATION_ONLY, 변환 기록의 0은 확인했다. 당시 OS 가족 상태를 지금 독립 실측했다는 뜻은 아니다. `completion.json`의 close 상태는 여전히 pending이며 사본에 `cleanup.json`은 없다. 자식 exit 0만으로 앱 정리와 검사 PASS를 선언하면 안 된다.

검사 이름 기준으로 나누면 다음과 같다. 이는 독립 원인 수가 아니다.

| 구분 | 실제 사유 |
|---|---|
| 기록·출처 관문 7개 | `provenance_missing`, `mesh_evidence_hash`, `boundary_evidence_hash`, `boundary_evidence_content`, `boundary_unreported`, `root_sensor_transform`, `case_assignment` |
| 수치·실험 계약 관문 6개 | `fixed_pose_evidence`, `stale_packet`, `sensor_timestamp`, `boundary_mask`, `scene_hit_mask`, `world_height_answer` |

`case_assignment`는 고정 자세·충돌 증거도 함께 요구한다. false를 true로 채우면 닫히는 단순 문서 누락이 아니다. `sensor_timestamp`에는 예상된 reset을 금지한 검사기 문제도 섞인다. 따라서 **“10개는 기록만 채우면 되고 실제 문제는 3개”라는 축약은 폐기**해야 한다.

**독립 재계산 결과.** 아래 step은 0부터 세는 capture 행이다.

| 항목 | 재계산과 정정 |
|---|---|
| 초기 자세 | 첫 16행 root 위치 최대 차 0.225732 m, 수평 성분 최대 차 0.064710 m. 15행 상대 z는 0.174211~0.295086 m다. 모든 환경이 0.17~0.25 m라는 서술은 틀리다. |
| 자동 reset | termination은 (36,4), (58,5), (168,6), (183,4), (246,4) 다섯 곳, timeout은 0. 최종 cfg의 종료항은 base_contact와 timeout뿐이므로 base_contact 원인이라는 해석은 자료와 부합한다. |
| timestamp | 음의 차 13개는 episode 증가 13개와 정확히 일치. 자동 reset 5개와 128행의 의도된 8환경 reset이다. 이를 실제 stale 센서 패킷 13개라고 부르면 틀리다. |
| gap_90 | 전체 187광선 miss와 root z < -20 m는 **173행부터**다. 191행부터라는 주장 정정. 173행 root z=-20.346617 m, ray start z=-0.346617 m, 마지막 root z=-66.615616 m. |
| oracle 불일치 | 비경계 hit/miss 불일치 15,521개 모두 env 5이며, 모두 ray 시작점이 oracle 표면보다 낮다. gap_0 miss 2,527개 일치는 맞다. |
| 경계 | 기대 2,494개·기록 2,493개. 차이는 (66,6,111) 하나. 두 경로의 경계 거리가 0.004999784 m와 0.005000229 m로 5 mm 임계 양쪽에 놓인다. |
| 변환의 제한적 일치 | 기록 hit→height 재계산 최대 오차 1.1921e-7, mask 완전 일치. 유효 hit의 XY 최대 오차 3.4631e-6 m, 비경계 oracle 표면 z 최대 오차 4.5777e-6 m. |

**“height 식이 이번 자료의 내부 일관성 검사에 걸리지 않았다”는 맞다. “센서→지도 전체가 검증됐다”는 틀리다.** 충돌 출처·root 변환 관문은 열려 있고, 낙하 후 XY만 보는 oracle의 적용 전제가 깨졌다. 이때 miss는 구멍만 뜻하지 않는다. 광선이 표면 아래에서 아래로 출발한 것도 miss다. 기존 데이터를 통과시키려고 oracle을 완화하지 말고, 다음 진단에서 광선 출발 높이·방향·길이의 유효 범위를 확인한다.

**보충 정정 수용.** 설치 `ray_caster.py:220~224,242~248`과 자료가 일치한다. `pos_w-root_pos_w` 최대 차는 약 1.12e-8 m이고 `ray_starts_w.z-pos_w.z`는 20.0 m다. cfg의 +20 m를 root_sensor_offset_b로 쓰면 안 된다. `_offset`을 읽되 그 view가 실제 비교 대상 root/base인지도 확인한다. 환경별 일치·회전 단위·drift 0 조건과 실제 root→pos 오차를 함께 기록한다. 이미 수정된 `mount_offset()`의 방향은 맞으며, 구현 전체 승인을 뜻하지 않는다.

## 2. 중력·종료 해제: 진단에는 가능하지만 고정의 증명이 아니다

**판단:** 진단 전용 8-case 센서 기하 시험에서 중력과 base_contact 종료를 끄는 것은 가능하다. 학습 A/B의 물리 설정을 바꾸지 않고, 변경 cfg·hash와 적용 목적을 명시하면 “동일 학습 시험지”를 훼손했다고 볼 이유는 없다. 다만 그 결과는 **기하·데이터 연결 시험**이며 중력 아래의 보행·접촉·지도 효과를 증명하지 않는다.

중력 0에서도 관절 구동, 초기 속도, 접촉·겹침 해소로 자세가 바뀔 수 있다. **“disable_gravity=True이므로 고정됨”은 기각한다.** 우선 이 변경으로 얻은 실제 첫 16행의 위치·자세·센서 위치가 기존 허용 범위인지 재야 한다. 고정 실패면 명시적인 root 고정 수단을 쓰고 속도·필요한 관절 상태와 접촉 조건도 통제한다. 매 제어 step에 pose만 쓰는 것도 중간 physics substep의 움직임을 막는 증명은 아니다.

고정 수단을 쓰더라도 센서 원출력·tracker를 그대로 읽고 기록 pose를 사후 교체하지 않는다. 64/128/192 개입은 유지하고 개입 뒤 센서 갱신을 검증한다. 현재 mode는 16 fixed + 240 live다. 256행 전부를 강제 고정했다면 live 240으로 표기하면 안 된다. 이후 구간도 oracle 유효 영역·광선 높이를 벗어나면 별도 HOLD로 남긴다.

## 3. PhysX 비교: 표본에서의 충돌 응답 일치는 인정, 메시 전체 동일성은 미확인

**판단:** USD→Warp 점·인덱스·world transform 대조와 **PhysX의 독립 query**는 적절한 방향이다. 다음을 갖추면 이 8-case 진단의 표본 광선에서 두 경로가 같은 지면을 본다는 증거로 받을 수 있다. PhysX cooked mesh 전체를 직접 추출했다거나 전체 표면이 동일하다는 뜻은 아니다. cooked mesh 접근 불가 주장은 이번에 확인하지 않았다.

- source USD·참조 자산, 정확한 mesh prim, collision 활성·approximation·transform, Warp 배열과 query 설정을 각각 보존한다. USD 내용 해시와 query 결과 해시는 다른 종류의 증거다.
- 같은 world-space origin·direction·유효 거리에서 hit/miss와 유효 hit 위치를 비교한다. 전체 hit 평균만 비교하지 않는다. 8환경·두 yaw·개입 전후, 구멍 miss·깊은 유효 바닥·단차 상하·stones를 구분하여 계획/시도/비교/경계 제외/차폐/오류 수와 최대 오차를 남긴다. 예상 답과 제외 규칙은 결과 전에 고정한다.
- `raycast_closest`가 로봇을 먼저 맞혔다면 그것은 지면 검증 표본이 아니다. 지면 collider를 정확히 고르는 query 경로를 쓰거나 차폐를 미검증으로 남긴다. 마지막 장면에서 과거 ray들을 다시 쏠 때도 지면 정적 상태·transform 불변을 증명하고 움직인 로봇의 차폐 영향을 분리한다.
- 원시 query 응답 또는 재계산 가능한 배열·prim 경로·표본 ID를 보존한다. 보고서 요약을 해시한 `collision_sha256`을 “충돌 메시 바이트 해시”라고 부르지 않는다.

**CPU 반례 확인:** 작성 중 probe의 순수 비교 함수에 정상 입력(평지 hit 1,000 + 구멍 miss 1,000)을 넣으면 agree=True다. 구멍 1,000개를 전부 차폐로 바꿔 **구멍을 하나도 검사하지 않은 입력도 agree=True**다. 전체 유효 hit 1,000개 조건만으로는 부족하다. 이 반례는 방향의 빈틈을 보여주며 A3.2 전체 시험을 대신하지 않는다. 당시 probe hash는 `05900e24a425bf71a0afb7ebf0cac43b3c8600e4344459fb58afea1eb43886c0`이다.

따라서 `kind=observed_collision_mesh`만 보고 PASS시키지 말고 **표본 충돌 응답 검증이라는 범위와 갈래별 검사 충족을 판정기에 명시**한다. query API 실패는 원자료 보존·오류 기록·HOLD로 처리할 수 있다. 하지만 native 접근 위반은 Python try/except로 보존된다는 보장이 없으며, 새 probe도 기존 hard deadline과 자원 제한을 따른다. query가 끝내 안 되면 USD+Warp 증거만 남기고 PhysX 부분은 미확인으로 둔다.

## 4. reset-aware timestamp: 수용하되 episode 증가만 믿지 않는다

**확인됨:** 설치 `sensor_base.py:169~187`은 reset 때 `_timestamp`를 0으로 하고, 다음 update에 dt를 더한다. 이번 자동 reset 행은 해당 env 시각 0, 의도된 128행은 8환경 모두 약 0.02다. 따라서 “언제나 단조 증가”는 이 구현에 잘못된 조건이다.

이 256행 계약에서는 다음을 함께 검사한다.

1. 같은 episode에서는 실제 update 주기와 맞는 timestamp 전진, generation 증가, 현재 sim_step의 독립 hook receipt를 요구한다. 상수 시각·중복 패킷을 허용하지 않는다.
2. 예정된 reset은 128행에서만 각 env episode가 정확히 +1. 실제 reset 표식·센서 갱신·pose 개입을 함께 확인한다. 의도하지 않은 termination과 timeout은 별도 HOLD다. episode 증가를 허용표로 사용해 자동 reset 다섯 개를 통과시키지 않는다.
3. 이번 의도된 reset은 127행 시각이 충분히 크므로 128행 되감김과 reset 후 약 1 control step 시각을 검사할 수 있다. 일반 규칙을 “모든 reset은 반드시 음의 차”로 쓰면 초기 0→0 reset이나 전역 시계를 쓰는 센서에 틀린다. 여기 설치판·현재 스케줄에 한정한다.

정상 예정 reset, 같은 episode 역행/정지, 가짜 episode 증가, reset 표식 없는 증가, 예정 밖 실제 reset, reset 뒤 이전 버퍼 재사용을 나눠 시험한다. 이 변경은 예외를 무조건 허용하는 완화가 아니라 **실제 시계 계약에 맞추는 수정**이어야 한다.

## 5. A3.2와 4차 정보 수집의 범위

**방향은 조건부 수용한다. “진단·환경·검사기 세 파일만”은 충분하지 않다.** 제안 자체에 mesh probe, 증거 형식, 시험과 manifest/approval 갱신이 들어간다. 이 직접 의존 범위까지 포함하되 A3 감독기·Job·lease·권한·무인 경로로 넓히지 않는다.

최소 수정 범위는 자세/자동 reset 통제, 정확한 sensor frame과 ray frame 구분, reset-aware 검사, 경계 좌표/정밀도 계약, 원시 mesh/query 증거와 갈래별 충족 검사다. 경계 mask를 검사기와 같은 함수로 만드는 것은 두 생산물의 일치를 보장할 뿐 독립 정답 검증은 아니다. 5 mm 안팎을 아는 입력으로 검증하고 실제 ray XY와 분석 XY 차이도 계속 검사한다. 원래 mask/차이 기록을 보존하여 사후 재계산을 숨기지 않는다.

이를 동결하고 CPU 정상 대조·의도한 실패 위치의 변이 시험을 기록하면 **4차는 참석 정보 수집 단회로 진행 가능한 범위**다. PhysX API를 처음 확인하다 HOLD가 나는 것 자체는 허용할 수 있다. 그 실행이 PASS할 것이라고 선승인하지 않는다. 17y/17ab의 새 동의·새 chain/출력·GPU 0 물리 결박·직전 자원/잠금·retry 0·900초·8환경/256step/optimizer 0·정리 확인을 유지한다. probe가 걸리면 제한 안에서 HOLD하며 자동 반복하지 않는다. 현재 수정 중 파일이나 과거 해시 목록을 새 승인 바이트로 쓰면 안 된다.

## 6. 0단계 PASS 전 B smoke

**기술적으로 가능하다. 다만 아직 없는 코드의 200 update·두 arm 실행 허용은 보류한다.** stage0는 지도 기하 신뢰성의 관문이고 배관 smoke는 optimizer·입출력·저장/복원의 관문이다. 목적을 분리하면 준비를 병렬화할 수 있다.

허용 가능한 별도 시험은 다음 조건을 갖춘 **참석 단회·고정 상한의 진단**이다.

- 원본 checkpoint 불변, 새 격리 출력, 고유 manifest에 `plumbing_only`와 stage0 미통과 표시. 결과·가중치를 A/B 성능, 지도 효과, 후속 학습 시작점으로 사용하지 않는다.
- 시험할 실제 입력 경로를 선언한다. CPU에서 답을 아는 tensor의 shape·mask·finite 값·축/순서를 먼저 확인한다. synthetic 입력이면 그렇게 표기한다. 미검증 실센서를 쓰면 성공은 배관 연결에만 한정한다. 진단용 무중력 cfg가 학습 cfg로 새지 않아야 한다.
- forward→loss→backward→optimizer→save/load 및 필요한 두 arm 경로를 검사한다. gradient/parameter 변화·NaN·예정 encoder freeze·학습률·arm별 초기화와 출력 격리를 확인한다. 단순 기동 확인에 200 update가 필수라는 근거는 없다. 우선 완전한 PPO iteration 1~2회 수준으로 줄이고, 200이 필요하면 누적 메모리/저장주기 등 구체적인 시험 목적·wall 상한을 별도로 정한다. iteration과 환경 step을 혼용하지 않는다.
- 코드·해석기·의존성·기동 옵션·종료와 실제 Job 가족 정리 경로의 CPU 검사가 있어야 한다. stage0의 optimizer=0 감독기를 우회해 학습을 숨기지 않고 별도 시험 계약과 새 직접 동의를 받는다. 자동 재시도·무인·후속 학습은 포함하지 않는다.

**GPU 배정 판단:** GPU 1의 데스크톱 점유 10.6 GB는 이번 의뢰의 보고값이며 현재 직접 재지 않았다. 정리가 끝났다고 가정하지 않는다. 가능하면 GPU 0에서 A3.2 수집과 작은 배관 smoke를 순차 배치한다. GPU 1은 기동 직전 UUID·가용 VRAM·기존 작업·lease·안전 여유가 확인된 뒤에만 별도 배정한다. 두 arm은 한 GPU에서 순차 실행해도 된다. 두 GPU를 채우려는 이유만으로 두 arm 동시 기동이나 검증되지 않은 큰 smoke를 허용하지 않는다.

## 7. 추가 ASTRA 왕복 없이 lead가 처리 가능한 경우

**가능하다. 모든 수정을 새 ASTRA 판정에 묶을 필요는 없다.** 이번 문서에 정한 기하·timestamp·증거 조건을 충족하는 A3.2 구현과 그 후 좁은 accessor/직렬화/버전 기록/API 호환 수정은 아래를 모두 갖추면 **lead의 검증 기록과 팀장의 해당 단회 새 동의**로 다음 참석 정보 수집을 판단할 수 있다.

- 바뀐 파일과 직접 영향, 원인·수정·정상/반례 기대값을 먼저 기록한다. 정상 소스가 같은 시험을 통과하고 변이가 의도한 위치에서 실패해야 한다. 실행/skip/hold/미시험, 실제 interpreter·패키지·원시 출력·해시를 함께 남긴다.
- 이 문서가 요구한 물리 단위·좌표계·고정/실제 동작 구분·원시 증거·갈래별 검사 조건을 유지한다. tolerance나 제외 범위를 넓혀 실패를 감추지 않는다. 아직 못 채운 조건은 HOLD로 유지한다.
- 실행당 새 불변 manifest/approval/claim/출력, 사람이 끝까지 보는 참석, 고정 시간·자원·시도 수, 실패 후 가족 정리 확인을 유지한다. 팀장 새 동의를 받았다는 다른 세션의 전달만으로 대체하지 않는다.
- **별도 검토 대상:** 검사 의미·허용 오차·oracle/경계의 판정 규칙을 이번 합의 밖으로 바꾸는 것, 원자료 사후 덮기, GPU/Job/잠금/마감/권한 경로 변경, 새 native crash 또는 격리 실패, 학습·평가·무인 승격. B 기동 구현은 현재 미확인이므로 이 작은 수정 위임에 섞지 않는다.

이 범위는 반복 수집의 절차를 줄이는 것이며 포괄적인 실행권이나 무인 승인 JSON이 아니다. **17z 무인 보류는 그대로 유지한다.** 4차 실제 안정성·PhysX query 성공·B 실행 경로는 미확인이다.

고칠 것: 현행 A2는 실제 PyTorch 장치 조회에서 수집 전에 막히므로 기동을 보류하며, 아래 최소 수정 후 참석 단회는 가능하지만 추가 watchdog을 붙인 현행 조합도 무인 단회 요건은 충족하지 못한다.

> 분류: A/정책학습 · ASTRA 17x 독립 검증
> 작성: 오흥재 (ASTRA 검증 작성) · 2026-10-15
> 근거: TASK-astra-17x-s2-stage0-a2.md 전문 · 17w 지적 · A2 및 추가 watchdog 고정 사본 · 설치 PyTorch/IsaacLab 소스 · CPU 재현
> 요지: 지정 반례 수정은 확인했지만 실제 장치 API, 실패 행 보존, 무인 기동의 준비 확인과 마감 보호가 남았다.
> 상태: 검토 완료 · GPU/Isaac 기동·운영 프로세스 접촉·기존 코드 수정·커밋 없음 · 승인 JSON 발급 없음

# ASTRA 17x · A2와 독립 watchdog

경로 약칭: A2는 `night-tools-20261013/s2_step4a2/`, W는 `night-tools-20261013/s2_step4a3_watchdog/`다. 17w에서 닫은 사항을 전부 재심사하지 않았다. 여기서 허용 조건은 기술 판단이며 실제 manifest·승인 발급은 위임받은 lead의 일이다.

**증거 경계 · 확인됨.** A2 `SHA256SUMS.txt`의 39/39 파일 일치, 목록 해시는 `17dbd53859ab1f0c9f2c987a180f8f5c097fb591ff8caf371f773f301eb976b5`. 전달 목록 `S2-STEP4A2-DELIVERY-SHA256.txt` 자체는 39행이 아니라 **6개 기록물의 목록**이다. 경로를 대응시키면 보고서·이슈 본문·39파일 목록·작업자 summary 4개가 일치한다. `HANDOFF.md`, `S2-STEP4A2-CLEAN-IMPORT.json`은 제공 폴더에 없다. 코드 39개의 일치를 부정하는 문제는 아니지만 전달 목록 6/6 확인이라고 보고하면 틀린다. W는 목록 5/5 일치다.

| 이번 확인 | 결과 | 해석 범위 |
|---|---|---|
| A2 수정 관련 정상 시험 6개 | 종료 0, PASS 4+10+7+4+4+11=40 | scene·checker·tracker·journal·device·contract. 나머지 과거 정상 시험을 전부 반복하지 않음 |
| A2 새 코드 변이 7개 | 7/7, 정상 종료 0·변이 종료 1·첫 FAIL=want | 원 소스의 한 앵커를 바꾼 실행과 정상 대조 확인 |
| 완결 사본 import | 필수 Python 모듈 22개가 Temp 사본 경로에서 import됨 | Isaac 생성·GPU 연결 성공의 뜻은 아님 |
| lead 기존 증거 재계수 | 정상 로그 84 PASS, 5+7 변이 로그의 정상 PASS와 첫 FAIL=want 일치 | 과거 종료 코드는 summary 기록. 이번 직접 재실행 40개와 구분 |
| W 정상 시험 | 종료 0, 13 PASS 재현 | 시험이 만든 CPU 프로세스만 사용. 실제 Isaac 없음 |
| W 코드 변이 4개 | 고정 summary의 want·first_fail 4/4 일치 | 별도 정상/변이 전체 stdout이 납품되지 않았고 이번에 4개를 재실행하지 않음. 독립 4/4 실측이라고 쓰지 않음 |
| 실제 Windows Job와 W 연결 | CPU 감독기를 W가 종료한 뒤 자식·손자 모두 소멸 | 이 경로는 이번에 직접 확인. 모든 장애·lease 경쟁까지 입증한 것은 아님 |

재현 위치: `C:/Users/AI-WS01/AppData/Local/Temp/astra17x_cpu_ckxbiu9u/`. `audit.json`, `results.json`, `a2mutants/summary.json`, `independent.json`, `secondary.json`, `watchdog_hashes.json`, `watchdog_normal.log`, `watchdog_probes.json`, `job_watch_probe/result.json`이 근거다. Temp는 장기 보존을 보장하지 않으므로 핵심 입력·결과는 아래에도 적었다. Python은 `anaconda3/envs/isaac311-moects/python.exe`, CUDA 노출은 `-1`, torch fixture에만 `KMP_DUPLICATE_LIB_OK=TRUE`다. 운영 lock·slot·출력 폴더를 획득하거나 바꾸지 않았다.

## 1. 17w 지적의 실제 수정 여부

**가. 환경 연결: 방향은 수정됐고 실제 성공은 미확인이다.** `s2_env_config_17v.py:58,89`가 rough6 비율만 고치는 대신 명시적 생성기를 대입한다. `s2_known_scene_a2.py:110`은 1×4열·네 종류·각 .25를 만든다. CPU 시험은 `trimesh` 대역으로 실제 `_terrain()` 함수를 호출해 .2m 표식·깊은 바닥·void를 확인한다. **registry 로딩, `build_generator()`의 실제 Isaac 클래스 생성, 최종 cfg 직렬화와 gym 생성까지 시험한 것은 아니다.** 첫 정보 수집에서 확인할 항목으로 남겨도 된다.

다만 현재는 그 확인까지 못 간다. **P1 · 실제 장치 API가 없다.** `s2_device_binding_a2.py:24`는 `torch.cuda.cudart().cudaDeviceGetPCIBusId(...)`를 호출한다. 설치된 `isaac311`, `isaac311-moects` 양쪽 PyTorch `2.7.0+cu128`의 `torch._C._cudart`에는 그 속성이 없다. GPU 초기화 없이 `hasattr`를 확인했고, 나머지 CUDA 상태만 대역으로 통과시킨 뒤 **실제 `_cudart` 모듈**을 주입하면 `DeviceHold: cudart_bus_unavailable`, 원인은 해당 `AttributeError`다. 두 해석기에서 `torch.cuda.is_initialized()`는 false였다. 이 코드는 `IsaacProvider` 생성보다 앞서 실행된다(`diag:259~262`). 정상 장치 시험은 존재하지 않는 API를 가짜 객체에 구현해 놓았으므로 실제 연결 증거가 아니다.

최소 수정: 설치판이 제공하는 장치 UUID 속성 또는 명시적으로 바인딩한 CUDA runtime API를 사용해 자식 장치와 NVML의 UUID/bus를 대조한다. `_CudaDeviceProperties.uuid` 속성의 존재는 CPU로 확인했으나 실제 반환값·표현은 미확인이다. 문자열 형식과 실패 경로를 시험하고 기동 시 실제 값을 기록한다. **조회 실패를 무시하거나 검사를 삭제하는 수정은 안 된다.**

**나. 지정 거짓 PASS와 갱신 digest: 해당 반례는 닫혔다.** 정상 정적 장면 fixture PASS를 먼저 확인한 뒤 독립적으로 바꿨다.

| 반례 | 직접 재현 결과 |
|---|---|
| `height[0,2,0]=NaN` | HOLD `height_nonfinite` |
| fixed 구간을 16개에서 1개로 축소 | HOLD `fixed_schedule` |
| root X만 +100m | HOLD `root_sensor_transform` |
| step_90 표식 제거 | HOLD `scene_hit_z` 및 구간별 marker 사유 |
| stones_90 표식 제거 | HOLD `scene_hit_z` 및 구간별 marker 사유 |
| 정적 평지 Z=0, reset 후 센서 Z=.7·height=.2 | 정상 fixture PASS. reset 뒤 height=0 강제는 HOLD |

`s2_sensor_tracker_17v.py:36~46`은 갱신 직후 env별 raw·root pose digest·timestamp·generation을 고정하고 `snapshot:63~66`에서 다시 대조한다. 버퍼 되돌림과 갱신 뒤 pose 변경 거절 시험을 재현했다. 설치 hook 파일 해시 결박도 있다. 실제 Isaac에서 관측과 hook이 같은 제어 step을 뜻하는지는 여전히 미확인이다. B 전체의 packet 소비 경로를 이번에 재심사한 것은 아니다.

**다. 자료 보존: 지도 검사 실패는 개선됐지만 모든 실패 행 보존은 아니다.** `capture:47`의 raw 선기록과 단계별 journal은 확인됐다. 지도 계산에서 step64가 실패해도 65행을 남기는 시험은 통과한다. 그러나 `translate/reset/change_yaw/step_zero`는 raw 보존용 try 바깥이다(`diag:35~46`). 독립 CPU provider에서 step64의 `step_zero()`가 hook 오류를 내게 하자 **0~63의 64행만 남고 row64 없음, `emergency_raw` 미호출**이었다. 실제 tracker는 갱신 hook 안에서 예외를 낼 수 있으므로 연결 가능한 실패다.

첫 수집 전에 step·개입·sampling 단계 전체를 감싸 실패 단계와 가능한 emergency raw를 보존한다. emergency accessor도 실패하면 그 오류와 마지막 보존 step을 별도로 기록한다. `final_cfg.json`도 `IsaacProvider` 생성 성공 뒤에야 쓰므로(`diag:75~81,261~268`) gym 생성 실패 시 사라진다. cfg·asset 선언은 생성 전에 journal에 남기는 것이 맞다. Python 초기 import 자체가 실패하면 journal보다 앞이므로, 이 경우 근거는 감독기 `attempt_start.json`과 자식 로그다. “모든 import 전에 launch 저장”이라는 보고는 범위가 과하다.

**라. 보호 연결: 일부는 닫혔고 일부는 이름만 있다.** `supervisor:134~160`에서 실제 GPU lease·host USD lock·NVML 사전 측정·실행 중 VRAM/디스크 검사·자식 로그가 호출된다. `resource_lease:68~75`와 설치 `C:/isaac/ext/go2_rl_robotlab/_eval/isaac_slot_v3.py:109~134`는 같은 경로의 byte 0을 `LK_NBLCK`로 잡고 `LK_UNLCK`로 푼다. **프로토콜 호환은 소스로 확인했으며 실제 공용 파일을 잡는 시험은 하지 않았다.**

반면 `usd_root`는 mkdir와 용량 계산에만 쓰인다. 자식 argv·환경·converter에 전달되지 않는다(`supervisor:141~148`). 이 디렉터리가 존재한다고 USD 격리가 성립하지 않는다. 자식 UUID→NVML 매핑은 검사하지만 `CUDA_VISIBLE_DEVICES`는 index이고 Kit 관찰은 정수 0 확인 또는 `unobserved`다. 실제 renderer의 물리 장치까지 확인됐다고 보고하면 안 된다.

## 2. 새 위험과 첫 수집/두 번째 PASS의 구분

| 항목 | 확인된 근거와 처리 |
|---|---|
| 수집과 검사 배열 규약 불일치 | `capture:61`이 매 행의 `ray_index`를 쌓아 `(256,187)`로 만들지만 checker:93은 `(187,)`만 받는다. 정상 provider를 실제 `capture()`에 통과시켜 HOLD `shape_or_steps` 재현. live 강제 HOLD 정책과 별개인 구현 오류다. 작은 수정이므로 첫 수집 전에 통일할 것을 권고한다. |
| 원래 ray 기하 검증 공백 | 정상 fixture의 `ray_starts_w` 전부 +100m, 또는 `ray_directions_w[...,2]=+1`로 바꿔도 각각 PASS였다. 현재는 유한성만 보고 실제 광선과 hit를 결박하지 않는다. **정보 수집을 막을 이유는 아니지만 두 번째 0 단계 PASS 전 필수 수정**이다. |
| 기하 파라미터 사전 검증 공백 | `.2m` 답 장면에 manifest `step_height_m=.3`을 주고 argv/digest를 일관되게 갱신하면 fake 자원 조건에서 prelaunch가 GO한다. 실제 configure는 이 값을 거절한다. parser/양수 검사만으로 실제 장면 계약을 검증했다고 하면 틀린다. |
| “격리 root” 밖 출력 | 현재 자식의 Kit 캐시·temp·변환 출력은 별도로 추적하지 않는다. 디스크 차감 감시는 같은 볼륨의 사용량을 보지만 경로 격리 증거는 아니다. 직접 USD 참조·변환 0을 코드/실제 로그로 확인하거나 검증된 격리 경로를 연결해야 한다. 예상 밖 변환을 침묵으로 수용하지 않는다. |
| 출력 용량 합산 | out·log 부모·usd가 중첩되면 중복 합산한다. log 부모를 큰 기존 폴더로 잡으면 이번 실행과 무관한 파일도 센다. 새 실행 전용·비중첩 루트로 묶고 중복 계산을 피한다. 1GiB는 엄밀한 파일 할당 상한이 아니라 주기 감시 기준이다. |

live 결과를 `HOLD_INFORMATION_ONLY`로 강제하고 후속 학습을 호출하지 않는 점은 적절하다. 따라서 위 checker 공백이 지금 곧바로 학습 허용을 만드는 것은 아니다. 그러나 metadata의 false 세 개만 true로 바꾸면 완성이라는 결론도 틀리다. 실제 fixed 자세 제어·메시/충돌 대응·timestamp·ray 기하까지 다음 관문에서 확인해야 한다.

## 3. 추가 watchdog으로 무인 단회가 가능한가

**판정: 아직 아니다. 종료 수단은 확인됐지만, 안전하게 준비된 뒤 시작한다는 보장이 없다.**

좋아진 부분은 분명하다. W 정상 시험 13개를 실제 CPU 프로세스로 재현했다. 이어 새 CPU 감독기가 A2의 실제 `JobOwner`로 자식을 띄우고 그 자식이 손자를 만든 뒤 heartbeat를 멈추게 했다. W가 감독기를 종료했고, 0.5초 뒤 원래 생성 시각의 자식·손자 모두 없어졌다. watchdog 종료 0, 감독기 종료 15였다. **감독기 사망 → Job handle 닫힘 → 해당 가족 종료**라는 경로는 이번 Windows 환경에서 확인됐다. 운영 프로세스에는 신호하지 않았다.

그러나 다음은 무인 기동 전 필수다.

- **준비 확인과 실패 시 정리.** `s2_launch_stage0.py:51~70`은 감독기를 먼저 실행하고 watchdog의 준비/생존을 확인하지 않은 채 0을 반환한다. 가짜 Popen으로 watchdog이 이미 종료 4인 경우를 만들고 과거 마감을 전달해도 launcher는 0·launch record를 남겼다. watcher import 실패, 잘못된 인자, 기동기 중도 종료 때 감독기만 남을 수 있다. watcher의 검증된 READY 전에는 GPU 자식을 실행하지 않도록 handshake를 두고, 준비 실패 시 방금 만든 소유 handle만 정리해야 한다.
- **실제 승인과 결박.** A2 계약은 `observer_mode == attended`만 받는다. 이를 그대로 두고 launcher만 DETACHED로 감싸는 것은 무인 조건 승인과 다르다. launcher/watchdog 코드·argv·status 경로·감독기 PID/생성 시각·attempt·manifest digest·마감을 함께 동결한다. heartbeat에도 같은 실행 identity를 넣고 대조한다. 임의의 별도 CLI 마감을 승인 마감으로 간주하지 않는다.
- **마감과 입력.** W는 wall clock만 쓰며 독립 monotonic 900초 상한이 없다. 시계 역행에도 단회 예산을 지키도록 둘을 함께 적용해야 한다. `hard_deadline_epoch`와 heartbeat의 NaN/Inf·미래 값도 거절해야 한다. 실제 함수에 NaN 마감·NaN heartbeat를 넣은 제한된 대역 시험은 인자 오류로 거절하지 않고 계속 polling했다. 정상 stale 대조는 kill 1회를 기록했다.
- **로그 실패가 종료를 막지 않도록.** `watchdog:92`의 trigger 로그가 kill보다 앞선다. 해당 기록에 `OSError`를 주입하면 그대로 예외 종료, kill 0회였다. 종료 경로가 로그 쓰기의 성공에 의존하면 안 된다. `AccessDenied`도 “정상적으로 스스로 끝남”으로 보고하지 말고 감시 불능으로 기록해야 한다(`watchdog:75~81`).
- **감시자 생존·최종 확인.** watcher 자신이 죽은 경우까지 현행은 다루지 않는다. 무한히 감시자를 늘리는 해법이 아니라 감독기 측 watcher 생존 확인 등 한 단계의 상호 고장 처리를 둔다. 강제 종료 결과는 별도 receipt로 보존하고 가족 종료 확인 전 후속 기동·lease 자동 재취득을 금지한다. 실제 Job 종료를 확인한 이번 CPU 시험을 보존하되 이것을 crash 뒤 lease 경쟁 시험으로 확대 해석하지 않는다.

README의 “첫 변이 3/4는 want 지정 오류” 설명은 최종 코드·summary와 모순되지는 않는다. 그러나 최초 stdout·수정 전 시험 바이트가 없으므로 그 원인까지 독립 확정하지 않는다. 최종 4/4도 제공 summary와 지정 실패 라벨의 일치까지만 확인했다. 이미 발견한 준비/로그/마감 반례로 무인 판단은 결정되므로 기존 변이 네 개 전체를 추가 반복하지 않았다.

**무인을 완성하지 못하면 실제 사람이 참석하고 종료 경로를 확보한 단회가 맞다.** LLM의 응답 가능 상태를 참석자로 적지 않는다. 단, 장치 API 등 첫 수집 최소 결함은 참석 여부와 관계없이 먼저 수정한다.

## 4. 기동 직전 값과 GO의 의미

17w 권고인 GPU 0·8환경·256 step·16 warmup·개입 64/128/192·optimizer 0·retry 0·`max_wall_s=900`·초기 free VRAM 8GiB 이상·실행 중 2GiB 미만 보류·초기 free disk 2GiB 이상·출력 감시 1GiB는 **출발 권고로 유지**한다. 최적값·충분성을 실측한 것은 아니다. 실행/정리 시간을 포함한 구체 절대 마감과 승인 만료를 발급 시각 기준으로 채운다. 토요일 정오는 전체 Windows 작업의 상한이며 단회 watchdog을 그때까지 느슨하게 두라는 뜻이 아니다.

prelaunch GO는 충분하지 않다. 현재 코드가 확인하는 것은 해시·일부 계약·NVML/disk·짧은 lock 획득·프로세스 이름 검사다. 다음을 함께 확인해야 한다.

1. **실제 환경:** 정확한 Python/import 경로, 수정된 장치 조회 API, 장면 답과 parameter 일치, criteria 값 `.002/.002/.005`, 네 지형 배정 계획, hook·asset 참조. 자산 URL 문자열 hash와 실제 USD/참조 자산 내용 hash를 구분한다.
2. **장치·예약:** UUID/index/bus와 자식 UUID·Kit 관찰 결과, 현재 메모리, 다른 Isaac/예약 실행. `competing_isaac_processes()`는 `kit.exe`/`isaac-sim` 이름만 보므로 **Python으로 돌아가는 Isaac을 놓칠 수 있다**. 공통 예약·참여자 현황과 함께 보며 `reservation_confirmed=True`를 실측 증거로 쓰지 않는다.
3. **경로·공용 잠금:** 새 out/USD/log/status/claim, STOP 없음, 중첩 없는 출력 예산, 같은 host lock·공통 GPU lease. prelaunch는 lock을 풀고 끝나므로 시작까지 다른 참여자가 들어올 수 있다. 감독기가 다시 lock을 얻는 것은 확인됐으나 lease 불참 실행기까지 배제하지는 못한다.
4. **승인·감시:** by·승인 ID·manifest digest·expires, 실제 참석자 또는 수정된 무인 계약·watchdog READY, 절대/monotonic 마감, STOP·오류 시 소유 가족 정리·로그/receipt. A2 supervisor는 60초 이내 같은 manifest의 GO를 요구하므로 그 시간 안에 실행하지 못하면 새 사전 측정이 필요하다.

지금 GPU·예약·여유 공간은 조회하지 않았다. 의뢰문의 “GPU 둘 다 빔”은 이번 검증의 실측이 아니다. 이 문서도 최종 승인 JSON을 대신하지 않는다.

## 5. 남은 순서와 견적

**먼저 고칠 최소 묶음:** 장치 조회 → step/초기 cfg 실패 자료 보존 → `ray_index` 규약·장면 parameter 사전 검사 → 실제 USD 출력 경로/변환 정책 확정. 수정 부분만 CPU 반례와 정상 대조를 확인하고 새 해시를 동결한다. 무인이면 W의 READY·승인 결박·마감·로그 실패 처리도 같은 묶음에 포함한다. 관문을 `True`로 바꾸거나 실패 검사를 빼서 시간을 줄이면 안 된다.

계획용 추정: 첫 수집 최소 수정·좁은 재확인 **20~45분**, 무인 기동 연결·장애 시험 추가 **30~60분**, 승인값 동결·prelaunch **5~10분**, 실제 수집 **최대 15분**. 측정 ETA가 아니고 담당자 병렬 작업·설치 API 문제에 따라 달라진다. 감독기·watchdog·원자료의 새 결함이 확인된 상태에서 “30분이면 무조건 기동”이라고 약속할 근거는 없다.

수집 후에는 **시작 실패 / N<256 부분 수집 / 256 수집 후 증거 부족 HOLD**를 나눈다. 소요·최소 VRAM·실제 장치·정리 결과를 함께 기록한다. HOLD claim을 지우거나 출력 이름만 바꿔 재시도하지 않는다.

다음 accessor 작업은 첫 수집과 병렬로 CPU에서 준비할 수 있다: 실제 Warp mesh vertices/faces/월드 변환, USD collision/숨은 plane/선택 mesh 대응, root-sensor·ray-start/direction·hit 결박, 관측과 sensor timestamp·reset 순서, fixed 자세의 실제 유지, Kit/driver/import 판. 두 번째 0 단계는 이 증거와 수정 checker로 **실제 PASS**를 얻는 별도 실행이다. 첫 HOLD를 학습 사슬 통과로 올리지 않는다. B 전체 구현·GPU 1의 다른 작업은 이번 검증 범위 밖이며, lead는 별도로 승인·준비된 일이 있을 때 공통 자원 충돌을 확인해 배정한다.

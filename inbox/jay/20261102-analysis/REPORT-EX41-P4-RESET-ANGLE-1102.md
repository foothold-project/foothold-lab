> 분류: 실험
> 작성: analyst · 2026-11-02
> 근거: planner 92cdb212 §4 · lead P4-2 의뢰 · 실제 reset 이벤트와 terrain_distribution 소비 경로
> 요지: 계단 리셋 상대 방향 히스토그램을 초기화와 50회·경계 기록에 연결
> 상태: CPU 검증 · GPU 표본 분포 및 통합 Kit 미확인

# EX-41 P4-2 계단 리셋 방향 기록

`확인됨`: 리셋 이벤트 `w86_runtime.reset_runtime`가 세 지형 이름 `pyramid_stairs`, `pyramid_stairs_inv`, `stage_stairs`를 실제 생성기 열 배치로 찾아 센다. env 번호로 계단을 추정하지 않는다. 지도 모드·보상·명령·reset yaw는 바꾸지 않았다. [명세 92cdb212](https://github.com/foothold-project/foothold-lab/blob/92cdb212/inbox/jay/20261101-ex41/P4-STAIR-START-AND-SIDE-SHARE.md) §4와 로컬 사본 `D:/mai-tmp/planner/P4-STAIR-START-AND-SIDE-SHARE-92cdb212.md`를 대조했다.

## 기록 계약

| 자리 | 내용 |
|---|---|
| `ex41_stair_start.jsonl` | W86 attach 시 초기 물리 리셋 누적 스냅샷. `initialization_index=0`, `iteration=null`. 복원될 학습 회차를 아직 모르므로 재개를 학습 n0으로 오인하지 않음 |
| `stage_log.jsonl`의 `terrain_distribution.stair_start_angle_hist` | 첫50회 이후 50회 간격과 실제 경계. `iteration`은 기존 runtime 실제 local 회차 |
| 네 구간 | yaw modulo90°, [0,15), [15,45), [45,75), [75,90). 균등 yaw의 기대 비율은 1/6, 1/3, 1/3, 1/6 |
| 원 yaw 12구간 | −180°~180° 30° 간격. 네 방향을 접었을 때 가려질 수 있는 편향 확인용 |
| 분모 | `sample_count`=유효 계단 리셋 표본 수, `resets_seen`=전체 리셋 수. terrain별 counts·yaw_counts·invalid_yaw |
| 범위 | `physical_reset_events_since_process_start`. 프로세스 재개 시 새 누적, 앞 프로세스와 합칠 때 별도 구분 |
| 결측 | 표본0이면 no_stair_reset_samples. 잘못된 quaternion 제외 및 invalid_yaw 수, 종류 식별 불가 unclassified, 진단 메타 부재 error 기록 |

이 값은 축에 나란한 계단 면 대비 yaw를 접은 것이다. 로봇 위치에서 가장 가까운 면을 기하학적으로 골라 그 법선과 잰 값은 아니다. `stage_stairs`도 같은 축 방향 요약으로만 읽는다. 균등 분포라는 성능 결론이나 문턱은 두지 않는다. 실제 분포는 아직 미측이다.

초기 env reset이 adapter 생성 전에도 발생할 수 있어 reset 이벤트가 env에 카운터를 먼저 만든다. quarantine 캐시 초기화인 `adapter.on_reset`은 다시 세지 않는다. 초기 영수증에 표본이 없으면 없다고 남기고 첫50회·다음 경계 표본을 읽는다.

## CPU 시험과 한계

`test_ex41_stair_start_cpu.py`의 답 아는 yaw, 지형 이름 변경, 잘못된 quaternion, 계단 없는 입력, n0 attach, 캐시 리셋 중복 방지, 실제 `flush_consumption(50/251)` 파일 되읽기를 확인한다. 관련 W86 · runtime · U12 · P8 합계 **50 PASS(74.76s)**, `D:/mai-tmp/analyst/p4-final2-2046.log`. 마지막 초기 표식의 회차 표기 변경 뒤 **7 PASS(6.72s)**, `D:/mai-tmp/analyst/p4-last-2050.log`.

처음 시험에서 정확한 15°가 도 단위 역변환 반올림으로 앞 구간에 들어가는 반례를 잡았다(1 FAIL/42 PASS). 라디안 비교로 수정. 이후 U12의 진단 미초기화 입력에는 device가 없어서 1 FAIL/48 PASS였고, 빈 스냅샷은 CPU에서 만들도록 수정했다. 이 두 실패를 지우지 않았다. 각각 `p4-2043.log`, `p4-final-2044.log`.

reset 기록 호출 제거 · 지형 분류 상수화 변이 둘을 시험이 검출(rc1): `D:/mai-tmp/analyst/w91-p4-mutants-2045/results.json`. 원 파일을 변경하지 않고 독립 CPU 프로세스의 모듈만 변이했다(M14).

Kit 실제 reset 이벤트 순서, 초기 quaternion 갱신 시각, 3,072 env의 기록 비용은 미확인이다. runner 통합 예행에서 `reset_base` 뒤 `ex41_record_reset` 호출과 실제 출력 분모를 확인해야 한다(R20). GPU·학습·실행 사본·원장은 건드리지 않았다(M02).

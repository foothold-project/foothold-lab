> 분류: 실험
> 작성: analyst · 2026-11-02
> 근거: 팀장 D151 · 11fdb8e4 · e6144734 U18 · turn_probe 원자료
> 요지: 단계 끝 16 env 세 모드 30칸의 기록 전용 영수증과 CPU 검산 계약
> 상태: CPU 15 PASS · 제거 변이 2개 검출 · GPU 사슬은 runner 담당, 통합 Kit 미확인

# EX-41 W91 영수증 계약

`코드확인`: `foothold_s2.eval.ex41_turn_receipt`는 CPU 수집기다. 평가 호출은 runner가 소유한다. [D151 원문](https://github.com/foothold-project/foothold-lab/blob/11fdb8e4/inbox/jay/20261028-plan/WORKLIST.md), [기존 진단 범위](https://github.com/foothold-project/foothold-lab/blob/e6144734/inbox/jay/20261101-ex41/U18-TURN-SIX-CASES-VS-W57.md).

## 호출과 원자료

각 `turn_probe` 호출은 `--envs 16 --cases all --forward-gaits --fixed-terrain` 및 `--map-mode` 세 값 `eval_gt`, `probe_prop_only`, `eval_pred`. 기본 다섯 경우는 부족하다. `--fixed-level`은 주지 않는다. task 및 체크포인트 관측 차원 호환성은 통합 Kit에서 확인할 것.

폴더는 `<root>/turn16_<mode>/`. runner는 자식 종료 코드 정수 하나를 `rc.txt`에 UTF-8로 쓰고 stdout/stderr는 `run.log`에 보존한다. 기존 `probe_result.json`과 `arrays_<case>.npz` 10개를 함께 둔다. 실행 전 빈 시도 폴더를 쓰고 재시도는 별도 폴더다.

```powershell
python -m foothold_s2.eval.ex41_turn_receipt --root <root> --checkpoint <actual_model.pt> --iteration <local_N> --stage <stage_end_label> --out <new_receipt.json>
```

`collect(root, checkpoint=..., iteration=..., stage=...)`도 같은 JSON을 반환한다. rc0은 자료 완비, rc2는 자료 미완료다. 잘못된 호출이나 다른 내용의 기존 영수증은 예외로 거절한다. 성능 통과나 학습 정지 판단이 아니다. 점수기 유지 26칸을 바꾸지 않는다.

## 단계와 저장본

7개 표식은 `S2-0`, `S2a`, `S2b`, `S2c`, `S2d`, `S2e`, `T0_prime`. 기본 local 회차는 0/750/1750/2750/4000/4500/5000이나, DR 유지와 +500 연장으로 실제 단계 끝이 이동한다. runner가 **실제 단계 끝 영수증**에서 회차를 선택한다. 6000은 부모 회차이고 EX-41 local 회차에 더하지 않는다. n0 정책의 저장 파일과 내부 iter가 0인지 runner가 확인한다. 없는 n0 파일을 가짜로 만들어 통과시키지 않는다.

## 스키마와 숫자

`schema=foothold-ex41-turn-diagnostic/1`, `record_only=true`, `decision=null`, `status=COMPLETE|INCOMPLETE`, `checkpoint{path,sha256}`, `iteration`, `stage`, `modes`, `errors`, `reader_sources`.

| 칸 | 정의와 검사 |
|---|---|
| 세 모드 | 모드별 JSON의 map_mode · envs16 · checkpoint SHA · 내부 iter 대조 |
| 경우 | 회전 여섯 + walk_turn_left/right + fwd0.5/fwd1.0, 총 모드당10 |
| 고정 칸 | assignment SHA 전체 `7f49a1e935ea1dd741b0db47fe6da965eaa772c03f30c94f9fa976125db33506` 재계산, level0, 평지 계열8+rough8 |
| 배열 | 16×1600, 200Hz×8초, alive/kept bool, 관절·발 위치·접촉·속도 유한성, kept 메타 일치 |
| Q | 명령 부호×살아 있는 표본의 yaw 평균을 kept env마다 계산 후 같은 가중 평균. 단위 rad/s |
| follow_ratio | Q / abs(command_wz). Q와 다른 값 |
| C | 접촉력 >1N 네 발 동시 접촉 비율, kept env 같은 가중 평균 |
| kept=0 | Q/C null, statistics_available=false. 실측 낙상은 파일 누락과 다름 |
| 출처 | 각 JSON · NPZ · rc · log의 절대경로와 실제 SHA256 |
| 장치 | run_identity 원문 보존. cuda:1 표기만으로 물리 GPU1 확인을 주장하지 않음 |

주의: 평지 계열은 `hf_pyramid_slope` level0 중앙 평탄부다. 완전 평지 전용 타일이라고 부르지 않는다. 전진 전구간4초는 기존 생산자가 배열을 저장하지 않고, 뒤 회전8초만 기록한다. 명령 전환 지연을 12초 전구간 시계열로 분석했다고 주장하지 않는다.

## 검증 범위

답을 아는 fixture: Q .6 rad/s · 추종비 .5 · C .5 · 전진 .5×8=4m. 잘못된 rc/완료표식/경우 누락/지도모드/체크포인트/회차/칸/명령/kept/NaN/짧은 배열을 거절한다. 실제 EX-35 m2000 세 모드 배열도 읽어 기존 통계와 독립 식을 대조한다. 이는 EX-41 신규 GPU 실행 증거가 아니다.

`확인됨`: `test_ex41_turn_receipt_cpu.py` 15 PASS(32.36s). 로그 `D:/mai-tmp/analyst/w91-2039.log`. 명령 대조 제거와 Q 부호 제거 두 변이를 실제 시험이 검출(rc1)했다. `D:/mai-tmp/analyst/w91-p4-mutants-2045/results.json`.

원자료 재집계는 `C:/mai/wt/foothold-lab/impl-turncases/logs/ex35_eval/m2000/turn16_<mode>/` 30 NPZ를 읽었다. 결과 `D:/mai-tmp/analyst/W91-EX35-raw-replay-1102.json`, SHA256 `87e5bc4ee6488c545a330fa6e13f3a90462173e5b025c11deb6726745056bffc`. 독립 좌/우 대표 값은 다음과 같다. 성능 판정은 하지 않았다.

| 모드 | 좌 Q rad/s · C · kept | 우 Q rad/s · C · kept |
|---|---|---|
| 정답 | .540075 · .485500 · 15 | 1.109016 · .436625 · 15 |
| 가림 | .417659 · .552857 · 14 | 1.075105 · .416016 · 16 |
| 복원 | .558955 · .493846 · 13 | 1.053051 · .448594 · 16 |

옛 출력에는 `run_identity`가 없으므로 물리 GPU1 실행 증거로 쓰지 않는다. 최신 호출의 UUID 대조·기동 시간·관측 차원은 runner의 통합 점검 사항이다. `Q`를 단순히 「추종비」라고 적은 U18 원문은 단위가 다르므로 여기서는 `Q`와 `follow_ratio`를 분리했다.

# SOL-24e · 학습과 영상 촬영의 GPU 메모리 경로 비교

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: sol · 2026-10-24
> 근거: GPU 1 촬영 표본 두 개, `record_sol23f.py` · `seq_video.py` · 과거 `record_seq.py` · `seq_video.sh` 읽기
> 요지: 현재 촬영은 1환경·1타일·960×540인데도 GPU 1에 약 6.3 GiB를 더 썼다. 과거 동시 촬영의 메모리 조건은 미측정이다.
> 상태: 코드·원자료 읽기 확인 · GPU 실험 미실행 · 절감 효과 미확인

## 지금 판단에 쓸 수 있는 값

10/24 EX-23 `model_500.pt` 촬영 두 건의 [GPU 표본](C:/Users/AI-WS01/s2_lab/run_20261024/ex23_model500_capture_measure)은 약 1초 간격 65행씩이다. `flat`에서 GPU 1 사용량은 2507~8807 MiB, `rough`에서는 2521~8730 MiB였다. 시작 전 약 2.5 GiB 대비 최고 증가분은 각각 **6300 MiB**, **6209 MiB**다. 두 실행의 감독기 rc는 0이고 [flat](C:/Users/AI-WS01/s2_lab/run_20261024/ex23_model500_flat/review.json)과 [rough](C:/Users/AI-WS01/s2_lab/run_20261024/ex23_model500_rough/review.json)는 각각 300프레임, 25fps, reset 0, 저장된 `force_gt=true`에 맞춘 GT 지도 사용 600/600 정책 틱을 기록했다.

root가 전한 현재 잔여 VRAM은 TD 3072 학습 GPU 1 약 1473 MiB, B 3072 학습 GPU 0 약 3.6 GiB다. 촬영 증가분 6.2~6.3 GiB는 두 잔여량보다 크다. **현재 도구를 그대로 두 학습과 겹쳐 촬영할 수 있다는 근거는 없다.** `gpu.jsonl`은 장치 전체 사용량이며 Kit 렌더·PhysX·정책·센서별 할당량은 분해하지 않는다. 과거 동시 촬영 당시의 장치별 VRAM 시간열은 이번 지정 자료에서 확인하지 못했다. 과거 성공을 부정하지 않지만, 당시 학습 점유와 지금의 3072 두 판 점유가 같았다고 볼 근거도 없다.

## 과거와 현재의 실제 경로

| 항목 | 과거 `s2_lab/record_seq.py` | 현재 `record_sol23f.py` | 메모리 판단 |
|---|---|---|---|
| Kit · RTX | `AppLauncher`, `--headless`, `enable_cameras=True`, `render_mode=rgb_array`, 매 프레임 `raw.render()` (`record_seq.py:15-36,52-61,183-205`) | 같은 AppLauncher 경로와 카메라 활성화 (`record_sol23f.py:356-365,413,503-534`) | 두 쪽 모두 headless rendering Kit 경험을 고른다. renderer별 비용 차이 미확인 |
| 화면 · 시간 | 960×540, 25fps, 12초, 300프레임 (`record_seq.py:28-30,49-51,87-98`) | 기본 960×540, 25fps, 12초, 300프레임 (`record_sol23f.py:255-264,297-309,475-486`) | 기본 영상 크기는 원인 아님 |
| 환경 · 지형 | `S2Adapter("open")`의 G0 평가 env, 1환경, `random_rough` 한 행·한 열 (`record_seq.py:52-61`, `adapters.py:499-510`, `terrain_sets.py:138-143`) | native B task, 1환경, 같은 `random_rough` 한 행·한 열과 같은 flat/rough noise (`record_sol23f.py:377-416`) | 타일 수 증가는 확인되지 않음. env 클래스 차이의 VRAM 효과 미측정 |
| 정책 · 센서 | `S2Adapter.load_policy`, START 지각과 depth sensor, `force_gt` 체크포인트 보정 (`record_seq.py:65-78`) | 같은 adapter loader, saved GT 검증, 실제 지도·깊이·종료 증거를 각 틱 CPU 복사 (`record_sol23f.py:421-465,548-615`) | 지도 증거는 CPU 복사가 주이나 전체 Kit 메모리 영향 미측정 |
| 물리 · 행동 | G0 open 평가 cfg와 `DelayedJointPositionActionCfg`; adapter가 일부 DR·관측 잡음을 끔 (`adapters.py:273-282`, `s1_env_cfg.py:78`) | EX-23 계열 native B cfg의 지연 없는 `JointPositionActionCfg`; fixed 모드가 DR과 시작 흔들기를 끔 (`s2_x23_cfg.py:19-30`, `record_sol23f.py:68-105`) | 물리 계약이 같지 않다. 과거 영상으로 현재 공식 평가를 대신할 수 없음 |
| 영수증 | 옛 `s2_lab/seq_video.sh:10-16`은 4회가 실패해도 `done`을 쓸 수 있음 | `seq_video.py:45-115,167-230`은 자식 rc, MP4 해독·300프레임, JSON/NPZ, 같은 시도, SHA 뒤에만 영수증 발행 | CPU 검증 비용은 GPU 피크의 확인된 원인 아님 |

설치 `AppLauncher`는 headless와 camera가 켜지면 `isaaclab.python.headless.rendering.kit`를 선택한다 (`app_launcher.py:719-729`). 두 코드 모두 이를 요구한다. 현재 표본의 GPU 1 사용량은 Kit 시작 약 20초 뒤 6 GiB를 넘지만, 그 시점의 할당 주체를 식별하는 단계별 GPU 기록은 없으므로 **6.3 GiB 증가의 단일 원인을 코드 차이로 단정할 수 없다.**

## 옵션 구분과 권고

| 선택 | 공식 촬영 조건 | 현재 근거 |
|---|---|---|
| 한 번에 한 편 촬영, `--headless`, 1환경, 1타일, GPU 지정 | 현재 구현 그대로 | 이미 적용됨. GPU 0 선택은 현재 free 3.6 GiB, GPU 1 선택은 free 1.47 GiB라 6.2~6.3 GiB 실측 증가분을 수용하지 못함 |
| 영상 화면 축소 또는 AppLauncher `--rendering_mode performance` | 물리·정책 입력은 유지할 여지가 있지만 영상 픽셀 조건은 변경됨 | 절감량 미측정. 현재 `seq_video.py` 부모는 recorder에 width/height/rendering_mode 인자를 전달하지 않아 그대로는 검증 영수증 경로에 적용 불가. 별도 구현·재검증 전 공식 결과에 쓰지 않음 |
| 과거 `record_seq.py`로 대체 | **변경됨**. native B env, 행동 지연, 종료 근거와 강한 영수증 계약이 달라짐 | 메모리 절감량도 미확인. 보조 영상으로만 취급 가능 |
| 카메라·깊이 센서 끄기, 지형 단순화, episode/프레임 수 축소, `map_mode` 또는 물리 모드 변경 | **변경됨**. 정책 입력 또는 평가 지형·영상 계약이 달라짐 | 공식 비교의 저메모리 대안으로 권고하지 않음 |

현재 두 학습을 중단하거나 pause하는 결론은 이 검토에서 나오지 않는다. root는 각 학습과 촬영의 같은 시각 free VRAM을 다시 재고, 공식 한 편의 **실제 증가분을 수용할 공간이 확인될 때만** 현재 영수증 경로로 한 번에 한 편을 실행할 수 있다. 그렇지 않으면 학습을 유지하고 해당 촬영을 충분한 GPU 여유가 생긴 뒤로 예약하는 것이 과학적 조건을 지키는 선택이다. 저해상도나 렌더 preset의 메모리 절감 효과는 미측정이며 이 보고서는 새 GPU 시도를 승인하지 않는다.

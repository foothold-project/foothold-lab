# C층 남은 칸 재시도 2회와 최근 시도 시간
> 분류: A/평가
> 작성: 오흥재 · scripter · 2026-11-03
> 근거: C층 큐 원자료와 최근 완료 시도 10건
> 요지: 정책 실패 시드 상한을 2회로 낮추고, Kit 묶음 실행의 이득과 위험을 분리했다.
> 상태: 부분 확인 · GPU 실제 가동률 미측정

## 적용 경계

- 이전 큐 PID 87452는 `OPERATOR_STOP`을 현재 칸의 2번째 시도 종료 뒤 읽고 23:34:07에 `operator_stop`으로 끝났다. `gpu1_remainder.lock`은 없다. 학습, 고정 큐 소스, 실행 셸은 수정하지 않았다.
- 옛 계획은 `D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/plan.json`이다. 새 계획은 같은 216칸 각각 시드 `[42,43]`인 `D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/cap2/plan.json`이다. 새 manifest는 `cap2/remaining.json`이며 기존 27개 완료 영수증과 남은 81칸을 다시 묶는다. 산출 `out`은 이어 쓰므로 이전 영상, 실패 기록, 영수증은 남는다.
- 실제 고정 큐의 `validate_plan`은 216칸 통과. 기존 4회 정책 실패 칸 두 개는 `exhausted`, 현재 칸 `stepping_stones_low_L4_probe_prop_only`는 2회 실패로 `exhausted`, 성공 칸은 `complete`. 기술 실패는 정책 시드 예산에서 제외하도록 wrapper의 카운트를 수정했다. CPU 반례 6개 통과. 전체 파일 시험의 기존 1개는 과거 `SLOWDOWN_HOLD.json`이 현 경로에 없어 실패했으며 이번 변경과 무관하다.
- 새 계획 SHA256 `481d3997aa38ccf648fe9adc4c5ebe01d0d92b439f51a2aa9fc1c7a6b0cb1b1e`, manifest SHA256 `25dc9f7ee32712d039d6d198c6e8df864ac8052ae3f77cdfb35d4b8ce65ff411`.

## 최근 완료 10시도

원자료 `D:/mai-tmp/c_layer_m6000_gpu1_remainder_v34/out/attempts/*/*/{started.json,child.log,compose.log,styled.json,closed.json}`. 산출 CSV `D:/mai-tmp/scripter/c_layer_latest10_timing.csv`. 각 시도의 450 프레임 완료 로그를 요구했다. 시각은 파일 생성 및 최종 기록 시각, 촬영은 `C76_PROGRESS`의 450 프레임 경과값이다.

| 구간 | 평균 초/시도 | 정의 |
|---|---:|---|
| 전체 | 249.402 | started 생성부터 closed 기록 |
| Kit 자식 전체 | 150.246 | child.log 생성부터 마지막 기록 |
| 촬영 루프 | 119.478 | C76_PROGRESS frame 450 elapsed_s |
| Kit 촬영 외 | 30.768 | Kit 자식 전체에서 촬영 루프를 뺀 값, 시작과 종료가 섞임 |
| 합성 | 58.404 | compose.log 생성부터 styled.json 기록 |
| 감사 등 | 40.752 | 전체에서 Kit 자식과 합성을 뺀 값 |

촬영 루프/전체 벽시계 비율 평균은 **47.9%**, Kit 자식/전체는 **60.3%**다. 이 값은 GPU 실제 가동률이 아니다. 이 10시도와 동기화된 GPU utilization 시계열이 없어 GPU 실제 사용 비율은 **미측정**이다. 다음 시도에서는 `nvidia-smi`의 장치별 utilization과 프로세스 메모리를 초 단위로 기록하고 Kit 자식 PID 및 시각과 대조해야 실제 비율을 말할 수 있다.

## Kit 한 번에 여러 칸 또는 시드

현재 `c_layer_queue.py:400-427`이 칸마다 기록기 자식을 새로 띄우고, `:455-478`이 합성 및 감사 후 다음 칸으로 간다. `record_c_layer.py`의 AppLauncher, 지형 생성과 센서, 정책 로드를 반복한다. 가장 작은 후보는 **같은 칸의 두 시드를 한 Kit 실행에서 순서대로** 기록하는 것이다. Kit 앱과 정책은 한 번만 띄우고 시드마다 reset, 명령, 센서, 카메라, 비디오 및 영수증을 새로 분리한다. 칸별 지형 종류·레벨·지도 모드까지 한 앱에서 바꾸는 안은 terrain과 sensor 재구성 계약을 검증해야 하므로 뒤로 둔다.

변경 범위는 별도 batch recorder 진입점, 큐의 시드 묶음 실행, 시드별 산출 격리와 검증 영수증, P1 관문과 최근 10회 평균 관문을 **시드 사이**에 다시 확인하는 부분이다. 답 아는 CPU 시험은 두 시드의 reset 독립성, 각 시드의 450프레임과 검정 검사, 실패 시 다른 시드 산출 불변, 두 영수증의 seed·SHA 일치, P1 도착 때 다음 시드 보류를 포함한다. Kit 시험은 같은 칸 두 시드 한 묶음에서 기존 단독 두 번과 지형 해시·명령·초기 관측을 대조한다. 위험은 Isaac reset 후 카메라·접촉 센서 내부 시각과 지형 난수 상태가 새 프로세스와 다를 수 있고, 장시간 Kit 프로세스의 메모리 누적이나 GPU0 학습 지연을 키울 수 있다는 점이다. **이 묶음 방식은 제안만 했고 구현하거나 실행하지 않았다.**

## 검증과 해시

CPU: `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/tests/test_c_layer_gpu1_remainder.py -q -p no:cacheprovider -k 'two_policy or technical_failure or four_policy or own_queue or p1_marker' --basetemp D:/mai-tmp/scripter/pytest_seed2_narrow` → 6 passed. 실제 고정 큐 `validate_plan` → 216 ready, 0 missing. 상태 재계산 → 정책 실패 4, 4, 2회 칸 exhausted, 성공 1회 칸 complete. 계획 및 manifest 전체 SHA와 새 코드 HEAD는 커밋 영수증에 남긴다.

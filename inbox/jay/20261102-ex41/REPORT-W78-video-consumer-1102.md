# EX-41 W78 단계 끝 영상 소비기 준비

> 분류: A/평가
> 작성: 오흥재 · 2026-11-02
> 근거: runner의 `ex41_w78_video_request.py` 계약 · W78 v2 계단 평가 코드 · CPU 시험
> 요지: 12개 요청 조합을 한 편씩 촬영하고 원자료와 v3.2 영수증을 검증하는 소비기를 준비했다.
> 상태: CPU 검증 완료 · Kit 촬영 미확인

## 구현과 연결

- 요청은 `foothold-ex41-w78-video-request/1`의 canonical ID, 파일명, manifest와 체크포인트 SHA가 같아야 한다.
- 한 번 실행할 때 12개 조합 가운데 한 편만 처리한다. GPU 작업판의 P4 관문을 촬영 전과 각 편 전에 읽고, P1 점유가 있으면 다음 편을 보류한다.
- 영상은 fixed64 계단 L5, 시작 목표 차 0/30/60/90°, 지도 셋, `stairs_fwd` 0.5 m/s 6초다. 실제 EX-41 소스 패키지를 우선 import하고 pose command 98차원 체크포인트를 요구한다.
- 원본 300 physics step과 150 frame, 다른 로봇 0 픽셀, map mode, v3.2 합성 영수증과 전 프레임 검사를 통과해야 최종 영상 영수증을 쓴다.

## CPU 증거

- `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m pytest foothold_s2/eval/tests/test_w78_video_consumer_cpu.py -q -p no:cacheprovider --basetemp D:/mai-tmp/scripter/pytest_w78_final`: **8 passed in 1.31s**.
- `python -m pyflakes`와 `ruff check --select F`: 각각 지적 0건. `git diff --check`: 0건.
- 깨끗한 임시 Git 소스의 실제 녹화기 `--plan-only`는 150 frame, 요청 ID, 체크포인트 SHA를 되읽어 통과했다. EX-41 소스 모듈 우선 import도 별도 프로세스로 확인했다.
- 현재 `C:/mai/wt/foothold-lab/runner-ex41-b6-b7`에는 다른 세션의 미커밋 변경이 있어 고정 소스 관문이 거절한다. 깨끗한 고정본 경로를 준비한 뒤 다시 사전 점검해야 한다. 실제 Kit 1편과 지도 소비는 아직 미확인이다.

## lead 실행 전 점검 명령

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -m foothold_s2.eval.w78_video_consumer --request '<run>/w78_video_requests/request_mXXXXX_<id>.json' --source-root '<clean-fixed-ex41-worktree>' --recorder 'D:/mai-wt/foothold-lab/scripter-w78-video/foothold_s2/eval/video25/record_c_layer.py' --composer 'D:/mai-wt/foothold-lab/scripter-w78-video/foothold_s2/eval/video25/compose_25e_v2style10.py' --python 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' --gpu-jobs-config 'D:/mai-wt/foothold-lab/scripter-w78-video/_out/tools/gpu_jobs/jobs.json' --out 'D:/mai-tmp/ex41/w78_video' --device cuda:1 --plan-only
```

실촬영 때는 코드 사본과 EX-41 소스 고정본의 SHA를 다시 재고 `--plan-only`만 뺀다. 이 보고서는 실제 촬영 승인이나 판정 근거가 아니다.

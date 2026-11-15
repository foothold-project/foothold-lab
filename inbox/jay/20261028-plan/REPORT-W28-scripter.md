> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 (scripter 반영) · 2026-10-28
> 근거: WORKLIST W28 · `_out/tools/gpu_jobs/gpu_jobs.py` · runner `render_queue_26d.py`
> 요지: 한 등록부에서 GPU 단위 작업을 우선순위대로 꺼내는 CPU 구현과 영상 완료 점검
> 상태: CPU 10시험 통과 · GPU/Kit 미실행 · 기존 소비자 전환 대기

# W28 구현 보고

기존 관리판은 `status`와 `gate`만 제공하고 작업을 꺼내 실행하지 않았다. runner의 렌더 대기열은 촬영·합성만 별도로 직렬 처리했다. 새 `queue_w28.py`는 공통 JSON 등록부, OS 잠금, 원자 상태 저장, GPU별 소비기, CPU 합성 소비기, 작업당 여러 단위, 단위 경계 우선순위 재판단, 실행 claim 및 실패 기록을 구현했다. 기존 우선순위 표식과 사슬 로그는 GPU1 낮은 우선순위 작업 진입 전에 확인한다.

`video_finish_w28.py`는 영상 영수증 제목·판정 존재·해시·전체 프레임 해독과 검은 화면을 CPU에서 확인하고 5표본 그림을 쓴다. 장면 의미와 자막의 실제 픽셀은 미확인이다. 결함 항목을 사람에게 넘기는 근거 파일은 `screen_check.json`이다.

시험: `CUDA_VISIBLE_DEVICES=''`에서 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m unittest _out/tools/gpu_jobs/test_queue_w28.py _out/tools/gpu_jobs/test_video_finish_w28.py -v` 결과 정상 10, 실패 0. 답을 아는 반례에는 낮은 작업 도중 높은 작업 등록, P1 준비 파일 부재/생성, GPU 점유, 잘못된 표식, 작업 실패, 중복 claim, 중복 등록, 승인 출처 누락, 제목/판정/프레임/검은 화면 오류가 포함된다. 실제 CPU MP4 하나를 쓰고 다시 열어 화면 표본과 SHA도 확인했다. GPU와 Kit는 실행하지 않았다.

실제 배포 전 남은 일: lead가 기존 평가 사슬 및 runner 소비기와 중복이 없는 전환 시점을 정하고, 각 등록 명세의 승인 출처와 검증 명령을 확인해야 한다. 코드가 `authorization_ref` 문자열의 진위를 검사하지 않으므로 등록만으로 학습 승인으로 간주하면 안 된다. 기존 실행 중인 작업은 이 대기열에 이관하지 않았다.

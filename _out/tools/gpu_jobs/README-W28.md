> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 (scripter 반영) · 2026-10-28
> 근거: WORKLIST W28 · 기존 gpu_jobs.py · render_queue_26d.py e202543a
> 요지: GPU0 · GPU1 · CPU 합성을 단일 등록부에서 우선순위별 한 건씩 소비한다
> 상태: CPU 검증판 · 실 GPU 소비 미기동 · 기존 실행자 전환은 lead 확인 전

# W28 GPU 작업 단일 대기열

`queue_w28.py`는 하나의 JSON 등록부를 공유하는 GPU0, GPU1, CPU 합성 소비기를 제공한다. 각 소비기는 작업 전체가 아니라 `units`의 한 건만 실행하고 다음 건을 고르기 전에 우선순위를 다시 읽는다. 실행 중인 한 건을 죽이거나 가로채지 않는다. 같은 GPU에 실행 claim이 남으면 재실행하지 않고 검토 대기로 둔다.

우선순위는 P0 승인 학습, P1 판정 평가, P2 진단, P3 반복 시드, P4 촬영·렌더다. P1 작업이 아직 저장본을 기다리면 `ready_file` 부재로 P4가 그 틈을 쓸 수 있다. GPU1의 기존 `PRIORITY_BUSY`와 `chain2.log`도 `--sources`에 넘기면 낮은 작업의 다음 건 진입에 반영한다. GPU 점검은 건마다 `nvidia-smi`로 하며 실패하면 진입하지 않는다.

등록 명세는 JSON 객체로 `id`, `kind`, `priority`, `gpu`, `owner`, `authorization_ref`, `output`, `cwd`, `argv`, `units`가 필수다. GPU 작업에는 `gpu_uuid`도 필수다. `kind`는 `training`, `judge`, `diagnostic`, `repeat`, `capture`, `compose`이며 `compose`만 `gpu:null`이다. `units`는 `[{"id":"case-001", "args":[...], "verify_argv":[...]}]` 형식이다. `capture`와 `compose`에는 검증 명령이 필수다. 승인 출처 문자열은 추적 필드이며 승인 자체를 발급하거나 검증하지 않는다. 실제 명령을 등록하기 전에 기존 승인과 소비 조건을 lead가 확인해야 한다.

GPU 장치 계약: `gpu=1`이면 자식 argv에는 `--device cuda:1`이 정확히 하나 있어야 한다. GPU0도 같은 방식이다. 실행 직전 `nvidia-smi`의 그 물리 번호 UUID를 등록 `gpu_uuid`와 대조하고, 상속된 `CUDA_VISIBLE_DEVICES`를 제거하며 `CUDA_DEVICE_ORDER=PCI_BUS_ID`를 자식에 넘긴다. `--gpu-id`, `--gpu-index`, 렌더러 장치 별도 플래그가 충돌하거나 검증되지 않으면 등록을 거절한다. CPU 합성 자식에는 빈 `CUDA_VISIBLE_DEVICES`를 넘긴다. 설치 Isaac Lab `app_launcher.py`는 `--device cuda:N`의 N을 `device_id`, `active_gpu`, `physics_gpu`에 넣는다. 실제 Kit 장치 UUID 소비는 이 CPU 시험의 범위 밖이다.

```powershell
$py = 'C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe'
$tool = 'C:/mai/wt/foothold-lab/scripter-w28/_out/tools/gpu_jobs/queue_w28.py'
$queue = 'C:/Users/AI-WS01/s2_lab/gpu_jobs/queue.json'
& $py $tool --queue $queue register C:/Users/AI-WS01/s2_lab/gpu_jobs/approved-job.json
& $py $tool --queue $queue status
# lead가 기존 소비자 중복이 없음을 확인한 뒤 각 GPU에 한 번만 시작한다.
& $py $tool --queue $queue serve --gpu 1 --sources C:/Users/AI-WS01/s2_lab/gpu_jobs/sources.json
```

`sources.json`의 두 선택 키는 `priority_busy`, `chain_log`다. 기존 평가 사슬이 끝난 뒤에는 오래된 chain log를 근거로 쓰지 않도록 source 목록을 갱신해야 한다. 새 `render_queue_26d.py` 호환판은 매 영상 건 직전에 같은 queue의 `legacy_claims`를 원자적으로 등록하고 종료 뒤 해제한다. 새 queue의 claim이 있으면 영상 건을 시작하지 않고 기다리며, 반대 순서도 막는다. **두 실행자에 똑같은 queue 절대경로를 주어야 한다.** 현재 메모리에 적재된 옛 renderer는 이 코드를 읽지 않으므로 자연 종료와 재기동을 확인하기 전에는 새 소비기의 `serve`를 시작하지 않는다. 실행 중인 프로세스를 강제 종료하거나 같은 항목을 중복 등록하지 않는다.

```powershell
# renderer 호환판은 별도 커밋에 있다. 기존 runner 기동 명령에 아래 두 인자를 더한다.
--w28-queue C:/Users/AI-WS01/s2_lab/gpu_jobs/queue.json --w28-module C:/mai/wt/foothold-lab/scripter-w28/_out/tools/gpu_jobs/queue_w28.py
```

영상 후처리 `video_finish_w28.py`는 compose 영수증의 `label`, `frames`, `expected`, `output`, `sha256`와 판정 JSON의 `decision` 또는 `verdict`를 검사한다. MP4 모든 프레임을 해독해 검은 프레임을 찾고 다섯 표본 화면을 만든다. `screen_check.json`의 flag가 있으면 해당 편만 사람이 판독한다. 화면의 의미나 자막의 실제 픽셀을 완전 검증했다는 뜻은 아니다.

```powershell
& $py _out/tools/gpu_jobs/video_finish_w28.py --video <완료.mp4> --receipt <완료.json> --verdict-json <판정.json> --title <기대 제목> --out <점검 폴더>
& $py -m unittest _out/tools/gpu_jobs/test_queue_w28.py _out/tools/gpu_jobs/test_video_finish_w28.py -v
```

실제 GPU 기동, 평가 사슬, 영상 촬영은 이 작업에서 하지 않았다. P1의 기존 평가 실행자도 아직 이 공통 queue에 claim을 쓰지 않으므로 그 운영 전환과 GPU 실측 확인 전에는 `serve`를 시작하지 않는다.

# EX-41 단계 끝 W57·W80 영상 소비 경로
> 분류: 실험 기록
> 작성: 오흥재 · scripter 반영 · 2026-11-04
> 근거: EX-40 stage_loop2.sh · map_mode_cells.py · terrain_skill_run.py · EX-41 m750 manifest · D102
> 요지: 단계 끝 저장본을 W57 39편과 W80 12편의 독립 촬영 명령으로 연결한다.
> 상태: CPU 경로 확인 · GPU 촬영 및 장면 판독 대기

## 범위와 재사용

- `foothold_s2/eval/ex41_stage_video.py`가 13개 W57 명령과 네 방향 W80 명령을 지도 세 모드로 전개한다. 한 호출은 한 편만 찍는다. 총 51개 조합이다.
- W57은 고정64칸의 `pyramid_stairs_inv` L1 env5, W80은 같은 지형 L2 env5다. 6초, 25 fps, 300 물리 step, 150 frame이다. 이는 영상 진단 칸이며 W57/W80 평가의 모든 지형·각도를 대표하지 않는다.
- `record_c_layer.py`의 EX-41 환경·저장본 로더, 정답/복원/끔 지도 선택, 다른 로봇 숨김과 instance segmentation, v3.4 합성 및 전 프레임 검사를 재사용한다. 기록기의 `stage_video`에 suite·명령·단계·EX-41 로더 증거를 남긴다.
- 저장본은 실행 manifest SHA와 대조한다. 기술 실패는 성공 영수증을 만들지 않는다. 영상 안의 reset 유무가 D48 파일 이름 success/fail을 정한다. D102 재생 목록에는 SHA·판 일치 영수증의 절대 경로만 넣는다. W78과 밀기 영상은 `--w78-out`, `--push-out`으로 별도 영수증 폴더를 지정해 합칠 수 있다.
- runner는 `stage_cases()`의 51 조합을 단계 끝마다 `priority=3`, `kind=render`, GPU1으로 등록한다. 이 코드에는 자동 등록이 없으며 학습 사본을 수정하지 않았다.

## 실제 CPU 확인

`코드확인`: `isaac311`에서 신규 8개와 W78·밀기 기존 19개를 합쳐 `27 passed in 11.58s`. 실제 EX-41 `model_750.pt`의 manifest SHA `575655db49e475e171c0a85a859ae4d261cac83814aee2a18be76d6711558e46`과 source HEAD를 대조한 소비기 `--plan-only`는 `planned`, W57 fwd0.5 명령 `[0.5,0,0]`을 냈다. 실제 기록기 `--plan-only`도 `rc 0`, 150 frames였다. Kit 촬영은 이 경로로 아직 실행하지 않았다.

첫 한 편 실행 명령의 작업 위치는 `D:/mai-wt/foothold-lab/scripter-ex41-stagevideo`다. GPU1 P1 점유가 없을 때만 관리판이 허용한다.

```powershell
$env:TEMP='D:/mai-tmp/scripter'; $env:TMP='D:/mai-tmp/scripter'; C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe -m foothold_s2.eval.ex41_stage_video --checkpoint C:/Users/AI-WS01/s2_lab/ex41_main_20261103_195435/main/EX-41-B-main_20261103_195435/model_750.pt --iteration 750 --stage-name S2a --suite W57 --case fwd0.5 --mode eval_gt --source-root D:/mai-wt/foothold-lab/scripter-ex41-stagevideo --recorder D:/mai-wt/foothold-lab/scripter-ex41-stagevideo/foothold_s2/eval/video25/record_c_layer.py --composer D:/mai-wt/foothold-lab/scripter-ex41-stagevideo/foothold_s2/eval/video25/compose_25e_v2style10.py --python C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe --gpu-jobs-config D:/mai-wt/foothold-lab/scripter-ex41-stagevideo/_out/tools/gpu_jobs/jobs.json --out D:/mai-tmp/scripter/ex41_stage_m750 --playlist-root C:/Users/AI-WS01/s2_lab/_playlists --device cuda:1
```

위 명령은 준비된 실행형이다. 직접 GPU를 띄우지 않았다. stage 이름은 m750 W78 요청의 `S2a`를 읽었다. 다른 회차는 해당 저장본 manifest와 단계 이름을 다시 대조해야 한다.

## 남은 관문

- P1 평가가 끝난 뒤 첫 한 편의 Kit·영수증·전 프레임 검사를 확인하고 lead가 장면을 판독한다.
- 기존 A 밀기/W78 큐 179·180의 소스 HEAD `1625006c`는 별도 고정이며 결과가 나올 때까지 수정하지 않는다. 두 편은 현재 P1 관문으로 대기 중이다.
- 51편 자동 등록은 runner 담당이다. 전체 촬영은 lead의 우선순위 운영에 따른다.


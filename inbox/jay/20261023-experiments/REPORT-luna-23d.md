> 분류: 실험 분석
> 작성: 오흥재 (luna 문서 반영) · 2026-10-23
> 근거: sol-23a runners/manifest.py · runners/status.py · eval/seq_video.py · EX-23 manifest
> 요지: 실제 foothold runner 게시물 형식으로 점검 요청을 만들고 완료 캡처 영수증을 재검증
> 상태: CPU 반례 시험 9 PASS · 실제 새 B/START run 없음 · GPU/Kit/학습/촬영 미실행

# LUNA-23d 중간 점검 감시기 수정

## 실제 runner 계약

`sol-23a/foothold_s2/runners/manifest.py`의 `update_progress`는 `manifest.json`에 `progress.completed_updates`와 `progress.total_env_steps`, 체크포인트별 `checkpoints`의 파일명 대 SHA256을 쓴다. 실제 EX-23 `foothold-manifest/1` manifest도 이 구조다. `runners/status.py`는 같은 run 폴더의 `train_start_status.json`에 `state`, `iter`, `time`을 원자 교체로 쓴다. 기존의 `status.json`, `manifest.model`, 가상 deadline 필드, 가상 checkpoint receipt 폴더 가정은 제거했다.

감시기는 manifest의 완료 회차와 체크포인트 SHA, 상태 파일의 최신 회차/상태/시각을 읽는다. 체크포인트 파일의 실측 SHA가 manifest 값과 같고 manifest 완료 update가 회차 이상일 때만 요청 후보가 된다. deadline은 실행자가 `--deadline`에 절대 ISO8601 시간대 포함 값으로 준다. run 파일에는 임의 필드를 요구하지 않는다.

체크포인트는 회차 숫자로 정렬한다. 500·1000·1500 고정점은 보존한다. 그 뒤 1000 update 간격 점검은 놓친 경계가 여러 개면 오름차순으로 처리한다. 3시간 점검 신호는 오래된 첫 후보에서 소비하지 않고, 현재 manifest에 기록되어 실제 SHA가 맞는 가장 최근 완료 체크포인트 하나를 고른다. 마감 뒤에는 새 요청을 만들지 않으며 pending·claimed·failed 요청을 `unresolved`에 남긴다.

## 상태와 완료 관문

요청, 상태, 진행 기준점은 `--state`로 지정한 **단일 원자 JSON 파일**에만 둔다. 별도 요청 파일을 중복 작성하지 않아 pending 요청 파일과 claimed 상태 파일이 갈라지지 않는다. scan 게시와 transition은 같은 `.lock` 파일의 OS byte-range/file lock 및 프로세스 안 thread lock을 획득한 뒤 읽기-수정-원자교체를 수행한다. 기본 scan은 dry-run이며 `--publish`를 줘야 이 단일 파일을 기록한다. 상태 전이는 pending → claimed → completed 또는 failed, failed → pending 재시도다.

`seq_video.py@85fe9d1d`의 성공 영수증은 `checkpoint_sha256`을 기록하며 `--verify-receipt`는 실제 체크포인트 파일 SHA와 영수증 값을 대조한다. `completed` 전이는 `--receipt`와 `--seq-video`가 필수다. 감시기는 CPU subprocess로 지정된 `seq_video.py --verify-receipt <영수증>`을 실행하고 종료 코드 0을 요구한다. 이어 영수증의 checkpoint SHA가 요청 checkpoint SHA와 같은지 확인하고, MP4·JSON·feet NPZ 3개 파일 SHA와 영수증/검증기 SHA, 검증기 출력을 완료 증거로 canonical state에 기록한다. 따라서 수동 완료만으로는 완료가 되지 않는다. 합성 파일 fixture로 실제 verifier CLI 호출도 확인했으며, 실제 캡처 산출물 검증은 미확인이다.

사용 예:

```powershell
python monitor_23d.py scan --run "C:/runs/B" --run "C:/runs/START-TD" --state "C:/runs/review-state.json" --deadline "2026-10-24T20:00:00+09:00"
python monitor_23d.py scan --run "C:/runs/B" --run "C:/runs/START-TD" --state "C:/runs/review-state.json" --deadline "2026-10-24T20:00:00+09:00" --publish
python monitor_23d.py transition --state "C:/runs/review-state.json" --id "<요청 ID>" --to completed --receipt "C:/runs/clip.done" --seq-video "C:/mai/wt/foothold-lab/sol-23a/foothold_s2/eval/seq_video.py"
```

## 검증과 한계

`python test_monitor_23d.py -v`: 9 PASS. 실제 `foothold-manifest/1` fixture와 `train_start_status.json` fixture, 동시 500/1000/1500/2500/3500의 숫자 순서, manifest SHA 불일치 제외, 상태 파일 부재 오류 노출, dry-run 무기록, 중복/재시작 상태 보존, 마감 뒤 failed 미완료 노출, 1550과 2000 동시 존재 시 3시간 점검이 2000을 고르는 반례, 완료 영수증 누락/검증 실패/체크포인트 SHA 불일치 거절을 확인했다. 별도 다중 프로세스 충돌 시험은 16개 transition 게시와 scan 게시를 동시에 걸고 모든 상태 변경 및 신규 요청이 단일 상태 파일에 남는지 확인했다. 추가로 임시 가짜 MP4/JSON/NPZ 파일과 완료 영수증을 `seq_video.py@85fe9d1d --verify-receipt`에 연결해 종료 코드 0, 파일 SHA 3개와 체크포인트 SHA 일치 뒤에만 completed가 기록되는 것을 CPU에서 확인했다. 합성 파일 fixture이므로 캡처나 영상 재생의 유효성은 확인한 것이 아니다.

`completed`는 유효한 촬영 영수증을 소비 검증했다는 뜻만 가진다. 위상, 그래프, 관절 해석, 영상 내용에 대한 사람의 판정 또는 실험 결과 분석 완료를 뜻하지 않는다.

실제 EX-23 manifest는 읽어 구조를 확인했으나 새 B/START run 폴더는 아직 없고, 이 도구를 실제 생산자 폴더에 연결하지 않았다. 두 학습의 동시 진행 및 촬영 안전성은 미확인이다. 본문은 측정 근거 또는 운용 허가가 아니다. 기존 4개 미커밋 영상을 건드리지 않았고 공유 `s2_lab`, 학습 코드, 학습/촬영 process, GPU, Kit, 외부 채널도 건드리지 않았다.

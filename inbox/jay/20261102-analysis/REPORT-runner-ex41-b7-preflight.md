> 분류: A/정책학습 · 시작 전 준비
> 작성: 오흥재 (runner 반영) · 2026-11-02
> 근거: EX-41 준비표 b021ce2c · 고정 인터페이스 8e0dc7a8 · 부모 학습 manifest와 model_7500.pt
> 요지: m7500 부모와 CPU 사전검사는 확인했으나 EX-41 본기동 연결과 Kit 검증은 아직 미완이다.
> 상태: CPU 사전검사 완료 · GPU/Kit/학습 미실행

# EX-41 B7 시작 사전검사 진행 보고

## 변경

- `foothold_s2/ex41_start_preflight.py`는 고정 checkout의 detached/clean/HEAD, 부모 체크포인트 경로·SHA·manifest 진행 회차를 읽기 전용으로 확인한다.
- 실제 `train_start.py`의 argparse 선언을 AST에서 추출하고 설치된 `cli_args.py`의 RSL-RL 인자 등록 함수를 호출해 후보 인자를 CPU에서 파싱한다. AppLauncher와 학습 스크립트는 import하지 않는다.
- `foothold_s2/scripts/make_ex41_playlists.py`는 명시한 영상 root와 출력 폴더만 사용해 `EX-41-mNNNNN-all|fail.m3u8`을 만든다. 실제 학습·평가 루프나 파일을 실행하지 않는다.
- W71 HOLD 수정은 기존 커밋 `4b3edd21`, W78 v2 CLI/산출 계약은 `5f326ece`에 있다. W78 계약에는 이동 비율, 계단 방향 0/30/60/90도, 세 지도 모드, 발별 스윙 높이, 끌림 비율이 들어 있다.

## 확인된 자료

부모 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_7500.pt`는 SHA256 `3a2cd2902c77b069ef1072d08e8254deadf663b56a9c95be704b07db52db2368`이다. 같은 폴더 manifest의 `checkpoints.model_7500.pt` SHA가 일치하고 `progress.completed_updates`는 7801이다. `train_start_status.json`은 readback 시 `running`, iter 7810을 기록했다. 이 둘의 시각 차이는 학습 중 갱신 차이로 보이며, m7500 체크포인트의 바이트·manifest 검증 결과에는 영향이 없다.

## 시험

`C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m pytest foothold_s2/tests/test_ex41_start_preflight_cpu.py foothold_s2/tests/test_ex40_b11_all_fixes_cpu.py -q`

결과: `34 passed in 17.44s`. EX-41 사전검사 7개는 clean detached 양성, attached/dirty 음성, 부모 SHA/manifest/progress 양성·음성, 실제 parser 선언 기반 인자 양성·음성, 명시한 출력 경로와 fail 목록 범위를 확인했다. W71 CPU 회귀 27개도 통과했다. `git diff --check` 통과.

## 미완료와 경계

고정 인터페이스 `8e0dc7a8`의 factory와 runtime 구현은 현재 `NotImplementedError` placeholder이다. 따라서 EX-41 runtime, EX-41 score watcher, shadow/stage loop가 사용할 정확한 score schema는 아직 없다. EX-40 watcher를 EX-41 결과에 연결하면 잘못된 판정 경로가 되므로 연결하지 않았다. Playlist 생성기만 준비되어 있고 단계 종료 시 호출하는 연결도 runtime/score schema 뒤에 남아 있다.

실제 train entrypoint parser 전체 실행, task/environment import, detached 고정 실행 worktree readback, Kit smoke, 첫 update는 미확인이다. AppLauncher import는 이 환경에서 Kit 부트스트랩과 EULA 프롬프트를 시작하는 경로여서 재호출하지 않았다. 이번 작업에서는 GPU, Kit, 학습을 시작하지 않았고 live EX-40 파일·원장·프로세스를 수정하거나 종료하지 않았다.

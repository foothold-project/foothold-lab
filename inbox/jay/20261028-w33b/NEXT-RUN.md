> 분류: 프로젝트 운영 · 다음 실행용 캐시 사본
> 작성: pipeline · 2026-10-28
> 근거: 팀장 pipeline 창 직접 W33b 승인 · mai-os PR62 · 프로젝트 #555
> 요지: 기존 작업은 불변, 새 실행에서만 UJITSO 캐시를 D:로 전달
> 상태: CPU argv 시험 통과 · 다음 실행 경로 선택은 lead 인계

# W33b 다음 실행 경로

작업 자리: `C:/mai/wt/foothold-lab/pipeline-w33b-next`, branch `feature/w33b-cache-next-jay`.

- 학습: 이 사본의 `foothold_s2/run_ex35.sh`. 실제 학습은 새로 시작하지 않았다.
- 평가: 이 사본의 `foothold_s2/eval/run_kit.sh`, `ex35_eval_chain2.sh`가 같은 ROOT를 통해 이 leaf를 호출한다. 사슬 자체는 원본과 같고 바꾸지 않았다.
- 촬영: 이 사본의 `foothold_s2/eval/video25/record_25e_x28.py`. `overlay_25e.py`는 원본의 그대로 사본이며, 두 파일의 출처는 impl-w04다. 촬영 구동기가 REC를 이 새 파일로 선택해야 적용된다. 이미 실행 중인 구동기는 바꾸지 않았다.

캐시 인자는 `--/UJITSO/datastore/localCachePath=D:/mai-cache/isaacsim-5.1/DerivedDataCache` 하나다. budget이나 남은 디스크에 따른 launch gate는 추가하지 않았다. 별도 10분 알림은 mai-os 담당이다.

기반: run_ex35/run_kit은 impl-w19 `3681d7dbe787c01463e50a57246a6f57e4866d0f`. record/overlay는 impl-w04 파일별 SHA로 아래처럼 고정했다. 이 사본은 main의 최신 구현을 대신하는 정본 승격이 아니므로 다른 실험 코드를 덮어쓰거나 전체 branch를 자동 merge하지 않는다.

원본 불변 SHA256:

- run_ex35: `e8fa748b523ff91ec9cb6f71b8fcacaf46bbc8f8750aab99f378682dd528c26f`
- run_kit: `52fcb92908a2ab39c53c13c37f44362c26b34c512457d4dee2d7e7c610d6ce34`
- record_25e_x28: `39e1edf30d24e611fd7aafa2aec4f1b3c666a6bee4a2568fa9e2255b4f2c10d5`

시험: `python foothold_s2/test_kit_cache_next.py` 5개 통과. 실제 자식 fixture script/module의 argv · 공백 경로 · 기존 Kit 설정 보존 · 종료값7 전달 · recorder 로컬 어댑터를 검사한다. 독립 검토에서 별도 토큰의 선행 하이픈 값이 argparse에 거절되는 문제를 재현했고, `--kit_args=<값>` 단일 토큰으로 고친 뒤 실제 argparse 회귀 시험을 통과했다. 두 shell은 `bash -n` 통과. 전체 실험 GPU suite를 실행했다는 뜻은 아니다. GPU1의 실제 캐시 위치/생성 확인은 별도 mai-os의 짧은 Kit probe 영수증으로 남겼다. 이 세 진입점의 전체 학습/Go2 평가/촬영은 새로 실행하지 않았다.

주의: 원본 shoot_w03g는 이전 recorder를 계속 가리키므로 다음 의뢰 때 REC/ROOT 경로를 명시적으로 선택한다. 기존 W03/W15를 중단하거나 재시작하지 않는다. 프로젝트 기존 판의 의미/정책/선택 규칙은 이 작업으로 바꾸지 않는다.

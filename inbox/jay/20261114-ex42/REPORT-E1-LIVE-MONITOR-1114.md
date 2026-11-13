# EX-42 E1 회차별 기술 지표와 조정 통로
> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · 2026-11-14
> 근거: CARD-E1-REDESIGN-v3-1113 §5.5 · 결정 48fd2c94 · a7c41171 · EX-42 E1 m250/m500 원자료
> 요지: 두 rank의 세 지도 모드 기술 지표를 회차별로 합치고, 승인 한계 안 조정을 회차 경계에서 영수증과 함께 적용한다.
> 상태: CPU 구현·시험 통과 · Kit 미실행 · 새 plan 승인 재고정 대기

## 변경과 측정 정의

- `foothold_s2/ex42_live_metrics.py`: 각 rollout step에서 실제 소비 명령, 지도 모드, 슬롯, 물리 step 뒤 몸 좌표 속도를 집계한다. reset된 env는 추종 비율에서 빼고 생존 분모·reset 수에 넣는다. 두 rank는 회차 끝에 합치며 rank별 원시 수치도 남긴다. `ex42_live_metrics.jsonl`과 `train_extra.jsonl`에 지도 GT/PRED/끔별 느린 전진 추종 비율·정체 비율·옆 좌우 따로·표본 수·20회 이동 평균·slow_track 활성 env-step 비율을 기록한다. `slow_track`의 활성 조건은 보상 항과 같은 속도 범위 0.1 이상 0.3 미만, yaw 명령 0, heading·깃발 제외다. 보상률 평균은 활성 env-step의 보상 항 값에 현재 가중치를 곱한 값이다.
- 지도 끔 생존은 50회 블록 간 0.05 초과 하락을 경보로 기록한다. 경보는 `alerts.jsonl`에도 남고 `EX42_ALERT_RUN_ID`로 지정한 Orca Run 받은편지함에 status를 보낸다. 전송 실패도 원장에 남기며 학습은 계속된다. 이는 조정 신호이며 졸업 판정은 아니다.
- `foothold_s2/ex42_live_adjust.py`: 매 회차 시작 때 rank 0이 `EX42_UPDATE_ADJUST` JSON 파일을 읽고 새 요청을 두 rank에 방송한다. 옛 네 보상 셀은 현행 `ex42-reward-adjust-limits.yaml` SHA와 값을 그대로 사용한다. 추가 셀의 승인 한계는 새 plan E1 행에 적어 plan SHA로 고정했다. 승인 밖 요청은 거절 기록 후 학습을 계속한다. 승인 안 요청은 두 rank의 실제 RewardManager·명령 표집 설정을 바꾸고 되읽기 일치 뒤 `ex42_update_adjust_m<N>.json`을 fsync하여 남긴다. rank 불일치·영수증 누락·영수증 밖 값 변화는 다음 rollout 전에 중단한다.
- 감시 단계는 초기 learning, 명시 조정으로 consolidating/solid/maintenance 전환, GT와 PRED 모두 최고 20회 평균 대비 0.05 초과 하락하면 learning 신호를 남긴다. 올림 숫자는 카드 §5.4에 미정이므로 자동 올림은 하지 않는다.

## 파일 계약

실행 plan `foothold_s2/curriculum/ex42-prep.yaml` SHA256은 **956e8c5f86f26ca2a64d5dc526789e2559e3b5e981e74f7fb6da86d87dd28a5c**에서 다시 계산해야 한다. 이 보고서 작성 뒤 파일이 바뀌면 여기 적힌 값은 옛 값이다. 기존 run의 plan으로 재개할 수 없으며 새 출발 승인·영수증의 plan SHA를 lead가 재고정해야 한다. 실행 환경에는 `EX42_ALERT_RUN_ID=run_...`가 필수이고, 조정 파일을 쓸 경우 `EX42_UPDATE_ADJUST=/절대경로/adjust.json`을 준다.

```json
{
  "schema": "ex42-update-adjust/1",
  "stage_id": "E1",
  "plan_sha256": "<새 실행 plan의 SHA256>",
  "changes": {
    "251": {
      "decided_by": "lead",
      "decided_at": "2026-11-14T00:09+09:00",
      "evidence": "<앞 경계 점수와 판단 기록 경로>",
      "rewards": {"slow_track": 0.2},
      "commands": {"low_forward_fraction": 0.4},
      "monitor": {"slow_forward": "learning"}
    }
  }
}
```

요청 파일에 이미 지난 회차를 다시 쓰면 그 회차의 원영수증과 일치해야 한다. 한계 밖 요청은 학습에 반영되지 않는다. 사용하지 않는 셀을 파일에서 생략할 수 있다.

## CPU 증거

- `isaac311`에서 새 지표·조정 13건 통과. 실제 CPU 두 rank `gloo`로 합친 GT 느린 전진 표본 2, 비율 0.75를 확인했다. 한계 밖 0.31 거절·rank 되읽기 차이 거절·영수증 삭제 및 값 변조 중단·Run 받은편지함 argv 시험을 포함한다.
- 기존 `test_ex42_segment_adjust_cpu.py`와 `test_ex42_training_entry_cpu.py` 포함 102 passed, 1 skipped. E1·prep·entry 등 계획 경로 94 passed. Kit, GPU, 실제 학습 속도는 측정하지 않았다.
- 실제 `EX-42-B-E1-again` m250/m500 `ex42_score.json`의 L0 fwd0.1 R은 GT 0.44670→0.31197, PRED 0.40742→0.33361이다. 두 지도에서 0.05 초과 하락 신호를 내는 답안 시험을 넣었다. 평가 R과 학습 env 회차 지표는 정의가 다르므로 수치 자체를 같은 판정으로 쓰지 않는다. 원자료 SHA256: m250 `0493348af8db731503dd6b2da3b7b2de53b62e08469aa21dd00c93614283a1ee`, m500 `ce60361dbb39c1ff7467abf6107ee040c3a136aaee82c006f00b5fb62e7c4414`.

## 남은 확인

새 plan으로 Kit 5회 예행에서 실제 RewardManager 재설정, 두 rank 동일 회차 적용, 지표 기록의 벽시계 비용을 확인해야 한다. 새 plan의 승인·기동 스크립트 SHA 재고정도 lead 몫이다. `EX42_ALERT_RUN_ID` 없는 기동은 환경 구성 단계에서 거절한다.

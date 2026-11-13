# EX-42 E1 회차별 기술 지표와 조정 통로
> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: 오흥재 · 2026-11-14
> 근거: CARD-E1-REDESIGN-v3-1113 §5.5 · 결정 48fd2c94 · a7c41171 · EX-42 E1 m250/m500 원자료
> 요지: 두 rank의 세 지도 모드 기술 지표를 회차별로 합치고, 승인 한계 안 조정을 회차 경계에서 영수증과 함께 적용한다.
> 상태: CPU 구현·시험 통과 · Kit 미실행 · 새 plan 승인 재고정 대기

## 변경과 측정 정의

- 느린 전진은 명령 속도 `[0.1,0.15)` · `[0.15,0.2)` · `[0.2,0.3)` m/s 세 칸으로도 나눈다. 각 칸에 지도 GT/PRED/끔별 표본 수·몸앞 속도 비율·멈춤 비율을 기록한다. 표본이 없으면 0 대신 `null`이다. 양 끝 경계와 0.3 제외 반례를 CPU로 확인했다.
- `foothold_s2/ex42_live_metrics.py`: 각 rollout step에서 실제 소비 명령, 지도 모드, 슬롯, 물리 step 뒤 몸 좌표 속도를 집계한다. reset된 env는 추종 비율에서 뺀다. 종료는 time_out과 낙상으로 나누고, 실행 계약의 `push_off_columns`를 기준으로 좁은 받침 지형과 그 밖의 지형을 따로 기록한다. 두 rank는 회차 끝에 합치며 rank별 원시 수치도 남긴다. `ex42_live_metrics.jsonl`과 `train_extra.jsonl`에 지도 GT/PRED/끔별 느린 전진 추종 비율·정체 비율·옆 좌우 따로·표본 수·20회 이동 평균·slow_track 활성 env-step 비율을 기록한다. 활성 조건은 보상 항과 같은 속도 범위 0.1 이상 0.3 미만이다. 이번 승인 판에서는 heading 느린 명령도 포함하며 heading과 일반 명령 표본을 따로 기록한다. 깃발과 자유 회전 명령은 제외한다.
- 지도 끔의 낙상 제외 생존은 50회 블록 간 변화를 기록한다. 학습 env 지표의 흔들림 폭이 아직 없어서 하락 문턱은 plan과 생성자 기본값 모두 `null`이고, 지금은 변화 기록만 남긴다. 기동 전 Kit 흔들림 실측 뒤 문턱을 plan에 고정해야 자동 경보·감시 단계 내림을 켤 수 있다. 전송 실패 뒤에는 최소 두 50회 블록 동안 재전송을 미룬다.
- `foothold_s2/ex42_live_adjust.py`: 매 회차 시작 때 rank 0이 `EX42_UPDATE_ADJUST` JSON 파일을 읽고 새 요청을 두 rank에 방송한다. 옛 네 보상 셀은 현행 `ex42-reward-adjust-limits.yaml` SHA와 값을 그대로 사용한다. 추가 셀의 승인 한계는 새 plan E1 행에 적어 plan SHA로 고정했다. 승인 밖 요청은 거절 기록 후 학습을 계속한다. 승인 안 요청은 두 rank의 실제 RewardManager·명령 표집 설정을 바꾸고 되읽기 일치 뒤 `ex42_update_adjust_m<N>.json`을 fsync하여 남긴다. rank 불일치·영수증 누락·영수증 밖 값 변화는 다음 rollout 전에 중단한다.
- 감시 단계는 초기 learning, 명시 조정으로 consolidating/solid/maintenance 전환, GT와 PRED 모두 최고 20회 평균 대비 0.05 초과 하락하면 learning 신호를 남긴다. 올림 숫자는 카드 §5.4에 미정이므로 자동 올림은 하지 않는다.

## 파일 계약

실행 plan `foothold_s2/curriculum/ex42-prep.yaml` SHA256은 **8b930fd2cf0a200f24ef9010b33700b590290c5371a17f98c99a429e66f27f0f**이다. 이는 draft 가지의 값이며 통합 v27 판에서는 다시 계산해야 한다. 기존 run의 plan으로 재개할 수 없으며 새 출발 승인·영수증의 plan SHA를 lead가 재고정해야 한다. 실행 환경에는 `EX42_ALERT_RUN_ID=run_...`가 필수이고, 조정 파일을 쓸 경우 `EX42_UPDATE_ADJUST=/절대경로/adjust.json`을 준다.

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

- `isaac311`에서 새 지표·조정·시작 계약 CPU 시험을 했다. 실제 CPU 두 rank `gloo`로 합친 GT 느린 전진 표본 2, 비율 0.75를 확인했다. 한계 밖 요청 거절·rank 되읽기 차이 거절·영수증 삭제 및 값 변조 중단·Run 받은편지함 argv 시험을 포함한다.
- 관련 E1·보상·명령·진입점 시험은 181 passed, 1 skipped였다. time_out 원시값을 쓰는 시작 경로 시험도 포함한다. Kit, GPU, 실제 학습 속도는 측정하지 않았다.
- 실제 `EX-42-B-E1-again` m250/m500 `ex42_score.json`의 L0 fwd0.1 R은 GT 0.44670→0.31197, PRED 0.40742→0.33361이다. 두 지도에서 0.05 초과 하락 신호를 내는 답안 시험을 넣었다. 평가 R과 학습 env 회차 지표는 정의가 다르므로 수치 자체를 같은 판정으로 쓰지 않는다. 원자료 SHA256: m250 `0493348af8db731503dd6b2da3b7b2de53b62e08469aa21dd00c93614283a1ee`, m500 `ce60361dbb39c1ff7467abf6107ee040c3a136aaee82c006f00b5fb62e7c4414`.

## 남은 확인

새 plan으로 Kit 5회 예행에서 실제 RewardManager 재설정, 두 rank 동일 회차 적용, 지표 기록의 벽시계 비용을 확인해야 한다. 새 plan의 승인·기동 스크립트 SHA 재고정도 lead 몫이다. `EX42_ALERT_RUN_ID` 없는 기동은 환경 구성 단계에서 거절한다.

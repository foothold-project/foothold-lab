> 분류: C/기록 · EX-42 계획 변경분
> 작성: analyst · 2026-11-07
> 근거: decisions.tsv 2026-11-07T17:25:16+09:00 · 6b9d6c19
> 요지: 확정된 운영 원칙 셋을 v5에 반영한 v6 변경분
> 상태: 문서 반영 완료 · 소비 코드·예행 완료를 뜻하지 않음

# 18:00 자료 · v6에서 바뀐 줄

[변경 patch](PLAN-ex42-v6-1725.patch). 전체 계획은 `D:/mai-tmp/analyst/PLAN-ex42-terrain-blocks-1106.md` v6, 직전 v5는 `D:/mai-tmp/analyst/w38-v6-evidence/PLAN-ex42-terrain-blocks-v5-before-1725.md`에 보존했다.

- §0.1·§0.5·결정 목록: 유지 미회복이면 시간 상자 만료만으로 난도 재상승 없음. 복습 또는 선행 충족 다른 과제로 학습 계속. 이 원칙을 다시 승인 질문으로 남기지 않음.
- §0.7·§0.9: 기계 감시250·정기 실패 영상/사람 판단500·유지 큰 하락250즉시. 15분은 큐 제외 1차 판독 목표. 새 변경만 승인 후 경계 적용, 무변경은 알림. 이전 의견서의 매250 사람 판독 제안은 대체.
- §0.9: 판단 시각을 팀장에 미리 알림(W58 runner). lead+analyst가 진행·보고, 팀장 참여 가능하면 함께, 외부 일정이면 두 사람이 진행. 알림·참여·승인 영수증 필드 추가.

학습량·문턱·보상 가중은 바꾸지 않았다. 250회 115분50초·500회231분40초·판독15분+경계130분50초는 기존27.8초/회 가정의 계산이며, 큐·평가·승인 지연까지 보장하는 ETA가 아니다. W58 연결 구현은 별도 확인 대상이다.

[결정 근거](https://github.com/foothold-project/foothold-lab/blob/6b9d6c19/inbox/jay/20261104-ex41-restart/decisions.tsv) · [15분 가안과 영상 선택 근거](https://github.com/foothold-project/foothold-lab/blob/15df9443/inbox/jay/20261107-lead-1800/OPINION-EX42-failure-video-loop-1107.md).

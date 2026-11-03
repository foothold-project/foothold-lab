# 정책 → 앱 전달 문서 안내: 석헌 님 · 현민 님 각자 문서 하나

> 분류: 운영
> 작성: 오흥재 · 2026-11-03 17:11
> 근거: foothold-lab PR #567 · inbox/jay/20261103-policy-handoff/
> 요지: 학습한 정책을 앱에 붙이는 일을 문서 넷으로 정리했다. 석헌 님은 AME-2 묶음을 만들어 PR, 현민 님은 앱에 모드 넷을 만든다. 이름 규칙과 폴더 꼴은 모두 같다.
> 상태: 확정

📢 **정책 → 앱 전달 문서: 각자 자기 문서 하나만 읽으면 됩니다**

학습한 정책(ONNX)을 앱 시뮬에 붙이는 방법을 문서로 정리했습니다. 위치는 lab 저장소 `inbox/jay/20261103-policy-handoff/` 입니다.

**누가 무엇을 읽나**
- **임석헌 님**: `HANDOFF-AME2-WORKER.md`. 안의 「지시문」 칸을 에이전트에 통째로 붙여 넣으면, AME-2 저장본(m14999)에서 ONNX · contract.json · 확인 기록을 뽑아 `inbox/lim/20261103-policy-handoff/ame2-demo/` 에 PR 까지 올립니다.
- **오현민 님**: `HANDOFF-APP-DEVELOPER.md`. 앱에 모드 넷을 만들고, 모드를 고르면 그 정책의 값(관측 · 명령 · 지도 · 토크 · 자르기 · ONNX)이 통째로 바뀌게 합니다. 값은 문서에 먼저 적어 두었으니 묶음을 기다리지 않고 구조부터 만들면 됩니다.
- 모두: `README.md` 에 이름 규칙 · 진행 순서 · 폴더 꼴이 있습니다.

**모드 넷과 이름**
- 코드 키 `nvidia` · `start` · `ame2` · `go2`
- 지금 이름 `nvidia-demo` · `start-demo` · `ame2-demo` · `go2-oh2l2`
- 최종 이름 `nvidia-foothold-v2` · `start-oh2l2` · `ame2-oh2l2` · `go2-oh2l2`
- `go2` 는 정책 없이 실기 Go2(순정 Sport 모드)의 SDK 움직임을 시뮬 화면에 그리기만 합니다.

**진행 순서**
1. 석헌 님이 ame2-demo 묶음 PR
2. 팀장이 PR 을 검증
3. 현민 님이 앱에 적용

**꼭 지킬 것**
- 모드마다 지도 만드는 함수를 따로 둡니다. AME-2 지도(29 × 13 × xyz, 6 cm)와 START 지도(32 × 16 높이, 5 cm)는 숫자 뜻이 다릅니다.
- 한 모드의 값을 다른 모드 기본값으로 쓰지 않습니다(예: START calf 토크 45.43 이 공통 23.5 로 잘리면 안 됩니다).
- ONNX 는 lab 묶음 폴더에 같이 올립니다. 앱 저장소에는 커밋하지 않고 묶음에서 복사해 sha256 을 맞춰 씁니다.
- 문장에 em dash(가로로 긴 줄표)를 쓰지 않습니다.

**링크**
- 문서 폴더: https://github.com/foothold-project/foothold-lab/tree/main/inbox/jay/20261103-policy-handoff
- PR: https://github.com/foothold-project/foothold-lab/pull/567

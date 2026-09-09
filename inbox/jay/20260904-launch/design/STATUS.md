# 런칭 영상 A · 설계 현황 (2026-09-09)

발표(9/4)는 끝났고 이건 후속 작업이다. 이 문서는 lead 세션이 정리돼도
설계가 안 사라지게 남기는 것이다. 아티팩트(claude.ai)는 별도로 산다.

## 어디까지 됐나

- 시나리오: 팀장이 마디별로 지시. `scenario-direction.md` 가 원문.
- 컷 매핑: 19컷. `cut-mapping.md` 가 재료와 자리 대조.
- Isaac 재촬영: 전부 완료. record_terrain_demo.py (main 에 있음, PR #279).
  뷰 여덟 개(horizon·firststep·belowfoot·legs·column·retreat·climb·prelude)와
  원점 CSV 셋(column·dense·grid) 로 뽑았다. 결과 mp4 는 재생성 가능해서 미저장.
- 힉스필드 재료 47건: library/ 에 INDEX.md·prompts.json 저장됨(#250).

## 왜 멈춰 있나 (기술 실패 아님)

두 개를 기다린다.
1. codex/astra 검증. 내 컷 매핑이 팀장 지시와 맞는지 독립 검증하려는데
   codex CLI 가 astra 미지원 + 업데이트 프롬프트로 막혔다. 팀장이 codex 정리 중.
2. 팀장 결정 셋. 80cm 영상 판별(캡션 필요) · 우분투 멀티부트 여부 · 스토리보드 승인.

## 다음 순서

codex 정리 → astra 검증 → 폭풍 통과 컷 하나 생성(36 크레딧) →
Isaac 컷 변환 → 조립 → 사운드. 변환·조립은 우분투에서 이어가도 된다
(힉스필드 MCP·ffmpeg 는 OS 무관).

## 크레딧

잔액 319.5. 새로 걸 것은 폭풍 통과 1컷 + Isaac 변환 여러 컷. 확정 전.

## 아티팩트 (claude.ai, 저장소 밖)

스토리보드·카탈로그·설계도는 claude.ai 아티팩트로 산다. URL 은 팀장 대화에 있다.
저장소에는 이 문서와 원문·매핑만 남긴다.

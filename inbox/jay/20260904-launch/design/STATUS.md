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

## 아티팩트 URL (claude.ai · 세션과 무관하게 유지됨)

대화는 위로 밀려 다음 세션이 못 본다. 그래서 여기 박아 둔다. 최신순.

| 무엇 | URL |
|---|---|
| 시나리오 대조 카탈로그 (재료 47건 + 마디별) | https://claude.ai/code/artifact/5f15c47a-65eb-4848-b1f8-08e20b05d141 |
| 스토리보드 19컷 + 연결 영상 | https://claude.ai/code/artifact/c478cb1c-52b6-456b-bf09-d68e1f34a361 |
| Isaac 결과 3컷 + 설계 | https://claude.ai/code/artifact/cb117797-10b9-4494-8f2b-df55a5bcbfe1 |
| 엔딩 사운드 세 판 | https://claude.ai/code/artifact/718fe2f8-1a07-4cdd-aa1e-d13c246e00b0 |
| A 완성본 (23초 · 구판) | https://claude.ai/code/artifact/14dbeeca-5a7f-4863-9d7f-a87d0c78fdd3 |
| B 완성본 (20초) | https://claude.ai/code/artifact/6b111cc0-e4dc-4c71-8de8-d6b843e2ab11 |
| 힉스필드 크레딧 내역 | https://claude.ai/code/artifact/7cf4dfff-ad71-4913-ae2f-a13728b7bd96 |

## 80 cm 갭 대조 (외부 출처 · 영상에 쓰려면 팀장 승인)

팀장이 물은 80 cm 파쿠르 영상은 우리 것이 아니다. 외부 저장소
yobel-sungkooklee/extreme-quadruped-parkour 의 레벨 9 다. system 세션이 확정했다.

- 단일 갭이 아니라 45 cm 착지대를 낀 80 cm 갭 12개 연속 도약이다.
  캡션을 「80 cm 갭 하나 뛴다」로 달면 틀린다.
- NVIDIA 설정과 우리 저장소에는 gap_bar / gap_strip 이 0건이다(외부 포크가 더한 지형).
- 우리 갭 폭은 0.275 m 이고 거기서 우리 성공률 0 퍼센트다. 저쪽의 2.9배 작은 갭이다.
- 파쿠르 저장소 원문은 우리가 직접 안 열었다. 위 수치는 우리 대조분석 문서
  inbox/jay/20260909-parkour-ablation-대조분석.md 의 인용이다.

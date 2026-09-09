# 리드의 컷 매핑 (검증 대상)

경로 약어
- LIB  = C:/Users/AI-WS01/orca/workspaces/foothold-lab/hf-launch2/inbox/jay/20260904-launch/library
- ISA  = C:/Users/AI-WS01/orca/workspaces/foothold-lab/roughcut/sim/eval/results
- ffmpeg = C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe

| 마디 | 지시 요지 | 배정 소스 | 상태 |
|---|---|---|---|
| 1 | 빈 땅 원경 인서트 | LIB/37-1355-nano-opening.png (스틸+밀기) | 확정 제안 |
| 2 | 지평선 실루엣, 소리 먼저 | ISA/20260905-horizon45/flat_army_A_4096_horizon.mp4 | Isaac, 변환 예정 |
| 3 | 첫발 개미샷, 먼지가 발보다 먼저 | ISA/20260906-firststep-tight/flat_army_A_4096_firststep.mp4 | Isaac, 변환 예정 |
| 4 | 2와 같은 구도, 더 가까이, 아직 먼지 속 | ISA/20260906-approach25/flat_army_A_4096_horizon.mp4 (리드 추천) | 리드 추천 검증 요망 |
| 5 | 행렬 내부 직접 | LIB/39-1548-seedance-02_aisle.mp4 | 확정 제안 |
| 6 | (가까워짐 진행) | LIB/22-1122-seedance-dune-03_lead.mp4 | 확정 제안 |
| 7 | (가까워짐 진행) | LIB/25-1229-seedance-00_foot.mp4 | 확정 제안 |
| 8 | 근접 측면, Go2 각인 | LIB/44-1548-seedance-01_side.mp4 | 확정 제안 |
| 9 | 측면 통과 | LIB/42-1548-seedance-04_underfoot.mp4 | 확정 제안 |
| 10 | 발밑 앤트 컷 | ISA/20260906-belowfoot/flat_army_A_4096_belowfoot.mp4 | Isaac. 변환은 예산상 보류(쟁점 Q5) |
| 11 | 선회 | LIB/40-1548-seedance-05_orbit.mp4 | 지적 미해결(쟁점 Q3) |
| 12 | 먼지 폭풍 | LIB/21-1114-seedance-dune-06_dolly.mp4 | 확정 제안 |
| 13 | 폭풍 통과, 12에서 이어짐 | 신규 생성 36cr. 12의 끝 프레임을 참조로 | 생성 예정 |
| 14 | 일렬 종대, Go2 필수 | ISA/20260907-column/flat_army_A_256_column.mp4 | Isaac 재촬영 완료, 변환 예정 |
| 15 | 발 착착 멈춤 | ISA/20260906-feet-stop/flat_army_A_4096_legs.mp4 | Isaac, 변환 예정 |
| 16 | 후퇴, 끝없는 대열, 뒷컷과 연결 | LIB/46-1556-seedance-06_dolly.mp4 | 쟁점 Q2 |
| 17 | 정렬 대열, Go2 필수 | ISA/20260907-prelude/flat_army_F_4096_prelude.mp4 | Isaac 재촬영 완료, 변환 예정 |
| 18 | 드론 상승 -> FOOTHOLD | ISA/20260907-climb-still/flat_army_F_4096_climb.mp4 | Isaac(정지판), 변환 예정 |
| 19 | 모션그래픽 (불변, 임팩트만 마지막 논의) | 기존 엔딩 타이틀 | 보류 |

## 리드가 스스로 확신하지 못하는 쟁점 (반드시 판정할 것)

- Q1. 4마디: 리드는 Isaac approach25(2와 같은 축)를 추천. 대안은 LIB/41(먼지속 행렬), LIB/22(안개 실루엣).
  원문 「두번째 컷과 같은 구도 느낌」을 기준으로 무엇이 맞나. 셋 다 실제로 열어 보고 판정하라.
- Q2. 16마디: 46-dolly 는 로봇이 걷는 중이다. 15에서 멈췄는데 16에서 걷다가 17에서 다시 멈추면
  연속성이 깨지는가. 대안: ISA/20260907-prelude (정지 후퇴감 낮은 부감). 둘 다 열어 보고 판정하라.
- Q3. 11마디: 팀장이 「로봇이 조금 비어보인다」고 지적했는데 리드가 해결하지 않았다. 40-orbit 을 열어
  실제 밀도를 보고, Isaac 재촬영(간격 좁힘)이 필요한지 판정하라.
- Q4. 1마디: 스틸+밀기가 첫 컷으로 죽어 보이지 않는가.
- Q5. 예산: seedance 4초 1080p = 36 고정, 잔액 319.5. 변환 대상은 2,3,4,14,15,17,18 (7건) + 13 생성
  = 288. 스틸 확인 3장 = 6. 합 294. 리드는 10마디(발밑) 변환을 보류했다. 이 우선순위가 맞는가.
- Q6. 톤: 변환 목표는 암부 p5 48, 채도 30, 색상 31도 (Dune 시험 실측 평균). LIB 의 seedance 재고와
  Isaac 변환분이 이 목표로 한 세계가 되는지, 재고 중 톤이 튀는 것이 있는지 표본으로 확인하라.

## 재료 전량
- LIB 아래 mp4 29개(고래 01 제외 28개가 재료) + png 18개. 파일명 = 순번-시각-모델-용도.
- ISA 아래 20260905-*, 20260906-*, 20260907-* 폴더가 Isaac 렌더.
- 참고 시트: 스크래치패드의 lib_A.png, lib_C.png, img_all.png, audit1.png, audit2.png, check567.png,
  newshots.png, rerender.png (경로: 이 문서와 같은 폴더의 상위 = scratchpad)

# 원문과 제출본 자료 대응표

> 분류: 운영
> 작성: Codex · 2026-09-29 12:19
> 근거: 보존 원문과 최종 HTML의 인쇄 DOM 직접 집계
> 요지: 원문의 절·그림·영상이 제출 PDF의 어디에 있는지 연결한다.
> 상태: `확인됨`
> 판: v1.1

원문: https://foothold-project.vercel.app/research-20260928-v2-mvp-report

## 원문 16절과 제출본 15절
사용자가 요청한 공식 제출본 편집에 따라 제작 이력, fs1·fs2 참고 항목, 원보고서 개정 이력을 제외했다. 제출본은 15절·346블록·47표이며 그림 8개와 영상 49편은 유지한다. 아래 수량 열은 원문 기준이다.

| 원문 절 | 제출 PDF 쪽 | 원문 표 | 원문 그림 | 원문 영상 |
|---|---|---:|---:|---:|
| 0. 이번에 한 일 | 2 | 0 | 0 | 0 |
| 1. 먼저 「미경험」이라는 말부터 바로잡는다 확인됨 | 2, 3, 4 | 1 | 1 | 0 |
| 2. 일반화 성적 · 한 장 | 4, 5, 6, 7 | 3 | 1 | 9 |
| 3. 성공률만으로는 안 보이는 것 | 7 | 2 | 0 | 0 |
| 4. 지형 하나하나 | 7, 8, 9, 10 | 2 | 1 | 0 |
| 5. 난이도를 올리면 어떻게 되나 | 10, 11, 12 | 2 | 1 | 0 |
| 6. 여기까지 어떻게 왔나 · 문제 파악 · 가설 · 실험 · 검증 | 12, 13, 14, 15, 16, 17, 18, 19, 20 | 10 | 2 | 7 |
| 7. 레시피 · v2 가 무엇으로 학습했나 | 21, 22 | 2 | 0 | 0 |
| 8. 어디서 멈췄나 · 멈출 기준 | 22, 23 | 3 | 0 | 0 |
| 9. 축 2 · 아홉 칸이 무엇인가 | 23, 24, 25, 26, 27, 28 | 8 | 0 | 18 |
| 10. 배포본과 참고 비교군 | 29 | 1 | 0 | 0 |
| 11. 다음 단계 | 29, 30, 31, 32 | 3 | 2 | 0 |
| 12. 재현 | 33 | 0 | 0 | 0 |
| 13. 근거 영상 전체 | 33, 34, 35, 36, 37, 38, 39 | 13 | 0 | 15 |
| 14. 자료 | 39, 40 | 1 | 0 | 0 |
| 판 이력 | 제출본에서 제외 | 1 | 0 | 0 |

## 본문 그림 8개

| 원본 파일 | PDF 쪽 |
|---|---|
| v2-terrain-catalog.png?v=8e000d3d | 3 |
| v2-generalization-summary.svg?v=2df8b28f | 4 |
| v2-terrain-bars.svg?v=50f72fb0 | 8, 9 |
| v2-difficulty-curve.svg?v=8edf902e | 10, 11 |
| v2-lineage.svg?v=ce12f925 | 12 |
| v2-blown-runs.svg?v=a4f73558 | 19, 20 |
| v2-next-step.svg?v=13c30b09 | 29, 30 |
| v2-height-scan.png?v=142b7383 | 31 |

## 영상 49편과 대표 장면

PDF에는 각 영상의 실제 주요 장면 49장, 학습 진행 비교 2장, 원본 링크가 들어 있다.

| 영상 | 파일 | 대표 시각 | PDF 쪽 |
|---|---|---:|---|
| V01 | hero-floatingring-v15-nvidia.mp4 | 2.2초 | 6 |
| V02 | hero-floatingring-v15-v1.mp4 | 2.2초 | 6 |
| V03 | hero-floatingring-v15-v2.mp4 | 2.2초 | 6 |
| V04 | hero-pit-v15-nvidia.mp4 | 2.2초 | 6 |
| V05 | hero-pit-v15-v1.mp4 | 2.2초 | 6 |
| V06 | hero-pit-v15-v2.mp4 | 2.2초 | 6 |
| V07 | hero-steppingstones-v10-nvidia.mp4 | 2.4초 | 6 |
| V08 | hero-steppingstones-v10-v1.mp4 | 2.4초 | 6 |
| V09 | hero-steppingstones-v10-v2.mp4 | 5.8초 | 6 |
| V10 | lineage-gap-v1.mp4 | 1.6초 | 15 |
| V11 | lineage-gap-D-fail.mp4 | 2.4초 | 15 |
| V12 | lineage-gap-v2.mp4 | 1.6초 | 15 |
| V13 | train-gap-forward.mp4 | 1.5초 | 16 |
| V14 | train-gap-omni.mp4 | 1.5초 | 16 |
| V15 | turnfall-v2a-iter1500.mp4 | 5.1초 | 18 |
| V16 | turnfall-v2b-iter1500.mp4 | 5.1초 | 18 |
| V17 | axis2ext-slow010-nvidia.mp4 | 10.1초 | 26 |
| V18 | axis2ext-slow010-v1.mp4 | 10.1초 | 26 |
| V19 | axis2ext-slow010-v2.mp4 | 10.1초 | 26 |
| V20 | axis2ext-slow020-nvidia.mp4 | 12초 | 26 |
| V21 | axis2ext-slow020-v1.mp4 | 12초 | 26 |
| V22 | axis2ext-slow020-v2.mp4 | 12초 | 26 |
| V23 | axis2ext-slow030-nvidia.mp4 | 12초 | 27 |
| V24 | axis2ext-slow030-v1.mp4 | 12초 | 27 |
| V25 | axis2ext-slow030-v2.mp4 | 12초 | 27 |
| V26 | axis2ext-slow040-nvidia.mp4 | 12초 | 27 |
| V27 | axis2ext-slow040-v1.mp4 | 12초 | 27 |
| V28 | axis2ext-slow040-v2.mp4 | 12초 | 27 |
| V29 | axis2ext-turnrest-nvidia.mp4 | 3.8초 | 27 |
| V30 | axis2ext-turnrest-v1.mp4 | 3.8초 | 27 |
| V31 | axis2ext-turnrest-v2.mp4 | 3.8초 | 27 |
| V32 | axis2ext-turnrev-nvidia.mp4 | 13.9초 | 28 |
| V33 | axis2ext-turnrev-v1.mp4 | 13.9초 | 28 |
| V34 | axis2ext-turnrev-v2.mp4 | 13.9초 | 28 |
| V35 | axis2-stop-nvidia.mp4 | 8.6초 | 34 |
| V36 | axis2-stop-v1.mp4 | 8.6초 | 34 |
| V37 | axis2-stop-v2.mp4 | 8.6초 | 34 |
| V38 | axis2-hold-nvidia.mp4 | 17.1초 | 34 |
| V39 | axis2-hold-v1.mp4 | 17.1초 | 34 |
| V40 | axis2-hold-v2.mp4 | 17.1초 | 34 |
| V41 | axis2-turn-nvidia.mp4 | 3.5초 | 35 |
| V42 | axis2-turn-v1.mp4 | 3.5초 | 35 |
| V43 | axis2-turn-v2.mp4 | 3.5초 | 35 |
| V44 | ss-v1-fail.mp4 | 2.4초 | 36 |
| V45 | stepping-stones-v2.mp4 | 5.8초 | 36 |
| V46 | stepping-stones-v2-cross.mp4 | 3.88초 | 36 |
| V47 | regress-stairsinv-d09-v1.mp4 | 3.6초 | 38 |
| V48 | regress-stairsinv-d09-v2.mp4 | 3.6초 | 38 |
| V49 | train-army.mp4 | 39초 | 39 |

## 판 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-09-29 | 최종 40쪽 PDF의 절·그림·영상 대응 집계 |


## 승인된 제외 목록

| 원문 블록 | 제외 이유 |
|---|---|
| s14-b003 | HUD 유무·제작 파이프라인에 관한 내부 기록 |
| s14-b035 | 영상 조각별 편집 길이 |
| s14-b038 | 영상 제작용 화면 축척 설명 |
| s14-b039 | 영상 제작 해상도 설명 |
| s14-b040 | 이전 영상과 화면 픽셀 수 비교 |
| s14-b041 | 화면 픽셀 수의 반복 설명 |
| s14-b043 | 영상 프레임 수와 검은 프레임 검수 기록 |
| s14-b045 | 이전 영상 삭제와 중복 판단 기록 |
| s14-b046 | 학습 진행 영상에 HUD가 없는 제작상 이유 |
| s14-b047 | 학습 진행 영상의 재촬영·편집 이력 |
| s14-b048 | 폐기한 영상과 화면 축척의 반복 설명 |
| s14-b050 | MVP 판정에서 제외한 fs1·fs2 참고 항목 제목 |
| s14-b051 | MVP 판정에서 제외한 fs1·fs2 참고 항목 |
| s16-b000 | 원보고서 개정 이력은 웹 기록에 보존하고 공식 제출본에서 제외 |
| s16-b001 | 원보고서 개정 이력은 웹 기록에 보존하고 공식 제출본에서 제외 |
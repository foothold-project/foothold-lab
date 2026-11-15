# B stones · 인용 원문 두 편의 치수 대조

> 분류: A/지형씬제작
> 작성: 오흥재 · analyst-lx · 2026-11-11 12:03
> 근거: 팀장 11:58 카드 · planner REVIEW-EX42-E1F-E2-ENTRY-1111 §3 · 원문 PDF 두 편 직접 확인
> 요지: 지형 계열의 원문 근거는 확인했지만, B의 0.71→0.41 m·틈 0.08→0.12 m는 두 원문의 수치와 다르다.
> 상태: 조사 완료 · 수치의 논문 등급 승격은 불가 · 학습 치수 변경 없음

## 결론

**두 논문을 열었다는 이유만으로 현재 B 치수를 「논문 수치」로 올리면 안 된다.** 종류·배치 원리는 인용 원문까지 확인됐다. 그러나 현재 B 범위는 코드값이며, 두 원문에서 그 범위를 찾지 못했다. 특히 He의 **12 cm는 작은 돌의 폭**이지 틈 폭이 아니다.

## 원문과 코드

| 출처·위치 | 로봇·조건 | 돌 한 변 | 명목 틈 | XY 이동 최대 | 높이 편차 최대 | 등급 |
|---|---|---:|---:|---:|---:|---|
| Zhang IROS 2024, PDF p.4 Table I, L0 | ANYmal-D · Stones-Everywhere | 0.92 m | 0.08 m | 0.036 m | 0.01 m | 논문 원문 |
| 같은 표 L5 | 같음 | 0.52 m | 0.18 m | 0.082 m | 0.06 m | 논문 원문 |
| 같은 표 L9 | 같음 | 0.20 m | 0.26 m | 0.118 m | 0.10 m | 논문 원문 |
| He Science Robotics 2025의 저자 공개 원고, PDF p.9 및 p.17 Supplementary Methods | ANYmal-D 시뮬 평가 grid stones / 추가 학습 grid stones small | 0.20 m / 최소 0.12 m | 해당 문단에 없음 | 무작위, 숫자 없음 | 무작위, 숫자 없음 | 논문 원문(공개 원고 판) |
| 현재 B, ame2_preset.py:97·202~210 | Go2용 구현 L0→L9 | 0.71→0.41 m | 0.08→0.12 m | 틈/4 = 0.02→0.03 m | ±0.06 m 고정 | 코드 |

[Zhang 원문](https://arxiv.org/pdf/2311.10484#page=4) Table I와 p.3 §III-A.1을 함께 확인했다. 표는 cm여서 위에서 m로 환산했다. 표의 중간 레벨은 선형이며 틈은 무작위 이동 전 격자 간격에서 돌 폭을 뺀 값이다. 실제 돌 사이 틈과 구분한다.

[He 저자 공개 원고](https://arxiv.org/pdf/2506.09588#page=17) p.17은 ANYmal-D 기본 학습에 grid stones, 추가 학습에 최소 폭 12 cm grid stones small을 분리한다. p.9 평가 문단은 grid stones 20×20 cm와 작은 돌 12×12 cm를 구분한다. [논문 식별 정보](https://pubmed.ncbi.nlm.nih.gov/40864729/)와 제목·저자를 대조했다. 이번에 수치를 읽은 것은 저자 arXiv 원고이며 출판사 최종 조판본으로 표기하지 않는다.

[AME-2 원문 Appendix A](https://arxiv.org/html/2601.08485v1#A1)는 Stones-Everywhere를 [26] Zhang와 [15] He에서 따랐다고 적는다. 이 문장은 계열의 근거다. B의 네 끝값이 해당 인용문 안에 있는 것은 아니다.

## 선언에 반영할 문구

- `original_dimensions`: Zhang의 L0/L5/L9 위 수치를 원문 별도 열로, He의 0.20/0.12 m는 서로 다른 과제의 돌 폭으로 기록.
- `training_dimensions`: 현재 B 0.71→0.41 m / 0.08→0.12 m 유지. 등급 「코드·우리 구현」 유지. 이 범위를 저자 원문과 동일하다고 쓰지 않음.
- 원문보다 더 어려운 지형을 이미 구현했다는 결론은 내릴 수 없다. 예를 들어 B L9의 돌은 Zhang L9보다 넓고 명목 틈은 좁다(수치 비교). 반대로 학습 성공·실패는 로봇·명령·관측이 달라 이 비교만으로 단정하지 않는다.
- 새 수치를 학습에 넣거나 B 메시를 다시 만들지 않았다. 선언 파일 수정은 planner 소유다.

## 확인 파일

PDF 원본은 저장소 밖 `/home/jay/mai/tmp/analyst-lx/stones-sources-1111/`에 보존했다.

| 파일 | SHA256 |
|---|---|
| zhang2024.pdf | a305b15386464ad5e2a6349cd7d5badb1d53bdab30c81b6647ba70a14bafc494 |
| he2025.pdf | bc4644955c009d2e1c68b7b6f50505d76c45c3f74e2127fa8916459e13b46c6c |

직접 본 페이지 PNG: `zhang-table1.png`(p.4), `he-supp17.png`(p.17). 추출문: zhang2024.txt:211~217, he2025.txt:897~910. PDF·페이지 이미지를 git에 복사하지 않는다. 현재 코드 위치: `foothold_s2/terrains/ame2_preset.py:97` 및 `:202`(평가 메시 PR642 기반 코드, B 파일 변경 없음).

# 회의록 한 페이지 인쇄

기준 디자인: `inbox/meang/20260818-rough-terrain-rl-study.pdf` (험지RL 공부와 접근).
폰트: 나눔고딕 (`fonts-nanum`. `render.sh`가 `print/fonts/`로 복사).

| 파일 | 역할 |
|---|---|
| `oneshot.css` | 공유 격자 · 나눔고딕 |
| `Foothold_260814.html` | 팀·운영 회의 예 |
| `Foothold(박철제님)_260824.html` | 멘토링 예 |
| `render.sh` | Chrome headless → A4 PDF |

새 회차:

1. 타이틀: `Foothold_YYMMDD` 또는 `Foothold(멘토명)_YYMMDD`
2. 가까운 HTML을 복사해 제목·초점·사분면·노트·다음만 바꾼다
3. `bash docs/meetings/print/render.sh` 로 PDF를 `docs/meetings/` 에 둔다
4. 같은 이름의 md도 `docs/meetings/` 에 남긴다

페이지를 둘로 나누지 않는다. 넘치면 문장을 줄인다.

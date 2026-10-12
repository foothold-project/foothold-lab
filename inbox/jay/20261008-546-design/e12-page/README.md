> 분류: A/정책학습 · 평가 · 페이지 생성기
> 작성: 오흥재 (lead 세션 · Claude 실행) · 2026-10-12
> 근거: _eval/out 의 E12-page.csv · E12-summary.json · curves · web_list.csv · episodes.csv · hud_sel.json (워크스테이션)
> 요지: E1 · E2 성능 · 영상 Artifact 두 페이지 (본 페이지 · 19500 영상) 를 만드는 생성기 사본. 숫자는 손으로 쓰지 않고 원자료에서 읽는다
> 상태: 3판 (10/12 밤) · 결함 영상 24 편은 재렌더 대기

# E1 · E2 페이지 생성기

- `build.py`: 원자료 → `index.html` (+ 영상 · 포스터 복사). 인자 `ck=20499|19500 mode=main|videos other=<다른 페이지 주소> site=<출력 폴더>` · `novideo` 는 영상 복사 생략
- `page.html`: 틀. `/*__DATA__*/` 자리에 자료가 들어간다
- `verify_traces.py`: 영상에 쓰인 기록 (parquet) 에서 판정값을 다시 계산해 episodes.csv 와 대조 (10/12: 325 편 일치)
- 올리기 전 검사: `_out/tools/page_audit.py` (상자 비율 · 가로 넘침 · 안 뜬 이미지 · 콘솔 오류) · `_out/tools/video_frame_audit.py` (검은 · 단색 · 파란 프레임)
- 페이지: https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN · https://claude.ai/artifact/HHArB8qjvrhWiZgehFyjg5

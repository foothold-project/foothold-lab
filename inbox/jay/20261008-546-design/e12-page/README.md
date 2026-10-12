> 분류: A/정책학습 · 평가 · 페이지 생성기
> 작성: 오흥재 (lead 세션 · Claude 실행) · 2026-10-12
> 근거: _eval/out 의 E12-page.csv · E12-summary.json · curves · web_list.csv · episodes.csv · hud_sel.json (워크스테이션)
> 요지: E1 · E2 성능 · 영상 Artifact 두 페이지 (본 페이지 · 19500 영상) 를 만드는 생성기 사본. 숫자는 손으로 쓰지 않고 원자료에서 읽는다
> 상태: 4판 (10/12 밤) · 중간 정리 · v2 비교 · 쉬운 설명 · 화면 전체 폭 · 결함 영상 24 편 교체 끝

# E1 · E2 페이지 생성기

- `build.py`: 원자료 → `index.html` (+ 영상 · 포스터 복사). 인자 `ck=20499|19500 mode=main|videos other=<다른 페이지 주소> site=<출력 폴더>` · `novideo` 는 영상 복사 생략
- `page.html`: 틀. `/*__DATA__*/` 자리에 자료가 들어간다
- `facts4.py`: 4판 본문의 `%%이름%%` 자리 값을 원자료에서 계산 (20000 전후 학습 곡선 · 칸별 하락 · noise 켬/끔 멈추기 · v2 대 E1 보상 · 명령 · 지형). 그림의 차원 숫자를 E1 · v2 체크포인트 가중치 모양과 대조하는 관문, 20000 명령 변경 로그 줄 관문이 들어 있다. torch 를 불러오므로 `KMP_DUPLICATE_LIB_OK=TRUE` 로 돌린다
- `verify_traces.py`: 영상에 쓰인 기록 (parquet) 에서 판정값을 다시 계산해 episodes.csv 와 대조 (10/12: 325 편 일치)
- 올리기 전 검사: `_out/tools/page_audit.py` (상자 비율 · 가로 넘침 · 안 뜬 이미지 · 콘솔 오류) · `_out/tools/video_frame_audit.py` (검은 · 단색 · 파란 프레임)
- 페이지: https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN · https://claude.ai/artifact/HHArB8qjvrhWiZgehFyjg5

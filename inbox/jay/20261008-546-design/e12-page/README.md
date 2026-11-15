> 분류: A/정책학습 · 평가 · 페이지 생성기
> 작성: 오흥재 (lead 세션 · Claude 실행) · 2026-10-12 (5판 2026-10-13 05:09)
> 근거: _eval/out 의 E12-page.csv · E12-summary.json · curves · web_list.csv · episodes.csv · hud_sel.json · un_* (미경험 지형 100 실행) · unseen_web_list.csv · cmdr_post.json · cmdr_eval_driver.json · 학습 로그 (워크스테이션)
> 요지: E1 · E2 성능 · 영상 Artifact 세 페이지 (본 페이지 · 19500 영상 · 미경험 지형 영상 144 편) 를 만드는 생성기 사본. 숫자는 손으로 쓰지 않고 원자료에서 읽는다
> 상태: 5판 (10/13 아침) · 밤사이 결과 · 미경험 지형 (ASTRA 14 반영) · RoboGauge (ASTRA 13 반영) · CMD-R 진행 · 다음 실험 · 앱 연결

# E1 · E2 페이지 생성기

- `build.py`: 원자료 → `index.html` (+ 영상 · 포스터 복사). 인자 `ck=20499|19500 mode=main|videos other=<다른 페이지 주소> site=<출력 폴더>` · `novideo` 는 영상 복사 생략. 5판부터 `facts5_*.py` 자리도 채운다
- `page.html`: 틀 (5판 조립 결과). `/*__DATA__*/` 자리에 자료가 들어간다
- `assemble_v5.py`: 4판 틀 + `v5/v5_*.html` 조각 → 5판 틀. 바꾸는 문구마다 찾는 문구 수를 확인한다 (ASTRA 13: model_20000 경계 · 명령 확대를 원인으로 쓰지 않음 · ASTRA 14: 「건넘」 대신 기준선 도달과 끝까지 생존을 나눔)
- `facts4.py`: 4판 본문의 `%%이름%%` 자리 값 (20000 전후 학습 곡선 · 칸별 하락 · noise · v2 대 E1). 가중치 모양 · 명령 변경 로그 줄 관문 포함. torch 를 불러오므로 `KMP_DUPLICATE_LIB_OK=TRUE`
- `facts5_night.py`: 밤사이 표의 진행 칸 (학습 iteration · 평가 유효 실행 수)
- `facts5_unseen.py`: 미경험 지형 표 (기준선 도달 · 도달 뒤 20 초 생존 · 20 초 생존). 하위 작업 집계 `UNSEEN-cells.csv` 와 생존 · 도달이 하나라도 다르면 멈춘다
- `facts5_cmdr.py`: CMD-R 절 (`cmdr_post.json` · `cmdr_summary.json` · bundle 대조)
- `unseen_vsel.py`: 본 페이지에 넣은 미경험 지형 영상 8 편의 판별 정보
- `unseen_gallery.py`: 미경험 지형 영상 144 편 페이지 (영상은 web 사본을 복사하고 sha256 대조 · 판마다 원자료로 다시 잰 결과)
- `verify_traces.py`: 영상에 쓰인 기록 (parquet) 에서 판정값을 다시 계산해 episodes.csv 와 대조 (10/12: 325 편 일치)
- 올리기 전 검사: `page_audit.py` (1920 · 1366 · 390 · 상자 비율 · 가로 넘침 · 안 뜬 이미지 · 콘솔 오류) · `audit_full.py` (어둠 · 단색 · 푸른 화면 · 모든 프레임). `v5/audit_unseen144.json` 은 144 편 전 프레임 위반 0. 이 검사는 멈춘 화면 · 로봇 누락을 못 잡는다 (ASTRA 14 7.2)
- 페이지: 본 https://claude.ai/artifact/BYuAVDuVJuRWVkAs5mGJSN · 19500 영상 https://claude.ai/artifact/HHArB8qjvrhWiZgehFyjg5 · 미경험 지형 영상 https://claude.ai/artifact/TKJKCUbk2TKwWB16DvY5h5

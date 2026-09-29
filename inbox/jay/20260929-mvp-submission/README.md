# FOOTHOLD MVP 종합보고서 제출본

> 분류: 운영
> 작성: Codex · 2026-09-29 12:18
> 근거: 공개 원보고서 보존본 · HTML/PDF 직접 대조 · 공개 영상에서 추출한 주요 장면
> 요지: 공개 보고서 전체를 브랜드 색상의 단일 HTML과 A4 PDF로 편집하고 오프라인 영상 묶음으로 전달한다.
> 상태: 제출본 변환·오프라인 전달 독립 검증 통과
> 판: v1.0

작업 이슈: [#484](https://github.com/foothold-project/foothold-lab/issues/484)

외부에 전달할 파일은 `output/`에 있다. **ZIP을 압축 해제한 뒤 HTML을 열면 인터넷 없이 영상까지 볼 수 있다.** PDF는 A4 34쪽이며 영상마다 실제 주요 장면과 원본 영상 링크를 제공한다.

| 파일 | 용도 |
|---|---|
| [FOOTHOLD-MVP.html](output/FOOTHOLD-MVP.html) | 하나의 웹페이지. 그림은 파일에 포함되고 영상은 공개 URL에서 재생된다 |
| `FOOTHOLD-MVP.pdf` | 제출·인쇄용 A4 34쪽. 목차와 영상 링크 포함 |
| `FOOTHOLD-MVP-submission.zip` | 오프라인 HTML, 같은 PDF, 영상 22편, 사용 안내, 파일 해시 목록 |

HTML과 PDF를 따로 전달할 때는 같은 폴더에 둔다. ZIP 안의 `media/` 폴더도 HTML과 함께 유지한다. PDF의 영상 링크와 공개 원자료 링크는 인터넷 연결이 필요하다. 원자료 전체와 학습 체크포인트는 제출 묶음에 포함하지 않는다.

저장소의 인쇄 PDF 제외 규칙에 따라 PDF와 이를 포함한 ZIP은 로컬 전달 파일로 남긴다. git에는 HTML, 보존 원문, 그림·장면, 생성 코드, 검증 기록을 올린다. 저장소를 새로 받은 경우 PDF와 ZIP은 아래 생성 순서로 다시 만들 수 있다. 영상 파일이 없다면 먼저 `acquire.py`를 실행해 보존 원문이 가리키는 매체를 내려받는다.

## 무엇을 보존하고 무엇을 편집했나

[공개 원보고서](https://foothold-project.vercel.app/research-20260928-v2-mvp-report)의 16절, 본문 블록 306개, 표 45개, 본문 그림 8개, 직접 삽입 영상 22편을 보존했다. 원문은 `source/report.html`에 저장했다. 최초 수집 시각과 해시는 `source/snapshot.json`, 최신 공개본과의 대조는 `source/latest-sync.json`에 있다. `확인됨`

개인 이름과 내부 직함은 외부 독자용 문장으로 바꿨다. 연구 대상과 두 평가 축을 소개하는 초록, 목차, 절 제목을 정리했다. 수치·실험 조건·실패·한계와 개정 이력을 유지했다. 실제 문장 변경은 `editorial-changes.json`에서 확인한다.

화면에서는 원 SVG 6개와 PNG 2개를 유지한다. PDF의 SVG는 원본에서 문구와 수치를 자동 추출해 글자를 키우고 재배치했다. 난이도 그래프는 두 패널로, 학습 중단 도식과 다음 연구 도식은 내용 경계에서 나누어 출력한다. 글자를 줄여 빈 공간에 억지로 밀어 넣지 않았다. 인쇄용 도식 원본은 `print-figures/`다.

낙상 영상에는 리셋 후 다시 서 있는 끝 장면 대신 실제 넘어지는 순간을 골랐다. PDF에는 대표 장면 22장과 학습 진행 비교 2장을 넣었다. `frame-selection.json`은 선정 시각·이유, `video-scenes.json`은 영상 메타데이터다. `stills/`에 실제 추출 프레임이 있다.

원문 V15 캡션의 “6.5초에서 넘어져 끝난다”는 검증에서 틀린 것으로 확인해 제출본에서 정정했다. **대표 장면 3.5초, 환경 기록의 낙상 판정 3.70초, 전체 영상 길이 6.48초**를 구분한다. 보존 원문은 바꾸지 않았다. V01~03·V20~21의 거리값은 영상 전체의 최종값이라는 설명도 붙였다.

## 검증과 범위

- `coverage.json`: 원문 블록과 화면 본문의 대응.
- `pagination-audit.json`: 페이지별 사용 높이, 잘림·가로 넘침, 원문 블록과 영상 대응.
- `delivery-check.json`: 390px 모바일, 새 탭 기본 인쇄, 인쇄 버튼, 인쇄 후 화면 복귀, PDF 목차 16개와 영상 링크 22개.
- `package-manifest.json`: ZIP과 내부 파일 해시. 원 영상 바이트 보존 확인.
- `VERIFY-MVP.md`, `VERIFY-MVP-2.md`: 독립 검증 결과. 초기 지적의 수정 후 재검증과 오프라인 전달 검증을 포함한다.

이 검증은 **제출본의 원문 보존과 전달 기능**을 확인한다. 원보고서의 정책 탐색 상한, 통계적 유의성, 실제 로봇 안전성 등 모든 연구 주장을 새로 승인하는 작업은 아니다. 직접 재검증하지 않은 연구 주장은 미확인이다. 새 학습이나 시뮬레이션은 실행하지 않았다.

HTML에는 화면용 `#web-content`와 조판 완료된 `#print-root`가 함께 있다. 브라우저 기본 인쇄가 비동기 조판을 기다리다 빈 페이지를 만드는 문제를 피하기 위한 구성이다. 콘텐츠를 세는 도구는 화면 본문과 인쇄본을 나눠 집계해야 한다.

## 다시 만드는 순서

`acquire.py`로 수집한 원문과 매체, `frames.py`로 추출한 장면이 있는 상태에서 다음 순서로 생성한다. `--refresh`는 공개 원문의 변경을 의도적으로 반영할 때만 사용하고, 결과 전체를 다시 검증한다.

```powershell
python inbox/jay/20260929-mvp-submission/print_figures.py
python inbox/jay/20260929-mvp-submission/build.py
python inbox/jay/20260929-mvp-submission/render.py
python inbox/jay/20260929-mvp-submission/check_delivery.py
python inbox/jay/20260929-mvp-submission/package_delivery.py
```

작성 환경은 Windows, Chrome, Python의 BeautifulSoup·PyMuPDF·Pillow다. Playwright는 저장소의 의존성 파일을 추가하지 않고 시스템 임시 폴더 `foothold-mvp-render-deps`에 설치했다. 영상 추출에는 별도 `isaac311` 환경의 OpenCV를 사용했다. 경로는 생성 스크립트에 명시돼 있으므로 다른 환경에서는 먼저 조정한다.

`render.py`는 A4 PDF를 만든 뒤 인쇄 DOM을 HTML에 저장한다. **`build.py`만 다시 실행하면 준비된 인쇄 DOM이 사라지므로 `render.py`까지 반드시 실행한다.** `qa/`의 전체 페이지 이미지를 눈으로 검토한 뒤 전달한다. QA와 임시 파일, 개별 원 MP4는 git에서 제외하고, 전달 ZIP에는 영상 전부를 포함한다.

## 판 이력

| 판 | 날짜 | 내용 |
|---|---|---|
| v1.0 | 2026-09-29 | 공개본 보존, 전체 자료를 포함한 HTML·PDF·오프라인 ZIP 제작, 독립 검증에 따른 인쇄·목차·도식·캡션 수정 |

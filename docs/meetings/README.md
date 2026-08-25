# meetings: 회의록

## 이 폴더는 공개되지 않습니다

회의록에는 아직 정리되지 않은 판단, 사람 이야기, 외부 관계자 언급이 섞입니다.
그래서 `docs/` 안에 있어도 **웹 게시 대상이 아닙니다.**
공개할 내용은 회의록에서 뽑아 `docs/research/` 나 기획 문서로 옮깁니다.

## 제목

종류를 먼저 확인하고, 뒤에 날짜(`YYMMDD`)를 붙인다.

| 종류 | 타이틀 | 예 |
|---|---|---|
| 팀·운영 회의 | `Foothold 회의록_YYMMDD` | `Foothold 회의록_260814` |
| 멘토링 정리 | `Foothold 정리본(멘토명)_YYMMDD` | `Foothold 정리본(박철제님)_260824` |

md 파일명은 `YYMMDD_Foothold_회의록.md` / `YYMMDD_Foothold_정리본_멘토.md`.
인쇄 PDF 파일명은 위 타이틀 그대로.

## 디자인

인쇄본은 **한 페이지**다. 기준은 `inbox/meang/20260818-rough-terrain-rl-study.pdf` (험지RL 공부와 접근)의 격자다.

- HTML: `docs/meetings/print/`
- 공유 스타일: `print/oneshot.css`
- PDF 다시 뽑기: `bash docs/meetings/print/render.sh`

새 회차는 기존 HTML을 복사해 제목·초점·사분면·노트·다음 할 일만 바꾼다. 페이지를 늘리지 않는다.

## 형식

- 머리에 **날짜 · 참석자 · 녹음 여부**를 적습니다.
- 인용은 **타임코드**를 답니다. 예: `(12:34) "선 긋지 말고"`
  나중에 "그렇게 말한 적 없다" 가 되면 확인할 방법이 그것뿐입니다.
- 결정이 나오면 그 자리에서 `docs/DECISIONS.md` 에 한 줄 옮깁니다. 회의록에만 있으면 아무도 안 봅니다.

## 원본 음성·전사

원본은 저장소에 넣지 않습니다. NAS 회의 폴더에 둡니다(경로는 #foothold-resource).

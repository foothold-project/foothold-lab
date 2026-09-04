# 발표 덱 생성기

> 분류: 가이드
> 작성: 오흥재 · 2026-09-04 11:10
> 근거: 실측(개조 전후 산출물 바이트 동일 확인) · 크롬 151 과 엣지에서 file:// 재생 확인
> 요지: `proposal-deck.html` 과 `proposal-deck.pdf` 를 만드는 생성기. 영상 교체는 빌드 한 번이면 된다.
> 상태: 확정

`../proposal-deck.html`(발표용)과 `../proposal-deck.pdf`(19쪽)를 만든다. 산출물은
8 MB 가 넘는 단일 파일이고 그 안에 폰트와 로고와 영상이 전부 들어 있다. 손으로
고칠 수 있는 물건이 아니므로 **여기를 고치고 다시 빌드한다.**

## 빌드

```
cd deliverables/plan/_deck
python slides.py
```

`../proposal-deck.html` 과 `deck.artifact.html` 두 개가 나온다. 앞의 것이 발표용이고,
뒤의 것은 웹 뷰어에 올릴 때 쓰는 골격 없는 사본이다. **둘을 바꿔 쓰면 안 된다.**
아래 「charset」 절을 보라.

PDF 는 크롬 헤드리스로 뽑는다.

```
chrome --headless=new --disable-gpu --no-pdf-header-footer \
       --print-to-pdf=<절대경로>/proposal-deck.pdf \
       file:///<절대경로>/proposal-deck.html
```

뽑은 뒤 **19쪽인지, 960x540 인지, 한글이 성한지** 확인한다. 쪽 수가 다르면 어딘가
넘침이 생긴 것이고, 한글이 깨졌으면 charset 문제다.

## 영상 교체

이것만 하면 된다.

```
git pull                                  # 720p 사본을 받는다
python slides.py                          # 영상과 포스터를 다시 심는다
```

영상은 `../assets/foothold-roughcut-720.mp4` 를 **빌드할 때마다 읽는다.** base64 를
`assets.json` 에 박아두지 않는 이유가 그것이다. 박아두면 원본이 바뀌어도 아무도
눈치채지 못한다. 인쇄본에 쓰는 정지 화면(포스터)도 같은 영상의 45번 프레임에서
그때 뽑는다.

캡션은 `slides.py` 안의 `FOOTHOLD roughcut v8 · 4,096 · 21s` 한 줄이다. 판이 바뀌면
숫자를 같이 고친다. **길이는 재서 쓴다.** 20.56초면 21s 다.

러프컷이 아닌 다른 성격의 영상으로 갈면 `roughcut` 이라는 말부터 맞지 않는다.

## 왜 이렇게 되어 있나

세 가지는 발표 PC 에서 실제로 깨졌던 것을 고친 결과다. 되돌리지 말 것.

**charset.** 발표용 산출물은 `<!doctype html>` 부터 시작하는 완전한 문서다. `<meta
charset>` 이 없으면 `file://` 로 열 때 HTTP 헤더가 없어 브라우저가 Windows-1252 로
읽고 한글이 통째로 깨진다. PDF 도 같이 깨진다. 2026-09-04 에 19쪽 전부가 그 상태로
main 에 올라가 있었다. 미리보기 파일에만 charset 이 있어서 화면으로는 드러나지 않았다.

> **판별법**: 브라우저 주소창에 붙여넣지 말고 **파일을 더블클릭해서** 연다.

**폰트.** 바깥 폰트에 의존하는 곳이 없다. Pretendard 를 파일 안에 심고, 고정폭이
필요한 자리도 같은 폰트의 `tnum`/`zero` 로 처리한다. 예전에는 `Consolas` 를 썼는데
Windows 밖에서 폭이 달라져 라벨이 밀렸다. SVG 안의 `font-family` 도 마찬가지다.

**좌표계.** 슬라이드는 1280x720 고정이고 화면에는 `scale` 로만 맞춘다. 해상도가 달라도
배치가 흔들리지 않는다. 안쪽 크기는 컨테이너 단위(`cqw`)로 쓰는데, 그것을 모르는
브라우저를 위해 같은 값을 px 로 환산한 폴백을 빌드가 자동으로 만들어 붙인다
(`1cqw = 12.8px`, `1cqh = 7.2px`. 컨테이너 폭이 1280 으로 고정이라 산술로 확정된다).

## 발표 조작

파일을 직접 열면 곧바로 한 장씩 넘기는 상태가 된다. 프레임 안(웹 뷰어)에서는
세로로 훑다가 「발표 모드로 보기」 버튼으로 들어간다. 발표 모드는 화면을 `fixed` 로
덮기 때문에 프레임 안에서 바로 켜면 높이가 0 으로 접힌다.

| 키 | 동작 |
|---|---|
| `→` `Space` `PageDown` | 다음 |
| `←` `PageUp` | 이전 |
| `F` | 전체화면 |
| `G` | 전체보기 |
| `B` | 화면 끄기 |
| 숫자 + `Enter` | 그 장으로 |

18쪽에 들어가면 영상이 스스로 재생되고 장을 벗어나면 처음으로 되감는다.

## 필요한 것

```
python 3.11+
PyAV        영상에서 포스터 프레임을 뽑는다
Pillow      그 프레임을 JPEG 로 줄인다
pypdf       뽑은 PDF 를 검사할 때만 쓴다
크롬        PDF 렌더
```

## 파일

| | |
|---|---|
| `slides.py` | 19장의 내용과 조립. 고칠 일은 대개 여기다 |
| `deck.tpl.html` | CSS 와 발표 스크립트가 든 틀 |
| `assets.json` | 로고와 사진 21개를 base64 로 담았다. 영상과 폰트는 여기 없다 |
| `PretendardVariable.woff2` | 심는 폰트 원본. SIL Open Font License 1.1 |

Pretendard 는 길형진(orioncactus)이 만들어 OFL 1.1 로 배포한다.
<https://github.com/orioncactus/pretendard>

# HUD 글꼴

> 분류: 운영
> 작성: 오흥재 · 2026-09-09 12:45
> 근거: 실측 (OFL 원문 대조 · 글꼴 name 테이블 되읽어 확인)
> 요지: Pretendard 를 굵기 고정 · 글자 부분집합으로 구워 심었다. OFL 1.1 §3 이 예약 이름을 금해 이름을 FOOTHOLD HUD 로 바꿨다.
> 상태: 확정
> 판: v1.0
> 이슈: #99

## 왜 심나

**시스템 글꼴을 찾지 않습니다.** 찾으면 이 PC 에서는 한글이 나오고 팀원 PC
에서는 네모가 나오는데, 그 차이는 영상을 다 만들고 나서야 보입니다.
`hud.Fonts` 는 여기 파일이 없으면 그 자리에서 죽습니다.

## 무엇이 있나

| 파일 | 무엇 |
|---|---|
| `FootholdHud-Regular.ttf` | wght 400 · 약 49 KB |
| `FootholdHud-Bold.ttf` | wght 700 · 약 49 KB |
| `OFL.txt` | 라이선스 원문 |

## 어디서 왔나

`deliverables/plan/_deck/PretendardVariable.woff2` 입니다. 저장소에 이미 있던
가변 글꼴이고, `build_font.py` 가 그것을 읽어

1. 굵기를 400 · 700 으로 고정하고 (Pillow 는 가변 글꼴 축을 편히 못 다룬다)
2. `hud.charset()` 의 글자만 남기고 (전체는 굵기당 몇 MB 다)
3. 글꼴 안의 **이름 기록을 갈아 끼운 뒤**
4. woff2 가 아닌 TTF 로 저장합니다 (Pillow 가 woff2 를 못 연다)

```
pip install fonttools brotli
python sim/eval/overlay/build_font.py
```

`brotli` 는 woff2 를 푸는 데만 씁니다. **영상을 만들 때는 둘 다 필요 없습니다.**
여기 TTF 가 이미 있기 때문입니다.

## 왜 이름을 바꿨나 `확인됨`

Pretendard 의 라이선스 원문 2행입니다.

```
Copyright (c) 2021, Kil Hyung-jin (https://github.com/orioncactus/pretendard),
with Reserved Font Name 'Pretendard'.
```

**Reserved Font Name 이 걸려 있습니다.** OFL 1.1 §3 은 Modified Version 이
그 이름을 쓰는 것을 금합니다. 굵기를 고정하고 글자를 덜어낸 이 파일은
Modified Version 이므로, 파일 이름도 글꼴 안의 이름 기록도 `FOOTHOLD HUD` 로
바꿨습니다. 「Pretendard 부분집합」이라고 부르면 위반입니다.

바꾸는 자리는 **이름 자리뿐**입니다(nameID 1 · 3 · 4 · 6 · 16 · 17 · 18 · 25).
저작권(0) · 상표(7) · 설명(9) · 라이선스(13 · 14) 고지는 그대로 둡니다.
거기 남은 "Pretendard" 는 위반이 아니라 **출처 표시**이고, OFL §2 는 저작권과
라이선스 고지를 함께 배포하라고 요구합니다.

`build_font.py` 가 구운 뒤 이름 자리를 **되읽어** 예약 이름이 남았는지 봅니다.
`tests/test_overlay.py::FontTest` 가 같은 것을 매번 다시 봅니다.

## 라벨을 더하려면

1. `hud.LABEL_TEXTS` 에 글자를 더한다
2. `python sim/eval/overlay/build_font.py` 로 다시 굽는다
3. 커밋한다

**2번을 잊으면 시험이 터집니다.** `FontTest.test_every_label_char_is_in_both_fonts`
가 `hud.charset()` 의 글자가 전부 글꼴에 있는지 봅니다. 이 관문이 없으면
네모가 난 것을 영상을 만들고 나서야 봅니다.

## 남은 일

저장소에 이미 있는 `deliverables/plan/_deck/PretendardVariable.woff2` 에는
**라이선스 원문이 같이 있지 않습니다.** OFL §2 가 요구하는 것이고, 이 폴더의
`OFL.txt` 는 여기 글꼴만 덮습니다. 덱 쪽도 같이 두는 것이 맞습니다.
이 PR 범위 밖이라 손대지 않았습니다.

## 판 이력

| 판 | 언제 | 무엇이 바뀌었나 | 근거 |
|---|---|---|---|
| v1.0 | 2026-09-09 | 처음 씀 | 실측 |

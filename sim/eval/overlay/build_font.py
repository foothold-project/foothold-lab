"""HUD 글꼴을 굽는다. `deliverables/plan/_deck/PretendardVariable.woff2` 에서.

## 왜 굽나

Pillow 는 woff2 를 못 엽니다. 그리고 저장소에 있는 것은 가변 글꼴 하나뿐입니다.
그래서 **필요한 글자만 남긴 정적 TTF 두 벌**(Regular · Bold)로 구워
`fonts/` 에 심습니다.

## 왜 부분집합인가

Pretendard 전체는 한 굵기가 몇 MB 입니다. 두 굵기면 저장소에 10 MB 가 들어옵니다.
HUD 가 쓰는 글자는 `hud.charset()` 이 정확히 알고 있고, 그것만 남기면 수십 KB 입니다.

**부분집합의 위험은 하나입니다.** 나중에 라벨을 더했는데 글꼴에 그 글자가 없으면
화면에 네모가 나옵니다. 그래서 `tests/test_overlay_hud.py` 가 `hud.charset()` 의
글자가 전부 글꼴에 있는지 매번 봅니다. **라벨을 더하면 시험이 먼저 터집니다.**

## 준비물

```
pip install fonttools brotli
```

`brotli` 는 woff2 를 푸는 데 필요합니다. 구운 뒤에는 안 씁니다. 팀원이
영상을 만들 때는 `fonts/` 에 이미 TTF 가 있으므로 **둘 다 필요 없습니다.**

## 라이선스 · **이름을 바꿔야 합니다**

Pretendard 는 SIL Open Font License 1.1 이고, **Reserved Font Name 이 걸려
있습니다**(`fonts/OFL.txt` 2행 · "with Reserved Font Name 'Pretendard'").

OFL 1.1 §3 은 **Modified Version 이 Reserved Font Name 을 쓰는 것을 금합니다.**
굵기를 고정하고 글자를 덜어낸 이 결과물은 Modified Version 입니다. 그래서
파일 이름도 글꼴 안의 이름 기록도 `FOOTHOLD HUD` 로 바꿉니다. 「Pretendard 부분집합」
이라고 부르고 싶겠지만 그 이름을 쓰면 라이선스 위반입니다.

원본이 무엇인지는 `fonts/README.md` 가 밝힙니다. §4 는 원저작자 표시를 요구하지
않지만, 밝히지 않을 이유도 없습니다.

```
python sim/eval/overlay/build_font.py
```
"""

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVAL = os.path.dirname(_HERE)
_REPO = os.path.dirname(os.path.dirname(_EVAL))

if _EVAL not in sys.path:
    sys.path.insert(0, _EVAL)

from overlay import hud  # noqa: E402

SOURCE_WOFF2 = os.path.join(_REPO, "deliverables", "plan", "_deck",
                            "PretendardVariable.woff2")

# OFL 1.1 §3 이 Reserved Font Name 을 금하므로 이름을 갈아 끼운다. 위 문서 참고.
FAMILY = "FOOTHOLD HUD"

WEIGHTS = (
    ("FootholdHud-Regular.ttf", 400, "Regular"),
    ("FootholdHud-Bold.ttf", 700, "Bold"),
)

# name 테이블에서 갈아 끼울 자리. 숫자는 OpenType nameID 다.
#
# **여기 있는 것이 「글꼴 이름」입니다.** OFL 1.1 §3 이 금하는 것은 이 자리에
# 예약된 이름을 쓰는 것입니다.
_NAME_FAMILY = 1
_NAME_SUBFAMILY = 2
_NAME_UNIQUE = 3
_NAME_FULL = 4
_NAME_POSTSCRIPT = 6
_NAME_TYPO_FAMILY = 16
_NAME_TYPO_SUBFAMILY = 17
_NAME_COMPAT_FULL = 18
_NAME_VAR_PS_PREFIX = 25

# 이름이 아니라 **고지**인 자리. 저작권(0) · 상표(7) · 설명(9) · 제작자 URL(11,12)
# · 라이선스(13,14) 는 그대로 둡니다. OFL §2 가 저작권과 라이선스 고지를 함께
# 배포하라고 요구하고, 상표 고지를 지우는 것은 요구된 적이 없습니다.
# 원본이 Pretendard 라는 사실은 지울 것이 아니라 밝힐 것입니다.
NAME_IDS = (
    _NAME_FAMILY, _NAME_SUBFAMILY, _NAME_UNIQUE, _NAME_FULL, _NAME_POSTSCRIPT,
    _NAME_TYPO_FAMILY, _NAME_TYPO_SUBFAMILY, _NAME_COMPAT_FULL,
    _NAME_VAR_PS_PREFIX,
)


def rename(font, family, style):
    """글꼴 안의 이름 기록을 통째로 갈아 끼운다.

    파일 이름만 바꾸면 시스템에는 여전히 예약된 이름으로 보입니다.
    **`name` 테이블이 진짜 이름입니다.**
    """
    full = "{} {}".format(family, style)
    postscript = "{}-{}".format(family.replace(" ", ""), style)

    replacements = {
        _NAME_FAMILY: family,
        _NAME_SUBFAMILY: style,
        _NAME_UNIQUE: "{} : FOOTHOLD sim/eval/overlay".format(full),
        _NAME_FULL: full,
        _NAME_POSTSCRIPT: postscript,
        _NAME_TYPO_FAMILY: family,
        _NAME_TYPO_SUBFAMILY: style,
        _NAME_COMPAT_FULL: full,
        _NAME_VAR_PS_PREFIX: family.replace(" ", ""),
    }

    table = font["name"]

    for record in list(table.names):
        if record.nameID in replacements:
            table.setName(replacements[record.nameID], record.nameID,
                          record.platformID, record.platEncID, record.langID)

    return full


def leftover_reserved_names(font, reserved=("Pretendard", "Source", "Inter",
                                            "M PLUS 1", "M+")):
    """**이름 자리**에 예약된 이름이 남아 있는가. 남으면 OFL 1.1 §3 위반이다.

    고지 자리(저작권 · 상표 · 설명 · 라이선스)는 보지 않습니다. 거기 남은
    "Pretendard" 는 위반이 아니라 **출처 표시**입니다. `NAME_IDS` 주석 참고.

    **되읽어 확인하는 자리입니다.** 「이름을 바꿨다」는 보고가 아니라
    「이름 자리에 정말 안 남았는가」를 봅니다.
    """
    found = []

    for record in font["name"].names:
        if record.nameID not in NAME_IDS:
            continue

        try:
            text = record.toUnicode()
        except Exception:  # noqa: BLE001
            continue

        for name in reserved:
            if name.lower() in text.lower():
                found.append((record.nameID, text))
                break

    return found


def build(source, out_dir, text):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    os.makedirs(out_dir, exist_ok=True)

    made = []

    for name, weight, style in WEIGHTS:
        font = TTFont(source)

        if "fvar" not in font:
            raise RuntimeError(
                "{} 가 가변 글꼴이 아닙니다. 굵기를 고를 수 없습니다.".format(source)
            )

        instantiateVariableFont(font, {"wght": weight}, inplace=True,
                                updateFontNames=False)

        options = subset.Options()
        options.layout_features = ["*"]
        options.name_IDs = ["*"]
        options.notdef_outline = True
        options.recalc_bounds = True
        options.drop_tables = []

        subsetter = subset.Subsetter(options=options)
        subsetter.populate(text=text)
        subsetter.subset(font)

        full = rename(font, FAMILY, style)

        leftover = leftover_reserved_names(font)

        if leftover:
            font.close()
            raise RuntimeError(
                "예약된 글꼴 이름이 남았습니다(OFL 1.1 §3): {}".format(leftover)
            )

        font.flavor = None

        path = os.path.join(out_dir, name)
        font.save(path)
        font.close()

        made.append((path, weight, full, os.path.getsize(path)))

    return made


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=SOURCE_WOFF2)
    parser.add_argument("--out_dir", default=hud.FONT_DIR)
    args = parser.parse_args()

    if not os.path.exists(args.source):
        raise SystemExit("원본 글꼴이 없습니다: {}".format(args.source))

    text = hud.charset()

    print("굽는 글자 {}자".format(len(text)))
    print(text)

    made = build(args.source, args.out_dir, text)

    for path, weight, full, size in made:
        print("  {:<28} wght={} name={:<22} {:>7} bytes".format(
            os.path.basename(path), weight, full, size))

    # 되읽어 확인한다. 구웠다는 보고가 아니라 **파일에 글자가 들어 있는지**를 본다.
    for path, _weight, _full, _size in made:
        missing = hud.missing_glyphs(path, text)

        if missing:
            raise SystemExit(
                "{} 에 빠진 글자가 있습니다: {}".format(path, "".join(missing))
            )

    print("\n[PASS] 두 벌 모두 필요한 글자를 전부 담았고, 예약 이름이 없습니다.")


if __name__ == "__main__":
    main()

"""한 프레임 위에 계측값을 그린다. Pillow 만 씁니다.

## 무엇을 그리고 무엇을 뺐나

| 그린다 | 왜 |
|---|---|
| 경과 시간 | 「몇 초에」를 말하려면 있어야 한다. 프레임 번호에서 공짜로 나온다 |
| **속도 · 명령 대 실제** | **이 도구가 있는 이유.** 아래 §주춤 |
| 전진 · 통과선까지 | 막대 하나. 「어디까지 갔나」가 한눈에 |
| 좌우 이탈 | 가운데 기준 게이지 하나. 방향이 새는 것이 보인다 |
| 판정 4축 | 램프 넷. **어느 축에서 떨어지는 중인지**가 보인다 |

| 뺐다 | 왜 |
|---|---|
| 발 높이 네 발 | 걸음 하나가 약 0.3초다. 50 fps 영상에서 15프레임이고, 6초 창에 네 줄을 겹치면 서로 뭉개져 안 읽힌다. 그리고 **발 높이는 chase 카메라가 이미 보여 준다.** trace 에는 적어 두었으니 필요해지면 칸을 하나 더 쓰면 된다 |
| 몸통 높이 · 기울기 | 같은 이유로 뺐다. 넣으면 화면이 여섯 칸이 되는데, 팀이 지금 보려는 것은 속도 하나다. trace 에는 있다 |
| 보상 | 프레임마다의 뜻이 사람에게 안 읽힌다. 판 단위 표에 남아 있다 |
| 세계좌표 x · y | 출발 자세 기준의 전진 · 좌우로 이미 바꿔 그렸다. 두 벌을 같이 두면 헷갈린다 |

**전부 넣지 않은 것이 설계입니다.** 화면 위 28% 만 씁니다. 로봇을 가리면
영상이 아니라 계기판이 됩니다.

## 주춤

`trace.slowdown_spans()` 가 「명령의 60% 아래로 0.15초 이상」을 구간으로 집습니다.
그 구간을 속도 그래프 바닥에 띠로 깔고, 왼쪽 칸에 「주춤 2 / 3」으로 셉니다.
**눈으로 세지 말고 표시된 것을 보라는 뜻입니다.** 문턱값은 인자로 열려 있습니다.

## 글꼴

`fonts/` 에 심어 둔 것만 씁니다. **시스템 글꼴을 찾지 않습니다.** 찾으면
이 PC 에서는 되고 팀원 PC 에서는 네모가 나오는데, 그 차이는 영상을 만들고
나서야 보입니다. 글꼴이 없으면 그 자리에서 죽습니다.
"""

import io
import os

from PIL import Image, ImageDraw, ImageFont

_HERE = os.path.dirname(os.path.abspath(__file__))

FONT_DIR = os.path.join(_HERE, "fonts")

FONT_REGULAR = os.path.join(FONT_DIR, "FootholdHud-Regular.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "FootholdHud-Bold.ttf")

# ---------------------------------------------------------------- 글자 목록
#
# **이 목록이 글꼴 부분집합의 정의입니다.** `build_font.py` 가 여기 있는 글자만
# 남기고, `tests/test_overlay_hud.py` 가 여기 있는 글자가 전부 글꼴에 있는지 봅니다.
# 새 라벨을 쓰려면 여기에 먼저 더하고 글꼴을 다시 구우십시오. 안 그러면 네모가
# 나오는데, 시험이 그것을 먼저 잡습니다.

LABEL_TEXTS = (
    "경과",
    "초",
    "속도",
    "명령",
    "대",
    "실제",
    "전진",
    "통과선",
    "까지",
    "좌우",
    "이탈",
    "주춤",
    "생존",
    "추종",
    "방향",
    "판정",
    "판",
    "미정",
    "통과",
    "실패",
    "넘어짐",
    "시간초과",
    "기준",
    "지형",
)

# 라벨 말고 값에 쓰는 글자. 숫자 · 단위 · 지형 이름(영문) · 구분자.
VALUE_CHARS = (
    "0123456789"
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    " .,:%/+-_()[]·"
)


def charset():
    """글꼴에 남겨야 하는 글자 전부."""
    chars = set(VALUE_CHARS)

    for text in LABEL_TEXTS:
        chars.update(text)

    return "".join(sorted(chars))


# ---------------------------------------------------------------- 색

INK = (233, 237, 245, 255)
MUTED = (141, 150, 168, 255)

PANEL = (11, 14, 21, 196)
EDGE = (255, 255, 255, 30)
GRID = (255, 255, 255, 26)

CMD_LINE = (150, 161, 182, 255)

GOOD = (46, 209, 158, 255)
WARN = (243, 179, 58, 255)
BAD = (255, 94, 94, 255)
IDLE = (92, 100, 118, 255)

SHORTFALL = (243, 179, 58, 74)
SLOWBAND = (255, 94, 94, 132)


def speed_color(speed, command):
    """속도 하나의 색. 명령 대비 비율로 가른다.

    경계에 뜻이 있습니다. 0.8 아래는 「따라가지 못하는 중」, 0.5 아래는
    「사실상 멈춘 중」입니다. 색이 갈리는 자리가 곧 읽는 사람의 문턱이 됩니다.
    """
    if command <= 0.0:
        return GOOD

    ratio = speed / command

    if ratio >= 0.8:
        return GOOD

    if ratio >= 0.5:
        return WARN

    return BAD


def _fade(color, alpha):
    return (color[0], color[1], color[2], alpha)


# ---------------------------------------------------------------- 글꼴


class Fonts(object):
    """크기별 글꼴 묶음. 같은 크기를 두 번 열지 않는다."""

    def __init__(self, regular_path=FONT_REGULAR, bold_path=FONT_BOLD):
        for path in (regular_path, bold_path):
            if not os.path.exists(path):
                raise FileNotFoundError(
                    "글꼴이 없습니다: {}\n"
                    "`python sim/eval/overlay/build_font.py` 로 구우십시오. "
                    "시스템 글꼴로 대신하지 않습니다. 그러면 이 PC 에서만 됩니다."
                    .format(path)
                )

        self._regular_path = regular_path
        self._bold_path = bold_path
        self._cache = {}

    def get(self, size, bold=False):
        size = max(1, int(round(size)))
        key = (size, bold)

        if key not in self._cache:
            path = self._bold_path if bold else self._regular_path
            self._cache[key] = ImageFont.truetype(path, size)

        return self._cache[key]


# ---------------------------------------------------------------- 그리기 도구


def text_size(draw, text, font):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def draw_text(draw, xy, text, font, fill, anchor="la"):
    draw.text(xy, text, font=font, fill=fill, anchor=anchor)


def dashed_line(draw, x0, y, x1, color, dash=7, gap=6, width=1):
    x = x0

    while x < x1:
        draw.line((x, y, min(x + dash, x1), y), fill=color, width=width)
        x += dash + gap


# ---------------------------------------------------------------- HUD


class Hud(object):
    """trace 한 벌을 화면 한 판에 맞춰 놓고, 프레임마다 그 위를 갱신한다.

    **정적인 부분은 한 번만 그립니다.** 패널 바탕 · 눈금 · 옅은 전체 곡선은
    프레임마다 다시 그릴 이유가 없습니다. 3000장짜리 영상에서 이 차이가 큽니다.

    ## 왜 위에 붙나 (`anchor`)

    기본값이 `top` 입니다. **chase 카메라는 로봇을 화면 아래쪽에 둡니다.**
    2026-09-09 에 아래에 붙여 만들어 보고 로봇 다리가 패널에 가린 것을
    눈으로 확인했습니다. 위쪽은 하늘이라 가릴 것이 없습니다.

    `topdown` 처럼 로봇이 한가운데 오는 화면에서는 어느 쪽이든 됩니다.
    """

    # 720p 기준 치수. 다른 해상도에서는 `self.scale` 로 함께 늘어난다.
    MARGIN = 18
    BAND_H = 186
    PAD = 15
    GAP = 20
    GUTTER = 34

    COL_A = 0.20
    COL_B = 0.44

    def __init__(self, size, trace, fonts=None, title=None,
                 slowdown_ratio=0.6, slowdown_min_s=0.15, anchor="top"):
        if anchor not in ("top", "bottom"):
            raise ValueError("anchor 는 top 이나 bottom 입니다: {}".format(anchor))

        self.width, self.height = size
        self.trace = trace
        self.fonts = fonts or Fonts()
        self.scale = self.height / 720.0
        self.anchor = anchor

        meta = trace.meta

        self.command = trace.command_vx
        self.gate_m = float(meta.get("gate_m", meta.get("min_progress_m", 0.0)))
        self.max_lat = float(meta.get("max_lateral_drift_m", 0.05))
        self.max_mae = float(meta.get("max_velocity_mae_mps", 0.25))
        self.termination = str(meta.get("termination_reason", ""))
        self.fell = self.termination == "base_contact" if self.termination else None

        if title is None:
            title = "{} · env {} · {}판".format(
                meta.get("terrain", "?"), meta.get("env_id", "?"),
                meta.get("episode", "?"),
            )

        self.title = title

        from . import trace as trace_mod

        self.spans = trace_mod.slowdown_spans(
            trace, ratio=slowdown_ratio, min_duration_s=slowdown_min_s
        )
        self._trace_mod = trace_mod

        self._layout()
        self._base = self._render_static()

    # ------------------------------------------------------------ 자리 잡기

    def _s(self, value):
        return value * self.scale

    def _layout(self):
        """세 칸으로 가른다. 시간 · 속도 · 판정.

        칸 너비를 픽셀이 아니라 **비율**로 잡습니다. 960x540 에서도 1280x720
        에서도 같은 그림이 나와야 하고, 시험이 두 크기를 다 봅니다.
        """
        s = self._s
        w, h = self.width, self.height

        margin = s(self.MARGIN)
        band_h = s(self.BAND_H)

        if self.anchor == "top":
            band_top = margin
        else:
            band_top = h - band_h - margin

        self.band = (margin, band_top, w - margin, band_top + band_h)

        pad = s(self.PAD)
        gap = s(self.GAP)

        left = self.band[0] + pad
        right = self.band[2] - pad

        self.inner_top = self.band[1] + pad
        self.inner_bottom = self.band[3] - pad

        usable = (right - left) - 2 * gap

        a_end = left + usable * self.COL_A
        b_start = a_end + gap
        b_end = b_start + usable * self.COL_B
        c_start = b_end + gap

        self.col_a = (left, a_end)
        self.col_b = (b_start, b_end)
        self.col_c = (c_start, right)

        # 속도 칸. 왼쪽에 눈금 글자 자리를 비워 둔다.
        # **이 자리를 안 비우면 눈금이 패널 밖으로 나가 잘립니다** `확인됨`
        # (2026-09-09 · "1.4" 가 "4" 로 잘려 나왔다).
        self.chart_box = (
            b_start + s(self.GUTTER),
            self.inner_top + s(30),
            b_end,
            self.inner_bottom - s(14),
        )

        # 판정 칸. 램프는 **한 줄**이다. 두 줄로 넣어 봤더니 100 px 짜리 칸에서
        # 위아래 글자가 겹쳤다 `확인됨` (2026-09-09 · 28 px 도 36 px 도 겹쳤다).
        # 한글은 ascent 가 커서 PIL 의 `mm` 기준점이 눈에 보이는 가운데와 다르다.
        self.lamp_h = s(30)
        self.lamp_gap = s(7)
        self.lamp_w = ((self.col_c[1] - self.col_c[0]) - 3 * self.lamp_gap) / 4.0

        bar_h = s(14)

        self.prog_box = (self.col_c[0], self.inner_top + s(62),
                         self.col_c[1], self.inner_top + s(62) + bar_h)
        self.drift_box = (self.col_c[0], self.inner_top + s(120),
                          self.col_c[1], self.inner_top + s(120) + bar_h)

    # ------------------------------------------------------------ 좌표 변환

    def _y_top(self):
        """속도 축 위 끝. 명령보다 넉넉히 위로 두되 이상값에 안 끌려간다.

        한 프레임의 튀는 값 때문에 축이 늘어나면 나머지 전부가 바닥에 눌립니다.
        그래서 최댓값이 아니라 **위에서 2% 를 버린 값**을 봅니다.
        """
        values = sorted(v for v in self.trace.column("speed_mps") if v is not None)

        if values:
            high = values[min(len(values) - 1, int(0.98 * len(values)))]
        else:
            high = self.command

        return max(self.command * 1.35, high * 1.15, 0.5)

    def _chart_xy(self, t_s, speed):
        x0, y0, x1, y1 = self.chart_box
        duration = max(self.trace.duration_s, 1.0e-6)

        x = x0 + (x1 - x0) * min(max(t_s / duration, 0.0), 1.0)
        y = y1 - (y1 - y0) * min(max(speed / self._y_top(), 0.0), 1.0)

        return x, y

    def _speed_at_x(self, x):
        x0, _y0, x1, _y1 = self.chart_box
        duration = self.trace.duration_s

        t = duration * (x - x0) / max(x1 - x0, 1.0e-6)
        row = self.trace.at_time(t)

        return (row or {}).get("speed_mps")

    # ------------------------------------------------------------ 정적 레이어

    def _render_static(self):
        layer = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        s = self._s
        f = self.fonts

        draw.rounded_rectangle(self.band, radius=s(12), fill=PANEL, outline=EDGE,
                               width=1)

        # 왼쪽 칸 · 제목
        draw_text(draw, (self.col_a[0], self.inner_top), self.title,
                  f.get(s(13)), MUTED)

        # 속도 칸 · 제목
        bx = self.col_b[0]
        draw_text(draw, (bx, self.inner_top), "속도", f.get(s(15), bold=True), INK)
        draw_text(draw, (bx + s(36), self.inner_top + s(3)), "명령 대 실제",
                  f.get(s(12)), MUTED)

        self._render_chart_frame(draw)
        self._render_ghost_curve(draw)
        self._render_right_frame(draw)

        return layer

    def _render_chart_frame(self, draw):
        s = self._s
        f = self.fonts
        x0, y0, x1, y1 = self.chart_box

        top = self._y_top()

        for value in (0.0, top):
            _, y = self._chart_xy(0.0, value)
            draw.line((x0, y, x1, y), fill=GRID, width=1)

        # 명령선. 점선으로 둬 실제 곡선과 안 헷갈리게 한다.
        _, cy = self._chart_xy(0.0, self.command)
        dashed_line(draw, x0, cy, x1, CMD_LINE, dash=s(8), gap=s(7),
                    width=max(1, int(s(2))))

        # 명령 라벨은 **왼쪽 끝 위**에 둔다. 오른쪽에 두면 큰 숫자와 겹친다
        # `확인됨` (2026-09-09).
        draw_text(draw, (x0 + s(3), cy - s(3)), "명령 {:.2f}".format(self.command),
                  f.get(s(11)), CMD_LINE, anchor="ld")

        # 세로 눈금. 1초마다(길면 5초마다).
        duration = self.trace.duration_s
        step = 1.0 if duration <= 12.0 else 5.0
        mark = step

        while mark < duration - 1.0e-9:
            x, _ = self._chart_xy(mark, 0.0)
            draw.line((x, y0, x, y1), fill=_fade((255, 255, 255), 16), width=1)
            draw_text(draw, (x, y1 + s(2)), "{:g}".format(mark), f.get(s(10)),
                      _fade(MUTED, 170), anchor="ma")
            mark += step

        draw_text(draw, (x1, y1 + s(2)), "{:g}s".format(round(duration, 2)),
                  f.get(s(10)), _fade(MUTED, 170), anchor="ra")

        # 세로축 눈금 글자. **비워 둔 왼쪽 자리 안에** 넣는다.
        draw_text(draw, (x0 - s(5), y1), "0", f.get(s(10)), _fade(MUTED, 170),
                  anchor="rs")
        draw_text(draw, (x0 - s(5), y0), "{:.1f}".format(top), f.get(s(10)),
                  _fade(MUTED, 170), anchor="rm")
        draw_text(draw, (x0 - s(5), (y0 + y1) / 2), "m/s", f.get(s(9)),
                  _fade(MUTED, 130), anchor="rm")

        # 주춤 띠. 전체를 옅게 깔아 둔다. 지나간 부분은 프레임마다 진하게 덧그린다.
        for start, end, _lowest in self.spans:
            sx, _ = self._chart_xy(start, 0.0)
            ex, _ = self._chart_xy(end, 0.0)
            draw.rectangle((sx, y1 - s(3), ex, y1), fill=_fade(SLOWBAND, 60))

    def _render_ghost_curve(self, draw):
        """판 전체의 속도 곡선을 옅게. 앞으로 무슨 일이 있을지의 밑그림이다.

        지나간 부분은 프레임마다 진한 색으로 덧그립니다. 둘을 같이 두면
        「지금 어디」와 「전체 모양」이 한 화면에 들어옵니다.
        """
        points = []

        for row in self.trace.rows:
            speed = row.get("speed_mps")

            if speed is None:
                continue

            points.append(self._chart_xy(row["t_s"], speed))

        self._ghost_points = points

        if len(points) >= 2:
            draw.line(points, fill=_fade(INK, 46), width=max(1, int(self._s(1.5))),
                      joint="curve")

    def _render_right_frame(self, draw):
        s = self._s
        f = self.fonts

        x0 = self.col_c[0]

        draw_text(draw, (x0, self.prog_box[1] - s(21)), "전진",
                  f.get(s(14), bold=True), INK)
        draw_text(draw, (x0 + s(32), self.prog_box[1] - s(19)), "통과선까지",
                  f.get(s(11)), MUTED)

        draw_text(draw, (x0, self.drift_box[1] - s(21)), "좌우",
                  f.get(s(14), bold=True), INK)
        draw_text(draw, (x0 + s(32), self.drift_box[1] - s(19)), "이탈",
                  f.get(s(11)), MUTED)

    # ------------------------------------------------------------ 프레임

    def draw(self, image, frame_index):
        """프레임 하나에 HUD 를 얹은 새 이미지.

        `image` 는 RGB PIL 이미지입니다. 원본은 안 건드립니다.
        """
        row = self.trace.rows[min(frame_index, len(self.trace.rows) - 1)]

        layer = self._base.copy()
        draw = ImageDraw.Draw(layer)

        self._draw_clock(draw, row)
        self._draw_chart(draw, row)
        self._draw_progress(draw, row)
        self._draw_drift(draw, row)
        self._draw_lamps(draw, row)

        out = image.convert("RGBA")
        out.alpha_composite(layer)

        return out.convert("RGB")

    def _draw_clock(self, draw, row):
        s = self._s
        f = self.fonts
        x0 = self.col_a[0]

        big = f.get(s(38), bold=True)
        text = "{:.2f}".format(row["t_s"])

        baseline = self.inner_top + s(58)

        draw_text(draw, (x0, baseline), text, big, INK, anchor="ls")

        # 단위는 숫자 **뒤에** 붙인다. 자리를 재서 붙이지 않으면 겹친다
        # `확인됨` (2026-09-09 · «초» 가 숫자에 깔렸다).
        used = draw.textlength(text, font=big)

        draw_text(draw, (x0 + used + s(5), baseline), "초", f.get(s(15)), MUTED,
                  anchor="ls")

        draw_text(draw, (x0, baseline + s(18)),
                  "경과 / {:g}초".format(round(self.trace.duration_s, 2)),
                  f.get(s(12)), _fade(MUTED, 200))

        if self.spans:
            seen = sum(1 for start, _e, _l in self.spans if start <= row["t_s"])
            color = BAD if seen else _fade(MUTED, 200)

            draw_text(draw, (x0, baseline + s(44)),
                      "주춤 {} / {}".format(seen, len(self.spans)),
                      f.get(s(13), bold=True), color)
        else:
            draw_text(draw, (x0, baseline + s(44)), "주춤 0", f.get(s(13)),
                      _fade(MUTED, 200))

    def _draw_chart(self, draw, row):
        s = self._s
        f = self.fonts
        x0, y0, x1, y1 = self.chart_box

        now_t = row["t_s"]
        speed = row.get("speed_mps")
        px, _ = self._chart_xy(now_t, 0.0)

        _, cy = self._chart_xy(0.0, self.command)

        # 명령에 못 미친 만큼을 채운다. **주춤이 면적으로 보이는 자리다.**
        step = max(1, int(s(1)))
        x = x0

        while x <= px:
            value = self._speed_at_x(x)

            if value is not None and value < self.command:
                _, sy = self._chart_xy(0.0, value)
                draw.line((x, cy, x, sy), fill=SHORTFALL, width=step)

            x += step

        passed = [p for p in self._ghost_points if p[0] <= px + 0.5]

        if len(passed) >= 2:
            draw.line(passed, fill=_fade(INK, 235), width=max(1, int(s(2))),
                      joint="curve")

        for start, end, _lowest in self.spans:
            if start > now_t:
                continue

            sx, _ = self._chart_xy(start, 0.0)
            ex, _ = self._chart_xy(min(end, now_t), 0.0)
            draw.rectangle((sx, y1 - s(3), ex, y1), fill=SLOWBAND)

        draw.line((px, y0, px, y1), fill=_fade(INK, 120), width=1)

        if speed is not None:
            color = speed_color(speed, self.command)
            _, sy = self._chart_xy(now_t, speed)
            r = s(4)
            draw.ellipse((px - r, sy - r, px + r, sy + r), fill=color)

            # 큰 숫자는 제목 줄 오른쪽 끝. 차트 밖이라 곡선을 안 가린다.
            value_font = f.get(s(24), bold=True)
            text = "{:.2f}".format(speed)

            draw_text(draw, (x1, self.inner_top - s(4)), text, value_font, color,
                      anchor="ra")

            used = draw.textlength(text, font=value_font)

            draw_text(draw, (x1 - used - s(5), self.inner_top + s(7)), "m/s",
                      f.get(s(10)), MUTED, anchor="ra")

    def _draw_progress(self, draw, row):
        s = self._s
        f = self.fonts
        x0, y0, x1, y1 = self.prog_box

        fwd = row.get("fwd_m") or 0.0
        gate = max(self.gate_m, 1.0e-6)

        draw.rounded_rectangle((x0, y0, x1, y1), radius=s(7),
                               fill=(255, 255, 255, 20))

        ratio = min(max(fwd / gate, 0.0), 1.0)

        if ratio > 0.0:
            end = x0 + (x1 - x0) * ratio
            color = GOOD if fwd >= gate else WARN
            draw.rounded_rectangle((x0, y0, max(end, x0 + s(7)), y1), radius=s(7),
                                   fill=color)

        draw_text(draw, (x0, y1 + s(3)), "{:.2f} m".format(fwd),
                  f.get(s(15), bold=True), INK)
        draw_text(draw, (x1, y1 + s(5)), "통과선 {:g} m".format(self.gate_m),
                  f.get(s(11)), MUTED, anchor="ra")

    def _draw_drift(self, draw, row):
        s = self._s
        f = self.fonts
        x0, y0, x1, y1 = self.drift_box

        lat = row.get("lat_m")

        draw.rounded_rectangle((x0, y0, x1, y1), radius=s(7),
                               fill=(255, 255, 255, 20))

        mid = (x0 + x1) / 2.0
        half = (x1 - x0) / 2.0

        # 축척. 기준값의 3배까지 담는다. 넘으면 끝에 붙는다.
        full = max(self.max_lat * 3.0, 0.03)

        for sign in (-1.0, 1.0):
            gx = mid + half * (sign * self.max_lat / full)
            draw.line((gx, y0, gx, y1), fill=_fade(GOOD, 150),
                      width=max(1, int(s(2))))

        draw.line((mid, y0 - s(3), mid, y1 + s(3)), fill=_fade(INK, 150), width=1)

        if lat is not None:
            ratio = min(max(lat / full, -1.0), 1.0)
            hx = mid + half * ratio
            color = GOOD if abs(lat) <= self.max_lat else WARN
            r = s(6)
            draw.ellipse((hx - r, (y0 + y1) / 2 - r, hx + r, (y0 + y1) / 2 + r),
                         fill=color)

            draw_text(draw, (x0, y1 + s(3)), "{:+.3f} m".format(lat),
                      f.get(s(15), bold=True), INK)

        draw_text(draw, (x1, y1 + s(5)), "기준 {:g} m".format(self.max_lat),
                  f.get(s(11)), MUTED, anchor="ra")

    def _draw_lamps(self, draw, row):
        s = self._s
        f = self.fonts

        state = self._trace_mod.running_verdict(
            self.trace, row, gate_m=self.gate_m,
            max_lateral_drift=self.max_lat,
            max_velocity_mae=self.max_mae,
            min_progress_m=self.gate_m,
            fell=self.fell,
        )

        order = (("생존", "survival"), ("전진", "progress"),
                 ("추종", "tracking"), ("방향", "direction"))

        w = self.lamp_w
        h = self.lamp_h

        x = self.col_c[0]
        y = self.inner_top

        for label, key in order:
            value = state[key]

            # 표시는 O · X · - 셋이다. 「통과 · 실패 · 미정」을 글자로 넣으면
            # 한 줄에 안 들어가고, **색만으로 두면 색을 못 가르는 사람이 못 읽는다.**
            if value is None:
                fill = (255, 255, 255, 16)
                edge = _fade(IDLE, 150)
                ink = _fade(MUTED, 215)
                mark = "-"
            elif value:
                fill = _fade(GOOD, 44)
                edge = _fade(GOOD, 190)
                ink = GOOD
                mark = "O"
            else:
                fill = _fade(BAD, 44)
                edge = _fade(BAD, 190)
                ink = BAD
                mark = "X"

            draw.rounded_rectangle((x, y, x + w, y + h), radius=s(7), fill=fill,
                                   outline=edge, width=1)

            # **한 줄이다.** 두 줄로 넣었더니 28 px 에서도 36 px 에서도 위아래
            # 글자가 겹쳤다 `확인됨` (2026-09-09). 한글 ascent 때문에 PIL 의
            # `mm` 기준점이 눈에 보이는 가운데와 다르다.
            draw_text(draw, (x + s(11), y + h / 2), label,
                      f.get(s(13), bold=True), ink, anchor="lm")
            draw_text(draw, (x + w - s(11), y + h / 2), mark,
                      f.get(s(14), bold=True), ink, anchor="rm")

            x += w + self.lamp_gap


def render_still(trace, size, frame_index, background=None, **kwargs):
    """영상 없이 한 장만. 시험과 눈으로 보기에 쓴다.

    `background` 가 없으면 짙은 회색 바탕에 그립니다. 글자가 읽히는지,
    자리가 겹치지 않는지를 영상을 만들기 전에 봅니다.
    """
    if background is None:
        background = Image.new("RGB", size, (34, 38, 46))

    painter = Hud(size, trace, **kwargs)

    return painter.draw(background, frame_index)


def missing_glyphs(font_path, text):
    """그 글꼴에 없는 글자. 있으면 화면에 네모가 나온다.

    `ImageFont` 로는 글리프 유무를 못 물으므로 `fontTools` 의 cmap 을 봅니다.
    `fontTools` 가 없으면 빈 목록을 돌려주는 대신 **죽습니다.** 「검사를 못
    했다」와 「검사를 통과했다」를 같은 값으로 돌려주면 안 됩니다.
    """
    from fontTools.ttLib import TTFont

    with io.open(font_path, "rb") as handle:
        font = TTFont(handle)

        covered = set()

        for table in font["cmap"].tables:
            covered.update(table.cmap.keys())

    return sorted({c for c in text if ord(c) not in covered})

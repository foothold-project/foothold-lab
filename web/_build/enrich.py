# -*- coding: utf-8 -*-
"""curriculum.html 에 도식 + 용어 툴팁을 주입한다. 원문 텍스트는 건드리지 않는다."""
import io, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figs import FIGURES
from refs import BY_SECTION, CSS as REFS_CSS
from field import BY_SECTION as FIELD_BY_SECTION, CSS as FIELD_CSS
from asciifigs import BY_KEY as ASCII_BY_KEY, CSS as ASCII_CSS
from sections import insert as insert_sections

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "curriculum.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else SRC

# ────────────────────────── 용어 사전 ──────────────────────────
# 형식: 표시어 → (제목, 설명HTML). 각 슬라이드에서 첫 등장 1회만 감싼다.
GLOSSARY = {
    "토크": ("토크 · torque",
        "<b>돌리는 힘</b>입니다. 미는 힘(N)과 다릅니다. 회전축을 중심으로 <b>얼마나 세게 비트는가</b>예요.<br>"
        "문손잡이를 잡고 돌릴 때, 손잡이 끝을 잡으면 쉽고 축 가까이를 잡으면 어렵죠. 같은 힘인데 토크가 다릅니다.<br>"
        "단위는 <b>N·m</b>. Go2 무릎은 <b>45.43 N·m</b>까지 냅니다."),
    "IMU": ("IMU · Inertial Measurement Unit · 관성 측정 장치",
        "<b>스마트폰에 든 그 센서입니다.</b> 폰을 기울이면 화면이 도는 것, 그게 IMU예요.<br>"
        "로봇이 <b>얼마나 기울었는지(자세)</b>와 <b>얼마나 빨리 도는지(각속도)</b>를 초당 500번 알려줍니다.<br>"
        "단 <b>위치나 속도는 못 잽니다</b>: 이게 A12에서 급소가 됩니다."),
    "DOF": ("DOF · Degree of Freedom · 자유도",
        "<b>독립적으로 움직일 수 있는 방향의 개수</b>입니다.<br>"
        "문은 경첩 하나로 열리니 1자유도, 사람 어깨는 앞뒤·좌우·회전이 되니 3자유도예요.<br>"
        "Go2는 다리 4개 × 관절 3개 = <b>12자유도</b>입니다."),
    "액추에이터": ("액추에이터 · actuator",
        "<b>실제로 움직이는 부품</b>. 로봇에서는 대개 모터를 말합니다.<br>"
        "센서가 '느끼는 쪽'이라면 액추에이터는 '움직이는 쪽'입니다."),
    "쿼터니언": ("쿼터니언 · quaternion",
        "<b>회전을 숫자 4개로 표현하는 방법</b>입니다.<br>"
        "각도 3개(롤·피치·요)로도 되지만, 그 방식은 특정 자세에서 축이 겹쳐 <b>계산이 무너지는 구간</b>이 생깁니다.<br>"
        "쿼터니언은 그 문제가 없어서 로봇·게임·항공에서 표준으로 씁니다. 뜻을 몰라도 쓸 수는 있습니다."),
    "각속도": ("각속도 · angular velocity",
        "<b>얼마나 빨리 회전하는가</b>. 속도가 '초당 몇 미터'라면 각속도는 <b>'초당 몇 도(또는 라디안)'</b>입니다.<br>"
        "IMU가 직접 재주는 값이라 로봇이 확실히 아는 몇 안 되는 숫자입니다."),
    "정책": ("정책 · policy",
        "<b>지금 상태를 보고 무엇을 할지 정하는 함수</b>입니다. 우리 경우엔 신경망이죠.<br>"
        "입력은 관측(숫자 42개), 출력은 관절 목표 각도 12개.<br>"
        "\"정책을 학습한다\" = \"이 신경망의 가중치를 조정한다\"입니다."),
    "보상": ("보상 · reward",
        "<b>잘했는지 못했는지를 알려주는 점수</b>. 매 순간 숫자 하나가 나옵니다.<br>"
        "강화학습은 이 점수의 합을 최대로 만들려고 합니다. <b>그래서 보상을 잘못 쓰면 엉뚱한 걸 잘하게 됩니다</b> (A10 보상 해킹)."),
    "에피소드": ("에피소드 · episode",
        "<b>시작부터 끝까지 한 판</b>입니다. 로봇을 세워놓고 걷게 하다가 넘어지거나 시간이 다 되면 한 에피소드가 끝나고 리셋됩니다.<br>"
        "게임 한 판이라고 생각하면 됩니다. 학습은 이 판을 수백만 번 반복합니다."),
    "관측": ("관측 · observation",
        "<b>정책이 매 순간 보는 숫자들의 묶음</b>입니다.<br>"
        "사람으로 치면 '지금 이 순간 내가 감지하는 모든 것'이에요. 여기 <b>안 들어간 정보는 정책이 절대 모릅니다.</b><br>"
        "그래서 관측 설계가 이 프로젝트의 급소입니다 (A12)."),
    "도메인 랜덤화": ("도메인 랜덤화 · domain randomization",
        "<b>시뮬레이션 조건을 매번 무작위로 흔드는 것</b>입니다. 마찰·무게·모터 세기·지연을 판마다 바꿉니다.<br>"
        "한 가지 조건에만 맞춘 정책은 현실에서 무너지니, 여러 조건을 겪게 해 <b>강건하게</b> 만듭니다.<br>"
        "⚠️ 많이 걸수록 좋은 게 아닙니다. 과하면 '아무 데서나 못하는' 정책이 됩니다."),
    "체크포인트": ("체크포인트 · checkpoint",
        "<b>학습 도중 저장해둔 신경망 상태 파일</b>입니다.<br>"
        "학습은 오래 걸리니 중간중간 저장하고, 나중에 그 지점부터 이어가거나 <b>학습 없이 재생만</b> 할 수 있습니다."),
    "하이퍼파라미터": ("하이퍼파라미터 · hyperparameter",
        "<b>학습을 시작하기 전에 사람이 정해줘야 하는 설정값</b>입니다. 학습률, 배치 크기, 에피소드 길이 같은 것들.<br>"
        "학습으로 저절로 정해지는 값(가중치)과 구분됩니다."),
    "온폴리시": ("온폴리시 · on-policy",
        "<b>지금 쓰는 정책으로 모은 데이터만 학습에 쓰는 방식</b>입니다. PPO가 여기 속합니다.<br>"
        "옛날 데이터를 재활용하지 않아 안정적이지만, 그만큼 <b>데이터를 많이 먹습니다</b>. 그래서 시뮬레이터가 필요합니다."),
    "sim-to-real": ("sim-to-real · 시뮬-현실 전이",
        "<b>시뮬레이션에서 배운 것을 실제 로봇에 옮기는 일</b>입니다.<br>"
        "이 프로젝트의 진짜 주제예요. 시뮬은 현실보다 너무 깨끗해서, <b>옮기는 순간 대부분 무너집니다.</b>"),
}


# 툴팁에서 백과 용어 사전으로 넘어가는 링크.
#  ★ 값은 glossary.py 의 실제 카드 slug 여야 한다. 아래에서 빌드 때 대조하고,
#    틀리면 빌드를 세운다. (죽은 앵커는 누르면 아무 데도 안 가는데 티가 안 난다.)
GLOSS_ANCHOR = {
    "토크": "torque", "IMU": "imu", "DOF": "dof",
    "액추에이터": "qdd", "쿼터니언": "quat", "각속도": "imu",
    "정책": "policy", "보상": "reward", "에피소드": "episode", "관측": "obs",
    "도메인 랜덤화": "domainrand", "체크포인트": "checkpoint",
    "하이퍼파라미터": "hparam", "온폴리시": "onpolicy", "sim-to-real": "sim2sim",
}

from glossary import SLUGS as _GS, NEW as _GN
_valid = set(_GS.values()) | {n[0] for n in _GN}
_dead = sorted(v for v in GLOSS_ANCHOR.values() if v and v not in _valid)
if _dead:
    raise SystemExit('[!] 용어 사전에 없는 앵커: %s' % ', '.join(_dead))
_missing = sorted(t for t in GLOSSARY if t not in GLOSS_ANCHOR)
if _missing:
    raise SystemExit('[!] 앵커가 지정되지 않은 툴팁 용어: %s' % ', '.join(_missing))

CSS = r"""
/* ═══ 도식 · 용어 (후처리 주입) ═══ */
figure.fdia{margin:1.35rem 0;background:var(--paper-2);border:1px solid var(--rule);padding:1rem 1.1rem .85rem;max-width:none;width:100%;overflow:visible!important}
figure.fdia svg{display:block;width:100%;height:auto;overflow:visible}
/* 기존 CSS가 figcaption 에 white-space:pre 를 상속시켜 줄바꿈이 죽는다. 명시적으로 해제 */
figure.fdia figcaption{font-size:.74rem;color:var(--ink-3);margin-top:.7rem;padding-top:.6rem;border-top:1px solid var(--rule);line-height:1.65;
  white-space:normal!important;overflow-wrap:break-word;word-break:keep-all;max-width:100%}
figure.fdia figcaption b{color:var(--ink-2)}
figure.fdia figcaption code{font-family:'Consolas','D2Coding',monospace;font-size:.94em;background:var(--card);padding:.05rem .25rem;border:1px solid var(--rule)}

/* 모바일: 그냥 축소하면 도식 글자가 6px 대로 떨어져 못 읽는다.
   표(.tw)와 같은 방식으로 가로 스크롤을 허용하고 최소 폭을 확보한다. */
@media (max-width:700px){
  figure.fdia{overflow-x:auto!important;overflow-y:visible;-webkit-overflow-scrolling:touch;
    padding:.85rem .8rem .7rem}
  figure.fdia svg{min-width:560px}
  figure.fdia figcaption{position:sticky;left:0;max-width:calc(100vw - 5rem)}
  figure.fdia::after{content:'← 좌우로 밀어서 보세요';display:block;position:sticky;left:0;
    font-size:.6rem;color:var(--ink-3);margin-top:.4rem;letter-spacing:.02em}
}

/* SVG 공용 클래스 */
.fdia .t-h{font-size:10.5px;font-weight:800;fill:var(--ink);text-anchor:middle}
.fdia .t-h2{font-size:9.6px;font-weight:800;fill:var(--ink);text-anchor:middle}
.fdia .t-h2-d{font-size:9.6px;font-weight:800;fill:var(--dim);text-anchor:middle}
.fdia .t-s{font-size:8.2px;fill:var(--ink-3);text-anchor:middle}
.fdia .t-s2{font-size:8.4px;fill:var(--ink-2);text-anchor:middle}
.fdia .t-s3{font-size:7.8px;fill:var(--ink-3);text-anchor:middle}
.fdia .t-n{font-size:8.8px;fill:var(--ink-2);text-anchor:middle}
.fdia .t-big{font-size:10.5px;font-weight:800;fill:var(--ink)}
.fdia .t-lab-n{font-size:8.4px;font-weight:700;fill:var(--note);text-anchor:middle}
.fdia .t-lab-d{font-size:8.4px;font-weight:700;fill:var(--dim)}
.fdia .t-lab-s{font-size:8.4px;font-weight:700;fill:var(--stop)}
.fdia .t-lab-c{font-size:8px;fill:var(--ink-3);text-anchor:middle}
.fdia .t-st-h{font-size:9.4px;font-weight:800;fill:var(--ink);text-anchor:middle}
.fdia .t-st-b{font-size:8.2px;fill:var(--ink-2);text-anchor:middle}
.fdia .t-formula{font-size:9.2px;font-weight:700;fill:var(--dim);text-anchor:middle;font-family:'Consolas',monospace}
.fdia .t-formula2{font-size:8.8px;font-weight:700;fill:var(--ink);text-anchor:middle;font-family:'Consolas',monospace}
.fdia .t-mini-b{font-size:9px;font-weight:800;fill:var(--stop);text-anchor:middle}
.fdia .t-mini-b2{font-size:9px;font-weight:800;fill:var(--dim);text-anchor:middle}
.fdia .t-mini-s{font-size:7.6px;fill:var(--ink-3);text-anchor:middle}
.fdia .t-ring-h{font-size:9.6px;font-weight:800;fill:var(--ink);text-anchor:middle}
.fdia .t-ring-big{font-size:19px;font-weight:800;fill:var(--dim);text-anchor:middle}
.fdia .t-ring-big2{font-size:19px;font-weight:800;fill:var(--note);text-anchor:middle}
.fdia .t-ring-s{font-size:8px;fill:var(--ink-2);text-anchor:middle}
.fdia .t-alert-h{font-size:9.6px;font-weight:800;fill:var(--stop)}
.fdia .t-alert-b{font-size:8.4px;font-weight:700;fill:var(--ink)}
.fdia .t-alert-s{font-size:7.9px;fill:var(--ink-2)}
.fdia .t-alert-i{font-size:7.9px;font-style:italic;fill:var(--stop)}
.fdia .t-key-h{font-size:9.4px;font-weight:800;fill:var(--dim)}
.fdia .t-key-b{font-size:8.4px;fill:var(--ink)}
.fdia .t-key-s{font-size:7.9px;fill:var(--ink-2)}
.fdia .t-key-i{font-size:7.9px;font-style:italic;fill:var(--ink-3)}
.fdia .t-em{font-weight:800;fill:var(--stop)}
.fdia .t-list-d{font-size:8.4px;fill:var(--ink-2)}
.fdia .t-list-s{font-size:8.4px;fill:var(--ink)}
.fdia .t-list-b{font-size:8.4px;font-weight:700;fill:var(--ink)}
.fdia .t-num{font-size:8.6px;font-weight:800;fill:var(--dim)}
.fdia .t-num-big{font-size:12px;font-weight:800;fill:var(--dim)}
.fdia .t-x{font-size:7.8px;font-weight:700;fill:var(--stop)}

.fdia .t-lab-d2{font-size:9px;font-weight:800;fill:var(--dim);text-anchor:middle}
.fdia .t-lab-s2{font-size:9px;font-weight:800;fill:var(--stop);text-anchor:middle}
.fdia .t-alert-h2{font-size:9.6px;font-weight:800;fill:var(--stop);text-anchor:middle}
.fdia .t-alert-b2{font-size:8.6px;font-weight:700;fill:var(--stop);text-anchor:middle}
.fdia .t-alert-i2{font-size:7.9px;font-style:italic;fill:var(--stop);text-anchor:middle}
.fdia .t-em2{font-weight:800;fill:var(--dim)}
.fdia .s-box{fill:var(--paper-2);stroke:var(--ink-2);stroke-width:1.3}
.fdia .s-panel{fill:var(--card);stroke:var(--rule);stroke-width:1.2}
.fdia .s-panel-d{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.3}
.fdia .s-alert{fill:var(--stop-soft);stroke:var(--stop);stroke-width:1.4}
.fdia .s-key{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.2}
.fdia .s-stage{fill:var(--card);stroke:var(--ink-2);stroke-width:1.3}
.fdia .s-stage-k{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.6}
.fdia .s-mini-s{fill:var(--stop-soft);stroke:var(--stop);stroke-width:1}
.fdia .s-mini-d{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1}
.fdia .s-code{fill:var(--paper-2);stroke:var(--ink-3);stroke-width:1}
.fdia .s-code-s{fill:var(--card);stroke:var(--stop);stroke-width:1}
.fdia .s-leg{stroke:var(--ink);stroke-width:2.6;stroke-linecap:round}
.fdia .s-leg2{stroke:var(--ink);stroke-width:3.2;stroke-linecap:round}
.fdia .s-arc{fill:none;stroke:var(--note);stroke-width:1.2;stroke-dasharray:3 2}
.fdia .s-rule{stroke:var(--rule);stroke-width:1}
.fdia .s-rule-s{stroke:var(--stop);stroke-width:1;opacity:.4}
.fdia .s-axis{stroke:var(--ink-3);stroke-width:1.1}
.fdia .s-flow{stroke:var(--ink-2);stroke-width:1.5}
.fdia .s-flow-b{stroke:var(--ink-3);stroke-width:1.2;stroke-dasharray:4 3}
.fdia .s-grav{stroke:var(--note);stroke-width:1.8}
.fdia .s-grav-d{stroke:var(--dim);stroke-width:1.8}
.fdia .s-curve-d{fill:none;stroke:var(--dim);stroke-width:2.2}
.fdia .s-curve-s{fill:none;stroke:var(--stop);stroke-width:1.8}
.fdia .s-ring-d{fill:var(--dim-soft);stroke:var(--dim);stroke-width:1.6}
.fdia .s-ring-n{fill:var(--note-soft);stroke:var(--note);stroke-width:1.6}
.fdia .f-ink{fill:var(--ink)} .fdia .f-dim{fill:var(--dim)}
.fdia .f-note{fill:var(--note)} .fdia .f-stop{fill:var(--stop)}

/* 용어 툴팁: 올려두면 설명, 누르면 용어 사전으로 간다 */
.term{border-bottom:2px dotted var(--note);cursor:pointer;font-weight:700;color:inherit;
  text-decoration:none}
.term:hover{border-bottom-style:solid}
/* .pop 은 내용 보관용일 뿐: 화면에 뜨는 건 body 직속 #termpop 이다.
   이유: section.slide 에 animation(transform)이 걸려 있어 그 안에서는 position:fixed 가
   섹션 기준으로 잡힌다(CSS 명세). 조상 transform 을 피하려면 body 로 빼내는 수밖에 없다. */
.term>.pop{display:none}
#termpop{position:fixed;z-index:99999;display:none;
  width:min(370px,calc(100vw - 24px));background:var(--ink);color:var(--paper);
  padding:.7rem .8rem;font-size:.73rem;font-weight:400;line-height:1.6;text-align:left;
  box-shadow:0 8px 28px rgba(0,0,0,.32);pointer-events:none;white-space:normal;
  word-break:keep-all;overflow-wrap:break-word;
  font-family:'Pretendard','Malgun Gothic','Segoe UI',system-ui,sans-serif;
  animation:popIn .14s ease}
#termpop.on{display:block}
@keyframes popIn{from{opacity:0;transform:translateY(4px)}to{opacity:1;transform:none}}

/* ★ 팝업은 배경이 항상 뒤집힌다(bg=--ink, 글자=--paper).
   그래서 강조색도 뒤집어 잡아야 한다. 평소 쓰는 --dim/--note 를 그대로 쓰면
   밝은 모드에서 '어두운 배경 + 어두운 청록'이 되어 안 보인다. */
#termpop{--pop-a:#3ec7b4;--pop-n:#e2a53c}
@media (prefers-color-scheme:dark){#termpop{--pop-a:#0a5f56;--pop-n:#8a5600}}
:root[data-theme="dark"] #termpop{--pop-a:#0a5f56;--pop-n:#8a5600}
:root[data-theme="light"] #termpop{--pop-a:#3ec7b4;--pop-n:#e2a53c}
#termpop b{color:var(--pop-a)}
#termpop .ph{display:block;font-weight:800;color:var(--paper);margin-bottom:.35rem;
  padding-bottom:.3rem;border-bottom:1px solid rgba(255,255,255,.18);font-size:.75rem}
/* 사전으로 가는 안내줄 */
#termpop .pmore{display:block;margin-top:.5rem;padding-top:.4rem;font-size:.68rem;font-weight:700;
  color:var(--pop-n);border-top:1px solid rgba(255,255,255,.18)}
@media (hover:none){ #termpop .pmore::after{content:': 한 번 더 누르면 이동';opacity:.75;font-weight:400} }
@media print{.term{border-bottom:none}#termpop{display:none!important}}
"""

JS = r"""
/* 용어 툴팁: body 직속 단일 팝업(포털)으로 띄운다.
   section.slide 의 animation transform 때문에 슬라이드 안에서는 position:fixed 가 깨지고,
   .tw(표 래퍼)·pre 의 overflow:auto 는 absolute 를 잘라낸다. 포털이 둘 다 피하는 유일한 방법. */
(function(){
  var GAP = 10, PAD = 12, box = null, cur = null;

  function el(){
    if (!box){ box = document.createElement('div'); box.id = 'termpop'; document.body.appendChild(box); }
    return box;
  }
  function hide(){ if (box) box.classList.remove('on'); cur = null; }

  function show(t){
    if (cur === t) return;
    var src = t.querySelector('.pop');
    if (!src) return;
    var p = el();
    p.innerHTML = src.innerHTML;
    p.classList.add('on');
    cur = t;
    var r = t.getBoundingClientRect(), w = p.offsetWidth, h = p.offsetHeight;
    var left = r.left;
    if (left + w > window.innerWidth - PAD) left = window.innerWidth - w - PAD;
    if (left < PAD) left = PAD;
    var top = r.top - h - GAP;                  // 기본은 위
    if (top < PAD) top = r.bottom + GAP;        // 위가 좁으면 아래로
    if (top + h > window.innerHeight - PAD) top = Math.max(PAD, window.innerHeight - h - PAD);
    p.style.left = Math.round(left) + 'px';
    p.style.top  = Math.round(top)  + 'px';
  }

  document.addEventListener('mouseover', function(e){
    var t = e.target.closest && e.target.closest('.term');
    if (t) show(t); else if (cur) hide();
  });
  /* .term 은 <a href="encyclopedia.html#t-…"> 다. 클릭은 막지 않는다. 사전으로 간다.
     다만 터치 기기에는 hover 가 없어서, 그대로 두면 설명을 볼 방법이 사라진다.
     그래서 손가락에서는 첫 탭 = 설명, 두 번째 탭 = 이동. */
  var TOUCH = !window.matchMedia || window.matchMedia('(hover: none)').matches;
  document.addEventListener('click', function(e){
    var t = e.target.closest && e.target.closest('.term');
    if (!t){ hide(); return; }
    if (TOUCH && cur !== t){ e.preventDefault(); show(t); return; }
    hide();                       /* 이동 직전 팝업을 지운다. 뒤로가기로 돌아오면 남아 있다 */
  });
  ['scroll','resize'].forEach(function(ev){ window.addEventListener(ev, hide, true); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') hide(); });
})();
"""


# 절마다 라벨이 다르다. 도식이 들어갈 블록을 명시한다
ANCHORS = {
    'A2':  '무엇을 배우나',
    'A3':  '무엇을 배우나',
    'A4':  '무엇을 배우나',
    'A5':  '이 순환이 초당 50번 돕니다',
    'A9':  '반드시 읽을 줄 알아야 하는 네 개',
    'A10': '왜 이게 가장 중요한가',
    'A12': '넣으면 실제 로봇에서 무너지는 것',
}


def replace_ascii(html):
    """ASCII 아트 도식(<pre class="dia">)을 SVG 도식으로 교체한다.
       폰트·자간에 따라 어긋나고 모바일·PDF에서 정렬이 무너지기 때문."""
    done = []
    def sub(m):
        body = m.group(1)
        for key, svg in ASCII_BY_KEY.items():
            if key in body:
                done.append(key)
                return svg
        return m.group(0)          # 못 찾으면 원본 유지
    out = re.sub(r'<pre class="dia">(.*?)</pre>', sub, html, flags=re.S)
    left = len(re.findall(r'<pre class="dia">', out))
    print('ASCII 교체 : %d개 / 남은 <pre class="dia"> %d개%s'
          % (len(done), left, '' if left == 0 else '  [!] 키를 못 찾은 것이 있다'))
    return out


def fix_init_crash(html):
    """★ 첫 화면이 빈 채로 뜨던 버그 수정.

       원본에 `backdrop.addEventListener('click', closeToc)` 가
       `window.closeToc = function(){...}` **보다 먼저** 나온다.
       그 시점에 closeToc 은 아직 없으므로 ReferenceError 가 나고,
       스크립트가 거기서 죽어 마지막 줄의 go(start) 가 실행되지 않는다.
       → 슬라이드에 .on 이 하나도 안 붙어 화면이 백지가 된다.

       조회를 클릭 시점으로 미루면 해결된다(그때는 window.closeToc 이 있다).
       원본을 고치지 않고 빌드에서 처리해, 팀원이 base 파일을 갱신해도 유지된다.
    """
    old = "backdrop.addEventListener('click', closeToc);"
    new = ("backdrop.addEventListener('click', function(){ closeToc(); });"
           "  /* 정의보다 먼저 참조돼 ReferenceError → 첫 화면 백지. 조회를 클릭 시점으로 미룸 */")
    if old not in html:
        print('  [!] closeToc 초기화 버그 패턴을 못 찾음. 원본이 바뀌었는지 확인 필요')
        return html
    return html.replace(old, new, 1)


def restyle_chrome(html):
    """상단 '테마' 버튼 → 우리 규칙(표지로 + PDF)으로 교체하고, 하단 이전/다음 바를 낮춘다."""
    # 1) 테마 버튼 교체
    old_btn = '<button class="tbtn" id="themeBtn" type="button">테마</button>'
    new_btn = ('<a class="tbtn home" href="index.html">← 표지로</a>\n'
               '    <button class="tbtn pdf" id="pdfBtn" type="button" '
               'title="브라우저 인쇄 창이 열립니다. 대상에서 &quot;PDF로 저장&quot;을 선택하세요.">PDF</button>')
    if old_btn not in html:
        raise SystemExit('[!] 테마 버튼 마크업을 못 찾음. 원본이 바뀌었는지 확인 필요')
    html = html.replace(old_btn, new_btn, 1)

    # 2) 테마 토글 JS 제거 (요소가 사라져 null 참조로 죽는다)
    a = html.find("document.getElementById('themeBtn')")
    if a > 0:
        b = html.find('});', a) + 3
        # ★ 2026-09-08 감사 F-05. 여기도 방어 없이 붙였다. 바로 윗줄 주석이
        #   「요소가 사라져 null 참조로 죽는다」고 적어 두고서 같은 실수를 했다.
        html = html[:a] + ("(function(){var b=document.getElementById('pdfBtn');"
                           "if(b)b.addEventListener('click',function(){window.print();});})();"
                           ) + html[b:]
    return html


CHROME_CSS = r"""
.prefs{margin:1.6rem 0 .4rem}
.prefs-h{font-size:.6rem;font-weight:800;letter-spacing:.15em;text-transform:uppercase;
  color:var(--dim);padding-bottom:.4rem;margin-bottom:.2rem;border-bottom:1px solid var(--rule)}

/* ═══ 상단바·하단바 정돈 (우리 페이지 규칙에 맞춤) ═══ */
.topbar .tbtn.home{text-decoration:none;display:inline-block}
.topbar .tbtn.pdf{font-weight:700;letter-spacing:.04em}

/* 하단 이전/다음. 2줄 스택이라 세로를 과하게 먹었다. 한 줄로 눕힌다. */
.navbar .row{padding:.4rem 1.5rem;gap:.5rem;align-items:stretch}
/* 2026-09-05 팀장 지적 「아래 네비게이션 바 제대로 얼라인 맞추라」. 두 번째다.
   .t 가 flex:1 1 auto 라 제목이 남는 폭을 다 먹었고, 첫 장에서는 이전 제목이
   비어 그 빈 상자가 가운데를 벌렸다. 높이도 baseline 정렬이라 서로 달랐다.
   두 버튼을 flex:1 1 0 으로 반반 나누고 높이를 stretch 로 맞춘다. */
.nbtn{flex:1 1 0;min-width:0;flex-direction:row!important;align-items:center;
  gap:.5rem;padding:.34rem .75rem}
.nbtn.next{flex-direction:row-reverse!important;justify-content:flex-start}
.nbtn .d{font-size:.6rem;flex:0 0 auto}
.nbtn .t{font-size:.76rem;flex:1 1 auto;min-width:0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nbtn.next .t{text-align:right}
.nbtn:disabled,.nbtn[disabled]{opacity:.45}
@media (max-width:700px){
  .navbar .row{padding:.34rem 1.1rem;gap:.4rem}
  .nbtn{padding:.3rem .6rem;gap:.35rem}
  .nbtn .d{font-size:.56rem}
  .nbtn .t{font-size:.7rem}
}
@media print{.topbar .tbtn.home,.topbar .tbtn.pdf{display:none!important}}

/* ═══════════ 인쇄 / PDF ═══════════
   원본 인쇄 CSS는 4줄뿐이라 PDF가 54쪽 백지로 나왔다. 원인 두 가지:
   ① .slide 에 animation:fade 가 걸려 있어 인쇄 캡처 시 opacity 0 상태로 잡힌다
      (kickoff.html 에는 opacity:1!important 가 있어서 정상이었다)
   ② @page 규격이 없어 US Letter 로 나온다 (다른 문서는 A4)
   ─────────────────────────────────── */
@page{ size:A4; margin:14mm 12mm; }
@media print{
  html{font-size:11.5px}
  html,body{height:auto!important;overflow:visible!important;background:#fff!important}
  .shell{display:block!important}
  .side,.topbar,.navbar,.backdrop,#termpop{display:none!important}
  main{max-width:none!important;padding:0!important;margin:0!important}
  /* ★ 백지의 원인: 애니메이션 초기 상태(opacity:0)로 캡처되는 것을 막는다 */
  /* ★ 크롬은 flex 컨테이너의 페이지 분할이 불안정해 SVG가 쪼개진다 → 인쇄에서는 block */
  .slide{
    display:block!important;
    animation:none!important;
    opacity:1!important;
    visibility:visible!important;
    transform:none!important;
    break-after:page;
    gap:1rem;
  }
  .slide:last-child{break-after:auto}
  /* 잘리면 안 되는 덩어리 */
  figure.fdia,figure.fdia svg,pre.dia,table,tr,.mini{break-inside:avoid;page-break-inside:avoid}
  figure.fdia{background:#fff!important;page-break-inside:avoid}
  /* ★ A4 세로 폭이 595px 라 모바일 규칙(max-width:700px)이 인쇄에도 걸린다.
     overflow-x:auto 가 SVG를 잘라내고 sticky 캡션이 흘러내린다. 전부 해제한다. */
  figure.fdia{overflow:visible!important;padding:1rem 1.1rem .85rem!important}
  figure.fdia svg{min-width:0!important;width:100%!important;max-width:100%!important}
  figure.fdia figcaption{position:static!important;max-width:none!important}
  figure.fdia::after{content:none!important;display:none!important}
  .term{border-bottom:none!important}
  a[href]::after{content:''}                   /* URL 자동 노출 방지 */
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}

"""


def insert_point(sec, anchor):
    """지정한 라벨이 든 .blk 블록이 완전히 닫힌 직후 위치를 돌려준다.
       라벨(.lbl)이나 리스트 안에 끼어들지 않도록 div 깊이를 세어 매칭한다."""
    a = sec.find(anchor)
    if a < 0:
        return None
    # 뒤로 훑어 감싸고 있는 .blk 의 여는 태그를 찾는다
    start = sec.rfind('<div class="blk">', 0, a)
    if start < 0:
        return None
    # 깊이를 세며 매칭되는 </div> 를 찾는다
    depth, i = 0, start
    tag = re.compile(r'<(/?)div\b[^>]*>')
    while True:
        m = tag.search(sec, i)
        if not m:
            return None
        depth += -1 if m.group(1) else 1
        i = m.end()
        if depth == 0:
            return i           # 매칭 </div> 바로 뒤


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def wrap_terms(html):
    """각 <section> 안에서 용어당 첫 등장 1회만 <span class='term'>으로 감싼다.

       ★ 반드시 '원문 위치를 먼저 수집 → 뒤에서 앞으로 치환' 해야 한다.
         앞에서부터 치환하면, 방금 주입한 툴팁 설명문 안의 단어가 다시 잡혀
         팝업이 중첩된다(예: IMU 설명문에 '각속도'가 들어 있다)."""
    terms = sorted(GLOSSARY.keys(), key=len, reverse=True)
    stats = {}
    SKIP = re.compile(r'<(/?)(svg|style|script|figcaption|code|pre)\b', re.I)

    def process_section(sec):
        used = set()
        parts = re.split(r'(<[^>]+>)', sec)
        skip = 0
        hits = []                      # (part_index, start, end, term)
        for i, p in enumerate(parts):
            if p.startswith('<'):
                m = SKIP.match(p)
                if m:
                    skip += -1 if m.group(1) else 1
                    skip = max(0, skip)
                continue
            if skip > 0 or not p.strip():
                continue
            for t in terms:
                if t in used:
                    continue
                j = p.find(t)
                if j < 0:
                    continue
                # 이미 잡힌 구간과 겹치면 건너뛴다
                if any(pi == i and not (j + len(t) <= a2 or j >= b2)
                       for pi, a2, b2, _ in hits):
                    continue
                hits.append((i, j, j + len(t), t))
                used.add(t)

        # 같은 조각 안에서는 뒤에서 앞으로 치환해야 인덱스가 안 밀린다
        for i, a2, b2, t in sorted(hits, key=lambda h: (-h[0], -h[1])):
            title, body = GLOSSARY[t]
            anchor = GLOSS_ANCHOR.get(t, '')
            href = 'encyclopedia.html#t-' + anchor if anchor else 'encyclopedia.html#glossary'
            more = ('<span class="pmore">→ 용어 사전에서 자세히 · 공식 문서 링크</span>')
            pop = ('<span class="pop"><span class="ph">%s</span>%s%s</span>'
                   % (title, body, more))
            parts[i] = (parts[i][:a2]
                        + '<a class="term" href="%s" data-t="%s">%s%s</a>' % (href, t, t, pop)
                        + parts[i][b2:])
            stats[t] = stats.get(t, 0) + 1
        return ''.join(parts)

    out = re.sub(r'(<section class="slide".*?</section>)',
                 lambda m: process_section(m.group(1)), html, flags=re.S)
    return out, stats


def main():
    html = io.open(SRC, encoding='utf-8').read()
    orig_len = len(html)

    # 0) 신설 절 삽입: 용어 감싸기보다 먼저 해야 새 절에도 툴팁이 붙는다
    html = insert_sections(html)

    # 1) 용어 툴팁: ★ 반드시 도식보다 먼저.
    #    나중에 하면 SVG 안의 텍스트(IMU 등)까지 <span>으로 감싸 SVG 파싱이 끊긴다.
    html, stats = wrap_terms(html)

    # 3) CSS / JS 주입
    # 2) 도식 주입 (용어 처리가 끝난 뒤): 각 섹션의 '무엇을 배우나' 블록 끝(</div>) 뒤
    placed = []
    for sid, figure in FIGURES.items():
        pat = re.compile(r'(<section class="slide"[^>]*data-id="%s">.*?)(?=</section>)' % sid, re.S)
        m = pat.search(html)
        if not m:
            print('  [!] 섹션 못 찾음: %s' % sid)
            continue
        sec = m.group(1)
        ins = insert_point(sec, ANCHORS[sid])
        if ins is None:
            print('  [!] 삽입 지점 못 찾음: %s (앵커 "%s")' % (sid, ANCHORS[sid]))
            continue
        new_sec = sec[:ins] + figure + sec[ins:]
        html = html[:m.start(1)] + new_sec + html[m.end(1):]
        placed.append(sid)

    # 2.4) 실전 기록(Layer 2/3) 주입: 절 본문 끝
    placed_field = []
    for sid, blk in FIELD_BY_SECTION.items():
        pat = re.compile(r'(<section class="slide"[^>]*data-id="%s">.*?)(?=</section>)' % re.escape(sid), re.S)
        m = pat.search(html)
        if not m:
            print('  [!] 실전 기록 대상 절 없음: %s' % sid)
            continue
        html = html[:m.end(1)] + blk + html[m.end(1):]
        placed_field.append(sid)

    # 2.5) 논문 카드 주입: 절 끝(마지막 </div> 뒤, </section> 앞)에 붙인다
    placed_refs = []
    for sid, papers in BY_SECTION.items():
        pat = re.compile(r'(<section class="slide"[^>]*data-id="%s">.*?)(?=</section>)' % re.escape(sid), re.S)
        m = pat.search(html)
        if not m:
            print('  [!] 논문 카드 대상 절 없음: %s' % sid)
            continue
        block = ('\n<div class="prefs">\n'
                 '<div class="prefs-h">이 절의 근거: 원문으로 이어집니다</div>\n'
                 + ''.join(papers) + '</div>\n')
        html = html[:m.end(1)] + block + html[m.end(1):]
        placed_refs.append('%s(%d)' % (sid, len(papers)))

    # 3) 상단바 '테마' → 표지로 + PDF, 하단바 높이 축소
    html = replace_ascii(html)
    html = fix_init_crash(html)
    html = restyle_chrome(html)

    style = CSS + CHROME_CSS + REFS_CSS + FIELD_CSS + ASCII_CSS
    if '</style>' not in html:
        raise SystemExit('[!] </style> 를 찾지 못해 CSS 주입 실패')
    html = html.replace('</style>', style + '\n</style>', 1)
    # 주입 확인: 조용히 빠지면 화면이 통째로 깨진다
    for name, probe in [('도식', '.fdia .t-h{'), ('논문', '.pref{'), ('실전', '.fld{'), ('ASCII', '.fdia .a-h{')]:
        if probe not in html:
            raise SystemExit('[!] %s CSS 가 주입되지 않음 (%s)' % (name, probe))
    if '</body>' in html:
        html = html.replace('</body>', '<script>%s</script>\n</body>' % JS, 1)

    leak = sum(m.group(1).count('<span class="term">')
               for m in re.finditer(r'<svg[^>]*>(.*?)</svg>', html, re.S))
    if leak:
        raise SystemExit('[!] SVG 안에 용어 span 이 %d건 주입됨. SVG 파싱이 깨진다' % leak)

    io.open(OUT, 'w', encoding='utf-8').write(html)

    print('도식 주입 : %d개  → %s' % (len(placed), ', '.join(placed)))
    print('실전 기록 : %s' % (', '.join(placed_field) or '없음'))
    print('논문 카드 : %s' % (', '.join(placed_refs) or '없음'))
    print('용어 감쌈 : %d종 / 총 %d회' % (len(stats), sum(stats.values())))
    for t in sorted(stats, key=lambda x: -stats[x]):
        print('   %-14s %d회' % (t, stats[t]))
    print('크기      : %s → %s bytes' % (format(orig_len, ','), format(len(html), ',')))


if __name__ == '__main__':
    main()

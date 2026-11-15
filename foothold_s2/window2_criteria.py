"""창 2 자동 기동 판정 기준 (SONNET-X25). 결과를 보기 전에 이 파일로 고정하고, 판정 json 에 이 파일의 SHA 를 남긴다. 결과를 보고 고치지 않는다.

팀장 원문(10/25 lead 전달): '창 1 두 판이 모두 ① Traceback · OOM 0, ② 고정 칸 평가에서 복원 지도 전진 · 생존이 부모 GT 기준선보다 0.10 넘게 떨어지지 않으면,
창 2(추가 250회, B 설정 그대로)를 GPU0에서 EX-30 → EX-31 순서로 자동 기동한다. 하나라도 어기면 멈추고 아침에 보고.'

해석(lead 지시문 그대로):
  - 비교 대상: 부모 B1500 의 모드 eval_gt(정답 지도) 대 자식 model_1750 의 모드 eval_pred(복원 지도), 같은 고정 지형 칸.
  - 전진 = 명령 fwd0.5 · fwd1.0 각각의 body_vx_integral_median_m 이 부모 값의 VX_RATIO_MIN 배 이상.
  - 생존 = 같은 두 명령 각각의 alive_envs_at_end / envs 가 (부모 비율 - ALIVE_DROP_MAX) 이상.
  - 두 판(EX-30, EX-31) 모두, 두 명령 모두 통과해야 한다. 하나라도 어기면 통과 아님.
  - 부모 전진 값이 0 이하면 비율 기준이 뜻이 없어 통과시키지 않는다(사유에 적는다).
  - Traceback · OOM 0 은 창 1 두 판의 train.log 와 세 평가의 run.log 에서 센다. 창 1 이 DONE 으로 끝나지 않았거나 산출물이 빠졌으면 통과 아님.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

COMMANDS = ("fwd0.5", "fwd1.0")
PARENT_MODE = "eval_gt"
CHILD_MODE = "eval_pred"
VX_KEY = "body_vx_integral_median_m"
ALIVE_KEY = "alive_envs_at_end"
VX_RATIO_MIN = 0.90
ALIVE_DROP_MAX = 0.10
BAD_LOG_PATTERNS = ("Traceback", "out of memory", "OutOfMemory")          # 대소문자 구분 없이 센다
PARENT_ITER = 1500
CHILD_ITER = 1750


def criteria_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()           # 줄바꿈이 CRLF 든 LF 든 같은 값

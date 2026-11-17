"""복원 지도 오프라인 가르기 (설계 DESIGN-MAP-EDGE-1117 2.3 ㄱ · 7 절 4): CPU 탐침 자식. 얼린 정본 3 이 정답 지도로 걷는 동안 (--modes eval_gt) TRNet 의 입력 · 정답을 적는다.
적는 것 (깊이가 갱신되는 틱 · 리셋 직후 첫 스텝만 = h_terr 가 바뀌는 스텝, 50 Hz 5 스텝에 한 번): env 번호 · 호출 번호 · first (리셋 직후) · depth2 (2, 60, 60) float16 ·
z_prop (TRNet.step 이 받는 몸감각 요약 128) · gt_map (32, 16). 정책 · 평가기 · 학습 코드는 안 바뀐다 (이 프로세스 안에서 StartPerception._advance 를 감쌀 뿐 · 값은 그대로 돌려줌).
쓰는 법: MAPFIT_OUT=<npz 경로> python -B -m foothold_s2.eval.ex42_mapfit_record_child <eval_map_modes 인자 (--modes eval_gt)>   (끝나면 MAPFIT_OUT 에 한 파일)"""
import os
import runpy
import sys

from foothold_s2.eval.ex42_mapfit_record import Recorder

recorder = Recorder()
recorder.install()
_real_exit = os._exit


def _save_then_exit(code=0):
    """eval_map_modes 는 끝에서 os._exit(0) 로 나가 finally 가 안 돈다: 나가기 전에 저장한다."""
    try:
        recorder.save(os.environ["MAPFIT_OUT"])
    finally:
        _real_exit(code)


os._exit = _save_then_exit
sys.argv = ["eval_map_modes"] + sys.argv[1:]
try:
    runpy.run_module("foothold_s2.eval.eval_map_modes", run_name="__main__")
finally:
    recorder.save(os.environ["MAPFIT_OUT"])

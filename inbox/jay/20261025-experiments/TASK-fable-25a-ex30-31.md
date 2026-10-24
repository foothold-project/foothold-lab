> 분류: 리서치
> 작성: 오흥재 · lead_tmp · 2026-10-25
> 근거: 팀장 직접 「설계 문서까지 작성하고 fable 세션에서 설계안을 검증」 · 이번 설계 묶음
> 요지: EX28 이후 두 전이판이 본류를 진전시키는지, 구체 과정과 관측·비교·재개 계약을 비판적으로 한 번 검토한다.
> 상태: 검토 의뢰 · 코드/GPU/학습/프로세스 변경 금지

# FABLE25a · EX30/31 설계 검토

팀장은 현재 lead_tmp 창에서 대화하며 이번 문서화·검토·lead 인계를 직접 요청했다. 원래 lead는 Claude 한도가 복구돼 다시 맡을 예정이고, Codex 잔여한도 때문에 새 Codex 작업자를 쓰지 않는다. **검토자는 Fable 기존 세션**, 대체 Codex 검토자가 아니다.

읽을 것: 이 폴더 `DESIGN-EX30-31.md` 전문, `IMPLEMENT-EX30-31.md`, `REQUIREMENTS-EX30-31.md`. 과거 사실은 인접23-experiments `RESULT-B1500-1024.md`, `VERIFY-astra-24f-requirements.md`의 관련 절. 실행 코드 `C:/mai/wt/foothold-lab/lead-tmp-start-b`@d9517fb9는 읽기만. 특히 `runners/sol23f_runner.py:222~233`, `start_runner.py:609~665`, `models/start_perception.py:132~170,185~232`, `sensors/depth_cam_cfg.py`, `sensors/depth_aug.py`, `commands/mixed_core.py`를 직접 확인한다. 논문은 START §II-C/D와 JEPLO §V.

팀장 확정: 두 판 **B1500에서 이어받기**. 위험 셋은 최초복원소비·action std·부모버릇. 아직장기기동승인아님. 과제는START구성위에우리뒤/옆·깃발·연속7종·성과curriculum·DR확대를올리는것이며,원문그대로scratch재현이아니다. 한계를숨기지말고가장치명적인틀린설계부터반박한다.

물음:
1. 두판의목적이현재최선인가? GT대조의필요/비용/해석한계,prop-only요구가유보된것은정직하고타당한가?
2. P0/P1/P2·C1/C2·DR의상충/순환전제/죽은확대경로,표확률·범위·평가horizon·8m타일위반은없는가? 80%·표본·두창규칙이너무쉽거나과도한가? 수치는우리제안임.
3. 같은부모·초기std/LR·과정journal·명령/RNG·동일확대에서대조가성립하는가? 첫force_gt전환과새episodeRNNreset은안전한가? 기존resume를무력화하지않는가?
4. 카메라·AUG·100ms깊이지연·물리/행동지연과원문/기존설계차이를제대로구분했는가? 계단뒤/옆의관측한계를숨기지않는가?
5. 우회전계측·정강이접촉·토크한계·미끄럼·지도/episode시간축·조기종료편향·실제소비시험에치명적결측이있는가?
6. 구현범위가너무커서성과가늦어지는가? 본류의요구를잊지않으면서첫동작가능묶음을더작게만들수있다면정확히어디까지인지제안. 새승인절차를마구추가하지말것.

산출물: 자신의 독립worktree에 `inbox/jay/20261025-experiments/VERIFY-fable-25a.md` **한 파일**. 머리5줄, 첫본문한문장판정. 각지적에파일/절·재현가능한반례·최소수정. 구현코드·기존원자료수정/GPU/프로세스종료/학습/push금지. 필요하면순수CPU계산만. 완료때파일절대경로와검토한설계커밋을lead_tmp에알려달라. 검토한번뒤중대한오류수정경로만한번재확인,무한전체반복은하지않는다.

# A/정책학습

학습 설정 · 보상 · 관측 · 파인튜닝. 담당 임석헌.

> 폴더는 이슈의 «작업 영역» 라벨과 1:1 이다.
> 이 자리에 넣을 것이 생기면 브랜치를 파고 PR 로 올린다. inbox 를 거치지 않는다.

## gap_training 뿌리 8개 (2026-09-22 추가)

이 자리가 **정본**이다. IsaacLab 설치 폴더의 같은 이름 파일은 **사본**이다.

    정본   sim/policy/
    사본   C:\isaac\IsaacLab\...\locomotion\velocity\config\go2\gap_training\

**왜 사본이 필요한가.** IsaacLab 은 `isaaclab_tasks/__init__.py:39` 의
`import_packages()` 가 패키지 `__path__` 를 훑으며 import 할 때만 태스크를
`gym` 에 등록한다 (`utils/importer.py:15~41`). 우리 `sim/policy/` 는 그
`__path__` 안에 없다. `sys.path` 에 붙여도(`.pth`) `import_packages` 가 안
걸어간다. **트리 안에 파일이 있어야 한다.** 부주의가 아니라 도구 제약이다.

**이 8개가 왜 늦게 올라왔나.** D · E · F · G · H · v2a · v2b 는 브랜치에
올라가 있었는데, 그것들이 **물려받는 뿌리**가 안 올라가 있었다. 사본만 있고
정본이 없으면 사본이 날아갔을 때 아무것도 못 돌린다.

    gap_wide_env_cfg   다른 7개 파일이 참조
    gap_terrain        6개
    gap_env_cfg        4개 (B 조건)
    gap_ppo_cfg        3개
    __init__           태스크 등록 전부 (10개)

**갈라지면 조용히 틀린다.** 2026-09-21 에 `v2a_env_cfg.py` 의 잡음 선언
셋(`scanner_drift_range` · `height_scan_noise` · `scanner_offset_pos`)이
정본에만 들어가고 사본에 안 부어졌다. 그 상태로 v2c 를 걸었으면 선언이 아예
안 불린 채 3시간을 돌고 **오류도 안 났다.** 다음 날 대조해서 잡았다.

그래서 관문이 필요하다. 셋을 다 세야 한다.

    1. 해시가 다르면 막는다
    2. 정본에 있는데 사본에 없으면 막는다   (v2c · v2d 가 그 모양이었다)
    3. 대조 대상이 0개면 통과가 아니라 실패다

3번이 빠지면 자료가 없을 때 검사가 조용히 사라진다.

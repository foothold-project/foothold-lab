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

## 설치본의 상류 파일에 붙은 한 줄 (2026-10-08 추가)

사본 폴더 말고도 설치본에는 **상류 파일 하나에 한 줄이 더 붙어 있다.** 위 표에 없는
파일이라 여기 적어 둔다. 설치본을 새로 깔 때 이 줄이 빠질 수 있다.

    파일   C:\isaac\IsaacLab\source\isaaclab_tasks\isaaclab_tasks\
           manager_based\locomotion\velocity\config\go2\__init__.py
    상류   isaac-sim/IsaacLab 37ddf62 (v2.3.2)

```diff
 from . import agents
+from . import gap_training  # 0905 gap training v1
```

**이 줄이 꼭 있어야 하는지는 확인하지 않았다** `미확인`. 상류의 `import_packages()` 는
`_walk_packages` 로 하위 패키지를 «재귀로» 훑어 import 한다
(`isaaclab_tasks/utils/importer.py`). 그러면 `gap_training` 도 이 줄 없이 불릴 수
있다. `isaaclab_tasks` 를 거치지 않고 `config.go2` 를 바로 import 하는 경로에서는 이
줄이 등록을 보장한다. **지우고 돌려 본 적은 없다.** 빼기 전에 시험할 것.

설치본의 `train.py` 수정(+17 −1 · optimizer 없는 체크포인트를 받는다)은
`_out/loop/train.py.patched` 와 git blob 이 같다 · 곧 줄끝을 맞춘 뒤 같다 (2026-10-08 확인 ·
[mai-os#31](https://github.com/vfxpedia/mai-os/issues/31)).

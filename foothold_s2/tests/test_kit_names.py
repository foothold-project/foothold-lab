"""Kit 쪽 파일이 부르는 Isaac Lab 이름이 설치본에 실재하는지 소스(AST)로 대조한다. Kit 없이 돌아간다.

가짜 cfg 시험은 실제 이름 불일치를 못 잡는다는 교훈(10/16)에 따라, 우리 파일의 `mdp.X` · `from isaaclab... import Y` ·
`params={...}` 의 키가 설치본 함수 인자에 있는지 본다. 설치본 경로는 환경 변수 ISAACLAB_DIR (기본 C:/isaac/IsaacLab).
"""

import ast
import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(os.environ.get("ISAACLAB_DIR", "C:/isaac/IsaacLab")) / "source"
PKG = pathlib.Path(__file__).resolve().parents[1]
KIT_FILES = [
    "tasks/s1_env_cfg.py", "tasks/s2_env_cfg.py", "tasks/s1b_env_cfg.py", "tasks/s1b_env.py", "tasks/delayed_action.py", "tasks/mdp_extra.py", "tasks/agents/s1_ppo_cfg.py", "rewards/start_rewards.py",
    "commands/mixed_command.py", "curriculum/terrain_levels_mixed.py", "robots/go2_cfg.py",
    "terrains/rough_go2_cfg.py", "rewards/mgdp_terms.py", "tasks/s2_x13_env.py", "tasks/agents/s2_ppo_cfg.py", "rewards/lg_terms.py", "tasks/s2_x15_cfg.py", "tasks/agents/s2_x15_ppo_cfg.py", "tasks/s2_x16_cfg.py", "tasks/agents/s2_x16_ppo_cfg.py", "rewards/nvidia_go2_rewards.py", "tasks/s2_x16n_cfg.py", "tasks/agents/s2_x16n_ppo_cfg.py", "tasks/s2_x17_cfg.py", "tasks/agents/s2_x17_ppo_cfg.py", "tasks/agents/s2_x18_ppo_cfg.py", "tasks/s2_x19_cfg.py", "tasks/s2_x20_cfg.py", "tasks/agents/s2_x19_ppo_cfg.py", "tasks/agents/s2_x20_ppo_cfg.py", "tasks/s2_x21_cfg.py", "tasks/s2_x22_cfg.py", "tasks/agents/s2_x21_ppo_cfg.py", "tasks/agents/s2_x22_ppo_cfg.py", "tasks/s2_x23_cfg.py", "tasks/agents/s2_x23_ppo_cfg.py", "tasks/v2_noscan_cfg.py", "tasks/agents/v2_noscan_ppo_cfg.py",
]
MDP_DIRS = [ROOT / "isaaclab_tasks/isaaclab_tasks/manager_based/locomotion/velocity/mdp",
            ROOT / "isaaclab/isaaclab/envs/mdp"]

pytestmark = pytest.mark.skipif(not ROOT.exists(), reason="설치된 Isaac Lab 소스 없음")


def _py_files(dirs):
    for d in dirs:
        yield from pathlib.Path(d).rglob("*.py")


def _defs(dirs):
    """이름 -> (파일, 노드). 함수 · 클래스 정의."""
    out = {}

    for f in _py_files(dirs):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                out.setdefault(node.name, node)

    return out


MDP_DEFS = _defs(MDP_DIRS) if ROOT.exists() else {}


def _arg_names(node):
    if isinstance(node, ast.ClassDef):
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "__call__":
                node = item
                break
        else:
            return None

    a = node.args

    return {x.arg for x in a.posonlyargs + a.args + a.kwonlyargs}


def _parse(rel):
    return ast.parse((PKG / rel).read_text(encoding="utf-8"))


def _mdp_names_used(tree):
    names = set()

    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "mdp":
            names.add(n.attr)

    return names


@pytest.mark.parametrize("rel", KIT_FILES)
def test_mdp_names_exist(rel):
    missing = sorted(n for n in _mdp_names_used(_parse(rel)) if n not in MDP_DEFS and not n.endswith("Cfg"))
    assert not missing, f"{rel}: 설치 mdp 에 없는 이름 {missing}"


def test_mdp_cfg_classes_exist():
    cfg_defs = _defs([ROOT / "isaaclab/isaaclab/envs/mdp"])
    used = set()

    for rel in KIT_FILES:
        used |= {n for n in _mdp_names_used(_parse(rel)) if n.endswith("Cfg")}

    assert used <= set(cfg_defs), sorted(used - set(cfg_defs))


def test_params_keys_are_function_arguments():
    """EventTerm · RewTerm · ObsTerm · DoneTerm · CurrTerm 의 func 와 params 키 대조 (우리 함수는 우리 소스에서)."""
    bad = []

    for rel in KIT_FILES:
        tree = _parse(rel)
        local = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        extra = _defs([PKG / "tasks", PKG / "rewards", PKG / "curriculum"])

        for call in [n for n in ast.walk(tree) if isinstance(n, ast.Call)]:
            kw = {k.arg: k.value for k in call.keywords if k.arg}

            if "func" not in kw or "params" not in kw or not isinstance(kw["params"], ast.Dict):
                continue

            func = kw["func"]
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if isinstance(func, ast.Attribute) and getattr(func.value, "id", "") == "mdp":
                node = MDP_DEFS.get(name)
            else:
                node = local.get(name) or extra.get(name)

            if node is None:
                bad.append(f"{rel}: {name} 정의 못 찾음")
                continue

            args = _arg_names(node)
            keys = [k.value for k in kw["params"].keys if isinstance(k, ast.Constant)]
            bad += [f"{rel}: {name} 에 인자 {k} 없음" for k in keys if args is not None and k not in args]

    assert not bad, bad


def test_imported_isaac_names_resolve():
    """`from isaaclab... import Y` 의 Y 가 해당 모듈 안(하위 파일 포함)에 정의돼 있는지."""
    bad = []

    for rel in KIT_FILES:
        for n in ast.walk(_parse(rel)):
            if not isinstance(n, ast.ImportFrom) or not n.module or not n.module.startswith(("isaaclab", "isaaclab_")):
                continue

            if n.module.startswith(("isaaclab_tasks.manager_based.locomotion.velocity", "isaaclab.utils.assets")):
                continue

            top = n.module.split(".")[0]
            base = ROOT / top / top
            sub = base.joinpath(*n.module.split(".")[1:])
            dirs = [sub] if sub.is_dir() else [sub.with_suffix(".py")]
            text = "\n".join(f.read_text(encoding="utf-8") for f in _py_files(dirs)) if sub.is_dir() \
                else (dirs[0].read_text(encoding="utf-8") if dirs[0].exists() else "")

            for alias in n.names:
                name = re.escape(alias.name)
                pat = (r"^\s*(def|class)\s+" + name + r"\b|^" + name + r"\s*[:=]|import .*\b" + name + r"\b")
                is_submodule = sub.is_dir() and ((sub / alias.name).is_dir() or (sub / (alias.name + ".py")).exists())

                if is_submodule:
                    continue

                if alias.name == "*" or re.search(pat, text, re.M) is None:
                    if alias.name != "*":
                        bad.append(f"{rel}: {n.module}.{alias.name}")

    assert not bad, bad

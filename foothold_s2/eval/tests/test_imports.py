"""AST import 검사. sibling import 를 숨기지 않는다 (smoke 전에 돌린다).

시험이 폴더를 sys.path 에 넣으면 `import judge` 같은 bare sibling import 가 시험에서는 되고
Kit 에서는 6 초 만에 실패한다 (10/18 사고). 그래서 소스를 «돌리지 않고» 읽어서 검사한다.
허용: 표준 라이브러리 · 아래 외부 패키지 · 완전한 이름 `foothold_s2.eval.<모듈>` (파일이 실제로 있어야 함).
"""

import ast
import os
import sys

EVAL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTERNAL = {"numpy", "torch", "pytest", "isaaclab", "isaaclab_rl", "isaaclab_tasks", "robot_lab",
            "gymnasium", "rsl_rl", "tensordict", "h5py", "trimesh", "matplotlib", "av", "PIL"}
ENTRY = {"run_eval.py"}  # 진입점 최상위에서 sys.path 를 만지지 않는지는 아래에서 따로 본다


def _modules():
    return {n[:-3] for n in os.listdir(EVAL_DIR) if n.endswith(".py")}


def _py_files():
    return sorted(os.path.join(EVAL_DIR, n) for n in os.listdir(EVAL_DIR) if n.endswith(".py"))


def _check(path):
    problems = []
    mods = _modules()
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                problems += _check_name(alias.name, mods, path, node)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                problems.append("%s:%d 상대 import 금지" % (os.path.basename(path), node.lineno))
                continue

            problems += _check_name(node.module, mods, path, node)

            if node.module == "foothold_s2.eval":
                for alias in node.names:
                    if alias.name not in mods:
                        problems.append("%s:%d foothold_s2.eval.%s 파일이 없음"
                                        % (os.path.basename(path), node.lineno, alias.name))

    return problems


def _check_name(name, mods, path, node):
    top = name.split(".")[0]
    where = "%s:%d" % (os.path.basename(path), node.lineno)

    if top in sys.stdlib_module_names or top in EXTERNAL:
        return []

    if top == "foothold_s2":
        parts = name.split(".")

        if len(parts) >= 3 and parts[1] == "eval" and parts[2] not in mods:
            return ["%s foothold_s2.eval.%s 파일이 없음" % (where, parts[2])]

        return []

    if top in mods:
        return ["%s bare sibling import %r (foothold_s2.eval.%s 로 쓸 것)" % (where, name, top)]

    return ["%s 알 수 없는 import %r" % (where, name)]


def test_no_bare_sibling_or_unknown_imports():
    problems = []

    for path in _py_files():
        problems += _check(path)

    assert not problems, "\n".join(problems)


def test_the_check_itself_catches_a_bare_sibling(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("import judge\nfrom stats import wilson\nimport numpy\n", encoding="utf-8")
    problems = _check(str(bad))
    assert len(problems) == 2 and all("bare sibling" in p for p in problems)


def test_entry_point_does_not_touch_sys_path():
    for name in ENTRY:
        source = open(os.path.join(EVAL_DIR, name), encoding="utf-8").read()
        assert "sys.path" not in source


def test_every_module_compiles():
    for path in _py_files():
        compile(open(path, encoding="utf-8").read(), path, "exec")

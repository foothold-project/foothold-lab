"""CPU contract checks for pre-optimizer plumbing evidence."""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from s2_plumbing import PlumbingHold, training_cfg_evidence

HERE=Path(__file__).resolve().parent


def contact_fn(*args,**kwargs):
    return None


def cfg(*,gravity=False,fix_base=False,contact=True):
    return SimpleNamespace(
        scene=SimpleNamespace(robot=SimpleNamespace(spawn=SimpleNamespace(
            rigid_props=SimpleNamespace(disable_gravity=gravity),fix_base=fix_base))),
        terminations=SimpleNamespace(illegal_contact=(SimpleNamespace(func=contact_fn) if contact else None),
                                     time_out=SimpleNamespace(func=contact_fn)))


def caught(label,value,want):
    try:training_cfg_evidence(value)
    except PlumbingHold as ex:
        if str(ex)==want:
            print(f"CAUGHT {label} first_FAIL={want} want={want}",flush=True)
            return
        raise AssertionError((label,str(ex),want)) from ex
    raise AssertionError((label,"not_caught"))


def test():
    result=training_cfg_evidence(cfg())
    assert result["task"]=="RobotLab-Go2-v0"
    assert result["contact_term"]=="illegal_contact"
    assert result["contact_function"].endswith("contact_fn")
    assert Path(result["contact_function_source"]).is_file()
    assert result["disable_gravity"] is False and result["fix_base"] is False
    print("PASS plumbing active termination function and physics guard",flush=True)
    caught("gravity",cfg(gravity=True),"diagnostic_gravity_leak")
    caught("root_fixed",cfg(fix_base=True),"diagnostic_root_fix_leak")
    caught("contact_disabled",cfg(contact=False),"active_contact_term_missing")
    entry=ast.parse((HERE/"s2_train_entry_17v.py").read_text(encoding="utf-8"))
    fn=next(n for n in entry.body if isinstance(n,ast.FunctionDef) and n.name=="make_runner")
    calls=[(n.lineno,ast.unparse(n.func)) for n in ast.walk(fn) if isinstance(n,ast.Call)]
    hook=min(n for n,name in calls if name=="pre_optimizer_hook")
    optimizer=min(n for n,name in calls if name=="make_optimizer")
    assert hook<optimizer
    print("PASS pre-optimizer hook precedes make_optimizer",flush=True)


if __name__=="__main__":test()

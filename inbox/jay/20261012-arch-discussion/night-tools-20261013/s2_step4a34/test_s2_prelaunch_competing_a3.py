"""17x: competing-Isaac detection must see python-launched Isaac tools, not only kit.exe. CPU fakes only."""
from types import SimpleNamespace
import psutil

import s2_stage0_prelaunch as pre


def fake(pid,name,cmd):
    return SimpleNamespace(info={"pid":pid,"name":name,"cmdline":cmd})


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def run(procs):
    original=psutil.process_iter
    psutil.process_iter=lambda attrs=None:iter(procs)
    try:return pre.competing_isaac_processes()
    finally:psutil.process_iter=original


def main():
    check("python_branch_run_found",len(run([fake(10**7+1,"python.exe",["python.exe","branch_run.py","--headless"])]))==1)
    check("python_isaaclab_found",len(run([fake(10**7+2,"python.exe",["C:\IsaacLab\isaaclab.bat"])]))==1)
    check("kit_exe_found",len(run([fake(10**7+3,"kit.exe",None)]))==1)
    check("unrelated_python_not_found",run([fake(10**7+4,"python.exe",["python.exe","-m","http.server"])])==[])
    check("non_python_without_cmdline_ignored",run([fake(10**7+5,"explorer.exe",None)])==[])
    try:run([fake(10**7+6,"python.exe",None)])
    except RuntimeError as ex:check("unreadable_python_cmdline_holds",str(ex)=="process_inventory_unreadable")
    else:check("unreadable_python_cmdline_holds",False)
    original=psutil.process_iter
    def deny(attrs=None):
        class P:
            @property
            def info(self):raise psutil.AccessDenied()
        yield P()
    psutil.process_iter=deny
    try:pre.competing_isaac_processes()
    except RuntimeError as ex:check("access_denied_holds",str(ex)=="process_inventory_unreadable")
    else:check("access_denied_holds",False)
    finally:psutil.process_iter=original


if __name__=="__main__":main()

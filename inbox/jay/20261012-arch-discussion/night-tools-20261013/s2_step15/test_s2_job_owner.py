"""Deterministic Job Object fake table. No actual process receives a signal."""
from s2_job_owner import JobOwner, OwnershipHold


class FakeKernel:
    def __init__(self,*,access_denied=False):
        self.events=[]; self.active=0; self.access_denied=access_denied
        self.table={700:"owned-parent",701:"owned-child"}
    def create_job(self): self.events.append("create_job"); return "job"
    def create_suspended(self,argv,cwd,env=None):
        self.events.append("create_suspended"); self.active=1
        return "process-handle","thread-handle",700
    def assign(self,job,process):
        self.events.append("assign")
        if self.access_denied: raise OwnershipHold("job_assign:access_denied")
    def resume(self,thread): self.events.append("resume")
    def active_count(self,job): return self.active
    def terminate_job(self,job): self.events.append("terminate_job"); self.active=0
    def terminate_suspended(self,process): self.events.append("terminate_suspended"); self.active=0
    def close(self,handle): self.events.append("close:"+handle)


def check(name,condition):
    assert condition,name
    print("PASS",name)


def main():
    k=FakeKernel(); owner=JobOwner(k)
    check("suspended_assigned_before_resume",owner.launch(["fake.exe"],".")==700 and
          k.events.index("assign")<k.events.index("resume"))
    k.table[700]="unrelated-reused-pid"
    k.active=2
    owner.stop_owned()
    check("pid_reuse_never_looked_up",k.table[700]=="unrelated-reused-pid" and
          "terminate_job" in k.events and not any("kill_pid" in x for x in k.events))
    owner.close()
    check("family_empty_before_handle_close",k.events[-1]=="close:job")
    denied=FakeKernel(access_denied=True); o=JobOwner(denied)
    try:o.launch(["fake.exe"],".")
    except OwnershipHold: pass
    else: raise AssertionError("access_denied")
    check("access_denied_suspended_owned_handle_only", "terminate_suspended" in denied.events and
          "resume" not in denied.events)
    o.close()
    k2=FakeKernel(); o2=JobOwner(k2);o2.launch(["fake.exe"],".")
    k2.active=2
    try:o2.close()
    except OwnershipHold:pass
    else:raise AssertionError("descendant_live")
    check("new_descendant_blocks_lease_release", "close:job" not in k2.events)
    o2.stop_owned();o2.close()

if __name__=="__main__":main()

"""Windows suspended-create Job Object owner. No process is launched on import.

The kernel handle is intentionally private to the supervisor. KILL_ON_JOB_CLOSE
closes the owned family if that supervisor exits. An external deadline watcher is
still needed for a hung supervisor, so this alone is not a live launch approval.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import subprocess


class OwnershipHold(RuntimeError):
    pass


class STARTUPINFO(ctypes.Structure):
    _fields_=[("cb",wintypes.DWORD),("lpReserved",wintypes.LPWSTR),
              ("lpDesktop",wintypes.LPWSTR),("lpTitle",wintypes.LPWSTR),
              ("dwX",wintypes.DWORD),("dwY",wintypes.DWORD),
              ("dwXSize",wintypes.DWORD),("dwYSize",wintypes.DWORD),
              ("dwXCountChars",wintypes.DWORD),("dwYCountChars",wintypes.DWORD),
              ("dwFillAttribute",wintypes.DWORD),("dwFlags",wintypes.DWORD),
              ("wShowWindow",wintypes.WORD),("cbReserved2",wintypes.WORD),
              ("lpReserved2",ctypes.POINTER(ctypes.c_byte)),
              ("hStdInput",wintypes.HANDLE),("hStdOutput",wintypes.HANDLE),
              ("hStdError",wintypes.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_=[("hProcess",wintypes.HANDLE),("hThread",wintypes.HANDLE),
              ("dwProcessId",wintypes.DWORD),("dwThreadId",wintypes.DWORD)]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_=[("PerProcessUserTimeLimit",ctypes.c_int64),
              ("PerJobUserTimeLimit",ctypes.c_int64),("LimitFlags",wintypes.DWORD),
              ("MinimumWorkingSetSize",ctypes.c_size_t),("MaximumWorkingSetSize",ctypes.c_size_t),
              ("ActiveProcessLimit",wintypes.DWORD),("Affinity",ctypes.c_size_t),
              ("PriorityClass",wintypes.DWORD),("SchedulingClass",wintypes.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_=[(k,ctypes.c_uint64) for k in ("ReadOperationCount","WriteOperationCount",
              "OtherOperationCount","ReadTransferCount","WriteTransferCount","OtherTransferCount")]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_=[("BasicLimitInformation",JOBOBJECT_BASIC_LIMIT_INFORMATION),
              ("IoInfo",IO_COUNTERS),("ProcessMemoryLimit",ctypes.c_size_t),
              ("JobMemoryLimit",ctypes.c_size_t),("PeakProcessMemoryUsed",ctypes.c_size_t),
              ("PeakJobMemoryUsed",ctypes.c_size_t)]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_=[("TotalUserTime",ctypes.c_int64),("TotalKernelTime",ctypes.c_int64),
              ("ThisPeriodTotalUserTime",ctypes.c_int64),("ThisPeriodTotalKernelTime",ctypes.c_int64),
              ("TotalPageFaultCount",wintypes.DWORD),("TotalProcesses",wintypes.DWORD),
              ("ActiveProcesses",wintypes.DWORD),("TotalTerminatedProcesses",wintypes.DWORD)]


class WinKernel:
    def __init__(self):
        if os.name!="nt": raise OwnershipHold("windows_required")
        self.k=ctypes.WinDLL("kernel32",use_last_error=True)
        for name,restype,args in (
            ("CreateJobObjectW",wintypes.HANDLE,[wintypes.LPVOID,wintypes.LPCWSTR]),
            ("SetInformationJobObject",wintypes.BOOL,[wintypes.HANDLE,wintypes.INT,wintypes.LPVOID,wintypes.DWORD]),
            ("CreateProcessW",wintypes.BOOL,[wintypes.LPCWSTR,wintypes.LPWSTR,wintypes.LPVOID,wintypes.LPVOID,
                                              wintypes.BOOL,wintypes.DWORD,wintypes.LPVOID,wintypes.LPCWSTR,
                                              ctypes.POINTER(STARTUPINFO),ctypes.POINTER(PROCESS_INFORMATION)]),
            ("AssignProcessToJobObject",wintypes.BOOL,[wintypes.HANDLE,wintypes.HANDLE]),
            ("ResumeThread",wintypes.DWORD,[wintypes.HANDLE]),
            ("QueryInformationJobObject",wintypes.BOOL,[wintypes.HANDLE,wintypes.INT,wintypes.LPVOID,
                                                          wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]),
            ("TerminateJobObject",wintypes.BOOL,[wintypes.HANDLE,wintypes.UINT]),
            ("TerminateProcess",wintypes.BOOL,[wintypes.HANDLE,wintypes.UINT]),
            ("GetExitCodeProcess",wintypes.BOOL,[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]),
            ("CloseHandle",wintypes.BOOL,[wintypes.HANDLE])):
            f=getattr(self.k,name); f.restype=restype; f.argtypes=args

    def _ok(self,value,label):
        if not value: raise OwnershipHold(f"{label}:winerror={ctypes.get_last_error()}")
        return value

    def create_job(self):
        job=self._ok(self.k.CreateJobObjectW(None,None),"job_create")
        limits=JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        limits.BasicLimitInformation.LimitFlags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        try:
            self._ok(self.k.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)),"job_limit")
        except BaseException:
            self.k.CloseHandle(job); raise
        return job

    def create_suspended(self,argv,cwd,env=None,log_path=None):
        if not argv or any(type(x) is not str or not x or "\x00" in x for x in argv):
            raise OwnershipHold("argv_invalid")
        si=STARTUPINFO();si.cb=ctypes.sizeof(si)
        pi=PROCESS_INFORMATION()
        cmd=ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        flags=0x4|0x8|0x200|0x400  # suspended, detached, new group, Unicode environment
        values=os.environ.copy() if env is None else env
        if any("\x00" in str(k) or "\x00" in str(v) or "=" in str(k) for k,v in values.items()):
            raise OwnershipHold("environment_invalid")
        block=ctypes.create_unicode_buffer("\x00".join(f"{k}={v}" for k,v in sorted(values.items()))+"\x00\x00")
        log_fd=None
        try:
            if log_path is not None:
                import msvcrt
                log_fd=os.open(os.fspath(log_path),os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_BINARY,0o600)
                handle=msvcrt.get_osfhandle(log_fd)
                os.set_handle_inheritable(handle,True)
                si.dwFlags|=0x100  # STARTF_USESTDHANDLES
                si.hStdOutput=handle;si.hStdError=handle
                si.hStdInput=None
            self._ok(self.k.CreateProcessW(argv[0],cmd,None,None,bool(log_fd is not None),flags,block,str(cwd),
                                           ctypes.byref(si),ctypes.byref(pi)),"process_create")
        finally:
            if log_fd is not None:os.close(log_fd)
        return pi.hProcess,pi.hThread,int(pi.dwProcessId)

    def assign(self,job,process): self._ok(self.k.AssignProcessToJobObject(job,process),"job_assign")
    def resume(self,thread):
        if self.k.ResumeThread(thread)==0xFFFFFFFF: raise OwnershipHold("resume_thread")
    def active_count(self,job):
        info=JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
        self._ok(self.k.QueryInformationJobObject(job,1,ctypes.byref(info),ctypes.sizeof(info),None),"job_query")
        return int(info.ActiveProcesses)
    def terminate_job(self,job): self._ok(self.k.TerminateJobObject(job,1),"job_terminate")
    def terminate_suspended(self,process): self._ok(self.k.TerminateProcess(process,1),"suspended_terminate")
    def exit_code(self,process):
        value=wintypes.DWORD()
        self._ok(self.k.GetExitCodeProcess(process,ctypes.byref(value)),"exit_code")
        return None if value.value==259 else int(value.value)
    def close(self,handle): self._ok(self.k.CloseHandle(handle),"handle_close")


class JobOwner:
    def __init__(self,kernel):
        self.kernel=kernel
        self.job=kernel.create_job()
        self.pid=None
        self.process=None
        self._closed=False

    def launch(self,argv,cwd,env=None,log_path=None):
        if self.pid is not None: raise OwnershipHold("job_already_started")
        process,thread,pid=(self.kernel.create_suspended(argv,cwd,env) if log_path is None else
                            self.kernel.create_suspended(argv,cwd,env,log_path))
        try:
            pass  # mutant omits Job assignment
            self.kernel.resume(thread)
            self.pid=pid
            self.process=process
        except BaseException:
            # This is the just-created suspended process handle, never a looked-up PID.
            self.kernel.terminate_suspended(process)
            self.kernel.close(process)
            raise
        finally:
            self.kernel.close(thread)
        return pid

    def active_count(self): return self.kernel.active_count(self.job)

    def exit_code(self):
        if self.process is None:raise OwnershipHold("process_not_started")
        return self.kernel.exit_code(self.process)

    def stop_owned(self,*,wait_seconds=10.,clock=None):
        import time
        if clock is None: clock=time.monotonic
        self.kernel.terminate_job(self.job)
        end=clock()+wait_seconds
        while self.active_count():
            if clock()>=end: raise OwnershipHold("owned_family_not_empty")
            time.sleep(.01)

    def close(self):
        if self._closed: return
        if self.active_count(): raise OwnershipHold("owned_family_still_running")
        if self.process is not None:
            self.kernel.close(self.process)
            self.process=None
        self.kernel.close(self.job)
        self._closed=True

"""Host-wide advisory leases keyed by GPU UUID; common USD lock is separate.

Windows byte locks are released by the OS when the owning process exits. Every
GPU-capable launcher must participate or the supervisor must own the time box.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


class LeaseHold(RuntimeError): pass


class FileLease:
    def __init__(self,root:Path,key:str):
        if not key or any(c in key for c in "\\/\x00"):
            raise LeaseHold("lease_key")
        self.root=root.resolve()
        self.path=self.root/(hashlib.sha256(key.encode()).hexdigest()+".lock")
        self.fd=None

    def acquire(self):
        if os.name!="nt": raise LeaseHold("windows_required")
        import msvcrt
        self.root.mkdir(parents=True,exist_ok=True)
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_BINARY,0o600)
        try:
            if os.fstat(fd).st_size==0: os.write(fd,b"0")
            os.lseek(fd,0,os.SEEK_SET)
            msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        except OSError as ex:
            os.close(fd)
            raise LeaseHold("lease_busy_or_access_denied") from ex
        self.fd=fd
        return self

    def release(self,*,family_empty:bool):
        if not family_empty: raise LeaseHold("family_not_empty")
        if self.fd is None:return
        import msvcrt
        os.lseek(self.fd,0,os.SEEK_SET)
        try:msvcrt.locking(self.fd,msvcrt.LK_UNLCK,1)
        finally:os.close(self.fd);self.fd=None


def gpu_lease(root:Path,uuid:str)->FileLease:
    if not uuid or uuid in ("UNDECIDED","synthetic-gpu-0","synthetic-gpu-1"):
        raise LeaseHold("real_gpu_uuid_required")
    return FileLease(root,"GPU:"+uuid)


def usd_conversion_lock(root:Path)->FileLease:
    return FileLease(root,"HOST:USD_CONVERSION")

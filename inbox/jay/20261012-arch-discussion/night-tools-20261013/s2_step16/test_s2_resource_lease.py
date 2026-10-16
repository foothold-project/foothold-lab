from pathlib import Path
import tempfile
from s2_resource_lease import FileLease, LeaseHold


def main():
    with tempfile.TemporaryDirectory(prefix="s2_leases_") as td:
        root=Path(td)
        first=FileLease(root,"GPU:UUID-A").acquire()
        try:FileLease(root,"GPU:UUID-A").acquire()
        except LeaseHold as ex: assert str(ex)=="lease_busy_or_access_denied"
        else:raise AssertionError("same_uuid_collision")
        print("PASS same_uuid_collision")
        second=FileLease(root,"GPU:UUID-B").acquire()
        third=FileLease(root,"HOST:USD_CONVERSION").acquire()
        print("PASS independent_uuid_and_usd_lock")
        try:first.release(family_empty=False)
        except LeaseHold as ex: assert str(ex)=="family_not_empty"
        else:raise AssertionError("live_family_release")
        print("PASS live_family_blocks_release")
        first.release(family_empty=True)
        second.release(family_empty=True)
        third.release(family_empty=True)
        again=FileLease(root,"GPU:UUID-A").acquire()
        again.release(family_empty=True)
        print("PASS release_then_reacquire")

if __name__=="__main__":main()

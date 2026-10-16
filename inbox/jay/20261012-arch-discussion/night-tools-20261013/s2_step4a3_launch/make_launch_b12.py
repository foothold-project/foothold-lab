import sys
from pathlib import Path
SRC = Path("C:/Users/AI-WS01/s2_lab/night-tools-20261013/s2_step4a3_launch/s2_attended_launch_b_plumbing.py")
DST = Path(sys.argv[1]); LIST_SHA = sys.argv[2]
t = SRC.read_text(encoding="utf-8")
def sub(old, new):
    global t
    if t.count(old) != 1: raise SystemExit("not unique (%d): %r" % (t.count(old), old[:70]))
    t = t.replace(old, new)
sub('B = WORK / "night-tools-20261013" / "s2_step8"          # frozen B bundle (copy of the repository\'s s2_step8 without evidence)',
    'B = WORK / "night-tools-20261013" / "s2_step12"         # frozen B bundle (sol step12 without evidence, nested A3.4 folder and test leftovers; list made by the lead)')
sub('LIST_SHA = "5175e4dfcabafe779b99dd23214cc37789e400498349339fd3b320d5e629fd11"', 'LIST_SHA = "%s"' % LIST_SHA)
sub('VERDICT_DOCS = ("VERIFY-astra-17ae.md",)', 'VERDICT_DOCS = ("VERIFY-astra-17ae.md", "VERIFY-astra-17ah.md")')
sub('"by": "lead freeze under ASTRA 17ae conditions (first B plumbing, A3.2 sequel); attendee=" + attendee,',
    '"by": "lead freeze under ASTRA 17ah conditions (B plumbing retry after the illegal_contact name fix, step12); attendee=" + attendee,')
DST.write_text(t, encoding="utf-8"); print("written", DST)

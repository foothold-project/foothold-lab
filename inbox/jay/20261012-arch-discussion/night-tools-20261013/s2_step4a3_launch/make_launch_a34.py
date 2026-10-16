"""Derive the A3.4 attended launcher from the A3.2 one. Every replacement must match exactly once."""
import sys
from pathlib import Path

SRC = Path("C:/Users/AI-WS01/s2_lab/night-tools-20261013/s2_step4a3_launch/s2_attended_launch_a3.py")
DST = Path(sys.argv[1])
LIST_SHA = sys.argv[2]
COUNT = int(sys.argv[3])
text = SRC.read_text(encoding="utf-8")

def sub(old, new):
    global text
    if text.count(old) != 1:
        raise SystemExit("replacement not unique (%d): %r" % (text.count(old), old[:70]))
    text = text.replace(old, new)

sub('"""Attended one-shot launcher for the S2 stage-0 information-only collection (A3 bundle).',
    '"""Attended one-shot launcher for the S2 stage-0 information-only collection (A3.4 bundle, RobotLab-Go2-v0).')
sub('BUNDLE = WORK / "s2_step4a3"', 'BUNDLE = WORK / "s2_step4a34"')
sub('LIST_SHA = "98bd193683ba48d8ad2ff4787309db0c8d572e4f0768044e866cda62758ff7f1"',
    'LIST_SHA = "%s"\nEXPECTED_COUNT = %d' % (LIST_SHA, COUNT))
sub('if count != 49 or bad:', 'if count != EXPECTED_COUNT or bad:')
sub('raise SystemExit("NO_GO: SHA256SUMS.txt differs from the list ASTRA 17y verified")',
    'raise SystemExit("NO_GO: SHA256SUMS.txt differs from the A3.4 list the lead verified")')
sub('''ASSET = ("https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/"
         "IsaacLab/Robots/Unitree/Go2/go2.usd")''',
    '''ASSET = "C:/isaac/ext/go2_rl_robotlab/resources/go2/urdf/go2.urdf"
ROBOTLAB_ASSET_CFG = "C:/isaac/ext/go2_rl_robotlab/source/robot_lab/robot_lab/assets/unitree.py"
CONVERTER_SOURCE = "C:/isaac/IsaacLab/source/isaaclab/isaaclab/sim/converters/asset_converter_base.py"
URDF_SHA = "f130b1d2cc61f3c1e54dab8f8b9ad27b0b54f85c968d89ea242c6d70ab2a5810"''')
sub('VERDICT_DOC = WORK.parent / "VERIFY-astra-17ac.md"', 'VERDICT_DOC = WORK.parent / "VERIFY-astra-17ah.md"')
sub('''                   {"chain_id": "s2-stage0-a3-live-20261015-150639", "result": "COLLECTED_256_ROWS_CHECKER_HOLD_13_REASONS"})''',
    '''                   {"chain_id": "s2-stage0-a3-live-20261015-150639", "result": "COLLECTED_256_ROWS_CHECKER_HOLD_13_REASONS"},
                   {"chain_id": "s2-stage0-a3-live-20261016-141535", "result": "COLLECTED_256_ROWS_CHECKER_HOLD_3_REASONS_SCENE_QUERY_SUPPORT_FALSE_ON_ISAACLAB_STOCK_GO2"})''')
sub('"attempt_ordinal": 4,', '"attempt_ordinal": 5,')
sub('"bundle": "A3.2 (A3.1 + robot held in place: gravity and base_contact termination off in the eight_case diagnostic; reset-aware sensor clock in the checker; one boundary formula; observed Warp/PhysX mesh evidence; provenance fields filled)",',
    '"bundle": "A3.4 (A3.2 moved to the training environment RobotLab-Go2-v0 with the URDF Go2 and illegal_contact termination; sim.enable_scene_query_support on before the physics scene exists; first-16-step PhysX/foot/root observation inside the unchanged 256 steps; asset closure hash and USD isolation evidence)",')
sub('''"asset_path": ASSET, "asset_ref_sha256": hashlib.sha256(ASSET.encode()).hexdigest(),''',
    '''"asset_path": ASSET, "asset_ref_sha256": hashlib.sha256(ASSET.encode()).hexdigest(),
        "asset_closure_sha256": closure_sha256(asset_snapshot(ASSET, ROBOTLAB_ASSET_CFG, CONVERTER_SOURCE)),
''')
sub('"expect_conversions": "0",', '"expect_conversions": "1",')
sub('"by": "lead freeze under ASTRA 17ac permission (fourth attempt, A3.2); attendee=" + attendee,',
    '"by": "lead freeze under ASTRA 17ah conditional permission (fifth attempt, A3.4); attendee=" + attendee,')
sub('from s2_zero_supervisor import canonical  # noqa: E402',
    'from s2_zero_supervisor import canonical  # noqa: E402\nfrom s2_a34_provenance import asset_snapshot, closure_sha256, sha as _prov_sha  # noqa: E402')
# the URDF content hash must equal the value ASTRA 17ah read, checked at freeze time
sub('def build(mode: str, attendee: str, consent: dict | None = None):\n    now = time.time()',
    'def build(mode: str, attendee: str, consent: dict | None = None):\n    if _prov_sha(ASSET) != URDF_SHA:\n        raise SystemExit("NO_GO: URDF content differs from the hash ASTRA 17ah read")\n    now = time.time()')
DST.write_text(text, encoding="utf-8")
print("written", DST, len(text))

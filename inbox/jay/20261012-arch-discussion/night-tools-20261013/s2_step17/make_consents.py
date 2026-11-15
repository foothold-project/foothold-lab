"""Write the four per-node consent files from ONE direct message of the team lead (ASTRA 17ai section 3). The quote is the lead's own words, verbatim.
usage: make_consents.py <recorded_at 'YYYY-MM-DD HH:MM KST'> <quote file (utf-8, verbatim message)> [asked_by_lead_at note file]
"""
import json, sys
from pathlib import Path
out = Path(__file__).resolve().parent.parent
rec, qf = sys.argv[1], Path(sys.argv[1+1])
quote = qf.read_text(encoding="utf-8").strip()
note = Path(sys.argv[3]).read_text(encoding="utf-8").strip() if len(sys.argv) > 3 else ""
scopes = {"consent_n1_a34.json": "stage0_a34_attended_once",
          "consent_n2_plumbing.json": "s2_plumbing_attended_one_shot_arm_A",
          "consent_n3_eval0.json": "s2_eval_kit_smoke_once",
          "consent_n4_foot.json": "s2_foot_kit_check_once"}
for name, scope in scopes.items():
    d = {"by": "오흥재 (팀장, 채팅에서 직접 입력)", "recorded_at": rec, "eula_accepted": "yes",
         "attending_until_end": "yes", "go_for_this_one_run": "yes", "quote": quote,
         "asked_by_lead_at": note, "scope": scope}
    (out / name).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out / name)

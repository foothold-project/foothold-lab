"""W72 boundary-only committed snapshot and explicit approval validation."""
from pathlib import Path


def read_committed_pair(config_path: str | Path, approval_path: str | Path) -> dict:
    """Pin both files to one Git HEAD, reject dirty/untracked/invalid input.

    Returns commit/config_sha256/approval_sha256/config/approvals.
    Runtime catches validation failures and retains last effective config.
    Returned bytes/data are a frozen snapshot; edits after this read wait for
    the next boundary. Never reads or writes the EX40 primary live ledger.
    """
    raise NotImplementedError('EX41 interface only')


def validate_change(before: dict, after: dict, approvals: dict) -> list[dict]:
    """Validate all changed leaf paths, ranges and locked-field invariants.

    Returns path/before/after/decision_id rows. Unknown or unauthorized field
    raises ValueError before any runtime mutation. Structural neural-network,
    observation/action dimensions, PD, perception loss are immutable in-run.
    """
    raise NotImplementedError('EX41 interface only')

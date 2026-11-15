"""Install-day integration check; run explicitly after runtime setup is verified."""

from foothold_s2.machine_profile import load_machine_profile
from foothold_s2.scripts.ex42_ops import verify_env_cfg_import, verify_train_entry_contract


def test_real_train_parser_and_environment_import_succeed_without_starting_kit():
    parser = verify_train_entry_contract()
    assert parser["parser"].startswith("train_start declarations")
    machine = load_machine_profile()
    assert parser["machine_profile"] == machine["machine_id"]
    assert parser["machine_profile_path"] == machine["profile"]
    assert parser["applauncher_passthrough"] == ["--headless", "--device", "cuda:0"]
    env = verify_env_cfg_import()
    assert env["kit_started"] is False
    assert env["imported"] is True

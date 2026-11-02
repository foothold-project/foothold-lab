"""Runner's EX-41 maintenance consumer rejects DR-enabled evaluation evidence."""

import pytest

from foothold_s2.curriculum.ex41_scoring import maintenance_counts_from_map_modes


def test_maintenance_consumer_rejects_dr_enabled_map_modes():
    documents = (
        {"dr": {"scale": 1.0}},
        {"dr_off": []},
        {"dr_off": ["physics_material", "add_base_mass"],
         "modes": {"eval_gt": {"fwd1.0": {"dr_scale": 0.5}}}},
    )
    for document in documents:
        with pytest.raises(RuntimeError):
            maintenance_counts_from_map_modes(document, {})

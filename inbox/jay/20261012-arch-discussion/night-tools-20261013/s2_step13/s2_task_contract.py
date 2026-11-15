"""Closed mapping between a registered task and its contact termination."""

CONTACT_TERMINATION_BY_TASK = {
    "RobotLab-Go2-v0": "illegal_contact",
    "Isaac-Velocity-Rough-Unitree-Go2-v0": "base_contact",
}


def contact_termination_for(task):
    try:
        return CONTACT_TERMINATION_BY_TASK[task]
    except (KeyError, TypeError) as ex:
        raise ValueError("unregistered_contact_termination_task") from ex

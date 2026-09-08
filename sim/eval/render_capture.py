"""Small safeguards for Isaac Lab's asynchronous viewport RGB capture."""

import numpy as np


def capture_lit_frame(env, *, minimum_mean=10.0, max_attempts=3):
    """Return a completed viewport frame from a scene known to be lit.

    Isaac Sim 5.1 can expose an all-zero Replicator buffer while a large RGB
    render product is still being updated.  Calling ``render`` again advances
    the off-screen pipeline.  The brightness check is deliberately explicit:
    this helper is only appropriate when the intended scene is known not to be
    black.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")

    means = []
    for attempt in range(1, max_attempts + 1):
        frame = np.ascontiguousarray(env.render())
        mean = float(np.asarray(frame, dtype=np.float32).mean())
        means.append(mean)
        if mean >= minimum_mean:
            return frame, attempt, means

    raise RuntimeError(
        "Viewport RGB buffer stayed below the expected brightness "
        f"({minimum_mean}) for {max_attempts} render calls: {means}"
    )

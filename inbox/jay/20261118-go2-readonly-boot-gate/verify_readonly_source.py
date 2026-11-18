#!/usr/bin/env python3
from pathlib import Path


SOURCE = Path(__file__).with_name("go2_readonly_monitor.cpp")
text = SOURCE.read_text(encoding="utf-8")

for forbidden in (
    "ChannelPublisher",
    "channel_publisher",
    "SportClient",
    "LocoClient",
    "MotionSwitcherClient",
    "publisher.InitChannel",
    ".Write(",
    ".Request(",
):
    assert forbidden not in text, f"forbidden command-path token: {forbidden}"

for required in (
    'ChannelSubscriber<LowState>',
    'ChannelSubscriber<LowCmd>',
    'ChannelSubscriber<SportState>',
    'ChannelSubscriber<ErrorString>',
    '"rt/lowstate"',
    '"rt/lowcmd"',
    '"rt/sportmodestate"',
    '"rt/errorlist"',
):
    assert required in text, f"missing receive-only evidence: {required}"

print("receive-only source guard: PASS")

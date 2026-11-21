"""Read one Go2 LowState over DDS (subscribe only, never publishes): battery % and motor temperatures.
ros2 topic echo cannot decode /lowstate on the Jetson (no unitree_go ROS message), so this uses unitree_sdk2py
from the foothold-robot venv:  ~/foothold-robot/venv/bin/python lowstate_once.py [out.json]
"""
import json
import sys
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_go.msg.dds_ import LowState_

ChannelFactoryInitialize(0, 'enP8p1s0')
got = []
sub = ChannelSubscriber('rt/lowstate', LowState_)
sub.Init(lambda m: got.append(m), 10)
t0 = time.time()
while not got and time.time() - t0 < 5:
    time.sleep(0.1)
if not got:
    print(json.dumps({'error': 'no lowstate in 5 s'}))
    sys.exit(1)
m = got[-1]
temps = [int(x.temperature) for x in m.motor_state[:12]]
names = ['FR_hip', 'FR_thigh', 'FR_calf', 'FL_hip', 'FL_thigh', 'FL_calf',
         'RR_hip', 'RR_thigh', 'RR_calf', 'RL_hip', 'RL_thigh', 'RL_calf']
hot = max(range(12), key=lambda i: temps[i])
out = dict(time=time.strftime('%H:%M:%S'), soc=int(m.bms_state.soc), power_v=round(float(m.power_v), 2),
           current_ma=int(m.bms_state.current), motor_temp_c=dict(zip(names, temps)),
           hottest=[names[hot], temps[hot]])
print(json.dumps(out, ensure_ascii=False))
if len(sys.argv) > 1:
    with open(sys.argv[1], 'w') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

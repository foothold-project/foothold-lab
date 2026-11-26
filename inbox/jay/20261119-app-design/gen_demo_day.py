"""DEMO-DAY v0.1 생성기: 에이전트 형식 (scenario-small.yaml 틀)."""
import sys, yaml
out = sys.argv[1]
def U(n): return f"00000000-0000-4000-8000-{n:012x}"
floors = [{'id': f, 'floor_id': U(i+1), 'map_version_id': U(0xa0+i+1)} for i, f in enumerate(['tunnel', 'plant_kr', 'plant_eu', 'arena'])]
W, P, CH, Z = [], [], [], []
def wp(i, f, x, y): W.append({'id': i, 'floor': f, 'x': x, 'y': y})
def path(*ids):
    for a, b in zip(ids, ids[1:]): P.append([a, b])
SWAP = 500  # 배터리 교체 칸 (Go2 X 는 켠 채 충전 안 됨). 검증기 상한 500 → 85 % 에 약 10 분
# 1 공동구: 2.4 km 한 줄, 환기구 11 (240 m), 접속공간 4, 분기 2, 반입구 2
for k in range(11): wp(f't_v{k+1:02d}', 'tunnel', 240*k, 0)
path(*[f't_v{k+1:02d}' for k in range(11)])
for j, x in enumerate([360, 840, 1560, 2040]): wp(f't_joint{j+1}', 'tunnel', x, 3); P.append([f't_v{round(x/240)+1:02d}', f't_joint{j+1}'])
wp('t_branch1', 'tunnel', 720, 40); P.append(['t_v04', 't_branch1'])
wp('t_branch2', 'tunnel', 1680, -40); P.append(['t_v08', 't_branch2'])
wp('t_sump', 'tunnel', 1440, -4); P.append(['t_v07', 't_sump'])
wp('t_swap_w', 'tunnel', -8, 0); P.append(['t_swap_w', 't_v01'])
wp('t_swap_e', 'tunnel', 2408, 0); P.append(['t_swap_e', 't_v11'])
CH += [{'id': 'T-SW-W', 'waypoint': 't_swap_w', 'yaw': 0.0, 'slots': 2, 'charge_pct_per_h': SWAP},
       {'id': 'T-SW-E', 'waypoint': 't_swap_e', 'yaw': 3.14, 'slots': 2, 'charge_pct_per_h': SWAP}]
Z += [{'id': 't_hatch_a', 'floor': 'tunnel', 'rect': [460, -6, 500, 6], 'crowd': [{'hours': '09:00-11:00', 'level': 0.5, 'kinds': ['person']}, {'hours': '14:00-16:00', 'level': 0.5, 'kinds': ['person']}]},
      {'id': 't_hatch_b', 'floor': 'tunnel', 'rect': [1900, -6, 1940, 6], 'crowd': [{'hours': '09:00-11:00', 'level': 0.4, 'kinds': ['person']}]}]
# 2 국내 공장 400 x 300: 등뼈 파이프랙 (y=150), 단위공정 4, 정문 · 하역장
for k, x in enumerate([20, 110, 200, 290, 380]): wp(f'k_rack{k}', 'plant_kr', x, 150)
path(*[f'k_rack{k}' for k in range(5)])
for name, x, y, at in [('k_pump', 110, 100, 'k_rack1'), ('k_hx', 200, 205, 'k_rack2'), ('k_steel', 290, 100, 'k_rack3'), ('k_gas', 290, 210, 'k_rack3'), ('k_ctrl', 20, 100, 'k_rack0'), ('k_unit3', 380, 100, 'k_rack4')]:
    wp(name, 'plant_kr', x, y); P.append([at, name])
wp('k_gate', 'plant_kr', 20, 280); P.append(['k_rack0', 'k_gate'])
wp('k_dock', 'plant_kr', 380, 280); P.append(['k_rack4', 'k_dock'])
CH += [{'id': 'K-SW1', 'waypoint': 'k_ctrl', 'yaw': 0.0, 'slots': 4, 'charge_pct_per_h': SWAP},
       {'id': 'K-SW2', 'waypoint': 'k_unit3', 'yaw': 0.0, 'slots': 4, 'charge_pct_per_h': SWAP}]
Z += [{'id': 'k_gate_z', 'floor': 'plant_kr', 'rect': [0, 160, 40, 300], 'crowd': [{'hours': '06:30-07:30', 'level': 0.8, 'kinds': ['person']}, {'hours': '14:30-15:30', 'level': 0.8, 'kinds': ['person']}, {'hours': '22:30-23:30', 'level': 0.6, 'kinds': ['person']}]},
      {'id': 'k_dock_z', 'floor': 'plant_kr', 'rect': [360, 160, 400, 300], 'crowd': [{'hours': '10:00-12:00', 'level': 0.6, 'kinds': ['forklift']}, {'hours': '14:00-16:00', 'level': 0.6, 'kinds': ['forklift']}]}]
# 3 해외 플랜트 600 x 400: 큰 길 (y=200), 철길 건널목 (x=300), Ex 구역, 크래커
for k, x in enumerate([20, 150, 300, 450, 580]): wp(f'e_road{k}', 'plant_eu', x, 200)
path(*[f'e_road{k}' for k in range(5)])
for name, x, y, at in [('e_sub', 20, 120, 'e_road0'), ('e_ex', 150, 320, 'e_road1'), ('e_ex_top', 170, 360, 'e_ex'), ('e_cracker', 450, 320, 'e_road3'), ('e_blockc', 580, 120, 'e_road4'), ('e_dock', 450, 60, 'e_road3')]:
    wp(name, 'plant_eu', x, y); P.append([at, name])
CH += [{'id': 'E-SW1', 'waypoint': 'e_sub', 'yaw': 0.0, 'slots': 4, 'charge_pct_per_h': SWAP},
       {'id': 'E-SW2', 'waypoint': 'e_blockc', 'yaw': 0.0, 'slots': 4, 'charge_pct_per_h': SWAP}]
Z += [{'id': 'e_dock_z', 'floor': 'plant_eu', 'rect': [400, 20, 500, 110], 'crowd': [{'hours': '07:00-17:00', 'level': 0.7, 'kinds': ['forklift']}]},
      {'id': 'e_rail_x', 'floor': 'plant_eu', 'rect': [290, 180, 310, 220]}]
# 4 경기장 60 x 40, 한 바퀴 240 m
for k, (x, y) in enumerate([(5, 5), (55, 5), (55, 35), (5, 35)]): wp(f'a_c{k}', 'arena', x, y)
path('a_c0', 'a_c1', 'a_c2', 'a_c3', 'a_c0')
wp('a_pit', 'arena', 2, 2); P.append(['a_pit', 'a_c0'])
CH += [{'id': 'A-SW', 'waypoint': 'a_pit', 'yaw': 0.0, 'slots': 2, 'charge_pct_per_h': SWAP}]
Z += [{'id': 'a_lap', 'floor': 'arena', 'rect': [0, 0, 60, 40]}]

M = [
 {'id': 'tunnel_sweep_w', 'steps': [{'goto': 't_v04'}, {'action': 'check_gas', 'duration_s': 60}, {'goto': 't_v01'}, {'goto': 't_swap_w'}]},
 {'id': 'tunnel_sweep_e', 'steps': [{'goto': 't_v08'}, {'action': 'check_gas', 'duration_s': 60}, {'goto': 't_v11'}, {'goto': 't_swap_e'}]},
 {'id': 'tunnel_joint_w', 'steps': [{'goto': 't_joint1'}, {'action': 'check_temp', 'duration_s': 90}, {'goto': 't_joint2'}, {'action': 'check_temp', 'duration_s': 90}, {'goto': 't_swap_w'}]},
 {'id': 'tunnel_joint_e', 'steps': [{'goto': 't_joint4'}, {'action': 'check_temp', 'duration_s': 90}, {'goto': 't_joint3'}, {'action': 'check_temp', 'duration_s': 90}, {'goto': 't_swap_e'}]},
 {'id': 'tunnel_sump', 'steps': [{'goto': 't_sump'}, {'action': 'inspect', 'duration_s': 120}, {'goto': 't_swap_e'}]},
 {'id': 'kr_round', 'steps': [{'goto': 'k_pump'}, {'action': 'check_temp', 'duration_s': 120}, {'goto': 'k_hx'}, {'action': 'read_gauge', 'duration_s': 120}, {'goto': 'k_gas'}, {'action': 'check_gas', 'duration_s': 120}, {'goto': 'k_ctrl'}]},
 {'id': 'kr_round_b', 'steps': [{'goto': 'k_gas'}, {'action': 'check_gas', 'duration_s': 120}, {'goto': 'k_hx'}, {'action': 'read_gauge', 'duration_s': 120}, {'goto': 'k_pump'}, {'action': 'check_temp', 'duration_s': 120}, {'goto': 'k_unit3'}]},
 {'id': 'kr_steel', 'steps': [{'goto': 'k_steel'}, {'action': 'inspect_valves', 'duration_s': 300}, {'wait': 60}, {'goto': 'k_ctrl'}]},
 {'id': 'eu_ex', 'steps': [{'goto': 'e_ex'}, {'action': 'check_points', 'duration_s': 300}, {'goto': 'e_ex_top'}, {'action': 'check_points', 'duration_s': 300}, {'goto': 'e_sub'}]},
 {'id': 'eu_cracker', 'steps': [{'goto': 'e_road2'}, {'goto': 'e_cracker'}, {'action': 'check_temp', 'duration_s': 180}, {'goto': 'e_dock'}, {'action': 'inspect', 'duration_s': 120}, {'goto': 'e_blockc'}]},
 {'id': 'arena_lap', 'steps': [{'goto': 'a_c0'}, {'goto': 'a_c1'}, {'goto': 'a_c2'}, {'goto': 'a_c3'}, {'goto': 'a_c0'}, {'action': 'lap_record', 'duration_s': 30}, {'goto': 'a_pit'}]},
]
R = []
def robot(i, start, ch, sched):
    R.append({'id': i, 'model': 'go2', 'start': start, 'home_charger': ch, 'battery': {'soc': 90, 'reserve': 10},
              'speed_mps': {'patrol': 0.8, 'transit': 1.0}, 'schedule': [{'at': a, 'mission': m} for a, m in sched]})
robot('T-01', 't_swap_w', 'T-SW-W', [(a, 'tunnel_sweep_w') for a in ['00:00', '04:00', '20:00']] + [('08:00', 'tunnel_joint_w'), ('16:00', 'tunnel_joint_w')])
robot('T-02', 't_swap_e', 'T-SW-E', [(a, 'tunnel_sweep_e') for a in ['00:00', '04:00', '20:00']] + [('08:00', 'tunnel_joint_e'), ('16:00', 'tunnel_joint_e')])
robot('T-03', 't_swap_w', 'T-SW-W', [(a, 'tunnel_sweep_w') for a in ['02:00', '06:00', '22:00']] + [('12:00', 'tunnel_joint_w')])
robot('T-04', 't_swap_e', 'T-SW-E', [(a, 'tunnel_sweep_e') for a in ['02:00', '06:00', '22:00']] + [('12:00', 'tunnel_sump'), ('19:00', 'tunnel_sump')])
kr_a = ['01:00', '05:00', '09:00', '13:00', '17:00']; kr_b = ['03:00', '07:00', '11:00', '15:00', '19:00']
for n, rid in enumerate(['K-01', 'K-02', 'K-03', 'K-04']):
    s = [(f"{int(a[:2]):02d}:{n*10:02d}", 'kr_round') for a in kr_a]   # 넷이 10 분 간격으로 나감 (같은 길)
    if rid == 'K-02': s += [('06:00', 'kr_steel'), ('14:30', 'kr_steel'), ('22:00', 'kr_steel')]
    robot(rid, 'k_ctrl', 'K-SW1', s)
for n, rid in enumerate(['K-05', 'K-06', 'K-07', 'K-08']):
    robot(rid, 'k_unit3', 'K-SW2', [(f"{int(a[:2]):02d}:{n*10:02d}", 'kr_round_b') for a in kr_b])
eu_a = ['06:00', '09:00', '12:00', '15:00', '18:00', '21:00']; eu_b = ['07:30', '10:30', '13:30', '16:30', '19:30', '22:30']
for n, rid in enumerate(['E-01', 'E-02', 'E-03', 'E-04']):
    robot(rid, 'e_sub', 'E-SW1', [(f"{int(a[:2]):02d}:{int(a[3:])+n*5:02d}", 'eu_ex') for a in eu_a])
for n, rid in enumerate(['E-05', 'E-06', 'E-07', 'E-08']):
    robot(rid, 'e_blockc', 'E-SW2', [(f"{int(a[:2]):02d}:{int(a[3:])+n*5:02d}", 'eu_cracker') for a in eu_b])
robot('A-01', 'a_pit', 'A-SW', [(a, 'arena_lap') for a in ['10:00', '14:00', '18:00']])
robot('A-02', 'a_pit', 'A-SW', [(a, 'arena_lap') for a in ['11:00', '15:00']])

# 교체 칸은 임무 끝마다 들르는 계획 (until_soc 95). 같은 교체 칸 두 자리를 넘지 않게 시각을 엇갈림
# 교체 칸: 임무마다 바로 뒤에 들름 (시작 + 1 분으로 걸어 두면 임무가 끝난 뒤 이어짐). 같은 칸 로봇은 출발을 엇갈려 자리 2 를 넘지 않음
# 교체 칸: 하루 시작에 집 교체 칸에 붙어 대기 (서 있으면 34.6 %/h 닳음). 임무마다 끝나는 시각 (모의 실행으로 잰 길이 + 2 분) 에 교체
DUR = {'tunnel_sweep_w': 32, 'tunnel_sweep_e': 32, 'tunnel_joint_w': 55, 'tunnel_joint_e': 55, 'tunnel_sump': 45,
       'kr_round': 27, 'kr_round_b': 31, 'kr_steel': 26, 'eu_ex': 33, 'eu_cracker': 40, 'arena_lap': 5}
CR = []
def hm(t): return f"{t//60:02d}:{t%60:02d}"
for r in R:
    first = min(int(i['at'][:2])*60+int(i['at'][3:]) for i in r['schedule'])
    if first > 0: CR.append({'robot': r['id'], 'charger': r['home_charger'], 'at': '00:00', 'until_soc': 95})
    for it in r['schedule']:
        t = int(it['at'][:2])*60+int(it['at'][3:]) + DUR[it['mission']] + 2
        CR.append({'robot': r['id'], 'charger': r['home_charger'], 'at': hm(t), 'until_soc': 95})
EV = [
 # crowd: 구역 시간대 (zones.crowd) 는 저절로. 아래는 정해진 막힘
 *[{'id': f'rail-{t.replace(":", "")}', 'kind': 'crowd', 'zone': 'e_rail_x', 'at': t, 'duration_min': 6, 'level': 1.0, 'kinds': []} for t in ['08:10', '10:40', '13:10', '15:40', '18:10']],  # 화차 통과 → 건널목 막힘
 {'id': 'kr-gate-shift', 'kind': 'crowd', 'zone': 'k_gate_z', 'at': '14:55', 'duration_min': 8, 'level': 1.0, 'kinds': ['person']},
 {'id': 'kr-conflict', 'kind': 'path_conflict', 'robot': 'K-03', 'at': '09:24', 'delay_min': 2},
 {'id': 'eu-conflict', 'kind': 'path_conflict', 'robot': 'E-07', 'at': '13:42', 'delay_min': 3},
 {'id': 'kr-valve-confirm', 'kind': 'wait_confirm', 'robot': 'K-02', 'at': '14:42', 'delay_min': 4},       # 철골 밸브 사람 확인
 {'id': 'kr-gauge', 'kind': 'wait_confirm', 'robot': 'K-03', 'at': '13:26', 'delay_min': 3},              # 게이지 범위 밖 → 사람 확인
 {'id': 't-joint-hot', 'kind': 'wait_confirm', 'robot': 'T-01', 'at': '16:17', 'delay_min': 5},           # 접속공간 과열 의심 → 사람 확인
 {'id': 'eu-ex-slow', 'kind': 'duration', 'robot': 'E-02', 'mission': 'eu_ex', 'at': '12:10', 'extra_min': 6},
 {'id': 'kr-gas', 'kind': 'fault', 'robot': 'K-07', 'at': '19:34', 'recover_min': 40, 'fail_code': 'OPERATOR_ABORT'},  # 가스 의심 → 멈춤 · 재배정
 {'id': 'eu-motor', 'kind': 'fault', 'robot': 'E-06', 'at': '14:07', 'fail_code': 'NAV_UNAVAILABLE'},     # 모터 과열 · 오늘 복귀 없음 → 재배정 시연
 {'id': 't-loc', 'kind': 'fault', 'robot': 'T-04', 'at': '06:15', 'recover_min': 3, 'fail_code': 'LOCALIZATION_LOST'},  # 반복 굴 위치 잃음
]
doc = {'version': 0, 'name': 'demo-day-v0.1', 'start': '2026-11-26T00:00:00+09:00', 'duration_h': 24, 'seed': 1126, 'pose_confidence': 0.95,
       'site': {'floors': floors, 'waypoints': W, 'paths': P, 'chargers': CH, 'zones': Z},
       'robots': R, 'missions': M, 'charge_rotation': CR, 'events': EV}
head = """# 분류: 데모 시나리오 (데모 에이전트 입력 · 에이전트 형식)
# 작성: app-design-lx · 2026-11-26 10:5x · 생성기로 만듦 (gen_demo_day.py)
# 근거: demo-scenario-contract-v0 D · G · H · I · app-lx 검증 (10:40, 틀 차이 250) · MAP-SITES.md · MAP-ARENA.md
# 요지: 하루 24 h · 22 대 · 지도 4 (floors 4 줄). 정시 · 같은 속도 · 배터리 교체 칸 교대. 어긋남은 crowd · path_conflict · wait_confirm · duration · fault 로만
# 상태: v0.1 · 좌표는 지도 제작 전 자리표 · floor_id / map_version_id 는 자리표 UUID
# 배터리: Go2 X 는 켠 채 충전되지 않음 → 「충전기」 는 배터리 교체 칸. charge_pct_per_h 500 (검증기 상한) = 85 % 에 약 10 분 (가정)
"""
open(out, 'w').write(head + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=200))

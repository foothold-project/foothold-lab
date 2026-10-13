# -*- coding: utf-8 -*-
"""CE12 adapter 의 알려진 답 시험 (CPU · Isaac 없이 · GPU 를 가린다).

분류: A/평가 · CE12-v1 이식 진단 1 시험
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:19
근거: DESIGN-astra-12-common-eval.md 5.2 · env_cfg.py · observation_manager.py · circular_buffer.py · joint_actions.py ·
      foothold-v2.env.yaml · sim/eval/gap_observations.py · actor_critic_moe_cts.py
요지: 기대값은 adapter 코드를 부르지 않고 손으로 적는다 (구현을 복제한 시험이 되지 않게). 변이 (mutate_adapters.py) 가 이 시험을 깨 본다.
상태: 시험 파일

실행: C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe test_adapters.py
      CE12_ADAPTERS=<경로> 를 주면 그 파일을 adapter 로 시험한다 (변이 사본용).
출력: 시험마다 「PASS Tnn 설명」 또는 「FAIL Tnn 설명: 사유」 한 줄. 하나라도 FAIL 이면 종료 코드 1.
"""
import os

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"  # torch 를 부르기 전에 GPU 를 가린다 (밤 학습 · 평가가 GPU 를 쓴다)
import sys  # noqa: E402

sys.dont_write_bytecode = True  # 남의 폴더 (foothold-lab sim/eval) 에 pyc 를 쓰지 않는다

import importlib.util  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import tempfile  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

torch.set_num_threads(2)
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = "C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexC"
sys.path.insert(0, WORK)
from isolation import assert_paths  # noqa: E402
TEST_ROOT = os.environ.get("CE12_TEST_ROOT", "")
assert_paths(test_root=TEST_ROOT, output=f"{TEST_ROOT}/adapter_output", real_fixture=os.path.join(os.path.dirname(HERE), "out_ce12", "native", "cts_e1_m20000"))
print(f"ISOLATION_PATHS temp={TEST_ROOT} real_fixture={os.path.join(os.path.dirname(HERE), 'out_ce12', 'native', 'cts_e1_m20000')}", flush=True)
tempfile.tempdir = TEST_ROOT
MOD_PATH = os.environ.get("CE12_ADAPTERS", os.path.join(HERE, "adapters.py"))
_spec = importlib.util.spec_from_file_location("ce12_adapters_under_test", MOD_PATH)
A = importlib.util.module_from_spec(_spec)
sys.modules["ce12_adapters_under_test"] = A
_spec.loader.exec_module(A)

# ------------------------------------------------------------------ 손으로 적은 기대값 (코드를 읽고 옮김 · adapter 를 안 부른다)
CTS_ORDER = ["FL_hip_joint", "FL_thigh_joint", "FL_calf_joint", "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
             "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint", "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint"]
# env_cfg.py:124-160 (PolicyCfg) · 이름 · 함수 · 차원 · scale · clip
CTS_TERMS = [("base_ang_vel", "base_ang_vel", 3, 0.25, (-100.0, 100.0)),
             ("projected_gravity", "projected_gravity", 3, 1.0, (-100.0, 100.0)),
             ("velocity_commands", "generated_commands", 3, 1.0, (-100.0, 100.0)),
             ("joint_pos", "joint_pos_rel", 12, 1.0, (-100.0, 100.0)),
             ("joint_vel", "joint_vel_rel", 12, 0.05, (-100.0, 100.0)),
             ("actions", "last_action", 12, 1.0, (-100.0, 100.0))]
# models/foothold-v2.env.yaml:539-669
V2_TERMS = [("base_lin_vel", "base_lin_vel", 3, None, None), ("base_ang_vel", "base_ang_vel", 3, None, None),
            ("projected_gravity", "projected_gravity", 3, None, None), ("velocity_commands", "generated_commands", 3, None, None),
            ("joint_pos", "joint_pos_rel", 12, None, None), ("joint_vel", "joint_vel_rel", 12, None, None),
            ("actions", "last_action", 12, None, None), ("height_scan", "height_scan_with_gap", 187, None, (-1.0, 1.0))]


def default_pose(name):
    """unitree.py:133-139 와 foothold-v2.env.yaml:155-159 (값이 같다): hip L +0.1 · R -0.1 · 앞 thigh 0.8 · 뒤 thigh 1.0 · calf -1.5."""
    leg, part = name.split("_")[0], name.split("_")[1]
    if part == "hip":
        return 0.1 if leg[1] == "L" else -0.1
    if part == "thigh":
        return 0.8 if leg[0] == "F" else 1.0
    return -1.5


# v2 의 런타임 관절 순서는 이 시험이 알 수 없다. 일부러 CTS 와 다른 순서 (Isaac USD 에서 흔한 부위별 순서 꼴) 를 시험용으로 준다.
# 이것은 v2 의 실제 순서라는 주장이 아니다 (실제 순서는 dump_native_v2.py 기록에서 받는다).
V2_FIXTURE_ORDER = ["FL_hip_joint", "FR_hip_joint", "RL_hip_joint", "RR_hip_joint", "FL_thigh_joint", "FR_thigh_joint",
                    "RL_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_calf_joint", "RL_calf_joint", "RR_calf_joint"]
SHUFFLED = ["RR_calf_joint", "FL_thigh_joint", "RL_hip_joint", "FR_calf_joint", "FL_hip_joint", "RR_hip_joint",
            "RL_calf_joint", "FR_thigh_joint", "RR_thigh_joint", "FL_calf_joint", "FR_hip_joint", "RL_thigh_joint"]
f32 = np.float32
TESTS = []


def test(tid, desc):
    def deco(fn):
        TESTS.append((tid, desc, fn))
        return fn
    return deco


def state(N, names, q, dq, ang, grav, cmd, lin=None, last=None, sz=None, hits=None):
    t = lambda a: None if a is None else torch.as_tensor(np.asarray(a, dtype=np.float32))  # noqa: E731
    return A.RawState(joint_names=list(names), joint_pos=t(q), joint_vel=t(dq), ang_vel_b=t(ang), projected_gravity_b=t(grav),
                      command=t(cmd), lin_vel_b=t(lin), last_action_raw=t(last), height_sensor_z=t(sz), ray_hits_z=t(hits))


def cts(N=2):
    return A.CTSStudentAdapter.from_source(N)


def v2(N=2, order=V2_FIXTURE_ORDER):
    return A.V2Adapter.from_env_yaml(order, N)


def eq(a, b, what, atol=0.0):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    assert a.shape == b.shape, f"{what}: 모양 {a.shape} != {b.shape}"
    d = np.abs(a - b)
    d = np.where(np.isnan(a) & np.isnan(b), 0.0, d)
    assert np.all(d <= atol), f"{what}: 최대 차 {np.nanmax(d):.3g} (첫 위치 {np.argwhere(d > atol)[0].tolist()})"


# ------------------------------------------------------------------ 3 step 손 표본 (CTS)
def sample_s(s, N=2):
    """step s (1, 2, ...) 의 원시 상태. env e 는 값에 e * 0.5 를 더한다. 모두 clip 범위 안."""
    ang = np.zeros((N, 3)); grav = np.zeros((N, 3)); cmd = np.zeros((N, 3))
    q = np.zeros((N, 12)); dq = np.zeros((N, 12)); last = np.zeros((N, 12))
    for e in range(N):
        ang[e] = 4.0 * (s + 0.1 * np.array([1, 2, 3])) + 4.0 * e * 0.5  # x 0.25 -> s+0.1.. (+0.5e) · clip 100 안
        grav[e] = 0.01 * s + np.array([0.0, 0.0, -1.0]) + 0.001 * e
        cmd[e] = s * np.array([0.1, 0.01, 0.001]) + 0.5 * e
        for j, n in enumerate(CTS_ORDER):
            q[e, j] = default_pose(n) + 0.01 * s + 0.001 * j + 0.5 * e
            dq[e, j] = 2.0 * s + 0.25 * j + 0.5 * e                    # x 0.05
            last[e, j] = 0.1 * s + 0.01 * j + 0.5 * e
    return dict(ang=ang, grav=grav, cmd=cmd, q=q, dq=dq, last=last)


def expected_single(smp, e):
    """45 칸 손 계산 (float32 연산 순서 그대로: q - q0, 그다음 x scale)."""
    out = []
    out += list(f32(smp["ang"][e]).astype(f32) * f32(0.25))
    out += list(f32(smp["grav"][e]))
    out += list(f32(smp["cmd"][e]))
    out += [f32(smp["q"][e, j]) - f32(default_pose(n)) for j, n in enumerate(CTS_ORDER)]
    out += list(f32(smp["dq"][e]).astype(f32) * f32(0.05))
    out += list(f32(smp["last"][e]))
    return np.array(out, dtype=f32)


def expected_history(singles):
    """singles: oldest -> newest 의 45 칸 표본 10 개. term-major 로 편다 (term 마다 10 칸 이어 붙인 뒤 term 끼리)."""
    blocks = [(0, 3), (3, 6), (6, 9), (9, 21), (21, 33), (33, 45)]
    return np.concatenate([np.concatenate([s[a:b] for s in singles]) for a, b in blocks])


def st_from(smp, names=CTS_ORDER, perm=None, with_last=True):
    q, dq = smp["q"], smp["dq"]
    if perm is not None:
        idx = [CTS_ORDER.index(n) for n in perm]
        q, dq, names = q[:, idx], dq[:, idx], perm
    return state(q.shape[0], names, q, dq, smp["ang"], smp["grav"], smp["cmd"], last=smp["last"] if with_last else None)


# ================================================================== 시험
@test("T01", "CTS 원본 설정 읽기: 관절 순서 · 항 순서 · scale · clip · 이력 10/1 · 행동 0.25 · clip [-100,100] (target) · 기본 자세")
def t01():
    sp = A.parse_cts_source()
    assert sp["obs_joint_names"] == CTS_ORDER, sp["obs_joint_names"]
    assert sp["action"]["joint_names"] == CTS_ORDER
    got = [(t.name, t.func, t.dim, t.scale, tuple(t.clip) if t.clip else None) for t in sp["policy_terms"]]
    assert got == CTS_TERMS, got
    assert sp["history_length"] == 10 and sp["single_history_length"] == 1
    assert all(v == 0.25 for v in sp["action"]["scale_by_name"].values())
    assert all(tuple(v) == (-100.0, 100.0) for v in sp["action"]["clip_by_name"].values())
    assert sp["action"]["preserve_order"] is True and sp["action"]["use_default_offset"] is True
    ad = cts(1)
    for n in CTS_ORDER:
        assert abs(ad.default_joint_pos[n] - default_pose(n)) == 0.0, n
        assert ad.default_joint_vel[n] == 0.0


@test("T02", "v2 env.yaml 읽기: 235 = 3+3+3+3+12+12+12+187 · scale 모두 None · clip 은 height 만 [-1,1] · offset 0.5 · miss 1.0 · 행동 0.25 · clip 없음 · `.*` preserve_order False")
def t02():
    sp = A.parse_v2_env_yaml()
    got = [(t.name, t.func, t.dim, t.scale, tuple(t.clip) if t.clip else None) for t in sp["policy_terms"]]
    assert got == V2_TERMS, got
    h = dict(sp["policy_terms"][-1].params)
    assert h == {"offset": 0.5, "miss_value": 1.0}, h
    a = sp["action"]
    assert a["scale"] == 0.25 and a["clip"] is None and a["joint_names"] == [".*"] and a["preserve_order"] is False
    hs = sp["height_scanner"]
    assert hs["size"] == [1.6, 1.0] and hs["resolution"] == 0.1 and hs["ordering"] == "xy" and hs["num_rays"] == 187
    assert hs["offset_pos"] == [0.0, 0.0, 20.0] and hs["ray_alignment"] == "yaw"
    ad = v2(1)
    for n in V2_FIXTURE_ORDER:
        assert ad.default_joint_pos[n] == default_pose(n), n


@test("T03", "CTS 이력 3 step 손 표본: term-major · oldest->newest · 첫 표본 10 칸 반복 · 최신 명령 87:90 · single 명령 6:9")
def t03():
    ad = cts(2)
    smps = [sample_s(s) for s in (1, 2, 3)]
    for smp in smps:
        o = ad.observe(st_from(smp))
    for e in range(2):
        singles = [expected_single(smps[0], e)] * 8 + [expected_single(smps[1], e), expected_single(smps[2], e)]
        eq(o["policy"][e].numpy(), expected_history(singles), f"policy env{e}")
        eq(o["single_obs"][e].numpy(), expected_single(smps[2], e), f"single env{e}")
        eq(o["policy"][e, 87:90].numpy(), f32(smps[2]["cmd"][e]), f"최신 명령 87:90 env{e}")
        eq(o["single_obs"][e, 6:9].numpy(), f32(smps[2]["cmd"][e]), f"single 명령 6:9 env{e}")
        eq(o["policy"][e, 60:63].numpy(), f32(smps[0]["cmd"][e]), f"가장 오래된 명령 60:63 env{e}")
    assert ad.history_slice("policy", "velocity_commands", -1) == (87, 90)
    # 첫 step 만 넣었을 때 10 칸 모두 같은 표본 (0 으로 채우지 않는다)
    ad1 = cts(2)
    o1 = ad1.observe(st_from(smps[0]))
    for e in range(2):
        eq(o1["policy"][e].numpy(), expected_history([expected_single(smps[0], e)] * 10), f"첫 표본 반복 env{e}")


@test("T04", "CTS reset(ids): 그 env 만 다음 표본을 10 칸에 반복 · 다른 env 는 이어감 · 기억한 raw action 은 0")
def t04():
    ad = cts(2)
    smps = [sample_s(s) for s in (1, 2, 3, 4)]
    for smp in smps[:3]:
        ad.observe(st_from(smp))
        ad.decode_action(torch.full((2, 12), 0.7))
    ad.reset(torch.tensor([0]))
    o = ad.observe(st_from(smps[3], with_last=False))   # last action 은 adapter 가 기억한 값
    s4_e0 = expected_single(smps[3], 0)
    s4_e0[33:45] = 0.0                                   # reset 된 env 의 last_action = 0 (action_manager.reset)
    eq(o["policy"][0].numpy(), expected_history([s4_e0] * 10), "reset env0")
    s_e1 = [expected_single(smps[i], 1) for i in range(4)]
    s_e1[3] = s_e1[3].copy()
    s_e1[3][33:45] = f32(0.7)                            # reset 안 된 env1 은 직전 raw 0.7
    eq(o["policy"][1].numpy(), expected_history([s_e1[0]] * 7 + s_e1[1:]), "이어가는 env1")
    eq(o["single_obs"][0, 33:45].numpy(), np.zeros(12, f32), "reset env0 single last_action")


@test("T05", "디버그 읽기 (update_history=False) 는 이력을 전진시키지 않는다 · 버퍼가 없을 때의 읽기는 저장하지 않는다")
def t05():
    ad = cts(2)
    smps = [sample_s(s) for s in (1, 2, 3)]
    ad.observe(st_from(smps[0]))
    o2 = ad.observe(st_from(smps[1]))
    p1 = ad.observe(st_from(smps[2]), update_history=False)
    p2 = ad.observe(st_from(smps[2]), update_history=False)
    eq(p1["policy"].numpy(), o2["policy"].numpy(), "읽기 1 = 직전 갱신")
    eq(p2["policy"].numpy(), o2["policy"].numpy(), "읽기 2 = 직전 갱신")
    eq(p1["single_obs"].numpy(), o2["single_obs"].numpy(), "single 읽기")
    o3 = ad.observe(st_from(smps[2]))
    for e in range(2):
        singles = [expected_single(smps[0], e)] * 8 + [expected_single(smps[1], e), expected_single(smps[2], e)]
        eq(o3["policy"][e].numpy(), expected_history(singles), f"읽기 뒤 갱신 env{e}")
    fresh = cts(2)
    pk = fresh.observe(st_from(smps[0]), update_history=False)
    eq(pk["policy"][0].numpy(), expected_history([expected_single(smps[0], 0)] * 10), "버퍼 없을 때 읽기")
    o = fresh.observe(st_from(smps[1]))
    eq(o["policy"][0].numpy(), expected_history([expected_single(smps[1], 0)] * 10), "그 읽기는 저장 안 됨")


@test("T06", "CTS scale · clip 경계: clip 다음 scale (ang 400->25 · dq 150->5 · q_rel 150->100 · action 120->100 · 경계 100 유지)")
def t06():
    ad = cts(1)
    q = np.array([[default_pose(n) for n in CTS_ORDER]], dtype=np.float64)
    q[0, 0] += 150.0
    q[0, 1] += 100.0
    q[0, 2] += -150.0
    dq = np.zeros((1, 12)); dq[0, 0] = 150.0; dq[0, 1] = -150.0; dq[0, 2] = 100.0; dq[0, 3] = 2.0
    last = np.zeros((1, 12)); last[0, 0] = 120.0; last[0, 1] = -100.0; last[0, 2] = 0.3
    o = ad.observe(state(1, CTS_ORDER, q, dq, [[400.0, -400.0, 2.0]], [[0.0, 0.5, -0.9]], [[0.3, 0.0, -0.5]], last=last))
    s = o["single_obs"][0].numpy()
    eq(s[0:3], [25.0, -25.0, f32(2.0) * f32(0.25)], "ang vel")
    eq(s[3:6], [0.0, 0.5, f32(-0.9)], "gravity")
    eq(s[6:9], [f32(0.3), 0.0, -0.5], "command")
    eq(s[9:12], [100.0, min(f32(100.0), f32(f32(q[0, 1]) - f32(default_pose(CTS_ORDER[1])))), -100.0], "joint pos rel")
    eq(s[21:25], [5.0, -5.0, 5.0, f32(2.0) * f32(0.05)], "joint vel")
    eq(s[33:36], [100.0, -100.0, f32(0.3)], "last action")


@test("T07", "v2 는 scale 이 없다 (CMD-R 의 0.25 · 0.05 를 복사하지 않는다) · 항 배치 0:3 lin · 3:6 ang · 9:12 cmd · 12:24 q · 24:36 dq · 36:48 act · 48:235 height")
def t07():
    ad = v2(1)
    q = np.array([[default_pose(n) + 150.0 for n in V2_FIXTURE_ORDER]])
    dq = np.full((1, 12), 150.0)
    last = np.full((1, 12), 120.0)
    hits = np.zeros((1, 187))
    o = ad.observe(state(1, V2_FIXTURE_ORDER, q, dq, [[400.0, 2.0, -3.0]], [[0.0, 0.0, -1.0]], [[0.3, 0.0, 0.5]],
                         lin=[[1.5, -0.2, 0.0]], last=last, sz=[0.4], hits=hits))["policy"][0].numpy()
    assert o.shape == (235,), o.shape
    eq(o[0:3], f32([1.5, -0.2, 0.0]), "lin vel")
    eq(o[3:6], [400.0, 2.0, -3.0], "ang vel (scale 없음)")
    eq(o[9:12], f32([0.3, 0.0, 0.5]), "command")
    eq(o[12:24], [f32(f32(default_pose(n) + 150.0) - f32(default_pose(n))) for n in V2_FIXTURE_ORDER], "q rel (clip 없음)")
    eq(o[24:36], np.full(12, 150.0), "dq (scale 없음)")
    eq(o[36:48], np.full(12, 120.0), "last action")
    eq(o[48:235], np.full(187, f32(f32(0.4) - f32(0.0)) - f32(0.5)), "height 평지 -0.1")


@test("T08", "CTS 관절 이름 순서를 섞은 입력이 같은 관측을 낸다 (두 step · 이력 포함 · 비트 동일)")
def t08():
    a1, a2 = cts(2), cts(2)
    for s in (1, 2):
        smp = sample_s(s)
        o1 = a1.observe(st_from(smp))
        o2 = a2.observe(st_from(smp, perm=SHUFFLED))
    eq(o1["policy"].numpy(), o2["policy"].numpy(), "policy")
    eq(o1["single_obs"].numpy(), o2["single_obs"].numpy(), "single")
    eq(o1["single_obs"][0, 9:21].numpy(), [f32(sample_s(2)["q"][0, j]) - f32(default_pose(n)) for j, n in enumerate(CTS_ORDER)],
       "q_rel 이 CTS 순서")


@test("T09", "v2 관절 이름 순서를 섞은 입력이 같은 관측을 낸다 · q_rel 은 adapter 에 준 순서 (V2_FIXTURE_ORDER)")
def t09():
    ad = v2(1)
    base = {n: default_pose(n) + 0.01 * (i + 1) for i, n in enumerate(CTS_ORDER)}
    vel = {n: 0.5 * (i + 1) for i, n in enumerate(CTS_ORDER)}
    outs = []
    for order in (CTS_ORDER, SHUFFLED, V2_FIXTURE_ORDER):
        outs.append(ad.observe(state(1, order, [[base[n] for n in order]], [[vel[n] for n in order]], [[0, 0, 0]], [[0, 0, -1]],
                                     [[0, 0, 0]], lin=[[0, 0, 0]], last=np.zeros((1, 12)), sz=[0.4], hits=np.zeros((1, 187))))["policy"])
    eq(outs[0].numpy(), outs[1].numpy(), "CTS 순서 입력 vs 섞은 입력")
    eq(outs[0].numpy(), outs[2].numpy(), "CTS 순서 입력 vs v2 순서 입력")
    eq(outs[0][0, 12:24].numpy(), [f32(base[n]) - f32(default_pose(n)) for n in V2_FIXTURE_ORDER], "q_rel 이 v2 순서")
    eq(outs[0][0, 24:36].numpy(), [vel[n] for n in V2_FIXTURE_ORDER], "dq 가 v2 순서")


@test("T10", "v2 height 알려진 답: sensor z 0.4 · hit 0 -> -0.1 (offset 20 안 더함) · inf/-inf/NaN -> +1 · 경계 clip [-1,1]")
def t10():
    ad = v2(1)
    hits = np.zeros((1, 187))
    hits[0, 1] = np.inf
    hits[0, 2] = np.nan
    hits[0, 3] = -np.inf
    hits[0, 4] = 2.0    # 0.4 - 2 - 0.5 = -2.1 -> -1
    hits[0, 5] = -3.0   # 0.4 + 3 - 0.5 = 2.9 -> 1
    hits[0, 6] = -0.6   # 0.5 경계 안
    o = ad.observe(state(1, V2_FIXTURE_ORDER, [[default_pose(n) for n in V2_FIXTURE_ORDER]], np.zeros((1, 12)), [[0, 0, 0]],
                         [[0, 0, -1]], [[0, 0, 0]], lin=[[0, 0, 0]], last=np.zeros((1, 12)), sz=[0.4], hits=hits))["policy"][0].numpy()
    h = o[48:]
    eq(h[0], f32(f32(0.4) - f32(0.0)) - f32(0.5), "평지", atol=0.0)
    assert abs(float(h[0]) + 0.1) < 1e-6, h[0]
    eq(h[1:4], [1.0, 1.0, 1.0], "miss")
    eq(h[4:6], [-1.0, 1.0], "clip")
    eq(h[6], f32(f32(0.4) - f32(-0.6)) - f32(0.5), "경계 안")


@test("T11", "v2 height 식이 저장소 sim/eval/gap_observations.py height_scan_with_gap 과 비트 동일 (무작위 · inf · NaN 섞음) · 그 뒤 clip")
def t11():
    p = os.path.join(A.LAB_ROOT, "sim", "eval", "gap_observations.py")
    sp = importlib.util.spec_from_file_location("lab_gap_observations", p)
    g = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(g)
    rng = np.random.RandomState(7)
    N = 5
    sz = rng.uniform(0.1, 0.6, N).astype(f32)
    hits = rng.uniform(-1.5, 1.5, (N, 187)).astype(f32)
    hits[rng.rand(N, 187) < 0.1] = np.inf
    hits[rng.rand(N, 187) < 0.05] = np.nan

    class _D:
        pos_w = torch.tensor(np.stack([np.zeros(N), np.zeros(N), sz], 1), dtype=torch.float32)
        ray_hits_w = torch.tensor(np.stack([np.zeros((N, 187)), np.zeros((N, 187)), hits], -1), dtype=torch.float32)

    class _S:
        data = _D()

    class _Scene:
        sensors = {"height_scanner": _S()}

    class _Env:
        scene = _Scene()

    class _Cfg:
        name = "height_scanner"

    ref = g.height_scan_with_gap(_Env(), _Cfg(), offset=0.5, miss_value=1.0).clamp(-1.0, 1.0).numpy()
    ad = v2(N)
    o = ad.observe(state(N, V2_FIXTURE_ORDER, np.tile([default_pose(n) for n in V2_FIXTURE_ORDER], (N, 1)), np.zeros((N, 12)),
                         np.zeros((N, 3)), np.tile([0, 0, -1.0], (N, 1)), np.zeros((N, 3)), lin=np.zeros((N, 3)),
                         last=np.zeros((N, 12)), sz=sz, hits=hits))["policy"].numpy()[:, 48:]
    eq(o, ref, "gap_observations 와 비교", atol=0.0)


@test("T12", "187 광선 순서: grid xy 순서 (x 가 가장 빨리) · 0=(-0.8,-0.5) · 16=(0.8,-0.5) · 17=(-0.8,-0.4) · 93=(0,0) · 186=(0.8,0.5) · adapter 가 순서를 안 바꿈")
def t12():
    g = A.grid_pattern_local((1.6, 1.0), 0.1, "xy").numpy()
    assert g.shape == (187, 2), g.shape
    for i, xy in ((0, (-0.8, -0.5)), (1, (-0.7, -0.5)), (16, (0.8, -0.5)), (17, (-0.8, -0.4)), (93, (0.0, 0.0)), (186, (0.8, 0.5))):
        eq(g[i], xy, f"광선 {i}", atol=1e-6)
    ad = v2(1)
    hits = (np.arange(187) * 0.001)[None, :].astype(f32)
    o = ad.observe(state(1, V2_FIXTURE_ORDER, [[default_pose(n) for n in V2_FIXTURE_ORDER]], np.zeros((1, 12)), [[0, 0, 0]],
                         [[0, 0, -1]], [[0, 0, 0]], lin=[[0, 0, 0]], last=np.zeros((1, 12)), sz=[0.4], hits=hits))["policy"][0].numpy()
    eq(o[48:], (f32(0.4) - hits[0]) - f32(0.5), "광선 순서 보존")
    loc = ad.locate("policy", 48 + 17)
    assert loc["term"] == "height_scan" and loc["ray"] == 17 and loc["ray_local_xy"] == [-0.8, -0.4], loc


@test("T13", "행동 해석: 관절마다 다른 target 을 모델별 역변환 raw 로 만들면 두 adapter 모두 이름으로 같은 target 을 복원 · 같은 raw 벡터는 모델마다 다른 target")
def t13():
    target = {n: default_pose(n) + 0.02 * (i + 1) * (-1) ** i for i, n in enumerate(CTS_ORDER)}
    a_c, a_v = cts(1), v2(1)
    raw_c = torch.tensor([[(f32(target[n]) - f32(default_pose(n))) / f32(0.25) for n in CTS_ORDER]], dtype=torch.float32)
    raw_v = torch.tensor([[(f32(target[n]) - f32(default_pose(n))) / f32(0.25) for n in V2_FIXTURE_ORDER]], dtype=torch.float32)
    common = SHUFFLED
    tc = a_c.decode_action(raw_c, out_joint_names=common).numpy()[0]
    tv = a_v.decode_action(raw_v, out_joint_names=common).numpy()[0]
    eq(tc, [target[n] for n in common], "CTS 복원", atol=1e-6)
    eq(tv, [target[n] for n in common], "v2 복원", atol=1e-6)
    t_wrong = a_v.decode_action(raw_c, out_joint_names=common).numpy()[0]
    assert np.max(np.abs(t_wrong - tv)) > 0.01, "CTS raw 를 v2 순서로 읽었는데 같은 target 이 나왔다"
    # 자기 순서로 돌려받으면 raw 순서 그대로 (CTS: FL_hip 이 0 번)
    eq(a_c.decode_action(raw_c).numpy()[0, 0], target["FL_hip_joint"], "CTS 0 번 = FL_hip", atol=1e-6)
    eq(a_v.decode_action(raw_v).numpy()[0, 1], target["FR_hip_joint"], "v2 fixture 1 번 = FR_hip", atol=1e-6)


@test("T14", "행동 clip 은 target 에 (CTS [-100,100] · v2 없음) · offset 인자를 그대로 쓴다")
def t14():
    a_c, a_v = cts(2), v2(2)
    raw = torch.tensor([[1000.0] * 12, [-1000.0] * 12])
    eq(a_c.decode_action(raw).numpy(), np.array([[100.0] * 12, [-100.0] * 12]), "CTS target clip")
    eq(a_v.decode_action(raw).numpy(), np.array([[f32(250.0) + f32(default_pose(n)) for n in V2_FIXTURE_ORDER],
                                                 [f32(-250.0) + f32(default_pose(n)) for n in V2_FIXTURE_ORDER]]), "v2 clip 없음")
    off = torch.tensor([[0.01 * j for j in range(12)], [-0.02 * j for j in range(12)]], dtype=torch.float32)
    r = torch.tensor([[0.4] * 12, [-0.8] * 12])
    eq(a_c.decode_action(r, offset=off).numpy(), (r * 0.25 + off).numpy(), "offset 인자")


@test("T15", "decode_action 의 raw 가 다음 관측의 last_action (CTS single 33:45 · v2 36:48) · 이름 순서는 정책 자기 순서")
def t15():
    a_c, a_v = cts(1), v2(1)
    raw = torch.tensor([[0.1 * (j + 1) for j in range(12)]], dtype=torch.float32)
    a_c.decode_action(raw)
    a_v.decode_action(raw)
    smp = sample_s(1, N=1)
    oc = a_c.observe(st_from(smp, with_last=False))
    eq(oc["single_obs"][0, 33:45].numpy(), raw[0].numpy(), "CTS last_action")
    ov = a_v.observe(state(1, CTS_ORDER, smp["q"], smp["dq"], smp["ang"], smp["grav"], smp["cmd"], lin=[[0, 0, 0]], sz=[0.4],
                           hits=np.zeros((1, 187))))
    eq(ov["policy"][0, 36:48].numpy(), raw[0].numpy(), "v2 last_action")
    a_v.reset()
    ov2 = a_v.observe(state(1, CTS_ORDER, smp["q"], smp["dq"], smp["ang"], smp["grav"], smp["cmd"], lin=[[0, 0, 0]], sz=[0.4],
                            hits=np.zeros((1, 187))))
    eq(ov2["policy"][0, 36:48].numpy(), np.zeros(12), "v2 reset 뒤 0")


@test("T16", "v2 adapter 는 관절 이름 목록 없이 만들 수 없다 · 이름 대응은 빠진 · 겹친 이름을 거절")
def t16():
    sp = A.parse_v2_env_yaml()
    for bad in (lambda: A.V2Adapter(sp, None, 1), lambda: A.V2Adapter.from_env_yaml(num_envs=1)):
        try:
            bad()
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError("이름 없이 만들어졌다")
    for src, dst in ((CTS_ORDER[:-1], CTS_ORDER), (CTS_ORDER + ["FL_hip_joint"], CTS_ORDER)):
        try:
            A.name_index(src, dst)
        except (KeyError, ValueError):
            pass
        else:
            raise AssertionError("잘못된 이름 목록이 통과했다")


def _small_cts_policy():
    from tensordict import TensorDict
    from rsl_rl.modules.actor_critic_moe_cts import ActorCriticMoECTS
    torch.manual_seed(3)
    obs = TensorDict({"policy": torch.zeros(1, 450), "critic": torch.zeros(1, 275), "single_obs": torch.zeros(1, 45)}, batch_size=[1])
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        m = ActorCriticMoECTS(obs, {"policy": ["policy"], "critic": ["critic"]}, 12, actor_hidden_dims=[16, 16], critic_hidden_dims=[16],
                              teacher_encoder_hidden_dims=[16], student_encoder_hidden_dims=[32, 16, 16], expert_num=2, latent_dim=8)
    return m.eval()


def _critic_invariance(m, ad, smps):
    from tensordict import TensorDict
    for smp in smps:
        o = ad.observe(st_from(smp))
    N = o["policy"].shape[0]
    g = torch.Generator().manual_seed(11)
    base = TensorDict({"policy": o["policy"], "single_obs": o["single_obs"], "critic": torch.zeros(N, 275)}, batch_size=[N])
    alt = TensorDict({"policy": o["policy"], "single_obs": o["single_obs"], "critic": torch.randn(N, 275, generator=g) * 10.0},
                     batch_size=[N])
    with torch.inference_mode():
        a0 = m.act_inference(base)
        a1 = m.act_inference(alt)
        a_ad = ad.infer(m, o)
        a_pol = m.act_inference(TensorDict({"policy": o["policy"] + 0.1, "single_obs": o["single_obs"], "critic": base["critic"]}, batch_size=[N]))
        a_sin = m.act_inference(TensorDict({"policy": o["policy"], "single_obs": o["single_obs"] + 0.1, "critic": base["critic"]}, batch_size=[N]))
        lat, _ = m.student_moe_encoder(m.actor_obs_normalizer(o["policy"]))
        a_man = m.actor(torch.cat([lat, m.single_obs_normalizer(o["single_obs"])], dim=-1))
    assert torch.equal(a0, a1), f"critic 을 바꾸자 action 이 변했다: {float((a0 - a1).abs().max())}"
    assert torch.equal(a0, a_ad), "adapter.infer (critic 열쇠 없음) 와 act_inference 가 다르다"
    assert torch.equal(a0, a_man), "student 경로 손 계산과 act_inference 가 다르다"
    assert float((a_pol - a0).abs().max()) > 0, "policy 이력을 바꿔도 action 이 그대로 (양성 대조 실패)"
    assert float((a_sin - a0).abs().max()) > 0, "single_obs 를 바꿔도 action 이 그대로 (양성 대조 실패)"
    assert torch.isfinite(a0).all()
    return a0


@test("T17", "act_inference: 작은 무작위 ActorCriticMoECTS 에서 critic 입력을 바꿔도 action 비트 동일 · policy/single 은 바뀜 · adapter.infer 는 critic 없이")
def t17():
    _critic_invariance(_small_cts_policy(), cts(3), [sample_s(s, N=3) for s in (1, 2)])


@test("T18", "실제 E1 체크포인트 (model_20000) 를 CPU 로 strict 적재 · 같은 invariance · adapter 관측으로 유한한 action")
def t18():
    ck = os.path.join(A.CTS_E1_RUN, "model_20000.pt")
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        m, info = A.load_cts_policy_cpu(ck)
    assert info["dims"] == {"policy": 450, "critic": 275, "single_obs": 45, "actions": 12}, info["dims"]
    a0 = _critic_invariance(m, cts(2), [sample_s(s) for s in (1, 2)])
    assert a0.shape == (2, 12)


@test("T19", "v2 체크포인트를 CPU 로 strict 적재 · adapter 235 관측으로 유한한 action (12)")
def t19():
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        m, info = A.load_v2_policy_cpu()
    assert info["dims"] == {"policy": 235, "actions": 12}, info["dims"]
    ad = v2(2)
    o = ad.observe(state(2, V2_FIXTURE_ORDER, np.tile([default_pose(n) for n in V2_FIXTURE_ORDER], (2, 1)), np.zeros((2, 12)),
                         np.zeros((2, 3)), np.tile([0, 0, -1.0], (2, 1)), [[0.5, 0, 0], [0, 0, 0]], lin=np.zeros((2, 3)),
                         sz=[0.35, 0.35], hits=np.zeros((2, 187))))
    a = ad.infer(m, o)
    assert a.shape == (2, 12) and torch.isfinite(a).all()


@test("T20", "서명 JSON: CTS 450/45 · 최신 명령 [87,90] · single [6,9] · clip 은 target · v2 235 · 이름 목록 · sha256")
def t20():
    d = tempfile.mkdtemp(prefix="ce12_sig_")
    try:
        sc = A.write_signature(cts(1), os.path.join(d, "cts.json"))
        sv = A.write_signature(v2(1), os.path.join(d, "v2.json"))
        rc = json.load(open(os.path.join(d, "cts.json"), encoding="utf-8"))
        assert rc["signature_sha256"] == sc["signature_sha256"] and len(rc["signature_sha256"]) == 64
        g = {x["name"]: x for x in rc["observation"]["groups"]}
        assert g["policy"]["dim"] == 450 and g["single_obs"]["dim"] == 45 and g["policy"]["history_length"] == 10
        assert rc["observation"]["latest_command_slice_policy"] == [87, 90] and rc["observation"]["command_slice_single_obs"] == [6, 9]
        assert rc["joint_names"]["observation"] == CTS_ORDER and rc["joint_names"]["action"] == CTS_ORDER
        assert all(v == [-100.0, 100.0] for v in rc["action"]["clip_on_target"].values())
        assert sv["observation"]["groups"][0]["dim"] == 235 and sv["joint_names"]["observation"] == V2_FIXTURE_ORDER
        assert sv["action"]["clip_on_target"] is None
        assert sv["observation"]["height_scan"]["scanner"]["offset_pos"] == [0.0, 0.0, 20.0]
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ------------------------------------------------------------------ compare_native 의 위치 보고 (가짜 기록)
def _import_compare():
    path = os.environ.get("CE12_COMPARE", os.path.join(HERE, "compare_native.py"))
    sp = importlib.util.spec_from_file_location("ce12_compare_under_test", path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


def make_fake_dump(model, d, T=4, N=3, seed=0, policy=None):
    """시험 대상 adapter 로 「native」 칸을 채운 가짜 기록. compare 의 위치 보고를 시험하는 용도이지 adapter 정답 시험이 아니다.
    policy 를 주면 raw_action 을 그 정책의 닫힌 고리 출력으로 채운다 (--recompute_action 경로 시험용)."""
    rng = np.random.RandomState(seed)
    art = SHUFFLED
    ad = cts(N) if model == "cts_student" else v2(N)
    K = {}
    sh = lambda *s: np.zeros(s, dtype=np.float32)  # noqa: E731
    for k, s in (("root_pos_w", 3), ("root_quat_w", 4), ("lin_vel_b", 3), ("ang_vel_b", 3), ("projected_gravity_b", 3), ("command", 3)):
        K[k] = rng.uniform(-0.5, 0.5, (T + 1, N, s)).astype(np.float32)
    K["joint_pos"] = (np.array([default_pose(n) for n in art])[None, None] + rng.uniform(-0.1, 0.1, (T + 1, N, 12))).astype(np.float32)
    K["joint_vel"] = rng.uniform(-2, 2, (T + 1, N, 12)).astype(np.float32)
    K["raw_action"] = rng.uniform(-1, 1, (T, N, 12)).astype(np.float32)
    K["action_offset"] = np.tile(np.array([ad.default_joint_pos[n] for n in ad.action_joint_names], np.float32), (T, N, 1))
    K["reset_after_step"] = np.zeros((T, N), bool)
    K["reset_after_step"][1, 2] = True
    K["terminated"] = K["reset_after_step"].copy()
    K["time_out"] = np.zeros((T, N), bool)
    if model == "v2":
        K["height_sensor_pos_w"] = rng.uniform(0.3, 0.4, (T + 1, N, 3)).astype(np.float32)
        K["ray_hits_w"] = rng.uniform(-0.2, 0.2, (T + 1, N, 187, 3)).astype(np.float32)
        g = A.grid_pattern_local().numpy()
        K["ray_starts_local"] = np.concatenate([g, np.full((187, 1), 20.0)], 1).astype(np.float32)
    K["last_action"] = sh(T + 1, N, 12)
    K["art_joint_names"] = np.array(art)
    pol, sin, tgt = [], [], []
    for k in range(T + 1):
        st = A.state_from_dump(K, k)
        K["last_action"][k] = ad._last_raw.numpy()
        o = ad.observe(st)
        pol.append(o["policy"].numpy())
        if model == "cts_student":
            sin.append(o["single_obs"].numpy())
        if k < T:
            if policy is not None:
                K["raw_action"][k] = ad.infer(policy, o).numpy()
            tgt.append(ad.decode_action(torch.tensor(K["raw_action"][k]), offset=torch.tensor(K["action_offset"][k])).numpy())
            ids = np.nonzero(K["reset_after_step"][k])[0]
            if len(ids):
                ad.reset(torch.tensor(ids))
    K["obs_policy"] = np.stack(pol)
    if model == "cts_student":
        K["obs_single_obs"] = np.stack(sin)
        K["obs_critic"] = sh(T + 1, N, 275)
    K["joint_target"] = np.stack(tgt)
    K["obs_joint_names"] = np.array(ad.obs_joint_names)
    K["action_joint_names"] = np.array(ad.action_joint_names)
    K["default_joint_pos"] = np.tile(np.array([default_pose(n) for n in art], np.float32), (N, 1))
    K["default_joint_vel"] = sh(N, 12)
    K["cell_index"] = np.zeros(N, np.int64)
    K["cell_names"] = np.array(["fake"])
    K["cell_cmd"] = sh(1, 3)
    K["model"] = np.array(model)
    p = os.path.join(d, f"{model}.npz")
    np.savez(p, **K)
    groups = ["policy", "single_obs"] if model == "cts_student" else ["policy"]
    meta = {"model": model, "obs_layout": {g: {"names": [x[0] for x in ad.layout(g)], "dims": [[x[2] - x[1]] for x in ad.layout(g)]}
                                           for g in groups}}
    mp = os.path.join(d, f"{model}.meta.json")
    json.dump(meta, open(mp, "w", encoding="utf-8"))
    return p, mp, K


def _rewrite(p, K):
    np.savez(p, **K)


@test("T21", "compare_native: 일치하는 가짜 기록은 통과 · 한 칸을 바꾸면 그 step · env · term · 이력 칸 · 관절 이름을 첫 불일치로 보고")
def t21():
    C = _import_compare()
    d = tempfile.mkdtemp(prefix="ce12_cmp_")
    try:
        p, mp, K = make_fake_dump("cts_student", d)
        r = C.compare(p, mp, A=A)
        assert r["status"] == "pass", [c for c in r["checks"] if not c["ok"]][:3]
        K["obs_policy"][2, 1, 88] += 1e-3                 # velocity_commands 최신 칸 (slot 9) 의 vy
        _rewrite(p, K)
        r = C.compare(p, mp, A=A)
        f = r["first_failure"]
        assert r["status"] == "mismatch" and f["check"] == "obs.policy" and f["step"] == 2 and f["env"] == 1, f
        assert f["where"]["term"] == "velocity_commands" and f["where"]["history_slot"] == 9 and f["where"]["element"] == 1, f
        K["obs_policy"][2, 1, 88] -= 1e-3
        j = CTS_ORDER.index("RL_thigh_joint")
        K["joint_target"][1, 0, j] += 1e-3
        _rewrite(p, K)
        r = C.compare(p, mp, A=A)
        f = r["first_failure"]
        assert f["check"] == "joint_target" and f["step"] == 1 and f["env"] == 0 and f["where"]["joint"] == "RL_thigh_joint", f
        K["joint_target"][1, 0, j] -= 1e-3
        K["obs_policy"][3, 0, 330 + 9 * 12 + CTS_ORDER.index("FR_calf_joint")] += 1e-3   # actions 최신 칸
        _rewrite(p, K)
        f = C.compare(p, mp, A=A)["first_failure"]
        assert f["where"]["term"] == "actions" and f["where"]["history_slot"] == 9 and f["where"]["joint"] == "FR_calf_joint", f
        pv, mpv, KV = make_fake_dump("v2", d, seed=1)
        r = C.compare(pv, mpv, A=A)
        assert r["status"] == "pass", [c for c in r["checks"] if not c["ok"]][:3]
        KV["obs_policy"][0, 2, 48 + 93] += 1e-3
        _rewrite(pv, KV)
        f = C.compare(pv, mpv, A=A)["first_failure"]
        assert f["where"]["term"] == "height_scan" and f["where"]["ray"] == 93 and f["where"]["ray_local_xy"] == [0.0, 0.0], f
        KV["obs_policy"][0, 2, 48 + 93] -= 1e-3
        KV["obs_joint_names"] = np.array(V2_FIXTURE_ORDER[::-1])
        _rewrite(pv, KV)
        r = C.compare(pv, mpv, A=A)
        assert r["status"] == "mismatch" and any(c["name"] == "names.obs_vs_action_joint_names" and not c["ok"] for c in r["checks"]), r["status"]
    finally:
        shutil.rmtree(d, ignore_errors=True)


@test("T22", "compare_native --recompute_action 경로: 실제 체크포인트 (E1 · v2) 닫힌 고리로 만든 가짜 기록에서 CPU 재계산 action 차 0 · 통과")
def t22():
    import contextlib
    import io
    C = _import_compare()
    d = tempfile.mkdtemp(prefix="ce12_rec_")
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            mc, _ = A.load_cts_policy_cpu(os.path.join(A.CTS_E1_RUN, "model_20000.pt"))
            mv, _ = A.load_v2_policy_cpu()
        for model, m, ck in (("cts_student", mc, os.path.join(A.CTS_E1_RUN, "model_20000.pt")), ("v2", mv, A.V2_CHECKPOINT)):
            p, mp, K = make_fake_dump(model, d, T=4, N=3, seed=5, policy=m)
            r = C.compare(p, mp, A=A, recompute_action=True, checkpoint=ck)
            bad = [c for c in r["checks"] if not c["ok"]]
            assert r["status"] == "pass", (model, bad[:2])
            rc = {c["name"]: c for c in r["checks"]}
            assert rc["action.recompute_from_adapter_obs"]["max_abs"] == 0.0 and rc["action.recompute_from_adapter_obs"]["n_compared"] == 4 * 3 * 12, rc["action.recompute_from_adapter_obs"]
            assert rc["action.recompute_from_native_obs"]["max_abs"] == 0.0
    finally:
        shutil.rmtree(d, ignore_errors=True)


REAL_DIR = os.path.join(os.path.dirname(HERE), "out_ce12", "native", "cts_e1_m20000")
REAL_NPZ_SHA = "c9b9e88d49de9e39ff52d255162e02538fa640eea1c96d3fd58b55bdad84d5d6"


@test("T23", "실제 native 기록 (10/14 00:25 · GPU 1 · E1 model_20000) 의 사본으로 compare --recompute_action: 문자열 dims 를 읽고 통과 · 관측 · target · last action 오차 1e-6 이하 · action 1e-4 이하 · reset · 전환 · miss 수")
def t23():
    """원본은 읽기만 한다 (임시 폴더에 사본). 원본이 없거나 바뀌었으면 실패로 알린다 (건너뛰지 않는다)."""
    import contextlib
    import io
    import hashlib
    src = os.path.join(REAL_DIR, "native.npz")
    assert os.path.isfile(src), f"실제 기록이 없다: {src}"
    assert hashlib.sha256(open(src, "rb").read()).hexdigest() == REAL_NPZ_SHA, "실제 기록 npz 가 10/14 00:25 판과 다르다"
    C = _import_compare()
    d = tempfile.mkdtemp(prefix="ce12_real_")
    try:
        for f in ("native.npz", "meta.json", "signature.json"):
            shutil.copy(os.path.join(REAL_DIR, f), os.path.join(d, f))
        with contextlib.redirect_stdout(io.StringIO()):
            r = C.compare(os.path.join(d, "native.npz"), A=A, recompute_action=True, checkpoint=os.path.join(A.CTS_E1_RUN, "model_20000.pt"))
        rc = {c["name"]: c for c in r.get("checks", [])}
        assert r["status"] == "pass", (r.get("reason"), r.get("first_failure"))
        assert rc["layout.policy"]["ok"] and rc["layout.single_obs"]["ok"] and rc["layout.policy"]["dims_written_as_text"] is True, rc["layout.policy"]
        for n in ("obs.policy", "obs.single_obs", "joint_target", "state.last_action_memory"):
            assert rc[n]["max_abs"] <= 1e-6 and rc[n]["n_compared"] > 0, (n, rc[n]["max_abs"])
        for n in ("action.recompute_from_adapter_obs", "action.recompute_from_native_obs"):
            assert rc[n]["max_abs"] <= 1e-4 and rc[n]["n_compared"] == 60 * 12 * 12, (n, rc[n]["max_abs"])
        cov = r["coverage"]
        assert (cov["reset_events"], cov["post_reset_action_steps"], cov["command_switch_events"], cov["post_switch_action_steps"],
                cov["ray_miss_count"]) == (2, 60, 1, 20, None), cov
        assert any("미측정" in x for x in cov["unverified_paths"]), cov["unverified_paths"]
        fo = r["focus"]
        assert [(x["reset_in_step"], x["env"]) for x in fo["post_reset"]] == [(29, 1), (29, 6)], fo["post_reset"]
        assert all(x["native_last_action_at_first_obs_max_abs"] == 0.0 and x["obs.policy"]["max_abs"] <= 1e-6 for x in fo["post_reset"])
        sw = fo["post_switch"]
        assert len(sw) == 1 and (sw[0]["switch_obs"], sw[0]["env"], sw[0]["action_steps_after_switch"]) == (40, 0, 20), sw
        assert sw[0]["action_from_adapter_obs"]["max_abs"] <= 1e-4 and sw[0]["action_from_adapter_obs"]["n"] == 20 * 12, sw[0]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    only = set(sys.argv[1:])
    fails = 0
    for tid, desc, fn in TESTS:
        if only and tid not in only:
            continue
        try:
            fn()
            print(f"PASS {tid} {desc}", flush=True)
        except AssertionError as e:
            fails += 1
            print(f"FAIL {tid} {desc}: {str(e)[:400]}", flush=True)
        except Exception as e:  # noqa: BLE001  (예외도 FAIL 한 줄로 · 변이 판정에서 crash 와 구분)
            fails += 1
            print(f"FAIL {tid} {desc}: {type(e).__name__}: {str(e)[:400]}", flush=True)
    n = len([t for t in TESTS if not only or t[0] in only])
    print(f"SUMMARY {n - fails}/{n} PASS · adapters={MOD_PATH}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

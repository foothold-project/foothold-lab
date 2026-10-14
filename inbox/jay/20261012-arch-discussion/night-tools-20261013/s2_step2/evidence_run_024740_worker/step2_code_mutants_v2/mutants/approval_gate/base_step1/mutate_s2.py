# -*- coding: utf-8 -*-
"""S2 시험 (test_s2.py) 을 믿기 위한 변이 (판 3): 사본에서 관문을 하나씩 망가뜨려 시험이 그것을 잡는지 본다.

분류: A/정책학습 · S2 A/B 입력 경로 1 단계 판 3 · 시험의 시험
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 판 1 2026-10-13 19:21 · 판 2 2026-10-13 23:32 · 판 3 2026-10-14 00:50
근거: DESIGN-s2-ab-v1.md 4 절 · 6 절 · VERIFY-astra-17d.md 6.2 · 6.4 · VERIFY-astra-17f2.md 2.1 · 3.1 · 3.2 · test_s2.py T1 ~ T14 ·
      s2_map_obs.py · s2_policy.py
요지: 원본 세 파일을 임시 폴더에 복사하고, 변이마다 새 사본의 문자열 하나를 바꿔 (정확히 한 곳에 걸려야 함) 사본의 test_s2.py 를
      GPU 를 가린 채 돌린다. 기대한 시험이 FAIL 하면 CAUGHT. 바꾸기 전에 변이 없는 사본이 모두 PASS 인지 먼저 본다.
      원본 파일은 읽기만 하고, 시작 · 끝의 sha256 을 대조한다 (복구 확인 한 줄). 부모 체크포인트는 시험이 읽기만 한다.
      판 2: 판 1 의 「1 m 보다 깊으면 mask 0」 「NaN 을 구멍으로」 를 정답으로 두던 변이를 새 의미에 맞게 바꾸고,
      고장 분리 · strict · 관문 · 20 m offset · encoder 고정 구간 · critic 점검 변이를 더했다.
      판 3: p01 ~ p05 는 뜻을 그대로 두고 바꿀 문자열만 판 3 코드 (EncoderControl) 에 맞췄다. 전 구간 고정 · S2 갱신 번호 · 재개 ·
      group lr 덮어쓰기 · step 전 hook · clipping 범위 관문마다 변이 q01 ~ q30 (q02 없음 · p03 과 같은 변이) 을 더했다.
      임시 사본 폴더의 부모는 환경 변수 S2_MUT_TMPDIR (없으면 시스템 임시 폴더).
상태: 변이 실행기

실행: CUDA_VISIBLE_DEVICES=-1 S2_MUT_TMPDIR=<임시 폴더> C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -I mutate_s2.py
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
FILES = ("s2_map_obs.py", "s2_policy.py", "test_s2.py")
N_TESTS = 14
TMP_ROOT = os.environ.get("S2_MUT_TMPDIR") or None
MO, PO = "s2_map_obs.py", "s2_policy.py"
A_RET = "    return map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype), faults"
A_CONST = "map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype)"

# (id, 파일, 바꿀 문자열, 새 문자열, 잡아야 할 시험, 설명)
MUTANTS = [
    # ---- 지도 입력 (판 1 부터 있던 것 · 새 의미에 맞춤)
    ("m01", MO, A_RET, f"    return torch.cat([{A_CONST}[:, :ray_hits_w.shape[1]], mask], dim=-1), faults",
     {"T6"}, "A 에 mask 실제 값 (height 만 상수)"),
    ("m02", MO, A_RET, f"    return torch.cat([height, {A_CONST}[:, ray_hits_w.shape[1]:]], dim=-1), faults",
     {"T6"}, "A 에 height 실제 값 (mask 만 상수)"),
    ("m04", MO, "    raw = sensor_z - hit_z - HEIGHT_OFFSET ", "    raw = hit_z - sensor_z - HEIGHT_OFFSET ",
     {"T1"}, "height 부호 반대 (맞은 점 - 센서)"),
    ("m05", MO, "    hit_finite = torch.isfinite(ray_hits_w).all(dim=-1) ", "    hit_finite = ~torch.isnan(ray_hits_w).any(dim=-1) ",
     {"T2"}, "정상 miss (+inf) 를 hit 로 (mask 1)"),
    ("m06", MO, '    indexing = "xy" if ordering == "xy" else "ij"', '    indexing = "ij"',
     {"T3"}, "광선 순서 ij (y 가 가장 빨리)"),
    ("m11", MO, "    hit_valid = hit_finite & ok\n",
     "    hit_valid = hit_finite & ok & ((sensor_pos_w[:, 2:3] - ray_hits_w[..., 2]) <= 1.0)\n",
     {"T2"}, "판 1 의 1 m 깊이 분류를 되살림 (깊은 바닥 mask 0)"),
    ("m12", MO, "MISS_HEIGHT = 1.0 ", "MISS_HEIGHT = 0.0 ",
     {"T2"}, "정상 miss 칸 height 를 0 으로 («깊음» 아님)"),
    ("m13", MO, "raw.clamp(HEIGHT_CLIP[0], HEIGHT_CLIP[1])", "raw",
     {"T2"}, "height clip 을 뺌"),
    ("m14", MO, "    height, mask, faults = height_and_mask(sensor_pos_w, ray_hits_w, strict=strict)\n    return torch.cat([height, mask], dim=-1), faults",
     "    height, mask, faults = height_and_mask(sensor_pos_w, ray_hits_w, strict=strict)\n    return torch.cat([mask, height], dim=-1), faults",
     {"T1"}, "map_obs_b 배치 [mask, height] 로 뒤바뀜"),
    ("m14b", MO, "        return torch.cat([height, mask], dim=-1), faults", "        return torch.cat([mask, height], dim=-1), faults",
     {"T1"}, "map_obs('B') 배치 [mask, height] 로 뒤바뀜"),
    # ---- 지도 입력 (판 2 의 고장 분리 · ASTRA 17d 6.2 · 6.4)
    ("n01", MO, "    sensor_ok = torch.isfinite(sensor_pos_w).all(dim=-1) ",
     "    sensor_ok = torch.ones(sensor_pos_w.shape[0], dtype=torch.bool) ",
     {"T8"}, "센서 위치 NaN · inf 를 못 알아봄"),
    ("n02", MO, "    all_pos_inf = (ray_hits_w == math.inf).all(dim=-1) ", "    all_pos_inf = ~torch.isfinite(ray_hits_w).all(dim=-1) ",
     {"T8"}, "판 1 처럼 비유한 hit 를 모두 정상 miss (구멍) 로"),
    ("n03", MO, "(ray_hits_w == math.inf).all(dim=-1)", "(ray_hits_w[..., 2] == math.inf)",
     {"T8"}, "z 만 +inf 인 손상 packet 을 정상 miss 로"),
    ("n04", MO, "    hit_finite = torch.isfinite(ray_hits_w).all(dim=-1) ", "    hit_finite = torch.isfinite(ray_hits_w[..., 2]) ",
     {"T8"}, "x 가 NaN 인 손상 packet 을 정상 hit 로"),
    ("n05", MO, "    sensor_z = sensor_pos_w[:, 2:3]\n", "    sensor_z = sensor_pos_w[:, 2:3] + 20.0\n",
     {"T8"}, "20 m ray 시작 offset 을 센서 높이에 다시 더함"),
    ("n06", MO, '    height, mask, faults = height_and_mask(sensor_pos_w, ray_hits_w, strict=strict)\n    if mode == "B":',
     '    height, mask, faults = height_and_mask(sensor_pos_w, ray_hits_w, strict=strict and mode == "B")\n'
     '    if mode == "A":\n        faults = MapFaults(faults.sensor_bad & False, faults.packet_bad & False)\n    if mode == "B":',
     {"T8"}, "A 만 고장 판정 · strict 를 건너뜀 (A · B 다른 관문)"),
    ("n07", MO, "FAULT_HEIGHT = 0.0 ", "FAULT_HEIGHT = 1.0 ",
     {"T8"}, "고장 칸 자리표시를 정상 miss 꼴 (1, 0) 로 (구멍으로 바뀜)"),
    ("n08", MO, "    if strict and faults.total:", "    if False and strict and faults.total:",
     {"T8"}, "strict 예외를 끔"),
    ("n09", MO, '    FAULT_KEYS = ("sensor_nonfinite_envs", "ray_packet_bad", "critic_input_nonfinite", "value_nonfinite")',
     '    FAULT_KEYS = ("sensor_nonfinite_envs", "critic_input_nonfinite", "value_nonfinite")',
     {"T8"}, "관문이 packet 고장을 무시"),
    ("n10", MO, '        self.counts["value_nonfinite"] += int(report["value_nonfinite"])', "        pass",
     {"T10"}, "관문이 critic 점검의 value NaN 을 무시"),
    # ---- 정책 (판 1 부터 있던 것)
    ("m03", PO, "        nn.init.zeros_(self.actor_in_map.weight)", "        nn.init.normal_(self.actor_in_map.weight, std=1e-3)",
     {"T4"}, "새 64 열을 0 이 아닌 값 (std 1e-3) 으로 시작"),
    ("m07", PO, "        latent = self.student_latent(obs)\n        z_map = ",
     "        with torch.no_grad():\n            latent = self.student_latent(obs)\n        z_map = ",
     {"T5"}, "student encoder 의 no_grad 를 forward 에 그대로 둠 (부모 act 처럼)"),
    ("m08", PO, "        z_map = self.map_encoder(self.map_input(obs))", "        z_map = self.map_encoder(self.map_input(obs)).detach()",
     {"T5"}, "map encoder 출력 detach (지도 경로 gradient 끊김)"),
    ("m09", PO, '            "map_encoder": list(self.map_encoder.parameters()),\n', "",
     {"T5"}, "optimizer 에서 map encoder 빠짐"),
    ("m10", PO, "        return self.critic(torch.cat([latent.detach(), obs_c], dim=-1))",
     "        return self.critic(torch.cat([latent, obs_c], dim=-1))",
     {"T5"}, "critic 의 latent.detach 를 뺌 (value 손실이 student encoder 로 감)"),
    ("m15", PO, "        self.actor_rest = copy.deepcopy(net[1:])", "        self.actor_rest = net[1:]",
     {"T7"}, "actor 뒤쪽을 부모와 공유 (깊은 복사 안 함)"),
    ("m16", PO, "        self.std = nn.Parameter(parent.std.detach().clone())", "        self.std = nn.Parameter(torch.ones_like(parent.std))",
     {"T4"}, "std 를 부모 값이 아닌 1 로"),
    ("m17", PO, "            torch.manual_seed(map_init_seed)",
     '            torch.manual_seed(map_init_seed + (1 if mode == "B" else 0))',
     {"T4"}, "A · B 의 map encoder 시드가 다름 (출발점 다름)"),
    ("m18", PO, "guard_a_constant: bool = True", "guard_a_constant: bool = False",
     {"T6"}, "A 상수 관문 끔"),
    ("m19", PO, "        pre = self.actor_in(torch.cat([latent, single_obs], dim=-1))",
     "        pre = self.actor_in(torch.cat([single_obs, latent], dim=-1))",
     {"T4"}, "actor 입력 순서 [single_obs, latent] 로 뒤바뀜"),
    ("m20", PO, "        self.std = nn.Parameter(parent.std.detach().clone())",
     "        parent.std.data.mul_(1.0001)\n        self.std = nn.Parameter(parent.std.detach().clone())",
     {"T7"}, "S2 를 지으며 부모 모듈 값을 바꿈 (메모리 안)"),
    # ---- 정책 (판 2 의 encoder 고정 구간 · 판 3 에서 바꿀 문자열만 EncoderControl 에 맞춤 · 뜻은 같음)
    ("p01", PO, "        return update_index < self.freeze_updates", "        return update_index <= self.freeze_updates",
     {"T9"}, "고정 구간 하나 더 김 (<=)"),
    ("p02", PO, "            return 0.0 if self._frozen else self.encoder_lr_ratio * base_lr", "            return 0.0 if self._frozen else base_lr",
     {"T9"}, "풀린 뒤 encoder lr 에 r 을 안 곱함"),
    ("p03", PO, "            p.requires_grad_(not frozen)", "            p.requires_grad_(True)",
     {"T9"}, "lr 0 으로만 고정 (gradient · Adam moment 가 고정 중에 쌓임 · full_freeze 도 같은 줄)"),
    ("p04", PO, "encoder_freeze_updates=_UNSET, encoder_lr_ratio=_UNSET,", "encoder_freeze_updates=50, encoder_lr_ratio=0.1,",
     {"T9"}, "W · r 에 기본값을 둠"),
    ("p05", PO, "        self._apply_freeze(self._frozen)      # 만들자마자", "        pass  # (변이) 만들자마자",
     {"T9"}, "만들 때 update 0 규칙을 안 걺 (첫 update 전 encoder 가 풀려 있음)"),
    # ---- 정책 (판 3: 전 구간 고정 · 17f-2 3.1 · 4)
    ("q01", PO, '        if name == ENCODER_GROUP and encoder_mode == "full_freeze":', "        if False:",
     {"T11"}, "full_freeze 인데 student encoder 를 optimizer 에 넣음"),
    ("q03", PO, "            return True                       # 어떤 번호에서도 풀리지 않는다", "            return update_index < 50",
     {"T11"}, "full_freeze 가 번호 50 에서 풀림"),
    ("q04", PO, "            if given:", "            if False:",
     {"T11"}, "full_freeze 가 W · r 을 말없이 받음"),
    ("q05", PO, "*, encoder_mode, encoder_freeze_updates=_UNSET", '*, encoder_mode="full_freeze", encoder_freeze_updates=_UNSET',
     {"T11"}, "encoder_mode 에 기본값을 둠"),
    # ---- 정책 (판 3: S2 갱신 번호 · 재개 · 17f-2 2.1)
    ("q06", PO, "        if idx != self.completed_updates:", "        if False:",
     {"T12"}, "다음 번호 검사를 뺌 (부모 20000 · runner 번호 · 건너뜀을 받음)"),
    ("q07", PO, "        frozen = self.is_frozen(idx)", "        frozen = self.is_frozen(max(idx - 1, 0))",
     {"T12"}, "상태 변경이 한 update 늦음 (W 의 첫 minibatch 가 아니라 W+1 에서 해제)"),
    ("q08", PO, "        self.completed_updates += 1", "        self.completed_updates += 0",
     {"T12"}, "완료 수를 안 셈"),
    ("q09", PO, '        self.optimizer.load_state_dict(sd["optimizer"])', "        pass",
     {"T12"}, "재개 때 optimizer 상태를 안 읽음"),
    ("q10", PO, "        self.base_lr = saved_lr", "        self.base_lr = self.base_lr",
     {"T12"}, "재개 때 lr 을 안 되돌림"),
    ("q11", PO, "            if sd[k] != getattr(self, k):", "            if False:",
     {"T12"}, "재개 때 mode · W · r 이 달라도 받음 (다른 실험)"),
    ("q12", PO, "        self.completed_updates = completed", "        self.completed_updates = 0",
     {"T12"}, "재개 때 완료 수를 0 으로 (W 를 다시 시작)"),
    ("q23", PO, "        if self.steps_this_update == 0:", "        if False:",
     {"T12"}, "optimizer step 없는 update 를 완료로 셈 (갱신 생략)"),
    ("q24", PO, '        if self._in_update is not None:\n            raise S2IndexError(f"S2 갱신 {self._in_update} 도중에는',
     '        if False:\n            raise S2IndexError(f"S2 갱신 {self._in_update} 도중에는',
     {"T12"}, "update 도중 저장을 받음"),
    ("q25", PO, '        if self._in_update is not None:\n            raise S2IndexError(f"S2 갱신 {self._in_update} 이 끝나지 않았는데',
     '        if False:\n            raise S2IndexError(f"S2 갱신 {self._in_update} 이 끝나지 않았는데',
     {"T12"}, "끝나지 않은 update 위에 다시 시작을 받음"),
    ("q26", PO, "    if isinstance(i, bool) or not isinstance(i, int):", "    if False:",
     {"T12"}, "번호의 형 검사를 뺌 (False · 0.0 · tensor 를 0 으로 받음)"),
    ("q30", PO, '            "optimizer": copy.deepcopy(self.optimizer.state_dict()),', '            "optimizer": self.optimizer.state_dict(),',
     {"T12"}, "저장이 optimizer 상태를 깊은 복사하지 않음 (뒤 step 이 저장을 바꿈)"),
    # ---- 정책 (판 3: group lr · 고정 상태 확인 · step 전 hook · 17f-2 3.2)
    ("q13", PO, "        fixed = self._set_lrs(base_lr)", "        fixed = {}",
     {"T13"}, "enforce_groups 가 group lr 을 다시 쓰지 않음 (확인만)"),
    ("q14", PO, "            if g_bad:", "            if False:",
     {"T13"}, "고정 encoder 의 grad None 확인을 뺌"),
    ("q15", PO, '        if self.encoder_mode == "full_freeze" and enc_in_opt:', "        if False:",
     {"T13"}, "full_freeze 에서 encoder 가 optimizer 에 끼어도 모름"),
    ("q16", PO, "        if rg_bad:", "        if False:",
     {"T13"}, "encoder requires_grad 확인을 뺌"),
    ("q17", PO, "            if s_bad:", "            if False:",
     {"T13"}, "고정 encoder 의 Adam 상태 확인을 뺌"),
    ("q18", PO, '            if g["lr"] != want:\n                probs.append', '            if False:\n                probs.append',
     {"T13"}, "audit 이 group lr 을 안 봄 (enforce 뒤 덮어쓰기를 hook 이 못 잡음)"),
    ("q19", PO, "        self._hook = optimizer.register_step_pre_hook(self._pre_step)", "        self._hook = None",
     {"T13"}, "step 전 hook 을 안 걺 (enforce 없이 step 해도 모름)"),
    ("q22", PO, "    if not (lr > 0.0 and math.isfinite(lr)):", "    if False:",
     {"T13"}, "base_lr 검사를 뺌 (NaN · 0 · 음수를 받음)"),
    ("q27", PO, "        self._enforced_lr = None              # step 마다 enforce 를 새로 요구한다", "        pass  # (변이)",
     {"T13"}, "enforce 한 번이 뒤 step 들을 모두 통과시킴"),
    ("q28", PO, "        if optimizer is not self.optimizer:", "        if False:",
     {"T13"}, "다른 optimizer 로 enforce 를 받음"),
    ("q29", PO, "        if other_off:", "        if False:",
     {"T13"}, "encoder 밖 매개변수가 꺼져도 모름"),
    # ---- 정책 (판 3: clipping 범위 · schedule r 0 · 17f-2 3.1)
    ("q20", PO, "    return [p for p in policy.parameters() if p.requires_grad]", "    return list(policy.parameters())",
     {"T14"}, "trainable_params 가 고정 encoder 까지 돌려줌 (판 2 의 전체 clip)"),
    ("q21", PO, '            if not (r > 0.0 and r < float("inf")):', '            if not (r >= 0.0 and r < float("inf")):',
     {"T9"}, "schedule 이 r 0 을 받음 (실제 고정이 아닌 lr 0)"),
    # ---- 정책 (판 2 의 critic 점검)
    ("p06", PO, "        obs_c = policy.get_critic_obs(obs)\n        value",
     '        obs["critic"].nan_to_num_(0.0)\n        obs_c = policy.get_critic_obs(obs)\n        value',
     {"T10"}, "critic 점검이 critic 입력을 고쳐 씀 (NaN -> 0)"),
    ("p07", PO, "CRITIC_HEIGHT_START = 88", "CRITIC_HEIGHT_START = 87",
     {"T10"}, "critic height 열을 한 칸 어긋나게 읽음"),
    ("p08", PO, '        "value_nonfinite": int((~torch.isfinite(value)).sum()),', '        "value_nonfinite": 0,',
     {"T10"}, "critic 점검이 value NaN 을 안 셈"),
]
# 관문 자체 시험: 구현은 그대로 두고 T7 의 손으로 적은 sha256 만 틀린 값으로 (파일은 건드리지 않는다)
GATE = [("g01", {"S2_EXPECT_PARENT_SHA256": "0" * 64}, {"T7"}, "T7 sha256 기대값을 틀린 값으로 (해시 대조가 헛돌지 않는지)")]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def make_copy(mut=None):
    if TMP_ROOT:
        os.makedirs(TMP_ROOT, exist_ok=True)
    d = tempfile.mkdtemp(prefix="s2_mut_", dir=TMP_ROOT)
    for f in FILES:
        shutil.copy2(os.path.join(HERE, f), os.path.join(d, f))
    if mut is not None:
        _mid, fname, old, new = mut[:4]
        p = os.path.join(d, fname)
        with open(p, "r", encoding="utf-8") as fh:
            src = fh.read()
        n = src.count(old)
        if n != 1:
            shutil.rmtree(d, ignore_errors=True)
            raise RuntimeError(f"{_mid}: 바꿀 문자열이 {fname} 에 {n} 번 (1 번이어야 함): {old!r}")
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(src.replace(old, new))
    return d


def run(d, extra_env=None):
    env = dict(os.environ)
    env["CUDA_VISIBLE_DEVICES"] = "-1"
    env.update(extra_env or {})
    t0 = time.time()
    p = subprocess.run([PY, "-I", os.path.join(d, "test_s2.py")], cwd=d, env=env, capture_output=True, timeout=900)
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace")
    fails = sorted(set(re.findall(r"^FAIL (T\d+)", out, re.M)), key=lambda s: int(s[1:]))
    passes = sorted(set(re.findall(r"^PASS (T\d+)", out, re.M)), key=lambda s: int(s[1:]))
    return {"rc": p.returncode, "fails": fails, "passes": passes, "summary": "SUMMARY" in out, "out": out, "err": err,
            "sec": time.time() - t0}


def first_reason(out, tid):
    """FAIL 줄에서 실패한 칸 (「k/n 칸 실패: ...」) 이나 예외 (「XxxError: ...」) 부분을 꺼낸다.
    판 3: 시험 제목에도 「: 」 가 들어 있어 판 2 처럼 첫 「: 」 뒤를 자르면 제목만 보였다."""
    for line in out.splitlines():
        if line.startswith(f"FAIL {tid} "):
            m = re.search(r"\d+/\d+ 칸 실패: .*$", line) or re.search(r"\b[A-Za-z_]\w*(?:Error|Exception|Fault): .*$", line)
            s = m.group(0) if m else line[len(f"FAIL {tid} "):]
            return s[:260]
    return ""


def main():
    h0 = {f: sha256(os.path.join(HERE, f)) for f in FILES}
    print("원본 sha256: " + " · ".join(f"{f} {h[:12]}" for f, h in h0.items()), flush=True)
    for mut in MUTANTS:   # 바꿀 문자열이 원본에 정확히 한 번 있는지 먼저 (돌리기 전에 정의 오류를 잡는다)
        n = open(os.path.join(HERE, mut[1]), encoding="utf-8").read().count(mut[2])
        if n != 1:
            print(f"변이 정의 오류 {mut[0]}: {mut[1]} 에 {n} 번")
            return 2
    d = make_copy()
    try:
        r = run(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"BASELINE rc={r['rc']} PASS {len(r['passes'])}/{N_TESTS} FAIL {r['fails']} ({r['sec']:.1f} s)", flush=True)
    if r["rc"] != 0 or len(r["passes"]) != N_TESTS:
        print(r["out"][-2000:] + r["err"][-2000:])
        print("BASELINE 실패: 변이 판정 불가")
        return 2
    caught = []
    for mut in MUTANTS:
        mid, fname, _old, _new, expect, desc = mut
        d = make_copy(mut)
        try:
            r = run(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        hit = sorted(expect & set(r["fails"]))
        ok = r["rc"] != 0 and r["summary"] and bool(hit)
        caught.append(ok)
        why = first_reason(r["out"], hit[0]) if hit else (r["err"][-300:] if not r["summary"] else "")
        tag = "CAUGHT" if ok else ("CRASH" if not r["summary"] else "MISSED")
        print(f"{tag} {mid} [{fname}] {desc} · 기대 {sorted(expect)} · FAIL {r['fails']} · rc {r['rc']} ({r['sec']:.1f} s)", flush=True)
        if why:
            print(f"    사유 ({hit[0] if hit else '-'}): {why}", flush=True)
    for gid, extra, expect, desc in GATE:
        d = make_copy()
        try:
            r = run(d, extra)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        hit = sorted(expect & set(r["fails"]))
        ok = r["rc"] != 0 and r["summary"] and bool(hit)
        caught.append(ok)
        tag = "CAUGHT" if ok else ("CRASH" if not r["summary"] else "MISSED")
        print(f"{tag} {gid} [관문 자체] {desc} · 기대 {sorted(expect)} · FAIL {r['fails']} · rc {r['rc']} ({r['sec']:.1f} s)", flush=True)
        if hit:
            print(f"    사유 ({hit[0]}): {first_reason(r['out'], hit[0])}", flush=True)
    h1 = {f: sha256(os.path.join(HERE, f)) for f in FILES}
    same = h0 == h1
    print(f"원본 sha256 시작 == 끝: {same}", flush=True)
    n = len(caught)
    k = sum(caught)
    print(("ALL CAUGHT" if k == n and same else "NOT ALL CAUGHT") + f" {k}/{n}", flush=True)
    return 0 if (k == n and same) else 1


if __name__ == "__main__":
    sys.exit(main())

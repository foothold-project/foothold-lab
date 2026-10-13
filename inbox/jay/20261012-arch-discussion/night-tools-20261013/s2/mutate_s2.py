# -*- coding: utf-8 -*-
"""S2 시험 (test_s2.py) 을 믿기 위한 변이: 사본에서 관문을 하나씩 망가뜨려 시험이 그것을 잡는지 본다.

분류: A/정책학습 · S2 A/B 입력 경로 1 단계 · 시험의 시험
작성: 오흥재 (lead 세션 · Claude 하위 작업 작성) · 2026-10-13 19:21
근거: DESIGN-s2-ab-v1.md 4 절 · test_s2.py T1 ~ T7 · s2_map_obs.py · s2_policy.py
요지: 원본 세 파일을 임시 폴더에 복사하고, 변이마다 새 사본의 문자열 하나를 바꿔 (정확히 한 곳에 걸려야 함) 사본의 test_s2.py 를
      GPU 를 가린 채 돌린다. 기대한 시험이 FAIL 하면 CAUGHT. 바꾸기 전에 변이 없는 사본이 7/7 PASS 인지 먼저 본다.
      원본 파일은 읽기만 하고, 시작 · 끝의 sha256 을 대조한다. 부모 체크포인트는 시험이 읽기만 한다.
상태: 변이 실행기

실행: C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe mutate_s2.py
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

# (id, 파일, 바꿀 문자열, 새 문자열, 잡아야 할 시험, 설명)
MUTANTS = [
    ("m01", "s2_map_obs.py",
     "        return map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype)",
     "        return torch.cat([map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype)"
     "[:, :ray_hits_w.shape[1]], height_and_mask(sensor_pos_w, ray_hits_w)[1]], dim=-1)",
     {"T6"}, "A 에 mask 실제 값 (height 만 상수)"),
    ("m02", "s2_map_obs.py",
     "        return map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], device=ray_hits_w.device, dtype=ray_hits_w.dtype)",
     "        return torch.cat([height_and_mask(sensor_pos_w, ray_hits_w)[0], map_obs_a(ray_hits_w.shape[0], ray_hits_w.shape[1], "
     "device=ray_hits_w.device, dtype=ray_hits_w.dtype)[:, ray_hits_w.shape[1]:]], dim=-1)",
     {"T6"}, "A 에 height 실제 값 (mask 만 상수)"),
    ("m03", "s2_policy.py", "        nn.init.zeros_(self.actor_in_map.weight)", "        nn.init.normal_(self.actor_in_map.weight, std=1e-3)",
     {"T4"}, "새 64 열을 0 이 아닌 값 (std 1e-3) 으로 시작"),
    ("m04", "s2_map_obs.py", "    depth = sensor_z - hit_z ", "    depth = hit_z - sensor_z ",
     {"T1"}, "height 부호 반대 (맞은 점 - 센서)"),
    ("m05", "s2_map_obs.py", "    valid = torch.isfinite(depth) & (depth <= MASK_MAX_DEPTH)",
     "    valid = ~torch.isnan(depth) & (depth <= MASK_MAX_DEPTH)",
     {"T2"}, "inf (안 맞음) 를 mask 1 로"),
    ("m06", "s2_map_obs.py", '    indexing = "xy" if ordering == "xy" else "ij"', '    indexing = "ij"',
     {"T3"}, "광선 순서 ij (y 가 가장 빨리)"),
    ("m07", "s2_policy.py", "        latent = self.student_latent(obs)\n        z_map = ",
     "        with torch.no_grad():\n            latent = self.student_latent(obs)\n        z_map = ",
     {"T5"}, "student encoder 의 no_grad 를 그대로 둠 (부모 act 처럼)"),
    ("m08", "s2_policy.py", "        z_map = self.map_encoder(self.map_input(obs))", "        z_map = self.map_encoder(self.map_input(obs)).detach()",
     {"T5"}, "map encoder 출력 detach (지도 경로 gradient 끊김)"),
    ("m09", "s2_policy.py", '            "map_encoder": list(self.map_encoder.parameters()),\n', "",
     {"T5"}, "optimizer 에서 map encoder 빠짐"),
    ("m10", "s2_policy.py", "        return self.critic(torch.cat([latent.detach(), obs_c], dim=-1))",
     "        return self.critic(torch.cat([latent, obs_c], dim=-1))",
     {"T5"}, "critic 의 latent.detach 를 뺌 (value 손실이 student encoder 로 감)"),
    ("m11", "s2_map_obs.py", "    valid = torch.isfinite(depth) & (depth <= MASK_MAX_DEPTH)", "    valid = torch.isfinite(depth)",
     {"T2"}, "1 m 보다 깊은 곳도 mask 1"),
    ("m12", "s2_map_obs.py", "INVALID_HEIGHT = 1.0 ", "INVALID_HEIGHT = 0.0 ",
     {"T2"}, "mask 0 칸 height 를 0 으로 («깊음» 아님)"),
    ("m13", "s2_map_obs.py", "raw.clamp(HEIGHT_CLIP[0], HEIGHT_CLIP[1])", "raw",
     {"T2"}, "height clip 을 뺌"),
    ("m14", "s2_map_obs.py", "    height, mask = height_and_mask(sensor_pos_w, ray_hits_w)\n    return torch.cat([height, mask], dim=-1)",
     "    height, mask = height_and_mask(sensor_pos_w, ray_hits_w)\n    return torch.cat([mask, height], dim=-1)",
     {"T1"}, "지도 배치 [mask, height] 로 뒤바뀜"),
    ("m15", "s2_policy.py", "        self.actor_rest = copy.deepcopy(net[1:])", "        self.actor_rest = net[1:]",
     {"T7"}, "actor 뒤쪽을 부모와 공유 (깊은 복사 안 함)"),
    ("m16", "s2_policy.py", "        self.std = nn.Parameter(parent.std.detach().clone())", "        self.std = nn.Parameter(torch.ones_like(parent.std))",
     {"T4"}, "std 를 부모 값이 아닌 1 로"),
    ("m17", "s2_policy.py", "            torch.manual_seed(map_init_seed)",
     '            torch.manual_seed(map_init_seed + (1 if mode == "B" else 0))',
     {"T4"}, "A · B 의 map encoder 시드가 다름 (출발점 다름)"),
    ("m18", "s2_policy.py", "guard_a_constant: bool = True", "guard_a_constant: bool = False",
     {"T6"}, "A 상수 관문 끔"),
    ("m19", "s2_policy.py", "        pre = self.actor_in(torch.cat([latent, single_obs], dim=-1))",
     "        pre = self.actor_in(torch.cat([single_obs, latent], dim=-1))",
     {"T4"}, "actor 입력 순서 [single_obs, latent] 로 뒤바뀜"),
    ("m20", "s2_policy.py", "        self.std = nn.Parameter(parent.std.detach().clone())",
     "        parent.std.data.mul_(1.0001)\n        self.std = nn.Parameter(parent.std.detach().clone())",
     {"T7"}, "S2 를 지으며 부모 모듈 값을 바꿈 (메모리 안)"),
]
# 관문 자체 시험: 구현은 그대로 두고 T7 의 손으로 적은 sha256 만 틀린 값으로 (파일은 건드리지 않는다)
GATE = [("g01", {"S2_EXPECT_PARENT_SHA256": "0" * 64}, {"T7"}, "T7 sha256 기대값을 틀린 값으로 (해시 대조가 헛돌지 않는지)")]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def make_copy(mut=None):
    d = tempfile.mkdtemp(prefix="s2_mut_")
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
    fails = sorted(set(re.findall(r"^FAIL (T\d+)", out, re.M)))
    passes = sorted(set(re.findall(r"^PASS (T\d+)", out, re.M)))
    return {"rc": p.returncode, "fails": fails, "passes": passes, "summary": "SUMMARY" in out, "out": out, "err": err,
            "sec": time.time() - t0}


def first_reason(out, tid):
    for line in out.splitlines():
        if line.startswith(f"FAIL {tid} "):
            k = line.find(": ")
            return line[k + 2:k + 2 + 160] if k >= 0 else line[:160]
    return ""


def main():
    h0 = {f: sha256(os.path.join(HERE, f)) for f in FILES}
    print("원본 sha256: " + " · ".join(f"{f} {h[:12]}" for f, h in h0.items()), flush=True)
    d = make_copy()
    try:
        r = run(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print(f"BASELINE rc={r['rc']} PASS {len(r['passes'])}/7 FAIL {r['fails']} ({r['sec']:.1f} s)", flush=True)
    if r["rc"] != 0 or len(r["passes"]) != 7:
        print(r["out"][-2000:] + r["err"][-2000:])
        print("BASELINE 실패: 변이 판정 불가")
        return 2
    caught = []
    rows = []
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
        rows.append((mid, tag, desc, fname, sorted(expect), r["fails"]))
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

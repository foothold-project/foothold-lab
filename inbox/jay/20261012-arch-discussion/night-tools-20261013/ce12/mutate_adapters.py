# -*- coding: utf-8 -*-
"""break-the-guard: adapters.py · compare_native.py 의 일부러 틀린 사본마다 test_adapters.py 의 지정 시험이 FAIL 해야 한다.

분류: A/평가 · CE12-v1 이식 진단 1 시험의 시험
작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-13 18:19
근거: 의뢰 (time-major 이력 · 0 으로 채운 초기 이력 · scale 누락) · DESIGN-astra-12 5.2 · _eval/mutate_isaac_slot.py 와 같은 방식
요지: 원본은 건드리지 않는다. 임시 폴더에 사본을 만들어 한 줄을 바꾸고 CE12_ADAPTERS / CE12_COMPARE 로 그 사본을 시험시킨다.
상태: 시험 파일

판정: 시험이 종료 코드 1 · 지정 시험이 모두 FAIL · Traceback 없음 이면 CAUGHT. 모두 CAUGHT 면 「ALL CAUGHT」.
실행: C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe mutate_adapters.py
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ADP = open(os.path.join(HERE, "adapters.py"), encoding="utf-8").read()
CMP = open(os.path.join(HERE, "compare_native.py"), encoding="utf-8").read()

M = [
    ("adapters", "M01 time-major 이력 (시점마다 45 칸을 이어 붙임)",
     "        return torch.cat([hist[t.name].flat() for t in self.terms], dim=-1)",
     "        return torch.cat([torch.cat([hist[t.name].buf[:, s] for t in self.terms], dim=-1) for s in range(hist[self.terms[0].name].H)], dim=-1)",
     ["T03"]),
    ("adapters", "M02 초기 이력을 0 으로 채움 (첫 표본 반복 안 함)",
     "            self.buf[first] = x[first].unsqueeze(1).expand(-1, self.H, -1)",
     "            pass",
     ["T03", "T04"]),
    ("adapters", "M03 scale 누락",
     "        v = v * torch.tensor(term.scale, dtype=torch.float32, device=v.device)",
     "        v = v",
     ["T03", "T06"]),
    ("adapters", "M04 scale 을 clip 보다 먼저",
     "    if term.clip:\n        v = v.clamp(min=term.clip[0], max=term.clip[1])\n    if term.scale is not None:\n"
     "        v = v * torch.tensor(term.scale, dtype=torch.float32, device=v.device)\n",
     "    if term.scale is not None:\n        v = v * torch.tensor(term.scale, dtype=torch.float32, device=v.device)\n"
     "    if term.clip:\n        v = v.clamp(min=term.clip[0], max=term.clip[1])\n",
     ["T06"]),
    ("adapters", "M05 v2 miss 를 -1 로 (옛 규격 1)",
     "    return torch.where(valid_hit, height, torch.full_like(height, float(miss_value)))",
     "    return torch.where(valid_hit, height, torch.full_like(height, float(-1.0)))",
     ["T10", "T11"]),
    ("adapters", "M06 v2 높이에 광선 offset 20 m 를 더함",
     "    height = sensor_z.unsqueeze(1) - ray_hits_z - offset",
     "    height = (sensor_z.unsqueeze(1) + 20.0) - ray_hits_z - offset",
     ["T07", "T10", "T11"]),
    ("adapters", "M07 관절을 이름이 아니라 자리로 맞춤",
     "    return [pos[n] for n in dst_names]",
     "    return list(range(len(dst_names)))",
     ["T08", "T09", "T13"]),
    ("adapters", "M08 디버그 읽기가 이력을 전진시킴",
     "        if update_history:\n            for t, v in zip(self.terms, self._samples(state)):",
     "        if True:\n            for t, v in zip(self.terms, self._samples(state)):",
     ["T05"]),
    ("adapters", "M09 reset 이 이력 횟수를 안 지움",
     "        self.num_pushes[ids] = 0",
     "        pass",
     ["T04"]),
    ("adapters", "M10 clip 을 target 이 아니라 raw 에",
     "        target = raw * self._act_scale + off\n        if self._act_clip is not None:\n"
     "            target = torch.clamp(target, min=self._act_clip[:, 0], max=self._act_clip[:, 1])\n",
     "        rawc = raw if self._act_clip is None else torch.clamp(raw, min=self._act_clip[:, 0], max=self._act_clip[:, 1])\n"
     "        target = rawc * self._act_scale + off\n",
     ["T14"]),
    ("adapters", "M11 v2 에 CMD-R 의 scale (ang 0.25 · dq 0.05) 복사",
     "        scale = None if t.get(\"scale\") is None else float(t[\"scale\"])",
     "        scale = {\"base_ang_vel\": 0.25, \"joint_vel_rel\": 0.05}.get(func) if t.get(\"scale\") is None else float(t[\"scale\"])",
     ["T02", "T07"]),
    ("adapters", "M12 CTS reset 이 기억한 raw action 을 안 지움",
     "            h.reset(ids)\n        self._last_raw[ids] = 0.0",
     "            h.reset(ids)\n        pass",
     ["T04"]),
    ("adapters", "M13 decode_action 이 raw 를 기억 안 함 (last_action 이 0 으로 남음)",
     "            self._last_raw = raw.clone()",
     "            pass",
     ["T04", "T15"]),
    ("adapters", "M14 이력 최신을 앞에 (newest -> oldest)",
     "        self.buf = torch.cat([self.buf[:, 1:], x.unsqueeze(1)], dim=1)",
     "        self.buf = torch.cat([x.unsqueeze(1), self.buf[:, :-1]], dim=1)",
     ["T03"]),
    ("adapters", "M15 v2 height clip 을 버림",
     "        clip = tuple(t[\"clip\"]) if t.get(\"clip\") else None",
     "        clip = None",
     ["T02", "T10"]),
    ("adapters", "M16 광선 격자를 ij 순서로",
     "    indexing = ordering if ordering == \"xy\" else \"ij\"",
     "    indexing = \"ij\"",
     ["T12"]),
    ("adapters", "M17 infer 가 평균이 아니라 표본 (act) 을 냄",
     "            return policy_module.act_inference(td)\n\n    def signature(self) -> dict:\n        sig = self._base_signature()\n        sig[\"observation\"] = {\n            \"groups\": [\n",
     "            return policy_module.act(td, is_teacher=False)\n\n    def signature(self) -> dict:\n        sig = self._base_signature()\n        sig[\"observation\"] = {\n            \"groups\": [\n",
     ["T17", "T18"]),
    ("adapters", "M18 v2 reset 이 기억한 raw action 을 안 지움",
     "        ids = slice(None) if env_ids is None else env_ids\n        self._last_raw[ids] = 0.0",
     "        ids = slice(None) if env_ids is None else env_ids\n        pass",
     ["T15"]),
    ("compare", "C01 대조기 위치 보고가 한 칸 밀림",
     "                self.first[\"where\"] = locate(idx)",
     "                self.first[\"where\"] = locate(idx + 1)",
     ["T21"]),
    ("compare", "C02 대조기가 기록의 reset 을 무시",
     "                ad.reset(torch.as_tensor(ids))",
     "                pass",
     ["T21"]),
    ("compare", "C03 action 재계산이 한 step 늦은 관측을 씀",
     "        a1 = ad.infer(m, obs_seq[k])",
     "        a1 = ad.infer(m, obs_seq[k + 1])",
     ["T22"]),
]


def main():
    tmp = tempfile.mkdtemp(prefix="ce12_mut_")
    res = []
    try:
        for k, (target, name, a, b, want) in enumerate(M):
            src = ADP if target == "adapters" else CMP
            assert src.count(a) == 1, f"{name}: 바꿀 문자열이 {src.count(a)} 번 나온다"
            p = os.path.join(tmp, f"mut_{k:02d}_{target}.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write(src.replace(a, b))
            env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1")
            env["CE12_ADAPTERS" if target == "adapters" else "CE12_COMPARE"] = p
            r = subprocess.run([sys.executable, os.path.join(HERE, "test_adapters.py")], capture_output=True, text=True, env=env,
                               encoding="utf-8", errors="replace", timeout=900)
            failed = [ln.split()[1] for ln in r.stdout.splitlines() if ln.startswith("FAIL ")]
            crashed = "Traceback (most recent call last)" in r.stderr
            caught = r.returncode == 1 and all(w in failed for w in want) and not crashed
            res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {r.returncode} failed {failed} want {want}"
                       f"{' · CRASH ' + r.stderr[-300:] if crashed else ''}")
            print(res[-1], flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(x.startswith("CAUGHT") for x in res)
    print(f"{n_ok}/{len(res)} CAUGHT")
    print("ALL CAUGHT" if n_ok == len(res) else "SOME MISSED")
    return 0 if n_ok == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())

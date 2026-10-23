"""학습 실행 manifest (SONNET-X11 계약 6) + 두 판 diff. Kit 없이 시험된다.

실행 시작 때 «실제로 소비한 것» 을 기록한다: repo HEAD 만이 아니라 import 된 파일의 SHA · 커밋 안 된 변경(dirty diff) · env/agent YAML ·
cli 인자 · 패키지 버전 · 모드(est mask · critic · clip · z/action 표집) · 초기 actor/critic/optimizer 상태 SHA · 완료 update 수 · 총 env step.
비밀값(토큰 · 키)은 환경 변수를 덤프하지 않고 cli 인자에서도 이름에 key · token · secret · password 가 든 것은 뺀다.

두 판 diff(`diff_manifests`)는 허용한 칸(est mask · run 식별자 · 시각 · 경로 · pid)만 달라야 통과한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time

SECRET = re.compile(r"key|token|secret|password", re.I)
WATCH_PREFIXES = ("foothold_s2", "rsl_rl", "isaaclab_rl")        # 실제 import 된 소비 코드(Isaac Lab 본체는 버전으로만 기록)

# 두 판 diff 에서 달라도 되는 칸 (점으로 이은 경로의 접두). 이것 말고 다르면 실패.
ALLOWED_DIFF_PREFIXES = (
    "run.name", "run.log_dir", "run.started_at", "run.pid", "run.cli_args.run_name", "run.cli_args.log_dir",
    "run.hydra_overrides.agent.perception.est_mode",             # hydra 인자는 key 단위: est_mode 만 허용
    "modes.est_mode",                                              # 처치(est mask)
    "yaml.agent.run_name", "yaml.agent.perception.est_mode", "yaml.env.log_dir",
    "files.manifest_file", "progress", "checkpoints", "files.added_after_start",
)

# 장치 배치(어느 GPU 에서 돌렸나)는 처치가 아니라 배치다: 따로 «허용 · 장치 배치» 로 표시한다
PLACEMENT_SUFFIXES = (".device", ".active_gpu", ".physics_gpu", "sim.device", ".local_rank", ".rank")

# 기록 범위 계약 (ASTRA-X13 M1 · M3): 이 manifest 가 «보증하지 않는 것» 을 숨기지 않고 적는다
RECORD_CONTRACT = {
    "consumed_code": "foothold_s2 · rsl_rl · isaaclab_rl 의 import 된 .py 파일 SHA. Isaac Lab 본체 · isaaclab_tasks · USD/MDL 자산 SHA 는 시간이 커서 범위 밖(버전 · 경로만)",
    "kl_probe": "같은 저장 history · 재생 버퍼의 같은 시작 hidden · 고정 epsilon 으로 est 를 다시 계산한 조건부 가우시안 KL. 옛 live hidden 을 이어 쓴 경우와의 구분 측정은 없음. 부분집합은 앞쪽 최대 kl_probe_envs(256) env 이며 전체 3072 env 의 KL 이 아님",
    "action_probe": "PD target 한계 초과율 · 토크 절단율만 기록하고 실제 관절 target · 관절각 값은 기록하지 않음",
    "reward_split": "보상 직후(reset 전) 값으로 env-step 단위 분류, 속도는 지수평균(시간 상수 약 10 스텝, 명령 변경 · reset 에서 다시 시작)",
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)

    return h.hexdigest()


def state_sha(obj) -> str:
    """텐서가 든 state_dict(또는 중첩 dict · list)의 내용 SHA. 키 순서와 무관하다."""
    import torch

    h = hashlib.sha256()

    def walk(x, path=""):
        if isinstance(x, dict):
            for k in sorted(x, key=str):
                walk(x[k], path + "/" + str(k))
        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(x):
                walk(v, path + "/" + str(i))
        elif isinstance(x, torch.Tensor):
            t = x.detach().cpu().contiguous()
            # flatten preserves the byte stream of non-scalar tensors and also
            # permits scalar optimizer counters (0-dimensional tensors).
            h.update(path.encode() + str(t.dtype).encode() + str(tuple(t.shape)).encode() + t.reshape(-1).view(torch.uint8).numpy().tobytes() if t.numel() else path.encode())
        else:
            h.update((path + repr(x)).encode())

    walk(obj)

    return h.hexdigest()


def imported_files(prefixes=WATCH_PREFIXES) -> dict[str, str]:
    """sys.modules 중 소비 코드의 파일 -> SHA."""
    out = {}

    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)

        if f and name.split(".")[0] in prefixes and os.path.isfile(f) and f.endswith(".py"):
            out[name] = sha256_file(f)

    return out


def git_state(repo: str) -> dict:
    def run(*a) -> bytes:
        try:
            return subprocess.run(["git", "-C", repo, *a], capture_output=True, timeout=60, creationflags=0x08000000 if os.name == "nt" else 0).stdout or b""
        except Exception:                                                  # noqa: BLE001
            return b""

    diff = run("diff", "HEAD", "--", "foothold_s2")             # 바이트 그대로 SHA (한글 · 줄바꿈 변환에 흔들리지 않는다)

    return {"head": run("rev-parse", "HEAD").decode("utf-8", "replace").strip(), "dirty_diff_sha256": sha256_bytes(diff), "dirty_diff_bytes": len(diff),
            "_dirty_diff_text": diff.decode("utf-8", "replace")}


def package_versions(names=("torch", "numpy", "gymnasium", "rsl-rl-lib", "isaaclab", "isaaclab_rl", "isaaclab_tasks", "tensordict")) -> dict:
    import importlib.metadata as md

    out = {}

    for n in names:
        try:
            out[n] = md.version(n)
        except Exception:                                                  # noqa: BLE001
            out[n] = None

    return out


def yaml_flat(path: str) -> dict:
    """YAML 을 점 경로 -> 스칼라 문자열로 편다. 태그(python 객체)는 문자열로 읽는다. 파일이 없으면 {}."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    def any_tag(loader, suffix, node):
        if isinstance(node, yaml.ScalarNode):
            return loader.construct_scalar(node)

        if isinstance(node, yaml.SequenceNode):
            return loader.construct_sequence(node, deep=True)

        return loader.construct_mapping(node, deep=True)

    Loader.add_multi_constructor("", any_tag)

    if not os.path.isfile(path):
        return {}

    with open(path, encoding="utf-8") as f:
        data = yaml.load(f, Loader=Loader)

    out = {}

    def walk(x, p):
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, p + "." + str(k) if p else str(k))
        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(x):
                walk(v, "%s[%d]" % (p, i))
        else:
            out[p] = str(x)

    walk(data, "")

    return out


def build_manifest(*, repo, log_dir, run_name, cli_args, modes, runner=None, env_yaml=None, agent_yaml=None) -> dict:
    """실행 시작 때 한 번. runner 가 있으면 초기 actor/critic/optimizer/지각 상태 SHA 도 넣는다."""
    gs = git_state(repo)
    diff_text = gs.pop("_dirty_diff_text")
    clean_args = {k: v for k, v in dict(cli_args).items() if not SECRET.search(str(k))}
    hydra_list = clean_args.pop("hydra_args", None) or []
    hydra_overrides = {}

    for item in hydra_list:                                   # "agent.perception.est_mode=zero" -> {"agent.perception.est_mode": "zero"}
        k, _, v = str(item).partition("=")
        hydra_overrides[k.strip()] = v.strip()
    m = {"schema": "foothold-manifest/1",
         "run": {"name": run_name, "log_dir": log_dir, "started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "pid": os.getpid(), "cli_args": clean_args,
             "hydra_overrides": hydra_overrides},
         "record_contract": RECORD_CONTRACT,
         "git": gs, "packages": package_versions(), "python": sys.version.split()[0], "modes": dict(modes),
         "files": {"imported_sha256": imported_files()},
         "yaml": {"env": yaml_flat(env_yaml) if env_yaml else {}, "agent": yaml_flat(agent_yaml) if agent_yaml else {}},
         "progress": {"completed_updates": 0, "total_env_steps": 0}, "checkpoints": {}}

    if runner is not None:
        pol = runner.alg.policy
        actor = {k: v for k, v in pol.state_dict().items() if k.startswith("actor") or k == "std" or k == "log_std"}
        critic = {k: v for k, v in pol.state_dict().items() if k.startswith("critic")}
        m["initial_state_sha256"] = {"actor": state_sha(actor), "critic": state_sha(critic), "ppo_optimizer": state_sha(runner.alg.optimizer.state_dict()),
                                     "perception": state_sha(runner.perception.state_dict()), "perception_optimizer": state_sha(runner.perception_optimizer.state_dict())}

    os.makedirs(log_dir, exist_ok=True)

    with open(os.path.join(log_dir, "source_dirty.diff"), "w", encoding="utf-8", newline="") as f:
        f.write(diff_text)

    return m


def write_manifest(log_dir: str, manifest: dict) -> str:
    path = os.path.join(log_dir, "manifest.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1, sort_keys=True)

    return path


def update_progress(log_dir: str, manifest: dict, completed_updates: int, total_env_steps: int, checkpoint: tuple | None = None) -> None:
    manifest["progress"] = {"completed_updates": int(completed_updates), "total_env_steps": int(total_env_steps)}

    if checkpoint:
        name, path = checkpoint
        manifest["checkpoints"][name] = sha256_file(path)

    write_manifest(log_dir, manifest)


def file_changes(manifest: dict) -> dict:
    """시작 때 기록한 소비 파일과 지금을 견준다: changed(SHA 다름) · missing(사라짐 또는 더는 import 안 됨 · 디스크에서 사라진 파일) · added(시작 뒤 새로 import 된 소비 파일 -> SHA)."""
    now = imported_files()
    old = manifest["files"]["imported_sha256"]
    seen_added = manifest["files"].get("added_after_start", {})
    changed = sorted(n for n, sha in old.items() if n in now and now[n] != sha)
    missing = sorted(n for n in old if n not in now)
    added = {n: sha for n, sha in now.items() if n not in old and seen_added.get(n) != sha}

    return {"changed": changed, "missing": missing, "added": added}


def changed_files(manifest: dict) -> list[str]:
    """시작 때 기록한 소비 파일 중 지금 SHA 가 달라진 모듈 이름 (실행 중 코드 변경 감지)."""
    now = imported_files()
    old = manifest["files"]["imported_sha256"]

    return sorted(n for n, sha in old.items() if n in now and now[n] != sha)


def flatten(obj, prefix="") -> dict:
    out = {}

    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, prefix + "." + str(k) if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, "%s[%d]" % (prefix, i)))
    else:
        out[prefix] = obj

    return out


def diff_manifests(a: dict, b: dict, allowed=ALLOWED_DIFF_PREFIXES) -> dict:
    """두 manifest 의 다른 칸을 허용(allowed)과 그 밖으로 가른다. `ok` 는 허용 밖 차이가 0 일 때만 True."""
    fa, fb = flatten(a), flatten(b)
    keys = sorted(set(fa) | set(fb))
    allowed_diffs, bad, placement = {}, {}, {}

    for k in keys:
        if fa.get(k, "<없음>") == fb.get(k, "<없음>"):
            continue

        entry = {"a": fa.get(k, "<없음>"), "b": fb.get(k, "<없음>")}

        if any(k == p or k.startswith(p + ".") or k.startswith(p + "[") for p in allowed):
            allowed_diffs[k] = entry
        elif (k.startswith("run.cli_args.") or k.startswith("yaml.")) and any(k.endswith(suf) for suf in PLACEMENT_SUFFIXES):
            placement[k] = entry
        else:
            bad[k] = entry

    return {"ok": not bad, "allowed_differences": allowed_diffs, "device_placement_differences": placement, "unexpected_differences": bad, "keys_compared": len(keys)}


def main(argv=None):
    """python -m foothold_s2.runners.manifest a/manifest.json b/manifest.json  -> 표준 출력에 diff 요약, 허용 밖 차이가 있으면 종료 코드 1."""
    argv = list(sys.argv[1:] if argv is None else argv)

    if len(argv) != 2:
        print("usage: manifest.py <A manifest.json> <B manifest.json>")

        return 2

    a, b = (json.load(open(p, encoding="utf-8")) for p in argv)
    res = diff_manifests(a, b)
    print(json.dumps({"ok": res["ok"], "keys_compared": res["keys_compared"], "allowed": sorted(res["allowed_differences"]),
                      "device_placement": sorted(res["device_placement_differences"]), "unexpected": res["unexpected_differences"]}, ensure_ascii=False, indent=1))

    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

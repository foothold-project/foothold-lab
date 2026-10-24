"""EX-30 · EX-31 부모 전환 (SONNET-X25, IMPLEMENT-EX30-31 T1). Kit 없이 시험된다.

EX-28 B 의 model_1500.pt 에서 «명시한 상태만» 가져와 새 판(자식)을 시작한다. 보통 resume(`Sol23FRunner.load`)은 variant · force_gt 가 다르면 거절하고, 그 검사는 그대로 둔다.
이 모듈은 그 옆의 별도 경로이고, 이름이 다른 부모 variant 를 받는 곳은 `import_parent` 한 곳뿐이다.

가져오는 것: 정책 · 지각 가중치(정규화 통계 포함), PPO · 지각 optimizer 상태, 두 학습률, 행동 std.
새로 시작하는 것: env 상태(지형 레벨 · 명령 과정) · RNG · episode/RNN/history · AdaSmpl 통계(p=1, count=0, 판별 force_gt 는 지도 처치에 따름) · 새 과정 단계 P0 · 자식 추가 갱신 수 0.
부모 파일은 읽기만 하고, 읽은 뒤 SHA 를 다시 재서 영수증에 적는다.

번호 규칙: 부모 `iter=N` 은 N+1 번 갱신을 끝낸 체크포인트다. 자식의 첫 갱신은 번호 N+1, k 번 갱신 뒤 저장 파일은 model_{N+k}, 합친 경험은 (N+1)+k 갱신이다.
자식의 정확한 재개(`restore_child`)는 자식 체크포인트만 받고 부모 체크포인트는 거절한다(`import_parent` 와 섞지 않는다).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import torch
import yaml

from foothold_s2.runners.manifest import state_sha

CKPT_FORMAT = "foothold-start/1"
PARENT_VARIANTS = ("B_friction_only",)                              # 이름이 다른 variant 를 받는 허용 목록(이 모듈 한 곳)
ALLOWED_PARENT_SHA256 = ("cb65ba5641ac7265664a02110c51f9a57b1427ecee74356870fcd462907c43b8",)      # 설계 §2.1: 부모는 EX-28 B model_1500.pt 하나
TERRAIN_RESTORE_MODES = ("none", "parent_levels")
TREATMENT_PCFG_KEYS = ("force_gt",)                                  # 부모와 달라도 되는 처치: 지도 선택(adaptive/gt) 하나
OPERATIONAL_KEYS = ("experiment_id", "run_name", "log_dir", "extra_updates", "deadline")           # 부모와 달라도 되는 운영 칸. 이 밖의 지각/학습/환경 칸은 부모와 같아야 한다(T2/T3 에서 바꿀 칸은 근거와 함께 여기에 명시적으로 더한다)
EXPERIMENT_MAP = {"EX-30": "adaptive", "EX-31": "gt"}                # 실험 번호 -> 지도 처치. 둘이 어긋나면 거절
B_SHAPES = {"std": (12,), "actor.0.weight": (512, 96), "actor.6.weight": (12, 128), "critic.0.weight": (512, 664)}      # 부모 B 의 실제 forward 모양(10/25 CPU 읽기)
AGENT_CFG_KEYS = ("policy", "algorithm", "num_steps_per_env", "clip_actions", "empirical_normalization")      # 부모 params/agent.yaml 과 같아야 하는 학습 cfg. 운영 칸(run_name · max_iterations · save_interval · device · logger · resume · load_*)은 빠진다. obs_groups 는 runner 가 풀어 쓰므로 비교하지 않는다
AGENT_IGNORE_SUBKEYS = ("class_name",)                                  # runner 가 정책 class_name 을 pop 해 쓰므로 양쪽에서 뺀다
EXPLICIT_RESET_FIELDS = ("env_state", "rng", "episode_rnn_history", "adasmpl.stats", "adasmpl.force_gt", "course_stage_P0", "iteration_counters", "child_new_updates")


class TransferRefused(ValueError):
    """부모 전환 또는 자식 재개 계약 위반."""


@dataclass(frozen=True)
class TransferSpec:
    parent_sha256: str
    experiment_id: str
    map_policy: str
    seed: int
    curriculum_spec_sha256: str
    terrain_restore: str = "none"                                       # "parent_levels" = 창 1: 부모 env_state 의 terrain_levels/types 만 두 판 똑같이 복원(나머지 env 상태는 버린다)

    def sha256(self) -> str:
        d = asdict(self)

        if d["terrain_restore"] == "none":
            d.pop("terrain_restore")                                    # 이 칸이 생기기 전 spec 의 SHA 를 바꾸지 않는다

        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


@dataclass
class TransferResult:
    model_state: dict
    optimizer_state: dict
    ppo_learning_rate: float
    perception_state: dict
    perception_optimizer_state: dict
    perception_learning_rate: float
    perception_cfg: dict                                               # 자식이 가져야 할 pcfg = 부모 pcfg 에서 처치 칸(force_gt)만 바꾼 값
    adasmpl_state: dict
    normalizers: dict
    parent_iter: int
    parent_completed_updates: int
    new_completed_updates: int
    explicit_reset_fields: tuple
    receipt: dict = field(default_factory=dict)
    parent_perception_cfg: dict = field(default_factory=dict)
    parent_depth_delay_ticks: int | None = None
    parent_map_input: str | None = None
    parent_agent_cfg: dict | None = None
    parent_terrain: dict | None = None                                 # terrain_restore="parent_levels" 일 때만: {"terrain_levels", "terrain_types"} (CPU 텐서)


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)

    return h.hexdigest()


def _clone_to(obj, device):
    if isinstance(obj, torch.Tensor):
        return obj.detach().clone().to(device)
    if isinstance(obj, dict):
        return {k: _clone_to(v, device) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_clone_to(v, device) for v in obj)

    return copy.deepcopy(obj)


def _all_finite(obj) -> bool:
    if isinstance(obj, torch.Tensor):
        return bool(torch.isfinite(obj.float()).all()) if obj.numel() else True
    if isinstance(obj, dict):
        return all(_all_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return all(_all_finite(v) for v in obj)

    return True


def _normalizers(model_state: dict, perception_state: dict) -> dict:
    return {f"{src}.{k}": v for src, sd in (("model", model_state), ("perception", perception_state)) for k, v in sd.items() if "norm" in k.lower() and isinstance(v, torch.Tensor)}


def child_meta(spec: TransferSpec, parent_iter: int, current_iter: int) -> dict:
    """자식 체크포인트에 적는 전환 기록. current_iter 는 막 끝낸 갱신 번호(부모 번호에서 이어 센다)."""
    return {"spec": asdict(spec), "spec_sha256": spec.sha256(), "parent_sha256": spec.parent_sha256, "experiment_id": spec.experiment_id, "map_policy": spec.map_policy,
            "parent_iter": int(parent_iter), "parent_completed_updates": int(parent_iter) + 1, "new_completed_updates": int(current_iter) - int(parent_iter),
            "total_completed_updates": int(current_iter) + 1}


def import_parent(parent_path, spec: TransferSpec, device: str = "cpu", shapes: dict | None = None, allowed_parent_shas=None, require_agent_yaml: bool = True) -> TransferResult:
    parent_path = Path(parent_path)
    shapes = B_SHAPES if shapes is None else shapes
    allowed = ALLOWED_PARENT_SHA256 if allowed_parent_shas is None else tuple(allowed_parent_shas)

    if spec.parent_sha256 not in allowed:
        raise TransferRefused(f"부모 SHA {spec.parent_sha256} 는 허용 목록에 없다(설계 §2.1 의 부모 하나만 받는다)")

    if spec.experiment_id not in EXPERIMENT_MAP or EXPERIMENT_MAP[spec.experiment_id] != spec.map_policy:
        raise TransferRefused(f"experiment_id {spec.experiment_id!r} 와 map_policy {spec.map_policy!r} 의 짝이 계약과 다르다")

    if not isinstance(spec.seed, int) or isinstance(spec.seed, bool):
        raise TransferRefused("seed 는 정수여야 한다")

    if spec.terrain_restore not in TERRAIN_RESTORE_MODES:
        raise TransferRefused(f"terrain_restore {spec.terrain_restore!r} 는 {TERRAIN_RESTORE_MODES} 중 하나")

    sha_before = file_sha256(parent_path)

    if sha_before != spec.parent_sha256:
        raise TransferRefused(f"부모 파일 SHA 가 다르다: {sha_before} != {spec.parent_sha256}")

    sd = torch.load(parent_path, weights_only=False, map_location="cpu")

    if sd.get("format") != CKPT_FORMAT:
        raise TransferRefused(f"START 체크포인트가 아니다: format={sd.get('format')!r}")

    own = sd.get("sol23f") or {}

    if own.get("initial_snapshot"):
        raise TransferRefused("초기 진단 snapshot 은 부모가 될 수 없다")

    if own.get("variant") not in PARENT_VARIANTS:
        raise TransferRefused(f"부모 variant {own.get('variant')!r} 는 허용 목록 {PARENT_VARIANTS} 에 없다")

    if "stage_transfer" in sd:
        raise TransferRefused("자식 체크포인트는 부모로 쓰지 않는다(restore_child 로 재개)")

    for key in ("model_state_dict", "optimizer_state_dict", "ppo_learning_rate", "perception_state_dict", "perception_optimizer_state_dict", "perception_cfg", "adasmpl", "iter"):
        if key not in sd:
            raise TransferRefused(f"부모 체크포인트에 {key} 가 없다")

    for name, shape in shapes.items():
        got = tuple(sd["model_state_dict"][name].shape) if name in sd["model_state_dict"] else None

        if got != tuple(shape):
            raise TransferRefused(f"{name} 모양 {got} 가 계약 {tuple(shape)} 와 다르다")

    if not (_all_finite(sd["model_state_dict"]) and _all_finite(sd["perception_state_dict"]) and _all_finite(sd["optimizer_state_dict"]) and _all_finite(sd["perception_optimizer_state_dict"])):
        raise TransferRefused("부모 가중치 또는 optimizer 상태에 NaN/Inf 가 있다")

    parent_iter = int(sd["iter"])
    model, perc = _clone_to(sd["model_state_dict"], device), _clone_to(sd["perception_state_dict"], device)
    opt, popt = _clone_to(sd["optimizer_state_dict"], device), _clone_to(sd["perception_optimizer_state_dict"], device)
    pcfg = dict(sd["perception_cfg"])
    pcfg["force_gt"] = spec.map_policy == "gt"
    ada = {"p": 1.0, "count": 0.0, "sum": 0.0, "sumsq": 0.0, "force_gt": spec.map_policy == "gt"}
    std = [float(x) for x in model["std"].detach().cpu().flatten()] if "std" in model else None
    parent_terrain = None

    if spec.terrain_restore == "parent_levels":
        env_state = sd.get("env_state") or {}
        lv, ty = env_state.get("terrain_levels"), env_state.get("terrain_types")

        if lv is None or ty is None or lv.shape != ty.shape or lv.dim() != 1 or int(lv.min()) < 0 or int(ty.min()) < 0:
            raise TransferRefused("terrain_restore=parent_levels 인데 부모 env_state 에 정상 terrain_levels/types 가 없다")

        parent_terrain = {"terrain_levels": lv.detach().cpu().clone(), "terrain_types": ty.detach().cpu().clone()}

    parent_agent, agent_sha = load_parent_agent_cfg(parent_path) if require_agent_yaml else (None, None)
    sha_after = file_sha256(parent_path)

    if sha_after != sha_before:
        raise TransferRefused("부모 파일이 읽는 동안 바뀌었다")

    receipt = {"parent_path": str(parent_path), "parent_sha256": sha_before, "parent_sha256_after_read": sha_after, "spec": asdict(spec), "spec_sha256": spec.sha256(),
               "parent_variant": own.get("variant"), "parent_iter": parent_iter, "parent_completed_updates": parent_iter + 1, "new_completed_updates": 0,
               "parent_adasmpl": dict(sd["adasmpl"]), "child_adasmpl": ada, "ppo_learning_rate": float(sd["ppo_learning_rate"]),
               "perception_learning_rate": float(popt["param_groups"][0]["lr"]), "action_std": std,
               "state_sha": {"model": state_sha(model), "optimizer": state_sha(opt), "perception": state_sha(perc), "perception_optimizer": state_sha(popt)},
               "explicit_reset_fields": list(EXPLICIT_RESET_FIELDS), "child_perception_cfg_force_gt": pcfg["force_gt"], "shapes_checked": {k: list(v) for k, v in shapes.items()},
               "parent_env_state_discarded": sorted(sd.get("env_state", {}).keys()), "parent_agent_yaml_sha256": agent_sha}

    if parent_terrain is not None:
        lv, ty = parent_terrain["terrain_levels"], parent_terrain["terrain_types"]
        receipt["terrain_restore"] = {"mode": spec.terrain_restore, "num_envs": int(lv.numel()), "parent_hash": terrain_hash(lv, ty), "parent_histogram": terrain_histogram(lv, ty),
                                      "restored": ["terrain_levels", "terrain_types"], "not_restored": ["common_step_counter", "range_curriculum", "env_hook", "rng", "adasmpl"]}

    return TransferResult(model_state=model, optimizer_state=opt, ppo_learning_rate=float(sd["ppo_learning_rate"]), perception_state=perc, perception_optimizer_state=popt,
                          perception_learning_rate=float(popt["param_groups"][0]["lr"]), perception_cfg=pcfg, adasmpl_state=ada, normalizers=_normalizers(model, perc),
                          parent_iter=parent_iter, parent_completed_updates=parent_iter + 1, new_completed_updates=0, explicit_reset_fields=EXPLICIT_RESET_FIELDS, receipt=receipt,
                          parent_perception_cfg=dict(sd["perception_cfg"]), parent_depth_delay_ticks=own.get("depth_delay_ticks"), parent_map_input=own.get("map_input"), parent_agent_cfg=parent_agent, parent_terrain=parent_terrain)


def terrain_hash(levels: torch.Tensor, types: torch.Tensor) -> str:
    """지형 칸(레벨 · 종류) 배열의 sha256. 두 판이 같은 칸을 이어 받았는지 비교하는 값."""
    return hashlib.sha256(levels.detach().cpu().long().numpy().tobytes() + b"|" + types.detach().cpu().long().numpy().tobytes()).hexdigest()


def terrain_histogram(levels: torch.Tensor, types: torch.Tensor) -> list:
    """레벨 x 종류 개수표(행 = 레벨)."""
    lv, ty = levels.detach().cpu().long(), types.detach().cpu().long()
    table = torch.zeros(int(lv.max()) + 1, int(ty.max()) + 1, dtype=torch.long)
    table.index_put_((lv, ty), torch.ones_like(lv), accumulate=True)

    return table.tolist()


def compare_window1_receipts(receipt_a: dict, receipt_b: dict) -> dict:
    """창 1 의 두 판(EX-30 · EX-31)이 같은 부모에서 같은 지형 칸을 이어 받았는지 영수증 둘로 단언한다. 다르면 TransferRefused."""
    ta, tb = receipt_a.get("terrain_restore"), receipt_b.get("terrain_restore")

    if not ta or not tb:
        raise TransferRefused("두 영수증 모두 terrain_restore 가 있어야 한다")
    if {receipt_a["spec"]["experiment_id"], receipt_b["spec"]["experiment_id"]} != {"EX-30", "EX-31"}:
        raise TransferRefused("한 쌍은 EX-30 과 EX-31 이어야 한다")
    if receipt_a["parent_sha256"] != receipt_b["parent_sha256"]:
        raise TransferRefused("두 판의 부모 SHA 가 다르다")
    for key in ("parent_hash", "restored_hash", "parent_histogram"):
        if ta[key] != tb[key]:
            raise TransferRefused(f"두 판의 terrain_restore.{key} 가 다르다")
    if ta["restored_hash"] != ta["parent_hash"] or tb["restored_hash"] != tb["parent_hash"]:
        raise TransferRefused("복원 뒤 지형 해시가 부모와 다르다")

    return {"parent_hash": ta["parent_hash"], "restored_hash": ta["restored_hash"], "equal": True}


def _norm(obj):
    """튜플 · 리스트 · 숫자 표기를 같은 모양으로(JSON 왕복)."""
    return json.loads(json.dumps(obj, sort_keys=True, default=str))


def load_parent_agent_cfg(parent_path) -> tuple[dict, str]:
    """부모 실행 폴더의 params/agent.yaml. 없으면 거절한다(PPO · 정책 cfg 를 대조할 근거가 없다)."""
    path = Path(parent_path).parent / "params" / "agent.yaml"

    if not path.is_file():
        raise TransferRefused(f"부모 실행 폴더에 params/agent.yaml 이 없어 PPO · 정책 cfg 를 대조할 수 없다: {path}")

    return yaml.safe_load(path.read_text(encoding="utf-8")), file_sha256(path)


def agent_cfg_diffs(parent_agent: dict, child_cfg: dict) -> dict:
    """부모 agent.yaml 과 자식 train_cfg 의 학습 cfg(algorithm · policy · 롤아웃 길이 등) 차이. 운영 칸은 AGENT_CFG_KEYS 에 없어 보지 않는다."""
    def clean(cfg, key):
        v = cfg.get(key)

        if isinstance(v, dict):
            v = {k: x for k, x in v.items() if k not in AGENT_IGNORE_SUBKEYS}

        return _norm(v)

    return {k: (clean(parent_agent, k), clean(child_cfg, k)) for k in AGENT_CFG_KEYS if clean(parent_agent, k) != clean(child_cfg, k)}


class _PyTupleLoader(yaml.SafeLoader):
    pass


_PyTupleLoader.add_constructor("tag:yaml.org,2002:python/tuple", lambda loader, node: list(loader.construct_sequence(node)))


def _python_tag(loader, suffix, node):
    """isaaclab dump_yaml 이 쓰는 그 밖의 python 태그(slice 등)는 태그 이름과 내용을 그대로 담은 값으로 읽어 비교만 한다(객체를 만들지 않는다)."""
    if isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        value = loader.construct_mapping(node, deep=True)
    else:
        value = loader.construct_scalar(node)

    return {"__python_tag__": suffix, "value": value}


_PyTupleLoader.add_multi_constructor("tag:yaml.org,2002:python/", _python_tag)


def load_dumped_yaml(path) -> dict:
    return yaml.load(Path(path).read_text(encoding="utf-8"), Loader=_PyTupleLoader)


def yaml_pair_diff(parent_path, child_path, allowed_paths=(), ignore_names=("log_dir", "device")) -> dict:
    """부모 · 자식 덤프 yaml 의 잎 단위 차이. ignore_names 는 이름(마지막 키)이 같은 운영 칸, allowed_paths 는 점으로 이은 경로(처치 칸).
    allowed_paths 의 항목이 ".*" 로 끝나면 그 경로 아래 모든 잎을 허용한다(점 경계까지: "a.b.*" 는 "a.b.c" 를 허용하고 "a.bx" 는 허용하지 않는다)."""
    def leaves(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield from leaves(v, f"{prefix}.{k}" if prefix else str(k))
        else:
            yield prefix, _norm(obj)

    a, b = dict(leaves(load_dumped_yaml(parent_path))), dict(leaves(load_dumped_yaml(child_path)))
    out = {}

    for k in sorted(set(a) | set(b)):
        if a.get(k, "<없음>") != b.get(k, "<없음>") and k.split(".")[-1] not in ignore_names and k not in allowed_paths and not any(ap.endswith(".*") and k.startswith(ap[:-1]) for ap in allowed_paths):
            out[k] = (a.get(k, "<없음>"), b.get(k, "<없음>"))

    return out


def unexpected_cfg_diffs(parent_pcfg: dict, child_pcfg: dict, defaults: dict) -> dict:
    """부모 pcfg 와 자식 pcfg 의 차이 중 허용 목록(처치 · 운영 칸) 밖인 것. 부모에 없는 칸은 그 시점의 기본값으로 본다."""
    expected = {**defaults, **parent_pcfg}
    keys = set(expected) | set(child_pcfg)
    allowed = set(TREATMENT_PCFG_KEYS) | set(OPERATIONAL_KEYS)

    return {k: (expected.get(k), child_pcfg.get(k)) for k in sorted(keys) if k not in allowed and expected.get(k) != child_pcfg.get(k)}


def apply_transfer(runner, result: TransferResult, spec: TransferSpec) -> None:
    """가져온 상태를 StartRunner(자식)에 쓴다. env 상태 · RNG 는 건드리지 않고 번호만 부모에서 이어 센다.

    쓰기 전에 모든 계약을 검사한다: 실험 번호 · 처치 · seed · 허용 목록 밖 cfg 차이. 쓰는 도중 실패하면 runner 를 «깨짐» 으로 표시해 이후 저장을 막는다(버리고 새로 만든다).
    """
    from foothold_s2.runners.start_runner import PERCEPTION_DEFAULTS

    if getattr(runner, "experiment_id", None) != spec.experiment_id:
        raise TransferRefused(f"runner 의 실험 {getattr(runner, 'experiment_id', None)!r} 와 spec 의 {spec.experiment_id!r} 가 다르다")

    if bool(runner.pcfg.get("force_gt", False)) != (spec.map_policy == "gt"):
        raise TransferRefused(f"runner force_gt={runner.pcfg.get('force_gt')!r} 가 map_policy {spec.map_policy!r} 와 다르다")

    env_seed = getattr(getattr(getattr(runner.env, "unwrapped", runner.env), "cfg", None), "seed", None)

    if env_seed != spec.seed:
        raise TransferRefused(f"spec seed {spec.seed} 와 env cfg seed {env_seed!r} 가 다르다")

    diffs = unexpected_cfg_diffs(result.parent_perception_cfg, dict(runner.pcfg), PERCEPTION_DEFAULTS)

    if diffs:
        raise TransferRefused(f"부모와 달라도 되는 칸(처치 {TREATMENT_PCFG_KEYS} · 운영 {OPERATIONAL_KEYS}) 밖의 cfg 가 다르다: {diffs}")

    if result.parent_agent_cfg is not None:
        agent_diffs = agent_cfg_diffs(result.parent_agent_cfg, runner.cfg)

        if agent_diffs:
            raise TransferRefused(f"부모 params/agent.yaml 과 다른 PPO · 정책 cfg(운영 칸 제외): {agent_diffs}")

    if result.parent_depth_delay_ticks is not None and runner.perception.cfg.depth_delay_ticks != result.parent_depth_delay_ticks:
        raise TransferRefused(f"depth_delay_ticks 부모 {result.parent_depth_delay_ticks} 자식 {runner.perception.cfg.depth_delay_ticks}")

    if runner.perception.cfg.map_input != result.parent_map_input:
        raise TransferRefused(f"map_input 부모 {result.parent_map_input!r} 자식 {runner.perception.cfg.map_input!r}")

    if getattr(runner, "_transfer_broken", False):
        raise TransferRefused("이전 전환이 도중에 실패한 runner 다. 버리고 새로 만든다")

    result.receipt["child_cfg_perception_lr"] = runner.pcfg.get("learning_rate")                       # cfg 값과 실제 값(부모 optimizer 의 값이 이긴다)을 둘 다 남긴다
    result.receipt["child_pcfg_sha256"] = state_sha(dict(runner.pcfg))

    if result.parent_terrain is not None:
        terrain = getattr(getattr(getattr(runner.env, "unwrapped", runner.env), "scene", None), "terrain", None)

        if terrain is None or getattr(terrain, "terrain_levels", None) is None:
            raise TransferRefused("terrain_restore 를 하려는데 이 env 에는 terrain_levels 가 없다")
        if tuple(terrain.terrain_levels.shape) != tuple(result.parent_terrain["terrain_levels"].shape):
            raise TransferRefused(f"부모 지형 칸 {tuple(result.parent_terrain['terrain_levels'].shape)} 와 이 env {tuple(terrain.terrain_levels.shape)} 의 env 수가 다르다")

    try:
        runner.alg.policy.load_state_dict(result.model_state)
        runner.perception.load_state_dict(result.perception_state)
        runner.alg.optimizer.load_state_dict(result.optimizer_state)
        runner.alg.learning_rate = result.ppo_learning_rate
        runner.perception_optimizer.load_state_dict(result.perception_optimizer_state)
        runner.adasmpl.load_state_dict(dict(result.adasmpl_state))
        runner.current_learning_iteration = result.parent_iter                  # learn() 은 재개일 때 parent_iter + 1 번부터 센다
        runner._resumed = True

        if result.parent_terrain is not None:                                                     # 지형 칸만 복원한다: 카운터 · 명령 과정 · RNG · AdaSmpl 통계는 새로
            runner._load_env_state({k: v.to(terrain.terrain_levels.device) for k, v in result.parent_terrain.items()})
            now = terrain_hash(terrain.terrain_levels, terrain.terrain_types)
            result.receipt["terrain_restore"]["restored_hash"] = now

            if now != result.receipt["terrain_restore"]["parent_hash"]:
                raise TransferRefused("복원한 지형 칸의 해시가 부모와 다르다")
    except BaseException:
        runner._transfer_broken = True
        raise

    runner.stage_transfer = {"spec": spec, "parent_iter": result.parent_iter, "base_iter": result.parent_iter}


@dataclass
class ChildState:
    state: dict
    meta: dict


def restore_child(path, expected_spec_sha: str) -> ChildState:
    """자식 체크포인트의 정확한 재개. 부모 체크포인트 · 다른 spec 의 자식은 거절한다."""
    sd = torch.load(path, weights_only=False, map_location="cpu")

    if sd.get("format") != CKPT_FORMAT:
        raise TransferRefused(f"START 체크포인트가 아니다: format={sd.get('format')!r}")

    meta = sd.get("stage_transfer")

    if not meta:
        raise TransferRefused("자식 체크포인트가 아니다(stage_transfer 없음). 부모는 import_parent 로만 읽는다")

    if meta.get("spec_sha256") != expected_spec_sha:
        raise TransferRefused(f"spec SHA 가 다르다: {meta.get('spec_sha256')} != {expected_spec_sha}")

    it = int(sd["iter"])

    if meta["new_completed_updates"] != it - meta["parent_iter"] or meta["total_completed_updates"] != it + 1 or meta["new_completed_updates"] < 0:
        raise TransferRefused("전환 기록의 갱신 수가 체크포인트 iter 와 어긋난다")

    return ChildState(sd, meta)

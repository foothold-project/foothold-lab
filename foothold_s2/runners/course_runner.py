"""EX-30 · EX-31 자식 runner (SONNET-X25, T1). `Sol23FRunner`(변경 없음)를 상속하고 전환 기록만 더한다.

- `begin_from_parent(path, spec)`: stage_transfer.import_parent 로 부모 상태를 가져와 적용한다(번호는 부모에서 이어 셈).
- 저장: 모든 체크포인트에 `stage_transfer` 전환 기록을 쓴다. 전환(또는 load)이 끝나지 않았거나, 이 프로세스에서 실제로 끝낸 갱신이 0 회이거나, 회차 번호가 실제 갱신 수와 어긋나면 거절한다.
- `learn(n)`: 추가 갱신 수가 0 이하면 기동을 거절한다.
- `load(path)`: 자식 체크포인트만 받고 spec SHA 가 같아야 한다(`restore_child`). 부모 체크포인트는 거절한다. `set_spec` 은 «재개 대기» 만 표시하고 load 가 끝나야 저장이 열린다.
"""

from __future__ import annotations

from foothold_s2.runners.sol23f_runner import Sol23FRunner
from foothold_s2.runners.stage_transfer import TransferRefused, TransferSpec, apply_transfer, child_meta, import_parent, restore_child


class _TransferChild(Sol23FRunner):
    experiment_id = "unset"
    stage_transfer = None                                           # 전환 또는 load 가 «끝난» 뒤에만 채워진다
    _pending_spec = None                                            # set_spec 이 둔 재개 대기 상태(저장 관문을 열지 않는다)
    _transfer_broken = False

    def begin_from_parent(self, parent_path, spec: TransferSpec, shapes: dict | None = None, allowed_parent_shas=None) -> dict:
        if self.stage_transfer is not None or self._pending_spec is not None:
            raise TransferRefused("이미 전환(또는 재개 등록)을 한 runner 다")
        result = import_parent(parent_path, spec, device=str(self.device), shapes=shapes, allowed_parent_shas=allowed_parent_shas)
        apply_transfer(self, result, spec)

        return result.receipt

    def set_spec(self, spec: TransferSpec, parent_iter: int) -> None:
        """새 프로세스의 재개 전용: load 가 읽을 spec 과 부모 번호를 등록한다. load 가 끝나기 전에는 저장할 수 없다."""
        if spec.experiment_id != self.experiment_id:
            raise TransferRefused(f"runner 의 실험 {self.experiment_id!r} 와 spec 의 {spec.experiment_id!r} 가 다르다")
        if self.stage_transfer is not None:
            raise TransferRefused("이미 전환을 마친 runner 다")
        self._pending_spec = {"spec": spec, "parent_iter": int(parent_iter)}

    def learn(self, num_learning_iterations: int, init_at_random_ep_len: bool = False) -> None:
        if num_learning_iterations <= 0:
            raise TransferRefused(f"추가 갱신 수 {num_learning_iterations} <= 0: 학습하지 않는 자식은 기동하지 않는다")
        if self.stage_transfer is None:
            raise TransferRefused("전환(begin_from_parent) 또는 재개(set_spec + load) 전에는 학습하지 않는다")
        super().learn(num_learning_iterations, init_at_random_ep_len)

    def state_dict(self, infos: dict | None = None) -> dict:
        if self.stage_transfer is None or self._transfer_broken:
            raise TransferRefused("전환 기록 없이(또는 전환이 깨진 채로) 자식 체크포인트를 저장하지 않는다")
        done = len(self.iter_log)                                   # StartRunner.learn 이 갱신을 끝낼 때마다 한 줄 더한다

        if done == 0:
            raise TransferRefused("이 프로세스에서 끝낸 갱신이 0 회라 자식 체크포인트를 저장하지 않는다")
        base = self.stage_transfer["base_iter"]

        if self.current_learning_iteration != base + done:
            raise TransferRefused(f"회차 {self.current_learning_iteration} 가 시작 {base} + 끝낸 갱신 {done} 와 다르다")
        state = super().state_dict(infos)
        state["stage_transfer"] = child_meta(self.stage_transfer["spec"], self.stage_transfer["parent_iter"], self.current_learning_iteration)

        return state

    def load(self, path: str, load_optimizer: bool = True, map_location: str | None = None) -> dict:
        if self._pending_spec is None:
            raise TransferRefused("set_spec 로 spec 을 먼저 등록해야 자식을 재개한다")
        spec = self._pending_spec["spec"]
        child = restore_child(path, spec.sha256())

        if child.meta["parent_iter"] != self._pending_spec["parent_iter"]:
            raise TransferRefused("자식 체크포인트의 부모 번호가 등록한 값과 다르다")
        infos = super().load(path, load_optimizer=load_optimizer, map_location=map_location)
        self.stage_transfer = {"spec": spec, "parent_iter": self._pending_spec["parent_iter"], "base_iter": self.current_learning_iteration}
        self._pending_spec = None

        return infos


class Ex30Runner(_TransferChild):
    variant = "EX30_mainline_adaptive"
    experiment_id = "EX-30"


class Ex31Runner(_TransferChild):
    variant = "EX31_gt_control"
    experiment_id = "EX-31"

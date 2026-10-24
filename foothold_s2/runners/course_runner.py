"""EX-30 · EX-31 자식 runner (SONNET-X25, T1). `Sol23FRunner`(변경 없음)를 상속하고 전환 기록만 더한다.

- `begin_from_parent(path, spec)`: stage_transfer.import_parent 로 부모 상태를 가져와 적용한다(번호는 부모에서 이어 셈).
- 저장: 모든 체크포인트에 `stage_transfer` 전환 기록을 쓴다. 전환 없이 저장하려 하면 거절한다.
- `load(path)`: 자식 체크포인트만 받고 spec SHA 가 같아야 한다(`restore_child`). 부모 체크포인트는 거절한다.
"""

from __future__ import annotations

from foothold_s2.runners.sol23f_runner import Sol23FRunner
from foothold_s2.runners.stage_transfer import TransferRefused, TransferSpec, apply_transfer, child_meta, import_parent, restore_child


class _TransferChild(Sol23FRunner):
    stage_transfer = None

    def begin_from_parent(self, parent_path, spec: TransferSpec, shapes: dict | None = None) -> dict:
        if self.stage_transfer is not None:
            raise TransferRefused("이미 전환을 마친 runner 다")
        result = import_parent(parent_path, spec, device=str(self.device), shapes=shapes)
        apply_transfer(self, result, spec)

        return result.receipt

    def set_spec(self, spec: TransferSpec, parent_iter: int) -> None:
        """새 프로세스의 재개 전용: load 가 읽을 spec 과 부모 번호를 먼저 등록한다."""
        self.stage_transfer = {"spec": spec, "parent_iter": int(parent_iter)}

    def state_dict(self, infos: dict | None = None) -> dict:
        if self.stage_transfer is None:
            raise TransferRefused("전환 기록 없이 자식 체크포인트를 저장하지 않는다")
        state = super().state_dict(infos)
        state["stage_transfer"] = child_meta(self.stage_transfer["spec"], self.stage_transfer["parent_iter"], self.current_learning_iteration)

        return state

    def load(self, path: str, load_optimizer: bool = True, map_location: str | None = None) -> dict:
        if self.stage_transfer is None:
            raise TransferRefused("set_spec 로 spec 을 먼저 등록해야 자식을 재개한다")
        child = restore_child(path, self.stage_transfer["spec"].sha256())

        if child.meta["parent_iter"] != self.stage_transfer["parent_iter"]:
            raise TransferRefused("자식 체크포인트의 부모 번호가 등록한 값과 다르다")

        return super().load(path, load_optimizer=load_optimizer, map_location=map_location)


class Ex30Runner(_TransferChild):
    variant = "EX30_mainline_adaptive"


class Ex31Runner(_TransferChild):
    variant = "EX31_gt_control"

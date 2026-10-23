"""rsl_rl 체크포인트 -> policy.onnx (S1-blind 기준, actor MLP [512, 256, 128] ELU). torch 가 있는 곳에서.

관측 정규화는 쓰지 않는다(`actor_obs_normalization=False`). 키 이름이 다르면 오류로 멈춘다.
"""

import torch


def load_actor(checkpoint, obs_dim=495, hidden=(512, 256, 128), action_dim=12):
    sd = torch.load(checkpoint, map_location="cpu", weights_only=False)["model_state_dict"]
    dims = [obs_dim, *hidden, action_dim]
    layers = []

    for i in range(len(dims) - 1):
        layers.append(torch.nn.Linear(dims[i], dims[i + 1]))

        if i < len(dims) - 2:
            layers.append(torch.nn.ELU())

    net = torch.nn.Sequential(*layers)
    mine = {k.replace("actor.", "", 1): v for k, v in sd.items() if k.startswith("actor.")}
    net.load_state_dict(mine, strict=True)

    return net.eval()


def export_onnx(checkpoint, path, obs_dim=495):
    net = load_actor(checkpoint, obs_dim=obs_dim)
    x = torch.zeros(1, obs_dim)
    torch.onnx.export(net, x, path, input_names=["obs"], output_names=["actions"], dynamo=False, opset_version=17,
                      dynamic_axes={"obs": {0: "batch"}, "actions": {0: "batch"}})

    return net

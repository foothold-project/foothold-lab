"""두 방 걷기 지도의 5 cm 점 (room_points_5cm.npy) 과 걸은 길 (room_grid.npz) 을 3D 보기 페이지 하나에 넣는다.
쓰는 법: python room_points_html.py <틀 html> <출력 html> <이름>=<map 폴더> [<이름>=<map 폴더> ...]
점은 걸은 길 둘레 5 m · 바닥 기준 -0.2~2.5 m 만 남기고, 바닥 기준 mm 정수 (int16) 를 base64 로 페이지 안에 넣는다
(파일을 따로 읽지 않아 로컬에서 바로 열린다).
"""
import sys, json, base64
import numpy as np

tpl, out = sys.argv[1], sys.argv[2]
clouds = []
for arg in sys.argv[3:]:
    name, d = arg.split("=", 1)
    P = np.load(f"{d}/room_points_5cm.npy").astype(np.float64)
    g = np.load(f"{d}/room_grid.npz")
    floor = float(g["floor"]); path = g["path"]
    xmin, xmax = path[:, 1].min() - 5, path[:, 1].max() + 5
    ymin, ymax = path[:, 2].min() - 5, path[:, 2].max() + 5
    z = P[:, 2] - floor
    k = (P[:, 0] > xmin) & (P[:, 0] < xmax) & (P[:, 1] > ymin) & (P[:, 1] < ymax) & (z > -0.2) & (z < 2.5)
    cx, cy = float(path[:, 1].mean()), float(path[:, 2].mean())
    Q = np.stack([P[k, 0] - cx, P[k, 1] - cy, z[k]], 1)
    q = np.round(Q * 1000).astype(np.int16)
    pa = np.round(np.stack([path[:, 1] - cx, path[:, 2] - cy, path[:, 3] - floor], 1) * 1000).astype(np.int16)
    clouds.append({"name": name, "n": int(k.sum()), "n_all": int(len(P)), "floor_z": round(floor, 4),
                   "pts": base64.b64encode(q.tobytes()).decode(), "path": base64.b64encode(pa.tobytes()).decode()})
    print(name, "kept", int(k.sum()), "of", len(P))
html = open(tpl, encoding="utf-8").read().replace("/*__CLOUDS__*/[]", json.dumps(clouds, separators=(",", ":")))
open(out, "w", encoding="utf-8").write(html)
print(out, len(html.encode()), "bytes")

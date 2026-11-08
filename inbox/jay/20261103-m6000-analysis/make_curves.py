"""EX-40 m0..m6000 learning curves from the run's tensorboard file (+ EX-41 from its own file)."""
import sys, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
plt.rcParams['font.family'] = 'Malgun Gothic'; plt.rcParams['axes.unicode_minus'] = False
E40 = r'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/events.out.tfevents.1793387639.AI-WS01.26240.0'
E41 = r'C:/Users/AI-WS01/s2_lab/ex41_main_20261103_195435/main/EX-41-B-main_20261103_195435/events.out.tfevents.1793703531.AI-WS01.84424.0'
def load(p):
    ea = EventAccumulator(p, size_guidance={'scalars': 0}); ea.Reload(); return ea
a, b = load(E40), load(E41)
def s(ea, tag, off=0, cap=None):
    ev = ea.Scalars(tag) if tag in ea.Tags()['scalars'] else []
    x = np.array([e.step + off for e in ev]); y = np.array([e.value for e in ev])
    if cap is not None: m = x <= cap; x, y = x[m], y[m]
    return x, y
def smooth(y, k=25):
    if len(y) <= k: return y
    w = np.ones(k); num = np.convolve(y, w, mode='same'); den = np.convolve(np.ones_like(y), w, mode='same')
    return num / den  # edge-normalised so the line does not dip at the ends
PANELS = [('Train/mean_reward', '평균 보상'), ('Train/mean_episode_length', '평균 에피소드 길이(스텝, 상한 1000)'),
          ('Metrics/base_velocity/error_vel_xy', '학습 중 평면 속도 오차'), ('Metrics/base_velocity/error_vel_yaw', '학습 중 회전 속도 오차'),
          ('Episode_Termination/bad_orientation', '넘어짐 종료 비율'), ('Policy/mean_noise_std', '정책 탐색 크기(noise std)'),
          ('Episode_Reward/stumble', '걸림 벌점 크기'), ('Episode_Reward/track_lin_vel', '속도 추종 보상')]
fig, axs = plt.subplots(4, 2, figsize=(18, 16), dpi=130, sharex=True)
for ax, (tag, name) in zip(axs.flat, PANELS):
    x, y = s(a, tag, 0, 6000); ax.plot(x, y, color='#bbb', lw=.6); ax.plot(x, smooth(y), color='#1f77b4', lw=1.6, label='EX-40')
    x2, y2 = s(b, tag, 6000 - 0)  # EX-41 steps continue the parent count
    if len(x2):
        if x2.min() < 6000: x2 = x2 + 6000
        ax.plot(x2, y2, color='#ddb', lw=.6); ax.plot(x2, smooth(y2), color='#8e44ad', lw=1.6, label='EX-41')
    for bnd, t in [(1500, 'B1'), (3000, 'B2'), (4500, 'B3a'), (5000, 'B3b'), (5500, 'B3c'), (6000, 'EX-41')]:
        ax.axvline(bnd, color='#999', lw=.7); ax.text(bnd + 15, ax.get_ylim()[1], t, fontsize=8, va='top', color='#555')
    ax.set_title(name, fontsize=11); ax.grid(alpha=.3)
axs[0, 0].legend(fontsize=9)
for ax in axs[-1]: ax.set_xlabel('누적 회차')
fig.suptitle('계보 1 학습 곡선: EX-40 m0 ~ m6000 (파랑) · EX-41 m6000 ~ (보라) · 원자료 tensorboard · 회색 원값, 선 25 회 이동평균', fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.97)); fig.savefig(sys.argv[1]); print('saved')

"""Final matched comparison using the same audited CPU definitions as B1000."""
import json
from pathlib import Path
import numpy as np
import analyze_b1000_1024 as base
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RAW = Path('C:/Users/AI-WS01/s2_lab/run_20261024')

def main():
    base.OUT = ROOT/'figs/ex28-u1500-review'
    base.MEDIA = RAW/'b1500_matched_review'
    base.SOURCES = [
        ('EX-23 flat', RAW/'ex23_model1500_flat_guarded24i'),
        ('B flat', RAW/'b_model1500_flat_guarded24i'),
        ('EX-23 rough', RAW/'ex23_model1500_rough_guarded24i'),
        ('B rough', RAW/'b_model1500_rough_guarded24i'),
    ]
    base.OUT.mkdir(parents=True, exist_ok=True)
    base.checks()
    rows = base.load()
    result = base.metrics(rows)
    base.plots(rows, iteration=1500)
    base.grids(rows)
    base.video(rows, iteration=1500)
    previous = json.loads((ROOT/'figs/ex28-u1000-review/matched_metrics.json').read_text(encoding='utf-8'))
    changes = {}
    for label, now in result['clips'].items():
        before = previous['clips'][label]
        changes[label] = {
            'u1000': before['segments'], 'u1500': now['segments'],
            'roll_abs_max_u1000_deg': before['roll_abs_max_deg'],
            'roll_abs_max_u1500_deg': now['roll_abs_max_deg'],
        }
    (base.OUT/'change_1000_1500.json').write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding='utf-8')
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), layout='constrained')
    for i, (label, change) in enumerate(changes.items()):
        ax = axes.flat[i]
        last = [[s['wz_one_second_means_radps'][-1] for s in change[k][2:]] for k in ['u1000','u1500']]
        x = np.arange(2)
        ax.bar(x-.16,last[0],width=.32,color=base.COLORS[2],label='1000회')
        ax.bar(x+.16,last[1],width=.32,color=base.COLORS[0],label='1500회')
        ax.scatter(x,[1.2,-1.2],marker='_',s=250,color=base.COLORS[1],label='명령')
        ax.axhline(0,color='#444444',lw=.7)
        ax.set(title=label,xticks=x,xticklabels=['좌회전 마지막 1초','우회전 마지막 1초'],ylabel='몸 z축 각속도 (rad/s)',ylim=(-1.5,1.5))
        ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2)
    fig.suptitle('회전의 지속: 같은 순차 명령 비교. rough는 출발 지형이며 회전 때 타일 밖 포함')
    fig.savefig(base.OUT/'turn_change_1000_1500.png',dpi=150);plt.close(fig)
    print(json.dumps({label:{'segments':row['segments'],'roll_abs_max_deg':row['roll_abs_max_deg'],'boundary':row['tile_boundary']} for label,row in result['clips'].items()},ensure_ascii=False))

if __name__ == '__main__':
    main()

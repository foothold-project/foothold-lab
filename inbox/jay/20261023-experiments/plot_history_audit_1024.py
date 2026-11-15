"""Scientific figures from saved CPU evidence; no model or simulator execution."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE/'figs/history-audit-1024'
plt.rcParams.update({'font.family':'Malgun Gothic','font.size':12,'axes.spines.top':False,
                     'axes.spines.right':False,'axes.unicode_minus':False,'savefig.facecolor':'white'})
TEAL='#16776B'; RED='#B4463B'; BLUE='#325D91'; DARK='#252D35'

def style(ax):
    ax.set_axisbelow(True);ax.grid(axis='y',alpha=.2);ax.tick_params(colors=DARK)

def main():
    s=json.loads((OUT/'s1_saved_evidence.json').read_text(encoding='utf8'))
    labels=['S1-a','D1 발 들기','D2 두 커널 축소','D3 선속도만 축소']
    folders=['base_scan_1500','d1_scan_1500','d2_scan_1500','d3_scan_1500']
    vals=[s['diagnostics'][k][0]['data']['stall']['stalled_fraction_v2to4s_lt_0.05']*100 for k in folders]
    fig,ax=plt.subplots(figsize=(11,4.6),layout='constrained')
    bars=ax.barh(labels,vals,color=[BLUE,BLUE,TEAL,BLUE]);ax.invert_yaxis();ax.set_xlim(0,100)
    for b,v in zip(bars,vals):ax.text(v+1,b.get_y()+b.get_height()/2,f'{v:.1f}%',va='center',weight='bold')
    ax.set_xlabel('2~4초 전진 속도 < 0.05 m/s인 유효 환경 비율 (%)')
    ax.set_title('S1-a 정지는 보상 폭 변경에 반응했지만, 원인 전체를 설명하지는 않는다',loc='left',pad=16)
    fig.suptitle('동일 1500번 정책 · random_rough · 전진 0.5 m/s · 각 64환경 · 시드 42',fontsize=11,x=.5)
    style(ax);fig.savefig(OUT/'s1_stall_diagnostics.png',dpi=160);plt.close(fig)
    p=json.loads((HERE/'figs/posture-history-1024/metrics.json').read_text(encoding='utf8'))
    xs=[r['iteration'] for r in p['ex23']]
    fig,axs=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    hs=[r['segments'][1]['height_m']*100 for r in p['ex23']]
    axs[0].plot(xs,hs,'o-',color=TEAL,lw=2);axs[0].set_ylim(0,45);axs[0].set_ylabel('접지 발 기준 몸 높이 (cm)')
    for x,v in zip(xs,hs):axs[0].annotate(f'{v:.1f}',(x,v),xytext=(0,8),textcoords='offset points',ha='center')
    axs[0].set_title('몸 높이는 1000번에서 회복')
    for seg,label,color in [(2,'좌회전 명령 +1.2',TEAL),(3,'우회전 명령 -1.2',RED)]:
        axs[1].plot(xs,[r['segments'][seg]['wz_tail'] for r in p['ex23']],'o-',label=label,color=color,lw=2)
    axs[1].axhline(1.2,ls=':',color=TEAL);axs[1].axhline(-1.2,ls=':',color=RED);axs[1].axhline(0,color=DARK,lw=.7)
    axs[1].set_ylim(-1.4,1.4);axs[1].set_ylabel('각 명령 구간 뒤 1.5초 평균 회전 속도 (rad/s)');axs[1].legend(fontsize=10)
    axs[1].set_title('지속 회전은 1500번에서 개선')
    for ax in axs:ax.set_xticks(xs);ax.set_xlabel('체크포인트 파일 번호');style(ax)
    fig.suptitle('EX-23 평지: 몸을 세우기와 회전 학습은 같은 시점이 아니다',fontsize=16)
    fig.savefig(OUT/'ex23_height_and_turn.png',dpi=160);plt.close(fig)
    d=json.loads((OUT/'ex29_independent_check.json').read_text(encoding='utf8'))
    rows=sorted((int(k),v) for k,v in d['log_rows'].items());x=np.array([k for k,v in rows])
    fig,axs=plt.subplots(3,1,figsize=(12,9),sharex=True,layout='constrained')
    axs[0].plot(x,[v['episode_length_steps']*.02 for k,v in rows],color=TEAL,lw=2);axs[0].set_ylabel('평균 에피소드 길이 (s)');axs[0].set_ylim(0,21)
    axs[1].plot(x,[v['bad_orientation_ratio']*100 for k,v in rows],color=RED,lw=2);axs[1].set_ylabel('자세 종료 로그 비율 (%)');axs[1].set_ylim(0,105)
    axs[2].plot(x,[v['terrain_level'] for k,v in rows],color=BLUE,lw=2);axs[2].set_ylabel('평균 지형 난도 행');axs[2].set_ylim(0,1.1)
    for ax in axs:
        ax.axvspan(90,124,color='#E9DFCE',alpha=.45);style(ax)
    axs[2].set_xlabel('학습 갱신 번호 (0부터 시작)')
    fig.suptitle('EX-29: 약 90회 이후 자세 실패가 지배적, 지형은 쉬워지는 중',fontsize=16)
    axs[0].set_title('음영 90~124회 · 3072환경 학습 logger 이동 평균 · 평가 영상 수치와 구분',fontsize=11,loc='left')
    fig.savefig(OUT/'ex29_collapse_timeline.png',dpi=160);plt.close(fig)
    print('3 figures written from saved evidence')

if __name__=='__main__':main()

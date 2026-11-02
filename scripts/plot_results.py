"""从已保存的结果绘图。需要 matplotlib（绘图库）；可用 --font 指定中文字体。"""
import argparse
import gzip
import json
import sys
from datetime import date
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--font', help='中文字体文件路径')
args = parser.parse_args()
if args.font:
    font_manager.fontManager.addfont(args.font)
    plt.rcParams['font.family'] = font_manager.FontProperties(fname=args.font).get_name()
else:
    plt.rcParams['font.family'] = ['Noto Sans CJK SC', 'Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'sans-serif']
plt.rcParams.update({'axes.unicode_minus': False, 'font.size': 11, 'axes.spines.top': False,
                     'axes.spines.right': False, 'savefig.dpi': 170})
with gzip.open(ROOT / 'results/backtest_results.json.gz', 'rt', encoding='utf-8') as f:
    results=json.load(f)
from analyze_results import compute_metrics
main = next(r for r in results if (r['batches'],r['exit_during'],r['exit_kind'])==(15,True,'cross'))
baseline = next(r for r in results if (r['batches'],r['exit_during'],r['exit_kind'])==(1,True,'cross'))
fig, axes = plt.subplots(2,1,figsize=(11,7.4),sharex=True,gridspec_kw={'height_ratios':[2,1]})
for r,label,color in [(main,'分15批买入','#195d8f'),(baseline,'一次性买入','#a16c32')]:
    dates=[date.fromisoformat(x['date']) for x in r['curve']]
    values=[x['value']/100000 for x in r['curve']]
    dd=compute_metrics(r)[4]
    axes[0].plot(dates,values,label=label,color=color,linewidth=1.4)
    axes[1].plot(dates,dd,color=color,linewidth=1.0)
axes[0].set_ylabel('资产价值 / 初始资金');axes[0].legend(frameon=False,loc='upper left')
axes[1].set_ylabel('相对历史高点跌幅');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
for ax in axes:ax.grid(alpha=.18)
fig.suptitle('分批买入与一次性买入的历史表现',fontsize=17,y=.98)
fig.text(.08,.025,'2020年11月16日至2026年10月30日｜样本内、零交易费用、可交易零碎份额',fontsize=10,color='#555555')
fig.tight_layout(rect=(0,.05,1,.96));fig.savefig(ROOT/'figures/equity_drawdown.png');plt.close(fig)
annual=main['annual'];years=list(annual);values=list(annual.values())
fig,ax=plt.subplots(figsize=(11,4))
ax.bar(years,values,color=['#195d8f' if x>=0 else '#b75c49' for x in values],width=.58)
for i,v in enumerate(values):ax.text(i,v+(2 if v>=0 else -2),f'{v:.2f}%',ha='center',va='bottom' if v>=0 else 'top',fontsize=11)
ax.axhline(0,color='#888888',linewidth=.8);ax.set_ylim(-22,118);ax.set_ylabel('期间收益率（%）')
ax.set_title('分15批主方案的分年度收益',fontsize=16,pad=12);ax.grid(axis='y',alpha=.18)
fig.text(.08,.025,'2020年仅含11月16日起的数据；2026年截至10月30日，均非完整年度。',fontsize=10,color='#555555')
fig.tight_layout(rect=(0,.06,1,1));fig.savefig(ROOT/'figures/annual_returns.png');plt.close(fig)
print('图表已生成')

"""绘制策略与同期市场基准；需要 matplotlib（绘图库）及中文字体。"""
import argparse
from datetime import date
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter
from analyze_benchmarks import load_series, metrics

parser=argparse.ArgumentParser();parser.add_argument('--font',help='中文字体文件路径');args=parser.parse_args()
if args.font:
    font_manager.fontManager.addfont(args.font)
    plt.rcParams['font.family']=font_manager.FontProperties(fname=args.font).get_name()
else:
    plt.rcParams['font.family']=['Noto Sans CJK SC','Microsoft YaHei','SimHei','Arial Unicode MS','sans-serif']
plt.rcParams.update({'axes.unicode_minus':False,'font.size':11,'axes.spines.top':False,'axes.spines.right':False})
dates,series=load_series();xs=[date.fromisoformat(d) for d in dates]
fig,axes=plt.subplots(2,1,figsize=(11.8,8),sharex=True,gridspec_kw={'height_ratios':[2,1]})
colors=['#165d8f','#777777','#b56735','#32816b']
for (name,values),color in zip(series.items(),colors):
    width=2.0 if name=='分15批切换策略' else 1.2
    axes[0].plot(xs,[v/100000 for v in values],label=name,color=color,linewidth=width)
    axes[1].plot(xs,metrics(values,dates)[1],color=color,linewidth=width*.7)
axes[0].set_ylabel('资产价值 / 初始资金');axes[0].legend(loc='upper left',frameon=False,ncol=2)
axes[1].set_ylabel('相对历史高点跌幅');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
for ax in axes:ax.grid(alpha=.16)
fig.suptitle('策略与同期基准的收益及回撤比较',fontsize=17,y=.98)
fig.text(.075,.025,'2020年11月16日开盘至2026年10月30日收盘｜初始资金10万元｜价格收益、不计现金分红及交易费用',fontsize=10,color='#555555')
fig.tight_layout(rect=(0,.05,1,.96))
fig.savefig(Path(__file__).resolve().parents[1]/'figures/benchmark_comparison.png',dpi=170)

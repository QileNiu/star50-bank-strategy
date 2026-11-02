"""比较策略与三项基准；数据、日期、费用及指标计算方式固定。"""
import csv
import gzip
import json
import math
import statistics
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INITIAL = 100000.0


def metrics(values, dates):
    previous = peak = INITIAL
    returns, drawdowns = [], []
    for value in values:
        assert math.isfinite(value) and value > 0
        returns.append(value / previous - 1)
        peak = max(peak, value)
        drawdowns.append(value / peak - 1)
        previous = value
    years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
    return {
        '累计收益率%': (values[-1] / INITIAL - 1) * 100,
        '年化收益率%': ((values[-1] / INITIAL) ** (1 / years) - 1) * 100,
        '夏普比率': statistics.mean(returns) / statistics.stdev(returns) * math.sqrt(252),
        '最大回撤%': -min(drawdowns) * 100,
        '期末资产元': values[-1],
    }, drawdowns


def load_series():
    with gzip.open(ROOT / 'results/backtest_results.json.gz', 'rt', encoding='utf-8') as f:
        results = json.load(f)
    result = next(r for r in results if (r['batches'], r['exit_during'], r['exit_kind']) == (15, True, 'cross'))
    with gzip.open(ROOT / 'results/benchmark_prices.csv.gz', 'rt', encoding='utf-8') as f:
        prices = list(csv.DictReader(f))
    dates = [r['date'] for r in prices]
    assert dates == [r['date'] for r in result['curve']]
    assert len(dates) == 1444 and dates == sorted(set(dates))
    # 所有方案以首日开盘价买入，逐日收盘估值；银行基金拆分前价格除以二。
    bank_open = float(prices[0]['bank_open_raw']) / 2
    bank_close = [float(r['bank_close_raw']) / (2 if r['date'] < '2025-07-07' else 1) for r in prices]
    series = {
        '分15批切换策略': [r['value'] for r in result['curve']],
        '沪深300价格指数': [INITIAL * float(r['csi300_close']) / float(prices[0]['csi300_open']) for r in prices],
        '持有科创50基金588000': [INITIAL * float(r['star_close_raw']) / float(prices[0]['star_open_raw']) for r in prices],
        '持有银行基金512800': [INITIAL * v / bank_open for v in bank_close],
    }
    return dates, series


def main():
    dates, series = load_series()
    summaries = []
    for name, values in series.items():
        values_summary, _ = metrics(values, dates)
        summaries.append({'方案': name, **{k: round(v, 4) for k, v in values_summary.items()}})
    with (ROOT / 'results/benchmark_summary.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0])); writer.writeheader(); writer.writerows(summaries)
    with (ROOT / 'results/benchmark_daily.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f); writer.writerow(['日期', *series])
        for i, d in enumerate(dates): writer.writerow([d, *[f'{v[i]:.6f}' for v in series.values()]])
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

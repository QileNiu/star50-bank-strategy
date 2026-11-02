"""复算已保存的六组回测结果；仅使用 Python（编程语言）标准库。"""
import csv
import gzip
import json
import math
import statistics
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INITIAL_CAPITAL = 100000.0
ANNUAL_TRADING_DAYS = 252


def compute_metrics(result):
    curve = result['curve']
    dates = [date.fromisoformat(row['date']) for row in curve]
    assert dates == sorted(set(dates)), '日期须有序且不重复'
    previous = peak = INITIAL_CAPITAL
    daily_returns, drawdowns = [], []
    for row in curve:
        value = float(row['value'])
        assert math.isfinite(value) and value > 0, '资产价值须为正数'
        daily_returns.append(value / previous - 1)
        previous = value
        peak = max(peak, value)
        drawdowns.append(value / peak - 1)
    years = (dates[-1] - dates[0]).days / 365.25
    total = previous / INITIAL_CAPITAL - 1
    annual = (previous / INITIAL_CAPITAL) ** (1 / years) - 1
    # 每日简单收益；无风险收益率为零；样本标准差；每年252个交易日。
    std = statistics.stdev(daily_returns)
    sharpe = statistics.mean(daily_returns) / std * math.sqrt(ANNUAL_TRADING_DAYS)
    max_drawdown = -min(drawdowns)
    assert math.isclose(total * 100, result['return_pct'], abs_tol=1e-8)
    assert math.isclose(-max_drawdown * 100, result['maxdrawdown_pct'], abs_tol=1e-8)
    return total * 100, annual * 100, sharpe, max_drawdown * 100, drawdowns


def main():
    with gzip.open(ROOT / 'results/backtest_results.json.gz', 'rt', encoding='utf-8') as f:
        results = json.load(f)
    summaries = []
    main_case = None
    for i, result in enumerate(results, 1):
        total, annual, sharpe, drawdown, daily_dd = compute_metrics(result)
        summary = {
            '方案': i, '买入批次': result['batches'],
            '建仓期间允许退出': '是' if result['exit_during'] else '否',
            '退出条件': '新发生向下交叉' if result['exit_kind'] == 'cross' else '5日均线低于20日均线',
            '累计收益率%': round(total, 4), '年化收益率%': round(annual, 4),
            '夏普比率': round(sharpe, 4), '最大回撤%': round(drawdown, 4),
            '入场轮次': result['cycle_count'],
        }
        summaries.append(summary)
        if (result['batches'], result['exit_during'], result['exit_kind']) == (15, True, 'cross'):
            assert main_case is None, '主方案不唯一'
            main_case = result
            main_dd = daily_dd
    assert main_case is not None
    with (ROOT / 'results/summary.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0]))
        writer.writeheader(); writer.writerows(summaries)
    with (ROOT / 'results/main_daily.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['日期', '资产价值元', '银行基金市值元', '科创50基金市值元', '相对历史高点跌幅%'])
        for row, dd in zip(main_case['curve'], main_dd):
            writer.writerow([row['date'], f"{row['value']:.6f}", f"{row['bank_value']:.6f}",
                             f"{row['star_value']:.6f}", f'{dd * 100:.6f}'])
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

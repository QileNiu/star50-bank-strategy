# -*- coding: utf-8 -*-
from jqdata import *
import math
from datetime import date, timedelta

# 回测界面选择：按天；初始资金100000元；2020-11-16至2026-10-30。
# 若账户可用行情不到上述结束日期，请使用实际可用日期。
THRESHOLD = 0.1798
BATCHES = 15
COMMISSION = 0.0       # 单边佣金比例；0.0005表示万分之五
MIN_COMMISSION = 0.0   # 每笔最低佣金，单位元
SLIPPAGE = 0.0        # 成交价相对报价的偏差比例


def initialize(context):
    g.index = '000688.XSHG'
    g.star = '588000.XSHG'
    g.bank = '512800.XSHG'
    set_benchmark(g.bank)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=COMMISSION,
                             close_commission=COMMISSION,
                             close_today_commission=0,
                             min_commission=MIN_COMMISSION), type='fund')
    set_slippage(PriceRelatedSlippage(SLIPPAGE))
    g.started = False
    g.active = False
    g.exit_pending = False
    g.steps = 0
    g.budget = 0.0
    g.last_close_value = float(context.portfolio.total_value)
    g.checked_year = None
    run_daily(prepare, time='before_open', reference_security=g.star)
    run_daily(trade, time='open', reference_security=g.star)
    run_daily(report, time='after_close', reference_security=g.star)


def signal_from_rows(rows):
    # 回撤高点每年重算；均线连续计算，不在年初重置。
    peaks, drawdowns = {}, []
    closes = [v for d, v in rows]
    for d, value in rows:
        # 聚宽可能缺少正式发布前的回溯行情。
        # 腾讯和新浪完整日线核对：2020-07-13最高收盘价1721.976。
        # 该段历史于2020-07-22收盘后发布，只从7月23日起使用。
        if d.year == 2020 and d >= date(2020, 7, 23):
            peaks[2020] = max(peaks.get(2020, value), 1721.976)
        peaks[d.year] = max(peaks.get(d.year, value), value)
        drawdowns.append(1.0 - value / peaks[d.year])
    entry = drawdowns[-2] <= THRESHOLD < drawdowns[-1]
    now5 = sum(closes[-5:]) / 5.0
    now20 = sum(closes[-20:]) / 20.0
    prev5 = sum(closes[-6:-1]) / 5.0
    prev20 = sum(closes[-21:-1]) / 20.0
    # 必须是新发生的向下交叉，不能仅判断当前5日均线低于20日均线。
    cross = prev5 >= prev20 and now5 < now20
    return entry, cross


def prepare(context):
    if not g.started:
        return

    def as_date(value):
        # 统一普通日期、带时间的日期及平台返回的日期类型。
        return date(*[int(x) for x in str(value)[:10].split('-')])

    previous = as_date(context.previous_date)
    start = date(previous.year, 1, 1) - timedelta(days=60)
    # 明确包含上一交易日收盘，避免截止时间被解释为当天零点。
    frame = get_price(
        g.index,
        start_date=start.strftime('%Y-%m-%d'),
        end_date=previous.strftime('%Y-%m-%d') + ' 23:59:59',
        frequency='daily',
        fields=['close'],
        skip_paused=False,
        fq=None
    )

    if frame is None or frame.empty:
        raise ValueError(
            '行情为空：回测日=%s，所需行情截止日=%s，指数=%s。'
            '请检查回测日期及该指数的数据权限。'
            % (context.current_dt, previous, g.index)
        )

    values = {}
    for t, v in frame['close'].dropna().items():
        d, value = as_date(t), float(v)
        if d <= previous and math.isfinite(value) and value > 0:
            values[d] = value
    rows = sorted(values.items())
    detail = '回测日=%s，需要截止到=%s，实际范围=%s至%s，有效日数=%d' % (
        context.current_dt, previous,
        rows[0][0] if rows else '无',
        rows[-1][0] if rows else '无', len(rows)
    )
    if not rows or rows[-1][0] != previous:
        raise ValueError(
            '缺少上一交易日行情：' + detail
            + '。请检查结束日期是否超出账户可用行情范围；不能用旧行情代替。'
        )
    if len(rows) < 21:
        raise ValueError(
            '均线历史不足21个交易日：' + detail
            + '。请将回测开始日期调至有足够历史行情之后。'
        )

    if g.checked_year != previous.year:
        sessions = get_trade_days(
            start_date=date(previous.year, 1, 1).strftime('%Y-%m-%d'),
            end_date=previous.strftime('%Y-%m-%d')
        )
        if len(sessions) == 0:
            raise ValueError('未取得当年交易日历：' + detail)
        expected = set(as_date(t) for t in sessions)
        # 发布前的年内高点已补入；发布后的行情仍必须完整。
        if previous.year == 2020 and previous >= date(2020, 7, 23):
            expected = set(d for d in expected if d >= date(2020, 7, 23))
        actual = set(d for d, v in rows if d.year == previous.year)
        missing = sorted(expected - actual)
        if missing:
            raise ValueError(
                '当年指数行情不完整：' + detail
                + '；首个缺失日期=%s。年内高点无法准确计算，'
                '请使用有完整年初行情的年份。' % missing[0]
            )
        g.checked_year = previous.year

    entry, cross = signal_from_rows(rows)
    if g.exit_pending:
        return
    if g.active:
        if cross:
            g.exit_pending = True
            g.steps = BATCHES
            log.info('向下交叉：今日卖出科创50，取消未完成批次。')
    elif entry:
        g.active = True
        g.steps = 0
        g.budget = g.last_close_value / BATCHES
        log.info('入场信号：%s；每批预算%.2f元。' % (previous, g.budget))


def position_amount(context, security):
    p = context.portfolio.positions.get(security)
    return int(p.total_amount) if p is not None else 0


def opening_price(security, buying):
    q = get_current_data()[security]
    price = float(q.day_open)
    if q.paused or not math.isfinite(price) or price <= 0:
        return None
    if buying and price >= q.high_limit:
        return None
    if not buying and price <= q.low_limit:
        return None
    return price


def buy_with_budget(context, security, budget):
    price = opening_price(security, True)
    if price is None:
        return 0
    cash = min(float(budget), float(context.portfolio.available_cash))
    estimated = price * (1.0 + SLIPPAGE)
    amount = int(max(0.0, cash - MIN_COMMISSION)
                 / (estimated * (1.0 + COMMISSION)) / 100) * 100
    if amount < 100:
        return 0
    result = order(security, amount)
    return int(result.filled) if result is not None else 0


def trade(context):
    if not g.started:
        buy_with_budget(context, g.bank, context.portfolio.available_cash)
        g.started = True
        return
    if g.exit_pending:
        if position_amount(context, g.star) > 0:
            if opening_price(g.star, False) is None:
                log.warn('科创50暂不能卖出，下个交易日继续尝试。')
                return
            order_target(g.star, 0)
        if position_amount(context, g.star) > 0:
            log.warn('科创50尚未全部卖出，保留卖出计划。')
            return
        g.exit_pending = False
        g.active = False
        buy_with_budget(context, g.bank, context.portfolio.available_cash)
        return
    if not g.active:
        buy_with_budget(context, g.bank, context.portfolio.available_cash)
        return
    if g.steps >= BATCHES:
        return
    # 每轮最多15个连续交易日；停牌、涨停等未成交批次不顺延。
    g.steps += 1
    if opening_price(g.star, True) is None:
        log.warn('第%d批未成交：科创50当前不能买入。' % g.steps)
        return
    needed = max(0.0, g.budget - context.portfolio.available_cash)
    if needed > 0:
        price = opening_price(g.bank, False)
        p = context.portfolio.positions.get(g.bank)
        if price is not None and p is not None:
            estimate = price * (1.0 - SLIPPAGE) * (1.0 - COMMISSION)
            amount = int(math.ceil((needed + MIN_COMMISSION) / estimate / 100)) * 100
            amount = min(amount, int(p.closeable_amount))
            if amount >= 100 or amount == int(p.total_amount):
                if amount > 0:
                    order(g.bank, -amount)
    # 使用卖出后实际可用资金，避免假设未成交订单已经释放现金。
    filled = buy_with_budget(context, g.star, g.budget)
    log.info('第%d/%d批：实际买入科创50 %d份。' % (g.steps, BATCHES, filled))


def report(context):
    g.last_close_value = float(context.portfolio.total_value)
    p = context.portfolio.positions.get(g.star)
    value = float(p.value) if p is not None else 0.0
    record(科创50持仓比例=value / g.last_close_value if g.last_close_value else 0.0)

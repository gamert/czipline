import sys
# print(sys.stdout.encoding)
# print(sys.getdefaultencoding())


# from zipline import get_calendar
# c = get_calendar('SZSH')
# print(c.first_session)
# Timestamp('1990-12-19 00:00:00+0000', tz='UTC', freq='C')


from zipline.api import symbol, sid, get_datetime

import pandas as pd
import numpy as np
from zipline.api import (attach_pipeline, pipeline_output, get_datetime,
                         calendars, schedule_function, date_rules)
from zipline.pipeline import Pipeline
from zipline.pipeline import CustomFactor
from zipline.pipeline.data import USEquityPricing
from zipline.pipeline.fundamentals import Fundamentals

from pandas._libs.tslib import normalize_date

#day = normalize_date()

# time frame on which we want to compute Fama-French
normal_days = 31
# approximate the number of trading days in that period
# this is the number of trading days we'll look back on,
# on every trading day.
business_days = int(0.69 * normal_days)

print(date_rules.month_end())

# 以下自定义因子选取期初数
class Returns(CustomFactor):
    """
    每个交易日每个股票窗口长度"business_days"期间收益率
    """
    window_length = business_days
    inputs = [USEquityPricing.close]

    def compute(self, today, assets, out, price):
        out[:] = (price[-1] - price[0]) / price[0] * 100


class MarketEquity(CustomFactor):
    """
    每个交易日每只股票所对应的总市值
    """
    window_length = business_days
    inputs = [USEquityPricing.tmv]

    def compute(self, today, assets, out, mcap):
        out[:] = mcap[0]


class BookEquity(CustomFactor):
    """
    每个交易日每只股票所对应的账面价值（所有者权益）
    """
    window_length = business_days
    inputs = [Fundamentals.balance_sheet.A107]

    def compute(self, today, assets, out, book):
        out[:] = book[0]


def initialize(context):
    """
    use our factors to add our pipes and screens.
    """
    pipe = Pipeline()
    mkt_cap = MarketEquity()
    pipe.add(mkt_cap, 'market_cap')

    book_equity = BookEquity()
    # book equity over market equity
    be_me = book_equity / mkt_cap
    pipe.add(be_me, 'be_me')

    returns = Returns()
    pipe.add(returns, 'returns')

    attach_pipeline(pipe, 'ff_example')
    schedule_function(
        func=myfunc,
        date_rule=date_rules.month_end())


def before_trading_start(context, data):
    """
    every trading day, we use our pipes to construct the Fama-French
    portfolios, and then calculate the Fama-French factors appropriately.
    """

    factors = pipeline_output('ff_example')

    # get the data we're going to use
    returns = factors['returns']
    mkt_cap = factors.sort_values(['market_cap'], ascending=True)
    be_me = factors.sort_values(['be_me'], ascending=True)

    # to compose the six portfolios, split our universe into portions
    half = int(len(mkt_cap) * 0.5)
    small_caps = mkt_cap[:half]
    big_caps = mkt_cap[half:]

    thirty = int(len(be_me) * 0.3)
    seventy = int(len(be_me) * 0.7)
    growth = be_me[:thirty]
    neutral = be_me[thirty:seventy]
    value = be_me[seventy:]

    # now use the portions to construct the portfolios.
    # note: these portfolios are just lists (indices) of equities
    small_value = small_caps.index.intersection(value.index)
    small_neutral = small_caps.index.intersection(neutral.index)
    small_growth = small_caps.index.intersection(growth.index)

    big_value = big_caps.index.intersection(value.index)
    big_neutral = big_caps.index.intersection(neutral.index)
    big_growth = big_caps.index.intersection(growth.index)

    # take the mean to get the portfolio return, assuming uniform
    # allocation to its constituent equities.
    sv = returns[small_value].mean()
    sn = returns[small_neutral].mean()
    sg = returns[small_growth].mean()

    bv = returns[big_value].mean()
    bn = returns[big_neutral].mean()
    bg = returns[big_growth].mean()

    # computing SMB
    context.smb = (sv + sn + sg) / 3 - (bv + bn + bg) / 3

    # computing HML
    context.hml = (sv + bv) / 2 - (sg + bg) / 2


def myfunc(context, data):
    d = get_datetime('Asia/Shanghai')
    print(d, context.smb, context.hml)


# zipline --start 2017-1-1 --end 2018-1-1 --bm-symbol 399001
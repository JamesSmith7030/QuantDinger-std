# TradingView Pine Script "四合一" -> QuantDinger Python 翻译
# 版本: Pine v5 -> QuantDinger Python
# 模块: 唐奇安通道 + 猎庄 + 洗盘入场 + 波段王

my_indicator_name = "【四合一】通道买卖点"
my_indicator_description = "唐奇安突破 + 猎庄吸筹 + 洗盘入场 + 波段王综合信号；红色买入/绿色卖出；副图指标。"

# @strategy stopLossPct 0.03
# @strategy takeProfitPct 0.06
# @strategy entryPct 1
# @strategy tradeDirection both

import numpy as np
import pandas as pd

df = df.copy()

#==============================================================================
# A. 参数 (与原 Pine 一致)
#==============================================================================
bar_limit = 100          # 猎庄柱子高度限制
dc_len = 20              # 唐奇安周期
len_cost = 34            # 主力成本周期
limit_level = -10        # 吸筹阈值
hunt_rsi_len = 14        # 猎庄RSI周期
bb_len = 20              # 布林周期
bb_mult = 2.0           # 布林偏差

#==============================================================================
# B. 工具函数
#==============================================================================
def tdx_sma(src, n, m):
    """TDX 增量SMA实现"""
    out = np.full(len(src), np.nan)
    for i in range(len(src)):
        if i == 0:
            out[i] = src.iloc[i] if not np.isnan(src.iloc[i]) else np.nan
        else:
            if np.isnan(out[i-1]):
                out[i] = src.iloc[i]
            else:
                out[i] = (m * src.iloc[i] + (n - m) * out[i-1]) / n
    return pd.Series(out, index=src.index)

def tdx_filter(cond, n):
    """TDX 条件过滤（避免重复信号）"""
    res = pd.Series(False, index=cond.index)
    last_bar_index = -999
    for i in range(len(cond)):
        if cond.iloc[i] and ((i - last_bar_index) > n):
            res.iloc[i] = True
            last_bar_index = i
    return res

def safe_div(numerator, denominator):
    """安全除法"""
    return np.where(denominator == 0, 0, numerator / denominator)

#==============================================================================
# C. 唐奇安通道
#==============================================================================
dc_upper = df['high'].rolling(dc_len).max().shift(1)   # 上轨（昨日最高）
dc_lower = df['low'].rolling(dc_len).min().shift(1)     # 下轨（昨日最低）

break_up = (df['close'] > dc_upper).astype(int)         # 上突破
break_down = (df['close'] < dc_lower).astype(int)       # 下突破

#==============================================================================
# D. 猎庄逻辑
#==============================================================================
hunt_main_cost = df['close'].rolling(len_cost).mean()
hunt_bias = (df['close'] - hunt_main_cost) / hunt_main_cost * 100
hunt_accum = np.where(hunt_bias < limit_level, np.abs(hunt_bias) * 3, 0)

# RSI
delta_h = df['close'].diff()
gain_h = delta_h.clip(lower=0)
loss_h = (-delta_h).clip(lower=0)
avg_gain_h = gain_h.ewm(alpha=1/hunt_rsi_len, adjust=False).mean()
avg_loss_h = loss_h.ewm(alpha=1/hunt_rsi_len, adjust=False).mean()
rs_h = avg_gain_h / avg_loss_h.replace(0, np.nan)
hunt_rsi_val = 100 - (100 / (1 + rs_h))

# 布林带下轨
bb_mid = df['close'].rolling(bb_len).mean()
bb_std = df['close'].rolling(bb_len).std()
hunt_lower = bb_mid - bb_mult * bb_std

hunt_yellow_cond = (df['close'] < hunt_lower) & (hunt_rsi_val < 30)

hunt_height_raw = np.where(hunt_yellow_cond,
                            np.where(hunt_accum > 0, hunt_accum, 20),
                            hunt_accum)
hunt_height = np.minimum(hunt_height_raw, bar_limit)

# 颜色: 黄=吸筹中, 紫=累积中
hunt_color_arr = np.where(hunt_yellow_cond, '#FFFF00',
                          np.where(hunt_accum > 0, '#9c27b0', np.nan))

#==============================================================================
# E. 洗盘入场逻辑
#==============================================================================
zbgs31 = (df['low'].shift(1) + df['open'].shift(1) + df['close'].shift(1) + df['high'].shift(1)) / 4
num = tdx_sma(np.abs(df['low'] - zbgs31), 13, 1)
den = tdx_sma(np.maximum(df['low'] - zbgs31, 0), 10, 1)
zbgs32 = np.where(den == 0, 0, num / den)
zbgs33 = pd.Series(zbgs32).ewm(alpha=0.1, adjust=False).mean()
zbgs34 = df['low'].rolling(33).min()

zbgs35_src = np.where(df['low'] <= zbgs34, zbgs33, 0)
zbgs35 = pd.Series(zbgs35_src).ewm(alpha=0.3, adjust=False).mean()

is_inflow = zbgs35 > zbgs35.shift(1)
is_wash = zbgs35 < zbgs35.shift(1)

# 买点逻辑
zbgs36 = df['close'] - df['close'].shift(1)
ema_diff = pd.Series(zbgs36).ewm(alpha=1/6, adjust=False).mean().ewm(alpha=1/6, adjust=False).mean()
ema_abs = pd.Series(np.abs(zbgs36)).ewm(alpha=1/6, adjust=False).mean().ewm(alpha=1/6, adjust=False).mean()
zbgs37 = np.where(ema_abs == 0, 0, 100 * ema_diff / ema_abs)

llv37_2 = zbgs37.rolling(2).min()
llv37_7 = zbgs37.rolling(7).min()
has_neg = (zbgs37 < 0).rolling(2).sum() > 0

# 金叉
ma2 = zbgs37.rolling(2).mean()
cross_ma = (zbgs37 > ma2) & (zbgs37.shift(1) <= ma2.shift(1))
zbgs38 = (llv37_2 == llv37_7) & has_neg & cross_ma

# 前一根满足条件
zbgs38_prev = zbgs38.shift(1).fillna(False)
entry_signal = tdx_filter(zbgs38_prev, 5)

# 星号信号
vol_up = df['volume'] > df['volume'].shift(1)
vol_up2 = df['volume'].shift(1) > df['volume'].shift(2)
close_le_open = df['close'] <= df['open']
zbgs310 = vol_up & vol_up2 & (df['volume'].shift(2) > df['volume'].shift(3)) & close_le_open
zbgs311 = zbgs310 & (df['close'].shift(1) <= df['open'].shift(1)) & (df['close'].shift(2) <= df['open'].shift(2))
zbgs312 = zbgs311 & (df['close'].shift(3) <= df['open'].shift(3)) & (df['high'] >= df['close'].rolling(60).mean())
zbgs326 = zbgs311 & (df['close'].shift(3) <= df['open'].shift(3)) & (df['high'] >= df['close'].rolling(30).mean())
zbgs328 = zbgs312 | zbgs326

# 主力持仓线
rsv_force = 100 * (df['close'] - df['low'].rolling(34).min()) / (
    df['high'].rolling(34).max() - df['low'].rolling(34).min())
main_force = pd.Series(rsv_force).ewm(alpha=1/3, adjust=False).mean()

#==============================================================================
# F. 波段王逻辑
#==============================================================================
llv_low_40 = df['low'].rolling(40).min()
var113 = safe_div((df['close'] - llv_low_40), llv_low_40) * 100

llv_low_27 = df['low'].rolling(27).min()
hhv_high_27 = df['high'].rolling(27).max()
var111 = safe_div((df['close'] - llv_low_27), (hhv_high_27 - llv_low_27)) * 100
var112 = tdx_sma(var111, 3, 1)
boDuanWang = tdx_sma(var112, 3, 1)

llv_low_55 = df['low'].rolling(55).min()
hhv_high_55 = df['high'].rolling(55).max()
k_val_trend = safe_div((df['close'] - llv_low_55), (hhv_high_55 - llv_low_55)) * 100
sma_k_trend = tdx_sma(k_val_trend, 5, 1)
sma_sma_k_trend = tdx_sma(sma_k_trend, 3, 1)
quShi = pd.Series(sma_k_trend * 3 - sma_sma_k_trend * 2).ewm(alpha=1/3, adjust=False).mean()

llv_low_9 = df['low'].rolling(9).min()
hhv_high_9 = df['high'].rolling(9).max()
kuaiSuXian = safe_div((df['close'] - llv_low_9), (hhv_high_9 - llv_low_9)) * 100
manSuXian = tdx_sma(kuaiSuXian, 3, 1)
kongTou = tdx_sma(manSuXian, 3, 1)

#==============================================================================
# G. 信号 (边缘触发)
#==============================================================================
# 洗盘入场信号 -> 买入
df['buy'] = entry_signal.fillna(False).astype(bool)
# 卖出信号：唐奇安下突破 or 波段王空头
sell_cond = (break_down == 1) | (kongTou < manSuXian)
df['sell'] = sell_cond.fillna(False).astype(bool)

# 避免同周期重复
df['buy'] = df['buy'] & (~df['buy'].shift(1).fillna(False))
df['sell'] = df['sell'] & (~df['sell'].shift(1).fillna(False))

# 信号位置标记
buy_marks = [df['low'].iloc[i] * 0.995 if df['buy'].iloc[i] else None for i in range(len(df))]
sell_marks = [df['high'].iloc[i] * 1.005 if df['sell'].iloc[i] else None for i in range(len(df))]

#==============================================================================
# H. 输出
#==============================================================================
output = {
    'name': my_indicator_name,
    'plots': [
        # 参考线
        {'name': '警戒线100', 'data': [100] * len(df), 'color': '#FFFF00', 'overlay': False},
        # 猎庄背景柱 (数值归一化到0-100)
        {'name': '猎庄背景柱', 'data': (hunt_height / bar_limit * 100).fillna(0).tolist(), 'color': '#9c27b0', 'overlay': False},
        # 洗盘入场柱 (归一化)
        {'name': '洗盘入场柱', 'data': (zbgs35 / zbgs35.max() * 100).fillna(0).replace(0, np.nan).tolist(), 'color': '#FF0000', 'overlay': False},
        # 唐奇安突破
        {'name': '唐奇安突破(上)', 'data': np.where(break_up == 1, 90, np.nan).tolist(), 'color': '#FFD700', 'overlay': False},
        {'name': '唐奇安突破(下)', 'data': np.where(break_down == 1, 50, np.nan).tolist(), 'color': '#00BFFF', 'overlay': False},
        # 波段王
        {'name': 'VAR113', 'data': var113.fillna(0).tolist(), 'color': '#FFFF00', 'overlay': False},
        {'name': '波段王', 'data': boDuanWang.fillna(0).tolist(), 'color': '#0000FF', 'overlay': False},
        {'name': '趋势', 'data': quShi.fillna(0).tolist(), 'color': '#FFA500', 'overlay': False},
        {'name': '快速线', 'data': kuaiSuXian.fillna(0).tolist(), 'color': '#008080', 'overlay': False},
        {'name': '慢速线', 'data': manSuXian.fillna(0).tolist(), 'color': '#FF0000', 'overlay': False},
        {'name': '空头', 'data': kongTou.fillna(0).tolist(), 'color': '#00FF00', 'overlay': False},
        # 主力持仓
        {'name': '主力持仓', 'data': main_force.fillna(0).tolist(), 'color': '#FF0000', 'overlay': False},
    ],
    'signals': [
        {'type': 'buy', 'text': 'B', 'data': buy_marks, 'color': '#00FF00'},
        {'type': 'sell', 'text': 'S', 'data': sell_marks, 'color': '#FF5252'}
    ]
}

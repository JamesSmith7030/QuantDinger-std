# ------------- 适配ETH/USDT短线合约：修改策略基础信息 -------------
my_indicator_name = "ETH/USDT Short-Term Contract RSI Mean Reversion Strategy (Optimized)"
my_indicator_description = "ETH/USDT合约短线：RSI(9) < 30买入，RSI(9) > 70卖出，增加成交量确认和波动率过滤，适配合约高波动特性。"

# 检查df是否为空
if df is None or len(df) == 0:
    # 如果数据为空，返回空结果
    output = {
        "name": my_indicator_name,
        "plots": [],
        "signals": [],
        "calculatedVars": {}
    }
else:
    df = df.copy()

    # 需要导入pandas，如果尚未导入的话
    try:
        import pandas as pd
        import numpy as np
    except ImportError:
        # 如果pandas已经导入，这里会跳过
        pass

    # ------------- 新增：计算ATR用于波动率过滤 -------------
    def calculate_atr(df, period=14):
        """计算平均真实波幅ATR，用于波动率过滤"""
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())

        # 修复：确保使用正确的pandas连接方法
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr

    # 计算ATR和成交量均线
    df['atr'] = calculate_atr(df, 14)
    df['volume_ma'] = df['volume'].rolling(window=20).mean()

    # ------------- 适配ETH/USDT短线合约：修改RSI周期（14→9，短线更灵敏） -------------
    def calculate_rsi(series, period=9):
        """计算RSI指标"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        # 修复：更稳健的除零处理
        rs = gain / loss.replace(0, 1e-8)  # 避免loss为0时报错
        rsi = 100 - (100 / (1 + rs))
        return rsi

    # 计算ETH/USDT收盘价的9周期RSI（短线合约核心指标）
    rsi = calculate_rsi(df['close'], 9)

    # ------------- 适配ETH/USDT短线合约：微调超买超卖阈值 -------------
    overbought = 70
    oversold = 30

    # 生成原始信号
    raw_buy = rsi < oversold
    raw_sell = rsi > overbought

    # 转换为边缘触发信号（避免重复连续信号）
    buy = raw_buy.fillna(False) & (~raw_buy.shift(1).fillna(False))
    sell = raw_sell.fillna(False) & (~raw_sell.shift(1).fillna(False))

    # ------------- 新增：波动率过滤（高波动期间谨慎交易） -------------
    # 计算波动率比率：ATR/当前价格
    volatility_ratio = df['atr'] / df['close']
    # 修复：确保volatility_ratio没有NaN值
    volatility_ratio = volatility_ratio.fillna(0)
    # 过滤条件：波动率低于阈值（可根据市场调整）
    volatility_filter = volatility_ratio < 0.02  # 波动率低于2%

    # ------------- 新增：成交量确认（避免假信号） -------------
    # 修复：处理NaN值并确保布尔类型
    volume_confirm = (df['volume'] > df['volume_ma'] * 1.5).fillna(False)

    # 应用过滤条件
    buy_filtered = buy & volatility_filter & volume_confirm
    sell_filtered = sell & volatility_filter & volume_confirm

    # ------------- 新增：趋势过滤（可选） -------------
    # 计算短期EMA(9)和长期EMA(26)
    ema_short = df['close'].ewm(span=9, adjust=False).mean()
    ema_long = df['close'].ewm(span=26, adjust=False).mean()
    # 修复：处理NaN值
    trend_up = (ema_short > ema_long).fillna(False)

    # 可以根据需要选择是否应用趋势过滤
    # 这里我们只使用趋势信息供参考，不强制过滤

    # ------------- 适配ETH/USDT短线合约：优化鲁棒性阈值 -------------
    if not buy_filtered.any() and not sell_filtered.any():
        # 无边缘触发信号时，回退到原始信号（但应用过滤）
        buy_filtered = raw_buy.fillna(False) & volatility_filter & volume_confirm
        sell_filtered = raw_sell.fillna(False) & volatility_filter & volume_confirm
    elif not buy_filtered.any():
        # 无买入信号时，小幅放宽买入条件
        buy_filtered = (rsi < oversold + 3).fillna(False) & (~raw_buy.shift(1).fillna(False)) & volatility_filter & volume_confirm
    elif not sell_filtered.any():
        # 无卖出信号时，小幅放宽卖出条件
        sell_filtered = (rsi > overbought - 3).fillna(False) & (~raw_sell.shift(1).fillna(False)) & volatility_filter & volume_confirm

    # 确保最终信号是布尔类型
    df['buy'] = buy_filtered.astype(bool)
    df['sell'] = sell_filtered.astype(bool)

    # 准备plot数据（长度与df一致）
    rsi_list = rsi.fillna(50).tolist()  # 填充NaN为50（中性值）
    overbought_line = [overbought] * len(df)
    oversold_line = [oversold] * len(df)

    # 新增：绘制EMA趋势线（完全兼容的方法）
    ema_short_list = []
    ema_long_list = []

    # 使用简单插值方法填充 NaN
    for i in range(len(df)):
        # 对于 EMA(9)，如果当前值是 NaN，尝试用最近的非 NaN 值
        if pd.isna(ema_short.iloc[i]):
            # 向前查找最近的合法值
            found_value = 0
            for j in range(i, -1, -1):
                if not pd.isna(ema_short.iloc[j]):
                    found_value = ema_short.iloc[j]
                    break
            # 如果向前没找到，向后查找
            if found_value == 0 and i < len(df) - 1:
                for j in range(i, len(df)):
                    if not pd.isna(ema_short.iloc[j]):
                        found_value = ema_short.iloc[j]
                        break
            ema_short_list.append(found_value)
        else:
            ema_short_list.append(ema_short.iloc[i])

        # 同样的方法处理 EMA(26)
        if pd.isna(ema_long.iloc[i]):
            found_value = 0
            for j in range(i, -1, -1):
                if not pd.isna(ema_long.iloc[j]):
                    found_value = ema_long.iloc[j]
                    break
            # 如果向前没找到，向后查找
            if found_value == 0 and i < len(df) - 1:
                for j in range(i, len(df)):
                    if not pd.isna(ema_long.iloc[j]):
                        found_value = ema_long.iloc[j]
                        break
            ema_long_list.append(found_value)
        else:
            ema_long_list.append(ema_long.iloc[i])

    # 新增：绘制ATR波动率（处理NaN值）
    atr_list = df['atr'].fillna(0).tolist()

    # ------------- 适配ETH/USDT短线合约：优化买卖标记点 -------------
    buy_marks = []
    sell_marks = []

    for i in range(len(df)):
        if df['buy'].iloc[i]:
            # 修复：确保使用有效价格
            if not pd.isna(df['low'].iloc[i]):
                buy_price = df['low'].iloc[i]
            elif not pd.isna(df['close'].iloc[i]):
                buy_price = df['close'].iloc[i]
            else:
                buy_price = 0
            buy_marks.append(buy_price * 0.998)
        else:
            buy_marks.append(None)

        if df['sell'].iloc[i]:
            # 修复：确保使用有效价格
            if not pd.isna(df['high'].iloc[i]):
                sell_price = df['high'].iloc[i]
            elif not pd.isna(df['close'].iloc[i]):
                sell_price = df['close'].iloc[i]
            else:
                sell_price = 0
            sell_marks.append(sell_price * 1.002)
        else:
            sell_marks.append(None)

    # 最终输出
    output = {
        "name": my_indicator_name,
        "plots": [
            {"name": "RSI(9) (ETH/USDT Short-Term)", "data": rsi_list, "color": "#9C27B0", "overlay": False, "type": "line"},
            {"name": "Overbought(70)", "data": overbought_line, "color": "#FF5252", "overlay": False, "type": "line"},
            {"name": "Oversold(30)", "data": oversold_line, "color": "#00E676", "overlay": False, "type": "line"},
            {"name": "EMA(9)", "data": ema_short_list, "color": "#2196F3", "overlay": True, "type": "line"},
            {"name": "EMA(26)", "data": ema_long_list, "color": "#FF9800", "overlay": True, "type": "line"},
            {"name": "ATR(14)", "data": atr_list, "color": "#795548", "overlay": False, "type": "line"}
        ],
        "signals": [
            {"type": "buy", "text": "B", "data": buy_marks, "color": "#00E676"},
            {"type": "sell", "text": "S", "data": sell_marks, "color": "#FF5252"}
        ],
        "calculatedVars": {
            "volatility_ratio": volatility_ratio.tolist(),
            "volume_confirmation": volume_confirm.tolist(),
            "trend_direction": trend_up.tolist()
        }
    }

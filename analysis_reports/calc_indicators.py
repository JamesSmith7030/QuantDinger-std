import json, math, sys

def compute_rsi(closes, period=14):
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    if len(gains) < period:
        return None
    ag = sum(gains[:period]) / period
    al = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        ag = (ag * 13 + gains[i]) / 14
        al = (al * 13 + losses[i]) / 14
    return 100 - 100 / (1 + ag / al) if al != 0 else 100

def compute_ema(closes, period):
    if len(closes) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for c in closes[period:]:
        ema = c * k + ema * (1 - k)
    return ema

def compute_macd(closes):
    if len(closes) < 26:
        return None, None, None
    k12 = 2 / 13; k26 = 2 / 27; k9 = 2 / 10
    all_e12 = [sum(closes[:12]) / 12]
    for c in closes[12:]:
        all_e12.append(c * k12 + all_e12[-1] * (1 - k12))
    all_e26 = [sum(closes[:26]) / 26]
    for c in closes[26:]:
        all_e26.append(c * k26 + all_e26[-1] * (1 - k26))
    difs2 = [all_e12[i + 14] - all_e26[i] for i in range(len(all_e26))]
    dif = difs2[-1]
    if len(difs2) < 9:
        return round(dif, 3), None, None
    dea = sum(difs2[:9]) / 9
    for d in difs2[9:]:
        dea = d * k9 + dea * (1 - k9)
    return round(dif, 3), round(dea, 3), round(2 * (dif - dea), 3)

def compute_bb(closes, period=20):
    if len(closes) < period:
        return None, None, None
    last = closes[-period:]
    mid = sum(last) / period
    std = math.sqrt(sum((x - mid) ** 2 for x in last) / period)
    return round(mid + 2 * std, 3), round(mid, 3), round(mid - 2 * std, 3)

def compute_atr(highs, lows, closes, period=14):
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        trs.append(tr)
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * 13 + tr) / 14
    return round(atr, 3)

def compute_ma(closes, n):
    return round(sum(closes[-n:]) / n, 3) if len(closes) >= n else None

def compute_kdj(highs, lows, closes, period=9):
    if len(closes) < period:
        return None, None, None
    k = d = 50.0
    for i in range(period - 1, len(closes)):
        h = max(highs[i - period + 1:i + 1])
        l = min(lows[i - period + 1:i + 1])
        r = (closes[i] - l) / (h - l) * 100 if h != l else 50
        k = k * 2 / 3 + r / 3
        d = d * 2 / 3 + k / 3
    j = 3 * k - 2 * d
    return round(k, 2), round(d, 2), round(j, 2)

def analyze(symbol, filepath):
    with open(filepath) as f:
        data = json.load(f)
    closes = [r['close'] for r in data]
    highs = [r['high'] for r in data]
    lows = [r['low'] for r in data]

    print(f"\n=== {symbol} INDICATORS ===")
    print(f"DataPoints: {len(closes)}")
    print(f"Current close: {closes[-1]:.3f}")
    rsi = compute_rsi(closes)
    print(f"RSI(14): {rsi:.2f}" if rsi else "RSI(14): N/A")
    dif, dea, macdh = compute_macd(closes)
    print(f"MACD DIF={dif} DEA={dea} HIST={macdh}")
    u, m, l = compute_bb(closes)
    print(f"BB Upper={u} Mid={m} Lower={l}")
    bw = round((u - l) / m * 100, 2) if m else None
    print(f"BB Width%={bw}")
    k, d, j = compute_kdj(highs, lows, closes)
    print(f"KDJ K={k} D={d} J={j}")
    atr = compute_atr(highs, lows, closes)
    print(f"ATR(14): {atr:.3f}" if atr else "ATR: N/A")
    print(f"MA5={compute_ma(closes,5)} MA10={compute_ma(closes,10)} MA20={compute_ma(closes,20)}")
    ema50 = compute_ema(closes, 50); ema200 = compute_ema(closes, 200)
    print(f"EMA50={round(ema50,3) if ema50 else 'N/A'} EMA200={round(ema200,3) if ema200 else 'N/A'}")
    h20 = max(highs[-20:]); l20 = min(lows[-20:])
    print(f"20d High={h20:.3f} 20d Low={l20:.3f}")
    pos20 = round((closes[-1] - l20) / (h20 - l20) * 100, 1) if h20 != l20 else 50
    print(f"20d Range Position: {pos20}%")
    # Pivot from second-to-last candle (last closed)
    ph = highs[-2]; pl = lows[-2]; pc = closes[-2]
    pivot = (ph + pl + pc) / 3
    r1 = 2 * pivot - pl; s1 = 2 * pivot - ph
    r2 = pivot + (ph - pl); s2 = pivot - (ph - pl)
    print(f"Pivot={pivot:.3f} R1={r1:.3f} R2={r2:.3f} S1={s1:.3f} S2={s2:.3f}")

analyze("RTSLAUSDT", "analysis_reports/rtslausdt_ohlcv.json")
analyze("RNVDAUSDT", "analysis_reports/rnvdausdt_ohlcv.json")

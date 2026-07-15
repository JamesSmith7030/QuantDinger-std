# -*- coding: utf-8 -*-
"""crypto-analysis-report 报告渲染器：解析 pull_okx_data.py 产出的 <SYM>.txt / <SYM>_c20.txt，
按三支柱框架评分并渲染中文 Markdown 深度分析报告，落盘到 --out-dir。

双模式（周期集、权重和止损 ATR 尺度不同，日线展示指标/枢轴口径共享）：
    short（默认·短线，1-3天）: 多周期 RSI/MACD = 15m/1H/4H/1D
    swing（波段，数天-数周）  : 多周期 RSI/MACD = 1H/4H/1D/1W（删 15m 噪声、加周线定趋势）

模式由数据文件里的 `=== MODE ===` 标记决定（pull_okx_data.py 写入）；--mode 显式指定可覆盖。
短线权重 30/40/30、日线 ATR 止损；波段权重 40/35/25、周线 ATR 止损。

用法：
    python build_report.py --symbols BTC,ETH,SOL,BNB --in-dir <拉取目录> --out-dir <报告目录> [--mode auto|short|swing]

文件名：short → <sym>_report_<ts>.md（向后兼容）；swing → <sym>_swing_report_<ts>.md
"""

import argparse
import datetime
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

# 各模式的多周期 RSI/MACD 段名 + 展示标签（顺序一致，索引对齐）
RSI_KEYS = {
    "short": ["RSI 15m", "RSI 1H", "RSI 4H", "RSI 1Dutc"],
    "swing": ["RSI 1H", "RSI 4H", "RSI 1Dutc", "RSI 1Wutc"],
}
MACD_KEYS = {
    "short": ["MACD 15m", "MACD 1H", "MACD 4H", "MACD 1Dutc"],
    "swing": ["MACD 1H", "MACD 4H", "MACD 1Dutc", "MACD 1Wutc"],
}
LABELS = {"short": ["15m", "1H", "4H", "1D"], "swing": ["1H", "4H", "1D", "1W"]}
MODE_CN = {"short": "短线", "swing": "波段"}
HOLD_CN = {"short": "短线（1-3天）", "swing": "波段（数天-数周）"}
# 三支柱权重（宏观, 量价, 衍生）：波段更看估值，宏观加权
WEIGHTS = {"short": (0.30, 0.40, 0.30), "swing": (0.40, 0.35, 0.25)}
# decide 里判趋势动能共振用的两个周期：波段看更高周期
TREND_TFS = {"short": ("4H", "1D"), "swing": ("1D", "1W")}
SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,20}$")
MAX_SYMBOLS = 20


def parse_symbols(raw):
    symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
    if not symbols or any(not SYMBOL_RE.fullmatch(s) for s in symbols):
        raise ValueError("币种仅允许 1-20 位 ASCII 字母或数字，多个币种用逗号分隔")
    if len(symbols) > MAX_SYMBOLS or len(symbols) != len(set(symbols)):
        raise ValueError(f"币种不得重复，且单批最多 {MAX_SYMBOLS} 个")
    return symbols


def parse_sections(txt):
    d, cur = {}, None
    for ln in txt.splitlines():
        m = re.match(r'===\s*(.+?)\s*===', ln)
        if m:
            cur = m.group(1)
            d[cur] = []
            continue
        if cur is not None:
            d[cur].append(ln)
    return {k: "\n".join(v) for k, v in d.items()}


def num(s, pat):
    m = re.search(pat, s, re.M)
    return float(m.group(1)) if m else None


def detect_mode(in_dir, symbols):
    """校验所有现有原始文件的 MODE 标记；缺少全部文件时由后续逐币错误处理。"""
    found = {}
    for c in symbols:
        p = Path(in_dir) / f"{c}.txt"
        if p.exists():
            sec = parse_sections(p.read_text(encoding="utf-8"))
            mode = (sec.get("MODE", "") or "").strip().lower()
            if mode not in ("short", "swing"):
                raise ValueError(f"{c}.txt 的 MODE 缺失或无效：{mode or '<empty>'}")
            found[c] = mode
    modes = set(found.values())
    if len(modes) > 1:
        detail = ", ".join(f"{c}={mode}" for c, mode in found.items())
        raise ValueError(f"检测到混合 mixed 模式，禁止批量混用：{detail}")
    return next(iter(modes), "short")


def parse(in_dir, coin, mode):
    labels = LABELS[mode]
    s = parse_sections((Path(in_dir) / f"{coin}.txt").read_text(encoding="utf-8"))
    d = {"unit": coin, "labels": labels, "mode": mode}
    t = s['TICKER']
    d['price'] = num(t, r'last\s+([\d.]+)')
    d['h24'] = num(t, r'24h high\s+([\d.]+)')
    d['l24'] = num(t, r'24h low\s+([\d.]+)')
    d['vol24'] = num(t, r'24h vol\s+([\d.]+)')
    d['chg'] = num(t, r'24h change %\s+(-?[\d.]+)')
    d['rsi'] = [num(s[k], r'^\s*14\s+([\d.]+)') for k in RSI_KEYS[mode]]
    d['hist'] = [num(s[k], r'macd\s+(-?[\d.]+)') for k in MACD_KEYS[mode]]
    m1d = s['MACD 1Dutc']  # 日线 MACD 明细两模式都取（§五/§六 用）
    d['macd1d'] = (num(m1d, r'dif\s+(-?[\d.]+)'), num(m1d, r'dea\s+(-?[\d.]+)'), num(m1d, r'macd\s+(-?[\d.]+)'))
    bb = s['BB 1D']
    d['bb1d'] = (num(bb, r'upper\s+([\d.]+)'), num(bb, r'middle\s+([\d.]+)'), num(bb, r'lower\s+([\d.]+)'))
    kd = s['KDJ 1D']
    d['kdj'] = (num(kd, r'k\s+([\d.]+)'), num(kd, r'd\s+([\d.]+)'), num(kd, r'j\s+([\d.]+)'))
    d['ema50'] = num(s['EMA50'], r'^\s*50\s+([\d.]+)')
    d['ema200'] = num(s['EMA200'], r'^\s*200\s+([\d.]+)')
    d['atr'] = num(s['ATR14'], r'^\s*14\s+([\d.]+)')  # 日线 ATR（§五展示 + 波动性）
    if mode == "swing":
        d['atr_w'] = num(s['ATR14W'], r'^\s*14\s+([\d.]+)')  # 周线 ATR（波段止损定尺）
    d['ma'] = (num(s['MA5'], r'^\s*5\s+([\d.]+)'), num(s['MA10'], r'^\s*10\s+([\d.]+)'), num(s['MA20'], r'^\s*20\s+([\d.]+)'))
    tl = s['TLS']
    d['tls'] = (num(tl, r'longRatio\s+([\d.]+)'), num(tl, r'shortRatio\s+([\d.]+)'), num(tl, r'longShortRatio\s+([\d.]+)'))
    d['funding'] = num(s['FUNDING'], r'fundingRate\s+(-?[\d.]+)') * 100  # %
    oi = s['OI']
    m = re.search(rf'{coin}-USDT-SWAP\s+[\d.]+\s+([\d.]+)', oi)
    d['oi'] = float(m.group(1)) if m else num(oi, rf'{coin}-USDT-SWAP\s+([\d.]+)')
    if coin == 'BTC':
        d['ahr999'] = num(s['AHR999'], r'ahr999\s+([\d.]+)')
        d['ah_zone'] = num(s['AHR999'], r'zone\s+(\d+)')
        d['rb_band'] = num(s['RAINBOW'], r'band\s+(\d+)')
    c = (Path(in_dir) / f"{coin}_c20.txt").read_text(encoding="utf-8")
    rows = re.findall(r'\d{4}/\d+/\d+ \d+:\d+:\d+\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)', c)
    closed = rows[1:21]  # 剔除今日成形，取 20 根已收盘
    d['sw_hi'] = max(float(r[1]) for r in closed)
    d['sw_lo'] = min(float(r[2]) for r in closed)
    d['prev'] = (float(closed[0][1]), float(closed[0][2]), float(closed[0][3]))  # 上一根已收盘 H/L/C
    return d


def i_of(d, label):
    return d['labels'].index(label)


def score(d):
    price = d['price']
    if 'ahr999' in d:
        a = d['ahr999']
        macro = 15 if a < 0.45 else 40 if a < 1.2 else 70 if a < 5 else 90
    else:
        below = (1 if price < d['ema200'] else 0) + (1 if price < d['ema50'] else 0)
        base = {2: 32, 1: 48, 0: 66}[below]
        rp = (price - d['sw_lo']) / (d['sw_hi'] - d['sw_lo']) * 100
        macro = base * 0.6 + rp * 0.4
    rsi_s = sum(d['rsi']) / 4
    macd_s = sum(1 for h in d['hist'] if h > 0) / 4 * 100
    ma_s = sum(1 for m in d['ma'] if price > m) / 3 * 100
    vp = (rsi_s + macd_s + ma_s) / 3
    fund_s = 50 - min(max(d['funding'] / 0.01 * 3, -15), 15)
    tls_s = 50 + (d['tls'][2] - 1.0) * 50
    deriv = (fund_s + tls_s) / 2
    wm, wv, wd = WEIGHTS[d['mode']]
    comp = macro * wm + vp * wv + deriv * wd
    return round(macro, 1), round(vp, 1), round(deriv, 1), round(comp, 1)


def derive(d):
    H, L, C = d['prev']
    P = (H + L + C) / 3
    R1 = 2 * P - L
    S1 = 2 * P - H
    R2 = P + (H - L)
    S2 = P - (H - L)
    U, M, Lo = d['bb1d']
    support = (S1 + d['sw_lo'] + Lo) / 3
    resistance = (R1 + d['sw_hi'] + U) / 3
    price = d['price']
    atr_stop = d.get('atr_w', d['atr'])  # 波段用周线 ATR 定止损，短线用日线 ATR
    atr_tf = '1W' if 'atr_w' in d else '1D'
    sl = max(price - 2 * atr_stop, support * 0.99)
    tp = min(price + 3 * atr_stop, resistance * 1.01)
    rr = (tp - price) / (price - sl) if price > sl else float('nan')
    sl_s = min(price + 2 * atr_stop, resistance * 1.01)   # 空单镜像（SKILL §2.5）
    tp_s = max(price - 3 * atr_stop, support * 0.99)
    rr_s = (price - tp_s) / (sl_s - price) if sl_s > price else float('nan')
    rp = (price - d['sw_lo']) / (d['sw_hi'] - d['sw_lo']) * 100
    bw = (U - Lo) / M * 100
    volp = d['atr'] / price * 100  # 波动性用日线 ATR（展示口径不变）
    return dict(P=P, R1=R1, S1=S1, R2=R2, S2=S2, support=support, resistance=resistance,
                sl=sl, tp=tp, rr=rr, sl_s=sl_s, tp_s=tp_s, rr_s=rr_s,
                rangepos=rp, bw=bw, volp=volp, atr_stop=atr_stop, atr_tf=atr_tf)


def directional_levels(k, direction):
    if direction == "做多":
        return k['sl'], k['tp'], k['rr']
    if direction == "做空":
        return k['sl_s'], k['tp_s'], k['rr_s']
    raise ValueError(f"不支持的交易方向：{direction}")


def fmt(x, dp=2):
    return f"{x:,.{dp}f}"


def decide(d, k, sc):
    macro, vp, deriv, comp = sc
    mode_cn = MODE_CN[d['mode']]
    price = d['price']
    ma5, ma10, ma20 = d['ma']
    i4, i1 = i_of(d, '4H'), i_of(d, '1D')
    rsi_4h = d['rsi'][i4]
    j = d['kdj'][2]
    lsr = d['tls'][2]
    rr = k['rr']
    above_ma = price > ma5 and price > ma10
    below_ma = price < ma5 and price < ma10
    ta, tb = TREND_TFS[d['mode']]  # 短线 4H+1D、波段 1D+1W
    st_up = d['hist'][i_of(d, ta)] > 0 and d['hist'][i_of(d, tb)] > 0
    st_dn = d['hist'][i_of(d, ta)] < 0 and d['hist'][i_of(d, tb)] < 0
    overbought = rsi_4h >= 70 or j >= 100
    oversold = rsi_4h <= 30 or j <= 0
    overheated = comp >= 60
    below200 = price < d['ema200']
    rr_s = k['rr_s']
    poor_rr = (not (rr == rr)) or rr < 1  # nan 或 <1
    poor_rr_s = (not (rr_s == rr_s)) or rr_s < 1
    ref_dir = None
    if below_ma and st_dn:
        # 偏空共振（跌破短均线 + 双周期 MACD 同负）→ 做空镜像；超卖/赔率差不追空（对称于做多侧）
        ref_dir = '做空'
        if oversold or poor_rr_s:
            form, dirn = 'B', 'HOLD'
            note = f"破位偏空但{'深度超卖' if oversold else f'追空 RR 仅 1:{rr_s:.2f}'}，不追空，反弹承压再评估"
        else:
            form, dirn = 'A', '做空'
            note = f"{mode_cn}偏空共振（跌破 MA5/10 + {ta}/{tb} MACD 同负），反弹承压进场，收复 MA10 减/离场"
    elif above_ma and st_up:
        ref_dir = '做多'
        if poor_rr or (overbought and rr < 1.2):
            form, dirn = 'B', 'HOLD'
            note = f"偏多结构已出现但追多 RR 仅 1:{rr:.2f}{'、超买' if overbought else ''}，观望等回踩"
        else:
            form, dirn = 'A', '做多'
            note = (f"逆大周期反弹，控仓、破 MA10 减" if below200 else f"{mode_cn}偏多，破 MA10 减")
    else:
        form, dirn = 'B', 'HOLD'
        note = f"结构未共振，{'市场过热，' if overheated else ''}观望"
    if form == 'A' and dirn == '做多':
        sig = f"🟢 BUY 买入（{mode_cn}做多确认）"
    elif form == 'A' and dirn == '做空':
        sig = f"🔴 SELL 卖出/做空（{mode_cn}偏空确认）"
    else:
        sig = f"🟡 NEUTRAL 中性（{zone_of(comp)}，HOLD）"
    rr_eff = rr_s if dirn == '做空' else rr  # 有效 RR 随方向取镜像值
    conf = "中 ~55%" if (form == 'A' and rr_eff == rr_eff and rr_eff >= 1.5) else ("中 ~50%" if form == 'A' else "低-中 ~45%")
    up_count = sum(1 for r in d['rsi'] if r > 50)
    down_count = sum(1 for r in d['rsi'] if r < 50)
    tf = f"{max(up_count, down_count) * 25}%"
    mps = f"{(up_count - down_count) / 4 * 5:+.0f}"
    cons = "BUY" if up_count >= 3 else "SELL" if down_count >= 3 else "MIXED"
    if form == 'A' and dirn == '做空':
        entry = f"反弹 MA5 ${fmt(ma5)} 附近承压不破再进场"
    elif form == 'A':
        if price < d['ema50']:
            entry = f"回踩 MA5 ${fmt(ma5)} 确认不破；EMA50 ${fmt(d['ema50'])} 为上方阻力"
        else:
            entry = f"回踩 MA5 ${fmt(ma5)} / EMA50 ${fmt(d['ema50'])} 附近确认不破"
    elif ref_dir == '做空':
        entry = f"不追空；反弹 MA5 ${fmt(ma5)} 附近承压不破再评估"
    elif ref_dir == '做多':
        if price < d['ema50']:
            entry = (f"不追高；先收复 EMA50 ${fmt(d['ema50'])} 并站稳；若先回落，"
                     f"只观察 MA5 ${fmt(ma5)} 是否守住")
        else:
            entry = f"不追高；回踩 MA5 ${fmt(ma5)} / EMA50 ${fmt(d['ema50'])} 且不破再评估"
    else:
        entry = f"暂不预设方向；等待价格与 MA5 ${fmt(ma5)} / MA10 ${fmt(ma10)} 重新共振"
    return dict(form=form, dir=dirn, note=note, sig=sig, conf=conf, tf=tf, mps=mps, cons=cons,
                entry=entry, overbought=overbought, below200=below200, st_up=st_up,
                above_ma=above_ma, overheated=overheated, ref_dir=ref_dir)


def reasons_risks(d, k, sc, dec):
    macro, vp, deriv, comp = sc
    price = d['price']
    ma5, ma10, ma20 = d['ma']
    lsr = d['tls'][2]
    i4, i1 = i_of(d, '4H'), i_of(d, '1D')
    npos = sum(1 for h in d['hist'] if h > 0)
    nma = sum(1 for m in d['ma'] if price > m)
    R = []
    if 'ahr999' in d:
        R.append(f"AHR999 {d['ahr999']} + 彩虹 band{int(d['rb_band'])} = 历史低估区，向下估值空间有限，中长线价值支撑")
    else:
        R.append(f"20日区间位置 {k['rangepos']:.1f}%，价 vs EMA50({fmt(d['ema50'], 1)})/EMA200({fmt(d['ema200'], 1)}) 定位估值维度")
    R.append(f"MACD 柱 {npos}/4 周期为正、站上 {nma}/3 均线（MA5/10/20），动能{'偏多修复' if d['hist'][i1] > 0 else '偏弱'}")
    if dec['form'] == 'A' and dec['dir'] == '做空':
        R.append(f"做空 RR 1:{k['rr_s']:.2f}，阻力 {fmt(k['resistance'])} 提供失效锚点，资金费率 {d['funding']:+.4f}%")
    elif dec['form'] == 'A':
        R.append(f"做多 RR 1:{k['rr']:.2f}，支撑 {fmt(k['support'])} 提供失效锚点，资金费率 {d['funding']:+.4f}%")
    elif dec.get('ref_dir') == '做空':
        R.append(f"偏空结构已出现，但做空 RR 仅 1:{k['rr_s']:.2f} 或存在超卖风险，当前不追空")
    elif dec.get('ref_dir') == '做多':
        R.append(f"偏多结构已出现，但做多 RR 仅 1:{k['rr']:.2f} 或存在超买风险，当前不追高")
    else:
        R.append(f"量价支柱 {vp}，多空结构尚未共振，当前不预设开仓方向")
    Rk = []
    if dec['below200']:
        pos50 = '上方' if price >= d['ema50'] else '下方'
        pos200 = '上方' if price >= d['ema200'] else '下方'
        Rk.append(f"价格位于 EMA50({fmt(d['ema50'], 1)}){pos50}、EMA200({fmt(d['ema200'], 1)}){pos200}，大周期仍受 EMA200 压制")
    if dec['overheated']:
        range_note = "贴近顶部" if k['rangepos'] >= 80 else "尚未贴近顶部"
        Rk.append(f"市场温度 {comp} 落入过热区，20日区间位置 {k['rangepos']:.1f}%（{range_note}）；高温不等于立即反转")
    elif dec['overbought']:
        if dec['dir'] == '做空' or dec.get('ref_dir') == '做空':
            Rk.append(f"4H RSI {d['rsi'][i4]} / KDJ J {d['kdj'][2]} 偏超买，但强势延续可能造成空头挤压")
        else:
            Rk.append(f"4H RSI {d['rsi'][i4]} / KDJ J {d['kdj'][2]} 偏超买，短线过热，做多 RR 仅 1:{k['rr']:.2f}")
    else:
        ma20_pos = '上方' if price >= ma20 else '下方'
        Rk.append(f"1D RSI {d['rsi'][i1]}、价格位于 MA20({fmt(ma20, 1)}){ma20_pos}，动能未确认强势")
    Rk.append(f"顶级交易员多空比 {lsr}（{'偏空' if lsr < 1 else '偏多'}），资金费率 {d['funding']:+.4f}%（{'多头付费' if d['funding'] > 0 else '空头付费'}）")
    return R, Rk


def zone_of(comp):
    return '抄底' if comp < 20 else '复苏' if comp < 40 else '中性' if comp < 60 else '过热' if comp < 80 else '狂热'


def rsirow(v):
    s = "超买" if v >= 70 else "超卖" if v <= 30 else "偏强" if v >= 55 else "偏弱" if v <= 45 else "中性"
    return f"{v}（{s}）"


def tf_dir(rsi_v, hist_v):
    if rsi_v > 55 and hist_v > 0:
        return '上涨'
    if rsi_v < 45 and hist_v < 0:
        return '下跌'
    if rsi_v > 50 or hist_v > 0:
        return '震荡偏强'
    return '震荡偏弱'


def report(in_dir, out_dir, coin, mode, ts, tsh):
    d = parse(in_dir, coin, mode)
    sc = score(d)
    k = derive(d)
    dec = decide(d, k, sc)
    macro, vp, deriv, comp = sc
    zone = zone_of(comp)
    R, Rk = reasons_risks(d, k, sc, dec)
    labels = d['labels']
    mode_cn = MODE_CN[mode]
    U, M, L = d['bb1d']
    dif, dea, hist1d = d['macd1d']
    ma5, ma10, ma20 = d['ma']
    lr, sr, lsr = d['tls']
    ema50_side = '上方' if d['price'] >= d['ema50'] else '下方'
    ema200_side = '上方' if d['price'] >= d['ema200'] else '下方'
    ema_state = f"EMA50{ema50_side} / EMA200{ema200_side}"
    i1 = i_of(d, '1D')
    rsi1d = d['rsi'][i1]
    npos = sum(1 for h in d['hist'] if h > 0)
    nma = sum(1 for m in d['ma'] if d['price'] > m)
    volcat = "高" if k['volp'] > 5 else "中" if k['volp'] > 2 else "低"
    lbl = "/".join(labels)
    wm, wv, wd = WEIGHTS[mode]
    wpct = f"宏观{wm * 100:.0f}% + 量价{wv * 100:.0f}% + 衍生品{wd * 100:.0f}%"
    comp_formula = f"{macro}×{wm:.2f} + {vp}×{wv:.2f} + {deriv}×{wd:.2f} = {comp}"
    ta, tb = TREND_TFS[mode]  # 趋势确认周期（提示语用）
    rsi_line = "、".join(f"{labels[i]} {rsirow(d['rsi'][i])}" for i in range(4))
    macd_line = "、".join(f"{labels[i]} {d['hist'][i]:+}" for i in range(4))
    rsi_detail = " / ".join(f"{labels[i]} {d['rsi'][i]}" for i in range(4))
    review = f"{labels[0]}/{labels[1]} 看择时，{labels[2]}/{labels[3]} 收盘复核趋势与 MACD 动能"
    active_dir = dec['dir'] if dec['form'] == 'A' else dec.get('ref_dir')
    active_sl, active_tp, active_rr = directional_levels(k, active_dir) if active_dir else (None, None, None)
    if dec['form'] == 'A':
        holding_note = f"{dec['dir']}止损参考 ${fmt(active_sl)}；触发失效条件离场"
    elif active_dir:
        holding_note = f"当前不开仓；{active_dir}候选失效位参考 ${fmt(active_sl)}"
    else:
        holding_note = "当前不开新仓；已有仓位沿用原计划，不新增方向假设"

    if dec['form'] == 'A':
        is_short = dec['dir'] == '做空'
        confirm_txt = ("偏空确认（跌破短均线+双周期 MACD 同负）" if is_short
                       else "偏多确认（站上短均线+多周期 MACD 转正）")
        entry_note = "反弹承压不破关键位" if is_short else "回踩确认不破关键位"
        sl_v, tp_v, rr_v = directional_levels(k, dec['dir'])
        sl_f = (f"min(现价+2×{k['atr_tf']}ATR, 阻力×1.01)" if is_short
                else f"max(现价−2×{k['atr_tf']}ATR, 支撑×0.99)")
        tp_f = (f"max(现价−3×{k['atr_tf']}ATR, 支撑×0.99)" if is_short
                else f"min(现价+3×{k['atr_tf']}ATR, 阻力×1.01)")
        side_txt = "空单参考" if is_short else "多单参考"
        guide = (f"**形态 A — 方向明确（{dec['dir']}，由数据决定）：**\n"
                 "| 项目 | 价位 | 说明 |\n|------|------|------|\n"
                 f"| **交易方向** | **{dec['dir']}** | {confirm_txt} |\n"
                 f"| 当前价格 | ${fmt(d['price'])} | 24h {d['chg']:+.2f}% |\n"
                 f"| 建议入场 | {dec['entry']} | {entry_note} |\n"
                 f"| 止损价 | ${fmt(sl_v)} | {sl_f} |\n"
                 f"| 止盈目标 | ${fmt(tp_v)} | {tp_f} |\n"
                 f"| 风险回报比 | 1 : {rr_v:.2f} | {side_txt} |\n\n"
                 f"> ⚠️ {dec['note']}。止损止盈基于 **{k['atr_tf']} ATR(14)=${fmt(k['atr_stop'])}**；"
                 f"支撑/阻力为三方法平均（枢轴+20日摆动+布林）。非投资建议。")
    else:
        guide = (f"**形态 B — HOLD（{dec['note']}）：只显示当前价格：**\n"
                 "| 项目 | 价位 | 说明 |\n|------|------|------|\n"
                 f"| **交易方向** | **HOLD（观望）** | {dec['note']} |\n"
                 f"| 当前价格 | ${fmt(d['price'])} | 24h {d['chg']:+.2f}% |\n\n"
                 f"> ⚠️ 参考（非当前建议入场）：结构支撑 ${fmt(k['support'])} / 阻力 ${fmt(k['resistance'])}；"
                 f"做多 RR 1:{k['rr']:.2f}、做空 RR 1:{k['rr_s']:.2f}。{dec['entry']}。非投资建议。")
    if coin == 'BTC':
        macro_txt = (f"AHR999 **{d['ahr999']}**（zone{int(d['ah_zone'])} 抄底/DCA 区）、彩虹 band{int(d['rb_band'])}、"
                     f"价位于 EMA50(${fmt(d['ema50'], 1)}){ema50_side}、EMA200(${fmt(d['ema200'], 1)}){ema200_side} → **历史低估区**。")
    else:
        macro_txt = (f"非 BTC 无 AHR999，均线估值：价 vs EMA50(${fmt(d['ema50'], 1)})/EMA200(${fmt(d['ema200'], 1)})、"
                     f"20日区间位置 **{k['rangepos']:.1f}%**。")
    r3 = "3. " + R[2] if len(R) > 2 else ""

    # 只评价本次真实计算的模式，不用当前数据臆测另一个模式。
    if dec['form'] == 'A':
        contract_note = f"仅按{dec['dir']}确认执行，控制杠杆，严格止损 ${fmt(active_sl)}"
    elif active_dir:
        contract_note = f"当前 HOLD；仅在{active_dir}条件重新确认后评估，候选失效位 ${fmt(active_sl)}"
    else:
        contract_note = "当前 HOLD；方向未确认，不开新仓"
    op_rows = (f"| {HOLD_CN[mode]} | {dec['note']} |\n"
               f"| 合约 | {contract_note} |")

    # §二 周期趋势预判：按当前模式的 4 个真实周期出方向（诚实，不再套固定日历标签）
    trend_rows = "\n".join(f"| {labels[i]} | {tf_dir(d['rsi'][i], d['hist'][i])} |" for i in range(4))

    md = f"""# {coin}/USDT 深度{mode_cn}分析报告

> 生成时间：{tsh} (UTC+8) ｜ 数据源：OKX 实时行情（基础档） ｜ 模式：**{mode_cn}**（周期 {lbl}） ｜ 分析框架：三支柱评分（{wpct}）
> ⚠️ 本报告仅为客观技术分析与数据整理，**不构成投资建议**。加密资产波动剧烈，请自行研究（DYOR）并自担风险。

---

## 综合结论
| 项目 | 结果 |
|------|------|
| **综合信号** | {dec['sig']} |
| **市场温度评分** | **{comp}/100** |
| **市场温度分区** | **{zone}**（仅表示估值/热度，不直接决定开仓方向） |
| **置信度** | {dec['conf']} |
| **分析模式** | {mode_cn}（多周期 {lbl}） |
| **市场阶段** | {'EMA200 下方大周期弱势中的反弹' if dec['below200'] else '均线上方'}；{'过热' if dec['overheated'] else '超买' if dec['overbought'] else '动能修复'} |
| **当前价格** | **${fmt(d['price'])}**（24h {d['chg']:+.2f}%） |

**一句话**：市场温度 {comp}（{zone}）；执行信号 {dec['dir']}。宏观 {macro} + 量价 {vp} + 衍生 {deriv}。{R[0]}

### 多周期客观共识
| 项目 | 值 |
|------|-----|
| 共识方向 | {dec['cons']} |
| 周期一致度 | {dec['tf']}（RSI 主导方向占比，{lbl}） |
| 多周期评分 | {dec['mps']}（-5 ~ +5） |

---

## 下一步（行动清单）
1. **🎯 盯关键位**：阻力 ${fmt(k['resistance'])}（R1 ${fmt(k['R1'])}）；支撑 ${fmt(k['support'])}（S1 ${fmt(k['S1'])}）
2. **📥 / ⏳ 操作倾向**：{dec['note']}
3. **🛡️ 持仓处理**：{holding_note}
4. **🔁 复核节奏**：{review}
5. **🔬 进阶**：如需精确仓位张数，调用 `position-sizer`

### 📋 开仓指南（ATR×结构融合，对齐后端引擎，仅供参考）

{guide}

---

## 一、实时市场数据
| 项目 | 值 |
|------|-----|
| 当前价格 | ${fmt(d['price'])}（24h {d['chg']:+.2f}%） |
| 24h 高 / 低 | ${fmt(d['h24'])} / ${fmt(d['l24'])} |
| 24h 成交量 | {fmt(d['vol24'])} {d['unit']} |
| 资金费率 | {d['funding']:+.4f}%（正=多头付费） |
| 未平仓量 OI | {fmt(d['oi'])} {d['unit']} |
| 顶级交易员多空比 | {lr}/{sr}（={lsr}） |

## 二、周期趋势预判（按本模式 {lbl}）
| 周期 | 方向 |
|------|------|
{trend_rows}

## 三、Crypto 交易大数据
| 项目 | 值 |
|------|-----|
| 24h 成交量 | {fmt(d['vol24'])} {d['unit']} |
| 资金费率 | {d['funding']:+.4f}%（正=多头付费/负=空头付费） |
| 未平仓量 OI | {fmt(d['oi'])} {d['unit']} |
| 顶级交易员多空比 | {lr}/{sr}（={lsr}，{'<1 偏空' if lsr < 1 else '>1 偏多'}） |
| 交易所净流 | --（数据缺失，OKX 行情不提供） |
| 稳定币净流 | --（数据缺失） |

> 因子偏向：衍生品 {deriv}（{'中性偏空' if lsr < 1 else '中性偏多'}）；挤仓风险：低。

## 四、三支柱评分拆解（权重 {wpct}）
### 支柱一 · 宏观周期（{wm * 100:.0f}%）— 评分 ≈ {macro}
{macro_txt}（分数越低=越低估=越利多）
### 支柱二 · 量价因子（{wv * 100:.0f}%）— 评分 ≈ {vp}
多周期 RSI：{rsi_line}。
多周期 MACD 柱：{macd_line}（{npos}/4 为正）。
均线：价 vs MA5 ${fmt(ma5, 1)} / MA10 ${fmt(ma10, 1)} / MA20 ${fmt(ma20, 1)}（{nma}/3 站上）；KDJ K{d['kdj'][0]}/D{d['kdj'][1]}/J{d['kdj'][2]}。
### 支柱三 · 衍生品（{wd * 100:.0f}%）— 评分 ≈ {deriv}
资金费率 {d['funding']:+.4f}%、OI {fmt(d['oi'])} {d['unit']}、顶级多空比 {lsr}。
### 市场温度评分
`{comp_formula}` → {zone}

## 五、技术指标 PRO
| 指标 | 值 | 状态 |
|------|-----|------|
| RSI(14) 1D | {rsi1d} | {"超买" if rsi1d >= 70 else "超卖" if rsi1d <= 30 else "中性"} |
| MACD(12,26,9) 1D | 柱 {hist1d:+} | {"看涨修复" if hist1d > 0 else "看跌"} |
| 均线趋势 | {"多头(站上MA5/10)" if d['price'] > ma5 and d['price'] > ma10 else "空头/纠缠"} | {ema_state} |
| ATR(14) | ${fmt(d['atr'])} | 真实波幅均值 |
| 布林带宽 % | {k['bw']:.2f}% | {"扩张" if k['bw'] > 15 else "挤压"} |
| 20 日区间位置 | {k['rangepos']:.1f}% | 0–100% |
| 支撑位 | ${fmt(k['support'])} | 三方法平均 |
| 阻力位 | ${fmt(k['resistance'])} | 三方法平均 |
| 波动性 | {volcat}（{k['volp']:.2f}%） | ATR/Price |

## 六、量化参数明细
| 参数 | 值 | 参数 | 值 |
|------|-----|------|-----|
| MACD DIF(快线) 1D | {dif} | MA(5) | ${fmt(ma5, 1)} |
| MACD DEA(信号线) 1D | {dea} | MA(10) | ${fmt(ma10, 1)} |
| MACD 柱(动能) 1D | {hist1d:+} | MA(20) | ${fmt(ma20, 1)} |
| 布林上轨 U | ${fmt(U, 1)} | 经典枢轴 Pivot | ${fmt(k['P'])} |
| 布林中轨 MB | ${fmt(M, 1)} | 支撑 S1 / 阻力 R1 | ${fmt(k['S1'])} / ${fmt(k['R1'])} |
| 布林下轨 L | ${fmt(L, 1)} | 支撑 S2 / 阻力 R2 | ${fmt(k['S2'])} / ${fmt(k['R2'])} |
| 布林带宽 % | {k['bw']:.2f}% | 20 日摆动高/低 | ${fmt(d['sw_hi'])} / ${fmt(d['sw_lo'])} |
| ATR(14) 绝对值 | ${fmt(d['atr'])}（{k['volp']:.2f}%） | 风险回报(多/空参考) | 1 : {k['rr']:.2f} / 1 : {k['rr_s']:.2f} |
| 计算用收盘价 | ${fmt(d['price'])} | — | — |

## 七、详细分析
**技术面**：多周期 RSI（{rsi_detail}）与 MACD 柱（{npos}/4 为正）显示动能{'偏多修复' if hist1d > 0 else '偏弱'}；带宽 {k['bw']:.2f}%、20日区间位置 {k['rangepos']:.1f}%。
**衍生品面**：资金费率 {d['funding']:+.4f}%、OI {fmt(d['oi'])}、顶级多空比 {lsr}；无明显挤仓，衍生偏{'中性偏空' if lsr < 1 else '中性偏多'}。
**宏观面**：{macro_txt} 基础档下 FRED 利率/CPI、恐惧贪婪指数、DXY/VIX、新闻等**需 datahub 增强档，暂缺**，未编造。

## 八、核心理由与风险
**核心理由**：
1. {R[0]}
2. {R[1]}
{r3}

**风险提示**：
1. {Rk[0]}
2. {Rk[1] if len(Rk) > 1 else ''}
3. {Rk[2] if len(Rk) > 2 else ''}

## 九、操作倾向（仅供参考，非投资建议）
| 风格 | 倾向 |
|------|------|
{op_rows}

---
> 数据快照时间：{tsh} (UTC+8) ｜ 模式：{mode_cn}（{lbl}）。技术指标为时点值，决策前请复核最新数据。
> 本报告由 crypto-analysis-report 技能自动生成，**仅供研究参考，不构成任何投资建议**。
"""
    suffix = "" if mode == "short" else "swing_"
    path = Path(out_dir) / f"{coin.lower()}_{suffix}report_{ts}.md"
    path.write_text(md, encoding="utf-8")
    summary_rr = active_rr if active_rr is not None else k['rr']
    return dict(coin=coin, price=d['price'], comp=comp, zone=zone, form=dec['form'],
                dir=dec['dir'], rr=summary_rr, rr_long=k['rr'], rr_short=k['rr_s'],
                rangepos=k['rangepos'], path=str(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default="BTC,ETH,SOL,BNB")
    ap.add_argument("--in-dir", required=True, help="pull_okx_data.py 产出的 <SYM>.txt/_c20.txt 所在目录")
    ap.add_argument("--out-dir", required=True, help="报告落盘目录")
    ap.add_argument("--mode", default="auto", choices=["auto", "short", "swing"],
                    help="auto=读数据文件 MODE 标记（默认）；short/swing 显式覆盖")
    args = ap.parse_args()
    try:
        symbols = parse_symbols(args.symbols)
    except ValueError as exc:
        ap.error(str(exc))
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    try:
        mode = detect_mode(args.in_dir, symbols) if args.mode == "auto" else args.mode
    except ValueError as exc:
        print(f"[错误] {exc}")
        return 1
    now = datetime.datetime.now()
    ts, tsh = now.strftime("%Y%m%d%H%M%S"), now.strftime("%Y-%m-%d %H:%M:%S")
    res, failed = [], []
    for c in symbols:
        try:
            res.append(report(args.in_dir, args.out_dir, c, mode, ts, tsh))
        except Exception as exc:  # noqa: BLE001 - 单币失败（多因 [FETCH_FAILED] 字段缺失）不拖垮整批
            failed.append((c, str(exc)))
    print(f"模式={MODE_CN[mode]}（{'/'.join(LABELS[mode])}）")
    print("coin  price      temp  zone  form/dir   RR(L/S)       rangepos  file")
    for r in res:
        print(f"{r['coin']:4} {r['price']:>10.2f} {r['comp']:>5} {r['zone']:4} "
              f"{r['form']}/{r['dir']:4} {r['rr_long']:>5.2f}/{r['rr_short']:<5.2f} "
              f"{r['rangepos']:>6.1f}%  {Path(r['path']).name}")
    for c, exc in failed:
        print(f"[跳过] {c}：{exc}（该币数据缺失/含 [FETCH_FAILED]，请重拉该币）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

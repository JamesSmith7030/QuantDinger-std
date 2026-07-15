# -*- coding: utf-8 -*-
"""crypto-analysis-report 报告渲染器：解析 pull_okx_data.py 产出的 <SYM>.txt / <SYM>_c20.txt，
按三支柱框架评分并渲染中文 Markdown 深度分析报告，落盘到 --out-dir。

双模式（K 线周期集不同，其余评分/ATR/枢轴口径一致）：
    short（默认·短线，1-3天）: 多周期 RSI/MACD = 15m/1H/4H/1D
    swing（波段，数天-数周）  : 多周期 RSI/MACD = 1H/4H/1D/1W（删 15m 噪声、加周线定趋势）

模式由数据文件里的 `=== MODE ===` 标记决定（pull_okx_data.py 写入）；--mode 显式指定可覆盖。
日线锚定指标（BB/KDJ/EMA/ATR/MA/枢轴/20日区间）两模式相同——先最小改动，仅切换多周期动能读数与标注。

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
    """从第一个能读到的 <SYM>.txt 的 MODE 标记推断模式，缺省 short。"""
    for c in symbols:
        p = Path(in_dir) / f"{c}.txt"
        if p.exists():
            sec = parse_sections(p.read_text(encoding="utf-8"))
            mode = (sec.get("MODE", "") or "").strip().lower()
            if mode in ("short", "swing"):
                return mode
    return "short"


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
    if overheated:
        form, dirn, note = 'B', 'HOLD', f"过热（综合{comp}）+区间位置{k['rangepos']:.0f}%，观望或减仓，不追高"
    elif below_ma and st_dn:
        # 偏空共振（跌破短均线 + 双周期 MACD 同负）→ 做空镜像；超卖/赔率差不追空（对称于做多侧）
        if oversold or poor_rr_s:
            form, dirn = 'B', 'HOLD'
            note = f"破位偏空但{'深度超卖' if oversold else f'追空 RR 仅 1:{rr_s:.2f}'}，不追空，反弹承压再评估"
        else:
            form, dirn = 'A', '做空'
            note = f"{mode_cn}偏空共振（跌破 MA5/10 + {ta}/{tb} MACD 同负），反弹承压进场，收复 MA10 减/离场"
    elif poor_rr or (overbought and rr < 1.2):
        form, dirn, note = 'B', 'HOLD', f"追多 RR 仅 1:{rr:.2f}{'、超买' if overbought else ''}，观望等回踩"
    elif above_ma and st_up:
        form, dirn = 'A', '做多'
        note = (f"逆大周期反弹，控仓、破 MA10 减" if below200 else f"{mode_cn}偏多，破 MA10 减")
    else:
        form, dirn, note = 'B', 'HOLD', "结构未共振，观望"
    if comp < 20:
        sig = "🟢 BUY 买入（抄底低估）"
    elif comp < 40:
        sig = "🟢 BUY 买入（复苏偏多）"
    elif comp < 60:
        sig = f"🟡 NEUTRAL 中性（{mode_cn + '偏多' if form == 'A' else '观望'}）"
    elif comp < 80:
        sig = "🟡 NEUTRAL 中性（过热减仓）"
    else:
        sig = "🔴 SELL 卖出（狂热对冲）"
    rr_eff = rr_s if dirn == '做空' else rr  # 有效 RR 随方向取镜像值
    conf = "中 ~55%" if (form == 'A' and rr_eff == rr_eff and rr_eff >= 1.5) else ("中 ~50%" if form == 'A' else "低-中 ~45%")
    tf = f"{sum(1 for r in d['rsi'] if r > 50) * 25}%"
    mps = f"{(sum(1 for r in d['rsi'] if r > 50) / 4 - 0.5) * 10:+.0f}"
    cons = "BUY" if sum(1 for r in d['rsi'] if r > 50) >= 3 else "MIXED"
    if form == 'A' and dirn == '做空':
        entry = f"反弹 Pivot {k['P']:.0f} / MA5 {ma5:.0f} 承压不破再进场"
    elif form == 'A':
        entry = f"现价回踩 Pivot {k['P']:.0f} / MA5 {ma5:.0f} 附近"
    else:
        entry = f"不追高；回踩 MA5 {ma5:.0f} / EMA50 {d['ema50']:.0f} 且不破再评估"
    return dict(form=form, dir=dirn, note=note, sig=sig, conf=conf, tf=tf, mps=mps, cons=cons,
                entry=entry, overbought=overbought, below200=below200, st_up=st_up,
                above_ma=above_ma, overheated=overheated)


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
    if dec['form'] == 'A':
        R.append(f"做多 RR 1:{k['rr']:.2f}，支撑 {fmt(k['support'])} 结构扎实，资金费率 {d['funding']:+.4f}% 无过热杠杆")
    else:
        R.append(f"量价支柱 {vp}，动能仍在，但当前位置追多性价比不足（见风险）")
    Rk = []
    if dec['below200']:
        Rk.append(f"价格处 EMA50({fmt(d['ema50'], 1)})、EMA200({fmt(d['ema200'], 1)}) 下方，大周期空头排列，反弹或遇均线压制")
    if dec['overheated']:
        Rk.append(f"综合 {comp} 落入过热减仓区，20日区间位置 {k['rangepos']:.1f}% 贴近顶部，回调概率升高")
    elif dec['overbought']:
        Rk.append(f"4H RSI {d['rsi'][i4]} / KDJ J {d['kdj'][2]} 偏超买，短线过热，做多 RR 仅 1:{k['rr']:.2f}")
    else:
        Rk.append(f"1D RSI {d['rsi'][i1]}、MA20({fmt(ma20, 1)}) 上方承压，动能未确认强势")
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

    if dec['form'] == 'A':
        is_short = dec['dir'] == '做空'
        confirm_txt = ("偏空确认（跌破短均线+双周期 MACD 同负）" if is_short
                       else "偏多确认（站上短均线+多周期 MACD 转正）")
        entry_note = "反弹承压不破关键位" if is_short else "回踩确认不破关键位"
        sl_v, tp_v, rr_v = (k['sl_s'], k['tp_s'], k['rr_s']) if is_short else (k['sl'], k['tp'], k['rr'])
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
                     f"价 vs EMA50(${fmt(d['ema50'], 1)})/EMA200(${fmt(d['ema200'], 1)}) 均在下方 → **历史低估区**。")
    else:
        macro_txt = (f"非 BTC 无 AHR999，均线估值：价 vs EMA50(${fmt(d['ema50'], 1)})/EMA200(${fmt(d['ema200'], 1)})、"
                     f"20日区间位置 **{k['rangepos']:.1f}%**。")
    r3 = "3. " + R[2] if len(R) > 2 else ""

    # §九 操作倾向：当前模式行放首位并带 dec.note
    other_mode = 'swing' if mode == 'short' else 'short'
    op_rows = (f"| {HOLD_CN[mode]} | {dec['note']} |\n"
               f"| {HOLD_CN[other_mode]} | {'逆 EMA200 大周期，反弹为主，谨慎轻仓' if dec['below200'] else '顺势持有，回踩加仓'} |\n"
               f"| 合约 | 高波动，控制杠杆，严格止损 ${fmt(k['sl'])} |")

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
| **综合评分** | **{comp}/100**（{zone}） |
| **置信度** | {dec['conf']} |
| **分析模式** | {mode_cn}（多周期 {lbl}） |
| **市场阶段** | {'EMA200 下方大周期弱势中的反弹' if dec['below200'] else '均线上方'}；{'过热' if dec['overheated'] else '超买' if dec['overbought'] else '动能修复'} |
| **当前价格** | **${fmt(d['price'])}**（24h {d['chg']:+.2f}%） |

**一句话**：宏观 {macro} + 量价 {vp} + 衍生 {deriv} → 综合 {comp}（{zone}）。{R[0]}

### 多周期客观共识
| 项目 | 值 |
|------|-----|
| 共识方向 | {dec['cons']} |
| 周期一致度 | {dec['tf']}（RSI>50 周期占比，{lbl}） |
| 多周期评分 | {dec['mps']}（-5 ~ +5） |

---

## 下一步（行动清单）
1. **🎯 盯关键位**：阻力 ${fmt(k['resistance'])}（R1 ${fmt(k['R1'])}）；支撑 ${fmt(k['support'])}（S1 ${fmt(k['S1'])}）
2. **📥 / ⏳ 操作倾向**：{dec['note']}
3. **🛡️ 持仓处理**：止损参考 ${fmt(k['sl'])}；过热/破位减仓
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
### 综合评分
`{comp_formula}` → {zone}

## 五、技术指标 PRO
| 指标 | 值 | 状态 |
|------|-----|------|
| RSI(14) 1D | {rsi1d} | {"超买" if rsi1d >= 70 else "超卖" if rsi1d <= 30 else "中性"} |
| MACD(12,26,9) 1D | 柱 {hist1d:+} | {"看涨修复" if hist1d > 0 else "看跌"} |
| 均线趋势 | {"多头(站上MA5/10)" if d['price'] > ma5 and d['price'] > ma10 else "空头/纠缠"} | {"EMA50/200 下方" if dec['below200'] else "EMA 上方"} |
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
    return dict(coin=coin, price=d['price'], comp=comp, zone=zone, form=dec['form'],
                dir=dec['dir'], rr=k['rr'], rangepos=k['rangepos'], path=str(path))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbols", default="BTC,ETH,SOL,BNB")
    ap.add_argument("--in-dir", required=True, help="pull_okx_data.py 产出的 <SYM>.txt/_c20.txt 所在目录")
    ap.add_argument("--out-dir", required=True, help="报告落盘目录")
    ap.add_argument("--mode", default="auto", choices=["auto", "short", "swing"],
                    help="auto=读数据文件 MODE 标记（默认）；short/swing 显式覆盖")
    args = ap.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)
    mode = detect_mode(args.in_dir, symbols) if args.mode == "auto" else args.mode
    now = datetime.datetime.now()
    ts, tsh = now.strftime("%Y%m%d%H%M%S"), now.strftime("%Y-%m-%d %H:%M:%S")
    res, failed = [], []
    for c in symbols:
        try:
            res.append(report(args.in_dir, args.out_dir, c, mode, ts, tsh))
        except Exception as exc:  # noqa: BLE001 - 单币失败（多因 [FETCH_FAILED] 字段缺失）不拖垮整批
            failed.append((c, str(exc)))
    print(f"模式={MODE_CN[mode]}（{'/'.join(LABELS[mode])}）")
    print("coin  price      comp  zone  form/dir   RR    rangepos  file")
    for r in res:
        print(f"{r['coin']:4} {r['price']:>10.2f} {r['comp']:>5} {r['zone']:4} "
              f"{r['form']}/{r['dir']:4} {r['rr']:>6.2f} {r['rangepos']:>6.1f}%  {Path(r['path']).name}")
    for c, exc in failed:
        print(f"[跳过] {c}：{exc}（该币数据缺失/含 [FETCH_FAILED]，请重拉该币）")
    if failed and not res:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

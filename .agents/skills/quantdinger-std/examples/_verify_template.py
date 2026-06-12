# 本地自检脚本：模拟 QuantDinger 指标沙盒，验证 examples/ 下模板是否满足执行契约。
# 用法：python _verify_template.py [模板文件名]（默认 ema_cross_four_way.py）
# 仅做离线结构校验，不等价于平台 validate 接口；提交前仍建议走 /indicators/validate。
import sys
from pathlib import Path

import numpy as np
import pandas as pd

target = Path(__file__).parent / (sys.argv[1] if len(sys.argv) > 1 else "ema_cross_four_way.py")
code = target.read_text(encoding="utf-8")

# 构造 200 根伪 K 线（带趋势 + 噪声，保证能产生交叉信号）
n = 200
rng = np.random.default_rng(42)
close = 100 + np.cumsum(rng.normal(0, 1, n)) + np.sin(np.arange(n) / 10) * 5
df = pd.DataFrame({
    "time": pd.date_range("2024-01-01", periods=n, freq="D"),
    "open": close + rng.normal(0, 0.3, n),
    "high": close + abs(rng.normal(0, 0.8, n)),
    "low": close - abs(rng.normal(0, 0.8, n)),
    "close": close,
    "volume": rng.integers(1000, 9999, n).astype(float),
})

env = {"df": df, "pd": pd, "np": np, "params": {}}
exec(compile(code, str(target), "exec"), env)

df_out, output = env["df"], env["output"]
errors = []

for col in ("open_long", "close_long", "open_short", "close_short"):
    if col not in df_out.columns:
        errors.append(f"缺少执行列 {col}")
    elif df_out[col].dtype != bool:
        errors.append(f"{col} 不是 bool（实际 {df_out[col].dtype}）")
    elif len(df_out[col]) != n:
        errors.append(f"{col} 长度 {len(df_out[col])} != {n}")

if not isinstance(output, dict) or "name" not in output:
    errors.append("output 缺失或没有 name")
for plot in output.get("plots", []):
    if len(plot["data"]) != n:
        errors.append(f"plot '{plot['name']}' 长度 {len(plot['data'])} != {n}")
for sig in output.get("signals", []):
    if len(sig["data"]) != n:
        errors.append(f"signal '{sig.get('text')}' 长度 {len(sig['data'])} != {n}")

n_open = int(df_out["open_long"].sum() + df_out["open_short"].sum())
if n_open == 0:
    errors.append("200 根伪 K 线上没有产生任何开仓信号，检查信号逻辑")

if errors:
    print(f"FAIL {target.name}")
    for e in errors:
        print("  -", e)
    sys.exit(1)

print(f"PASS {target.name}: open_long={int(df_out['open_long'].sum())} "
      f"close_long={int(df_out['close_long'].sum())} "
      f"open_short={int(df_out['open_short'].sum())} "
      f"close_short={int(df_out['close_short'].sum())}, "
      f"plots={len(output.get('plots', []))}, signals={len(output.get('signals', []))}")

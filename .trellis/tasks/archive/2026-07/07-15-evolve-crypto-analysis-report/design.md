# Design: crypto-analysis-report v1.4.0

## Baseline

Build on committed `v1.3.2` (`c38a08a`). That commit arrived while planning was in
progress and is treated as user-owned baseline work. No v1.3.2 behavior is reverted;
the new short mirror path is completed and made internally consistent.

## Scope Boundary

The implementation boundary is the automated crypto path:

1. `pull_okx_data.py` validates symbols and produces short/swing raw snapshots.
2. `build_report.py` parses snapshots, calculates the unchanged score and levels,
   decides an executable direction, renders reports, and emits a batch summary.
3. `SKILL.md` and `usage-and-maintenance.md` describe the actual crypto workflow and
   standardized chat response.
4. One standard-library regression test module covers deterministic behavior.

Yahoo Finance and Bitget stock/stock-token automation remain a future task. The docs
will label that path as deferred/manual instead of claiming end-to-end automation.

## Semantic Model

### Market condition

`score(d)` remains numerically unchanged. Its fourth value is explicitly named and
rendered as `市场温度评分`; `zone_of()` remains the comparable market-temperature zone:
抄底、复苏、中性、过热、狂热.

The score answers "where is the market in its valuation/heat cycle?" It does not issue
an order direction.

### Executable signal

`decide()` remains the single owner of the execution result:

| Qualified setup | `综合信号` | `交易方向` |
|---|---|---|
| Long structure and RR gate pass | BUY | 做多 |
| Short structure and RR gate pass | SELL | 做空 |
| No qualified setup | NEUTRAL / HOLD | HOLD |

Low temperature never creates BUY by itself. High temperature never creates SELL by
itself. Overheated markets can remain HOLD when neither side passes its setup gates.

### Directional values

Add one small direction selector in `build_report.py` that returns the active stop,
target, and RR for `做多` or `做空`. Reuse it everywhere that currently selects these
values independently: guide, action list, reasons, contract row, and terminal summary.
This removes the v1.3.2 long-side leakage without a new framework.

For HOLD, `decide()` records the rejected candidate side when known. A rejected short
setup uses short-side RR and "不追空/反弹承压" wording; a rejected long setup uses
long-side RR and "不追高/等待回踩" wording. Structurally neutral HOLD shows both RR
values as references and does not imply an entry.

## Consensus Contract

Count RSI periods strictly above and below 50. Neutral values at exactly 50 count
toward neither side.

- at least 3 of 4 above 50: BUY consensus;
- at least 3 of 4 below 50: SELL consensus;
- otherwise: MIXED;
- agreement = dominant directional count / 4.

Thus four bearish periods are `SELL / 100%`, four bullish periods are `BUY / 100%`,
and a 2/2 split is `MIXED / 50%`.

## Input and Batch Reliability

Both CLIs validate the comma-separated base symbols before subprocess execution or
path construction. Accepted symbols are uppercase ASCII alphanumerics, 1-20 characters;
empty, path-like, whitespace-containing, and shell-metacharacter values fail fast.
`pull_okx_data.py` also validates non-negative retries/delays, positive timeout,
ordered delay bounds, and `candle-limit >= 22` before network work.

In auto mode, `build_report.py` inspects every available requested raw file. Invalid
MODE markers or mixed short/swing markers are fatal with a clear error. Missing symbol
files continue through per-symbol reporting so the complete failed-symbol list is shown.

Any requested symbol failure returns non-zero, even when other reports were generated.
Successful outputs are preserved; there is no rollback or deletion of useful reports.

## Report and Chat Output

The report summary separates these rows:

- `市场温度评分` and `市场温度分区`;
- `综合信号`;
- `交易方向` in the opening guide.

The terminal batch summary emits active direction plus both long/short RR references so
the chat layer cannot mistake long RR for a short setup.

The skill's final-response contract uses the user's preferred table: asset, price, 24h,
temperature score, zone, executable signal, long/short RR, 20-day range position, and
report link. It then explains market change (only when a prior snapshot exists), each
asset's HOLD/BUY/SELL reason, the portfolio-level meaning, and actual data-tier status.

## Compatibility

- Existing raw short/swing formats remain valid.
- Score calculations and thresholds remain unchanged, preserving numeric comparisons.
- Existing Markdown files remain untouched.
- Consumers parsing the old `综合评分` label must adapt to `市场温度评分`; this is an
  intentional semantic change and justifies version `1.4.0`.

## Testing

Use `unittest`, `tempfile`, and `unittest.mock`; add no dependency.

Deterministic tests cover bullish, bearish, HOLD, symmetric consensus, directional
RR/stop selection, rejected-side wording, symbol validation in both CLIs, mixed MODE
rejection, and partial batch failure status. A final smoke render uses an existing saved
short snapshot outside committed fixtures; swing compatibility is also exercised with
synthetic mode data if no saved swing snapshot exists.

## Risks and Rollback

- Risk: historical text parsers may depend on `综合评分`. Mitigation: version/changelog
  call out the rename and numeric value remains unchanged.
- Risk: stricter symbols reject previously tolerated malformed input. This is intended.
- Risk: v1.3.2 short behavior has little live history. Synthetic regression cases must
  exercise all text and level selections before release.
- Rollback is file-level revert of this task's changes; no data migration is required.


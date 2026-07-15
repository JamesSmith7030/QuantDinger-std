# Review and evolve crypto-analysis-report

## Goal

Review the skill against repeated real-world use, preserve the parts that are working,
and evolve the current baseline into a more internally consistent, testable, and
operationally reliable release. Reports must remain research-only and data-driven.

## Confirmed Facts

- The user requested review, summarization, learning, evolution, and concrete self-improvement after sustained use of `crypto-analysis-report@1.3.1`.
- While planning started, the repository baseline advanced independently to `v1.3.2`
  (`c38a08a`, 2026-07-15). This task must build on that commit and must not revert it.
- The current production path is the crypto short/swing flow implemented by
  `pull_okx_data.py` and `build_report.py`; recent five-asset runs completed with
  validated OKX fields but took about 195 seconds.
- A synthetic bearish case reproduces an internal contradiction: `综合信号=BUY`,
  `交易方向=做空`, `周期一致度=0%`, `共识=MIXED`, while the core reason still says
  `做多 RR`. This is behavior, not merely stale documentation.
- The bearish path added in v1.3.2 still has long-side leaks in summary RR, action-list
  stop loss, core reasons, HOLD follow-up wording, and contract stop references.
- Bearish multi-timeframe agreement is reported as `0% / MIXED`; consensus currently
  has no `SELL` state and agreement is calculated only as the bullish share.
- Multi-symbol rendering exits successfully when some symbols fail, provided at least
  one report succeeds. Automation can therefore mistake partial output for full success.
- Symbol input is not validated before it is interpolated into Windows `shell=True`
  commands and file paths.
- `usage-and-maintenance.md` is stale: it omits `build_report.py`, contradicts itself
  about datahub in the stock branch, and does not describe the v1.3.2 behavior.
- The user established a preferred chat summary containing price, score, zone, signal,
  RR, 20-day range position, report links, market-change interpretation, per-asset
  reasoning, and data-source status. The current skill only asks for paths plus one-line
  conclusions.

## Requirements

- Preserve OKX as the crypto source, short/swing mode behavior, independent per-symbol
  Markdown files, and the research-only disclaimer.
- Make the high-level signal, execution direction, opening guide, reasons, risk/reward,
  stop references, and chat summary semantically consistent for BUY/HOLD/SELL cases.
- Make multi-timeframe consensus symmetric for bullish and bearish agreement.
- Validate symbol inputs in both command-line scripts before command execution or path use.
- Fail automation visibly on partial multi-symbol rendering while retaining successfully
  generated reports and listing failed symbols.
- Reject or clearly report mixed/invalid mode inputs rather than silently applying the
  first symbol's mode to every symbol.
- Standardize the expanded chat response requested by the user without adding a separate
  reporting framework.
- Update version metadata, changelog, and maintenance documentation to match actual files
  and behavior.
- Add the smallest deterministic regression suite that covers direction consistency,
  bearish consensus, mirror RR/stop selection, invalid symbols, mixed/partial input, and
  short/swing compatibility without requiring live network access.
- Use saved raw snapshots only for smoke validation; do not fabricate market values.

## Acceptance Criteria

- [ ] A bearish synthetic case cannot produce BUY plus `做空`, bullish-only reasons, or a long-side stop/RR.
- [ ] Four bearish RSI periods report `SELL` with 100% agreement; four bullish periods report `BUY` with 100% agreement; a 2/2 split reports `MIXED` with 50% agreement.
- [ ] BUY, SELL, and HOLD reports each use the correct directional entry, stop, target, RR, reasons, and follow-up wording.
- [ ] Invalid/path-like symbols are rejected before any subprocess or file access.
- [ ] Any failed requested symbol makes `build_report.py` return non-zero while preserving and listing successful outputs.
- [ ] Mixed short/swing raw inputs are rejected with a clear message.
- [ ] Existing validated short and swing snapshots still render complete nine-section reports with disclaimers.
- [ ] Final chat output follows the user's expanded comparison-and-interpretation format.
- [ ] `SKILL.md` and `usage-and-maintenance.md` agree on version, file layout, dependencies, scratch/raw placement, and test commands.
- [ ] The final review summarizes retained strengths, defects fixed, lessons learned, remaining limits, and the next evidence threshold for further complexity.

## Constraints

- Do not place raw data or test artifacts in `analysis_reports/`; only final report Markdown belongs there.
- Do not add third-party dependencies or a new abstraction layer.
- Do not change scoring thresholds or trading semantics without explicit user approval.
- Do not modify unrelated QuantDinger strategy, backend, frontend, or trading code.

## Decisions

- The user approved separating market condition from execution direction:
  - the existing 0-100 score remains comparable but is explicitly presented as
    `市场温度评分` plus its valuation/heat zone;
  - `综合信号` represents the executable result only: confirmed long = BUY, confirmed
    short = SELL, and no qualified setup = HOLD/NEUTRAL;
  - low valuation does not automatically mean BUY, and overheating does not
    automatically mean SELL;
  - the opening guide must agree with the executable signal.
- This release covers only the actively used crypto short/swing automation path.
- Stock and stock-token automated reporting (Yahoo Finance, Bitget, trading sessions,
  and the separate stock scoring model) is deferred to a dedicated future iteration.
- Because report semantics change while the score values remain comparable, the target
  release is `v1.4.0` rather than another patch release.

## Out of Scope

- Implementing Yahoo Finance or Bitget stock/stock-token fetchers and renderers.
- Recalibrating score thresholds or optimizing them against trading returns.
- Increasing live OKX request concurrency solely to reduce the current runtime; optimize
  only after a repeatable benchmark shows a safe limit-rate trade-off.
- Deleting historical raw/report artifacts from the user's workspace.

## Follow-up TODO

- [ ] Create a separate Trellis iteration for automated stock and stock-token reports:
  Yahoo Finance real-stock data, Bitget stock-token data, US trading-session handling,
  premium/discount calculation, the separate stock scoring model, deterministic tests,
  and an end-to-end report workflow. Start only after crypto `v1.4.0` is complete; do not
  mix this scope into the current release.

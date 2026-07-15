# Implementation Plan: crypto-analysis-report v1.4.0

## 1. Lock Current Failures (RED)

- [x] Add one `unittest` module under the skill that imports both reference scripts.
- [x] Reproduce the confirmed bearish contradiction: BUY + 做空, 0%/MIXED consensus,
      long RR reason, and wrong long stop/RR selection.
- [x] Add bullish, overheated HOLD, 4-up, 4-down, and 2/2 consensus cases.
- [x] Add invalid-symbol cases for both CLIs, mixed MODE input, and partial batch failure.
- [x] Run the focused suite and record the expected pre-fix failures.

## 2. Correct the Execution Contract (GREEN)

- [x] Keep `score()` and `zone_of()` formulas unchanged; rename rendered semantics to
      market temperature.
- [x] Make `decide()` derive BUY/SELL/HOLD only from the qualified execution result.
- [x] Make consensus direction and agreement symmetric.
- [x] Add one reused directional-level selector and route guide, action list, reasons,
      contract row, and terminal summary through it.
- [x] Preserve the rejected candidate side for HOLD and render matching long/short
      follow-up language.
- [x] Remove uncomputed advice for the other analysis mode; require a separate mode
      report instead of claiming "回踩加仓" from unavailable data.

## 3. Harden CLI Boundaries

- [x] Validate symbols before subprocess or path use in both scripts.
- [x] Validate pull retry/delay/timeout/candle-limit arguments before network calls.
- [x] Reject invalid and mixed raw MODE markers clearly.
- [x] Return non-zero for any requested-symbol render failure while preserving successful
      outputs and printing every failure.

## 4. Align Documentation and Version

- [x] Bump metadata/changelog to `v1.4.0` and summarize the semantic split and fixes.
- [x] Update the report template and workflow examples, including temporary raw storage.
- [x] Add the expanded chat-response contract with long/short RR clarity.
- [x] Update maintenance file layout, test command, v1.3.2/v1.4.0 behavior, and datahub
      health-check wording.
- [x] Mark stock/stock-token automation as deferred to a dedicated future iteration.

## 5. Verification and Review

- [x] Run `python -m unittest discover -s .agents/skills/crypto-analysis-report/tests -p "test_*.py" -v`.
- [x] Run syntax compilation for the two production scripts and test module.
- [x] Render the latest saved short raw snapshot to a temporary output directory; verify
      all nine sections, disclaimer, temperature rows, execution signal, dual RR, and
      expected unchanged scores.
- [x] Render or synthesize a swing case and verify 1D/1W trend plus weekly ATR behavior.
- [x] Run invalid-symbol, mixed-mode, and partial-failure CLI checks and confirm non-zero
      exits with clear messages.
- [x] Run `git diff --check`, inspect the complete diff, and perform a focused code review.
- [x] Update Trellis project knowledge only if a durable cross-task rule was learned;
      avoid duplicating the skill's own maintenance documentation.

## Rollback Points

- After Step 2: revert only `build_report.py` if report semantics fail smoke validation.
- After Step 3: revert only the CLI validation changes if a valid OKX symbol is rejected.
- Documentation/version changes land only after behavior and tests pass.

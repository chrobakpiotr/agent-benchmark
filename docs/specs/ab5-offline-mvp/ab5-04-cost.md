# AB5-04 - cost and statistics

Status: draft.

## Pricing snapshot (`agent-benchmark/pricing/v1`)

`snapshot_utc`, `source`, `basis` (`api-price-list` | `subscription-estimate`) and per model id: `currency`
(ISO 4217), `unit` (`per_token` | `per_thousand_tokens` | `per_million_tokens`), `input`, `output`, `cache_read`
(explicit null if unknown), `input_includes_cache_read`. Never fetched automatically. `report --pricing FILE`
copies it into the run as `pricing.json` once; a different snapshot for the same run is refused; its digest is
listed in the report inputs.

## Rules

- Trial cost = sum over all attempts (retries, reviewer calls) of priced usage. Model is chosen by
  `model_resolved`, falling back to `model_requested` (recorded as `priced_by`).
- `input_includes_cache_read=true`: cache tokens are carved out of input, not added; cache > input = unpriceable.
- Missing usage, missing rate for a non-zero category or missing model -> not fully priced. Report shows
  `known_subtotal` with coverage `full/partial/unknown`; `total` only when every started trial is fully priced.
- Cost per PASS = total of all started trials / PASS. 0 PASS -> `null` with "no successful solution". Never 0.
- Costs are always labelled estimates (basis). No currency conversion: different currencies ->
  `cost_comparable: false`. A subscription CLI must use basis `subscription-estimate`, never API rates silently.
- Operational success denominator = all started trials. Predeclared `manifest.exclusions`
  (`timeout/cancel/error/unknown` + reason) only feed `success_after_exclusions` with its own denominator.
- First-attempt PASS (1 attempt) and after-retry PASS (>1 attempts) reported separately.

## AC -> evidence (`tests/test_cost.py`, values computed by hand in comments)

| AC | Test |
|---|---|
| zero PASS | `test_retries_cache_and_zero_pass` |
| partial usage / missing price / missing model | `test_fixture_run_partial_usage`, `test_missing_rate_or_usage_is_not_zero`, `test_missing_model_rate` |
| currency / unit change | `test_retries_cache_and_zero_pass` (USD vs EUR), `test_same_currency_is_comparable`, `test_unit_change_gives_same_amount` |
| cache overlap | `test_cache_included_in_input_is_not_double_counted`, `test_contradictory_cache_overlap` |
| retries counted | `test_retries_cache_and_zero_pass` (2 attempts per trial) |
| denominators and exclusions in report | `test_exclusions_have_their_own_denominator` |
| snapshot bound, not refetched | `test_pricing_is_bound_to_the_run` |

## Open / not done

- Wall time to result currently covers the execution call only; queue/setup and grading time are not measured.
- No invoice/billed-amount import (only estimates).

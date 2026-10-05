"""Pricing snapshots and token cost. A snapshot is a dated, sourced file; prices are never fetched automatically.

Cost computed here is always an estimate from rates x recorded usage, labelled with the snapshot basis.
Unknown stays unknown: missing usage, rate or model never becomes 0.
"""
from decimal import Decimal

from .schema import _enum, _fail, _keys, _str, _version

PRICING_VERSION = "agent-benchmark/pricing/v2"
BASES = ("api-price-list", "subscription-estimate")
UNITS = {"per_token": Decimal(1), "per_thousand_tokens": Decimal(1000), "per_million_tokens": Decimal(1000000)}


def _rate(v, path, nullable=False):
    if v is None and nullable:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        _fail(path, "must be a non-negative number" + (" or null" if nullable else ""))
    try:
        d = Decimal(str(v))
    except ArithmeticError:
        _fail(path, "must be a non-negative number")
    if not d.is_finite() or d < 0:
        _fail(path, "must be a non-negative number")
    return d


def validate_pricing(p):
    _version(p, "pricing", PRICING_VERSION)
    _keys(p, "pricing", ("schema_version", "snapshot_utc", "source", "basis", "models"))
    _str(p["snapshot_utc"], "pricing.snapshot_utc")
    _str(p["source"], "pricing.source")
    _enum(p["basis"], "pricing.basis", BASES)
    if not isinstance(p["models"], dict) or not p["models"]:
        _fail("pricing.models", "must be a non-empty object keyed by model id")
    for name, m in p["models"].items():
        path = f"pricing.models[{name!r}]"
        _keys(m, path, ("currency", "unit", "input", "output"), ("cache_read", "cache_write"))
        if not isinstance(m["currency"], str) or len(m["currency"]) != 3 or not m["currency"].isupper():
            _fail(f"{path}.currency", "must be an ISO 4217 code like 'USD'")
        _enum(m["unit"], f"{path}.unit", tuple(UNITS))
        for f in ("input", "output"):
            _rate(m[f], f"{path}.{f}")
        _rate(m["cache_read"], f"{path}.cache_read", nullable=True)
        _rate(m["cache_write"], f"{path}.cache_write", nullable=True)
    return p


def price_scope(units, cache_semantics, model):
    """Return (known_amount, fully_priced) for one attempt's usage units.

    Cache semantics come from the usage event (contract v1):
    - separate: every unit is priced at its own rate;
    - included_in_input: cache tokens are carved out of input, not added (cache > input is unpriceable);
    - unknown: with non-zero or unknown cache tokens, input and cache cannot be split, so only output is priced.
    known_amount is a lower bound and None when nothing could be priced.
    """
    div = UNITS[model["unit"]]
    inp, out = units["input_tokens"], units["output_tokens"]
    cr, cw = units["cache_read_tokens"], units["cache_write_tokens"]
    full = True
    if cache_semantics == "included_in_input":
        if None in (inp, cr, cw):
            inp, full = None, False
        elif cr + cw > inp:
            return None, False
        else:
            inp -= cr + cw
    elif cache_semantics == "unknown" and not (cr == 0 and cw == 0):
        inp = cr = cw = None
        full = False
    known = []
    for tokens, rate in ((inp, model["input"]), (out, model["output"]), (cr, model["cache_read"]),
                         (cw, model["cache_write"])):
        rate = _rate(rate, "rate", nullable=True)
        if tokens is None or (rate is None and tokens > 0):
            full = False
        elif rate is not None:
            known.append(Decimal(tokens) * rate / div)
    return (sum(known, Decimal(0)) if known else None), full


def price_trial(row, model):
    """Sum over all attempts (retries included). Fully priced only with complete usage and every scope priced."""
    priced = [price_scope(s["units"], s["cache_semantics"], model) for s in row["usage_scopes"]]
    known = [a for a, _ in priced if a is not None]
    full = bool(priced) and all(f for _, f in priced) and row["measurement_quality"] == "complete"
    return (sum(known, Decimal(0)) if known else None), full


def fmt(d):
    return None if d is None else format(d.normalize(), "f")

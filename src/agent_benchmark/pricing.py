"""Pricing snapshots and token cost. A snapshot is a dated, sourced file; prices are never fetched automatically.

Cost computed here is always an estimate from rates x recorded usage, labelled with the snapshot basis.
Unknown stays unknown: missing usage, rate or model never becomes 0.
"""
from decimal import Decimal

from .schema import _enum, _fail, _keys, _str, _version

PRICING_VERSION = "agent-benchmark/pricing/v1"
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
        _keys(m, path, ("currency", "unit", "input", "output", "input_includes_cache_read"), ("cache_read",))
        if not isinstance(m["currency"], str) or len(m["currency"]) != 3 or not m["currency"].isupper():
            _fail(f"{path}.currency", "must be an ISO 4217 code like 'USD'")
        _enum(m["unit"], f"{path}.unit", tuple(UNITS))
        for f in ("input", "output"):
            _rate(m[f], f"{path}.{f}")
        _rate(m["cache_read"], f"{path}.cache_read", nullable=True)
        if not isinstance(m["input_includes_cache_read"], bool):
            _fail(f"{path}.input_includes_cache_read", "must be true or false")
    return p


def price_usage(usage, model):
    """Return (known_amount, fully_priced) for one trial's usage under one model rate entry.

    known_amount is None when nothing could be priced. fully_priced requires complete usage and a rate for
    every non-zero category. With input_includes_cache_read the cache tokens are carved out of input, not added.
    """
    if usage is None:
        return None, False
    div = UNITS[model["unit"]]
    rate = {"input": _rate(model["input"], "r"), "output": _rate(model["output"], "r"),
            "cache_read": _rate(model["cache_read"], "r", nullable=True)}
    inp, out, cache = usage["input_tokens"], usage["output_tokens"], usage["cache_read_tokens"]
    if model["input_includes_cache_read"]:
        if inp is not None and cache is not None and cache > inp:
            return None, False  # contradictory usage: cannot carve cache out of input
        inp = None if inp is None or cache is None else inp - cache
    parts = [(inp, rate["input"]), (out, rate["output"]), (cache, rate["cache_read"])]
    known, full = [], True
    for tokens, r in parts:
        if tokens is None or (r is None and tokens > 0):
            full = False
        elif r is not None:
            known.append(Decimal(tokens) * r / div)
    return (sum(known, Decimal(0)) if known else None), full


def fmt(d):
    return None if d is None else format(d.normalize(), "f")

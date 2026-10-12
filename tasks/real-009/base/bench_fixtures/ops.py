"""Task-owned helper for agent-benchmark's hidden cases: Python comparison operators on a parsed Version."""
import operator

from src.semver import Version


def _op(name, version, other):
    return getattr(operator, name)(Version.parse(version), other)


def eq(version, other):
    return _op("eq", version, other)


def ne(version, other):
    return _op("ne", version, other)


def lt(version, other):
    return _op("lt", version, other)


def gt(version, other):
    return _op("gt", version, other)

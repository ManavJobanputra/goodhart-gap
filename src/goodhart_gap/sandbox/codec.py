"""Safe tagged-JSON codec for values crossing the sandbox boundary.

Candidate code returns arbitrary Python values. We must move them from the child
process to the parent without pickle or eval (INV-3). This codec encodes values
into JSON-compatible structures with explicit type tags so that tuples, sets,
bytes, NaN/inf and int-keyed dicts survive the round trip.

Tags:
    {"__t__": "tuple",  "items": [...]}
    {"__t__": "list",   "items": [...]}
    {"__t__": "set",    "items": [...]}          (frozenset decodes to set)
    {"__t__": "dict",   "items": [[k, v], ...]}  (preserves key types)
    {"__t__": "bytes",  "b64": "..."}
    {"__t__": "float",  "v": "nan" | "inf" | "-inf"}
    {"__t__": "int",    "v": "<arbitrary precision int as string>"}

Everything else (None, bool, int in range, finite float, str) is emitted as a
plain JSON value. Decoding rejects unknown tags.
"""

from __future__ import annotations

import base64
import math
from typing import Any

_MAX_DEPTH = 200


class CodecError(ValueError):
    """Raised when a value cannot be encoded/decoded safely."""


def _encode(obj: Any, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        raise CodecError("nesting too deep")
    if obj is None or isinstance(obj, bool):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        # JSON ints are fine within float range; tag huge ints to avoid loss.
        if -(2**53) < obj < 2**53:
            return obj
        return {"__t__": "int", "v": str(obj)}
    if isinstance(obj, float):
        if math.isnan(obj):
            return {"__t__": "float", "v": "nan"}
        if math.isinf(obj):
            return {"__t__": "float", "v": "inf" if obj > 0 else "-inf"}
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return {"__t__": "bytes", "b64": base64.b64encode(bytes(obj)).decode("ascii")}
    if isinstance(obj, complex):
        return {"__t__": "complex", "re": obj.real, "im": obj.imag}
    if isinstance(obj, tuple):
        return {"__t__": "tuple", "items": [_encode(x, depth + 1) for x in obj]}
    if isinstance(obj, list):
        return {"__t__": "list", "items": [_encode(x, depth + 1) for x in obj]}
    if isinstance(obj, (set, frozenset)):
        items = [_encode(x, depth + 1) for x in obj]
        items.sort(key=lambda v: repr(v))
        return {"__t__": "set", "items": items}
    if isinstance(obj, dict):
        pairs = [[_encode(k, depth + 1), _encode(v, depth + 1)] for k, v in obj.items()]
        return {"__t__": "dict", "items": pairs}
    raise CodecError(f"cannot encode value of type {type(obj).__name__}")


def encode(obj: Any) -> Any:
    """Encode a Python value into a JSON-compatible tagged structure."""
    return _encode(obj, 0)


def _decode(obj: Any, depth: int) -> Any:
    if depth > _MAX_DEPTH:
        raise CodecError("nesting too deep")
    if isinstance(obj, list):
        # A bare JSON list should not occur (we always tag), but be lenient.
        return [_decode(x, depth + 1) for x in obj]
    if not isinstance(obj, dict):
        return obj
    tag = obj.get("__t__")
    if tag is None:
        # Plain dict without tag: treat as a plain mapping of str->value.
        return {k: _decode(v, depth + 1) for k, v in obj.items()}
    if tag == "tuple":
        return tuple(_decode(x, depth + 1) for x in obj["items"])
    if tag == "list":
        return [_decode(x, depth + 1) for x in obj["items"]]
    if tag == "set":
        return {_decode(x, depth + 1) for x in obj["items"]}
    if tag == "dict":
        return {_decode(k, depth + 1): _decode(v, depth + 1) for k, v in obj["items"]}
    if tag == "bytes":
        return base64.b64decode(obj["b64"].encode("ascii"))
    if tag == "complex":
        return complex(obj["re"], obj["im"])
    if tag == "float":
        v = obj["v"]
        if v == "nan":
            return math.nan
        if v == "inf":
            return math.inf
        if v == "-inf":
            return -math.inf
        raise CodecError(f"bad float tag {v!r}")
    if tag == "int":
        return int(obj["v"])
    raise CodecError(f"unknown tag {tag!r}")


def decode(obj: Any) -> Any:
    """Decode a tagged structure back into a Python value."""
    return _decode(obj, 0)

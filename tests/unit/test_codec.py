"""Tests for the safe tagged-JSON codec (INV-3)."""
from __future__ import annotations

import math

import pytest

from goodhart_gap.sandbox.codec import CodecError, decode, encode


def roundtrip(v):
    return decode(encode(v))


def test_roundtrip_scalars() -> None:
    for v in [None, True, False, 0, 1, -1, 2, 3.5, "hello", ""]:
        assert roundtrip(v) == v


def test_roundtrip_tuple_vs_list() -> None:
    t = roundtrip((1, 2, 3))
    assert isinstance(t, tuple) and t == (1, 2, 3)
    lst = roundtrip([1, 2, 3])
    assert isinstance(lst, list) and lst == [1, 2, 3]
    assert type(t) is not type(lst)


def test_roundtrip_set() -> None:
    s = roundtrip({1, 2, 3})
    assert isinstance(s, set) and s == {1, 2, 3}


def test_roundtrip_bytes() -> None:
    assert roundtrip(b"\x00\xffabc") == b"\x00\xffabc"


def test_roundtrip_nan_inf() -> None:
    assert math.isnan(roundtrip(math.nan))
    assert roundtrip(math.inf) == math.inf
    assert roundtrip(-math.inf) == -math.inf


def test_roundtrip_int_keyed_dict() -> None:
    d = {1: "a", 2: "b"}
    out = roundtrip(d)
    assert out == d
    assert set(out.keys()) == {1, 2}


def test_roundtrip_nested() -> None:
    v = {"a": [1, (2, 3), {4, 5}], "b": {"c": b"x"}, "d": math.nan}
    out = roundtrip(v)
    assert out["a"][0] == 1
    assert out["a"][1] == (2, 3)
    assert out["a"][2] == {4, 5}
    assert out["b"]["c"] == b"x"
    assert math.isnan(out["d"])


def test_roundtrip_big_int() -> None:
    big = 2**80
    assert roundtrip(big) == big


def test_unknown_tag_rejected() -> None:
    with pytest.raises(CodecError):
        decode({"__t__": "evil", "v": 1})


def test_unsupported_type_rejected() -> None:
    class Foo:
        pass

    with pytest.raises(CodecError):
        encode(Foo())

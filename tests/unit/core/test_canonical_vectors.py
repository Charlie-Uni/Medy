"""Known-answer vectors for canonical_json / canonical_hash / operation_key (M0-06 cross-platform evidence).

The expected strings and digests were computed once (CPython 3.11.16, macOS arm64, 2026-09-17) and are
fixed here. Any other interpreter build, operating system or hash seed that runs this suite proves
byte-identical output; a mismatch means the canonical form changed, which would silently break
idempotency keys, params_hash values and retrieval_version.
"""

import os
import subprocess
import sys
import unicodedata

import pytest

from medops.core.canonical import canonical_hash, canonical_json, operation_key

VECTORS = [
    ("empty_object", {}, "{}", "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"),
    ("empty_array", [], "[]", "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"),
    (
        "nested_key_order",
        {"b": {"d": 1, "c": [3, {"z": None, "y": True}]}, "a": "x"},
        '{"a":"x","b":{"c":[3,{"y":true,"z":null}],"d":1}}',
        "58533c0313e57ae20d7057f5888d512716343205dd32d04b9eb0910d6f0cd92d",
    ),
    (
        "numbers",
        {
            "int": 1,
            "float_one": 1.0,
            "neg_zero": -0.0,
            "big_int": 12345678901234567890,
            "sci": 1e21,
            "small": 1e-7,
            "tenth": 0.1,
            "third": 1 / 3,
        },
        '{"big_int":12345678901234567890,"float_one":1.0,"int":1,"neg_zero":-0.0,"sci":1e+21,"small":1e-07,"tenth":0.1,"third":0.3333333333333333}',
        "cb64a8879e64181fc7338a4a1ef05475d240b9a3c624af68ef014d3223571444",
    ),
    (
        "bool_vs_int",
        {"t": True, "one": 1, "f": False, "zero": 0},
        '{"f":false,"one":1,"t":true,"zero":0}',
        "5e5afd1a2f93d35bf6b6e86ba8bbc3dd56793367e4156181116e4670de5bb043",
    ),
    (
        "unicode_nfc",
        {"药": "阿司匹林 100 mg", "é": "café"},
        '{"é":"café","药":"阿司匹林 100 mg"}',
        "df9fa46f3708f4fb1ffcbd48c1eda41a591633c737c96701345c6924ccf2caae",
    ),
    (
        "unicode_nfd",
        {"药": "阿司匹林 100 mg", "é": "cafe\u0301"},
        '{"é":"cafe\u0301","药":"阿司匹林 100 mg"}',
        "044032e521330bb0c1a25cb764c3fe2344ae37570b11ef7992b7b6604ccbf0ef",
    ),
    (
        "astral_and_controls",
        {"emoji": "\U0001f48a", "ctrl": "a\tb\nc\u001fd", "quote": '"\\/'},
        '{"ctrl":"a\\tb\\nc\\u001fd","emoji":"\U0001f48a","quote":"\\"\\\\/"}',
        "e084be49b6daf37e6f0f29eab8df1725c709ac91e8534dd87e628a05afbcd7e6",
    ),
    (
        "key_sort_by_code_point",
        {"b": 1, "B": 2, "中": 3, "a": 4, "1": 5, "é": 6},
        '{"1":5,"B":2,"a":4,"b":1,"é":6,"中":3}',
        "4c0849213f3d36ceae324ff8dbcec6da8ed2c722901473a26d24ce912887ee86",
    ),
    (
        "empty_and_space_keys",
        {"": 0, " ": 1},
        '{"":0," ":1}',
        "711f97d6b61cac017d92581743286ce5682d31f5f1629f77b5288f885593dd82",
    ),
]

OPERATION_KEY_VECTOR = {
    "operation_scope": "ask",
    "run_id": "0123456789abcdef0123456789abcdef",
    "node_name": "retrieve",
    "input_and_versions": {
        "policy_version": "pol-2026.09",
        "retrieval_version": "e3b0c442",
        "skill_version_set": ["label_lookup@1.2.0", "citation_check@0.9.1"],
        "model_config_version": "cfg-7",
        "input": {"query": "示例药品X片 用法用量", "k": 20},
    },
    "expected": "0e7dd6d5a2aa5e6d8d7afd3baed05fe69cc7de717c22680d472e1af35e3a5b44",
}


@pytest.mark.parametrize("name,value,expected_json,expected_sha", VECTORS, ids=[v[0] for v in VECTORS])
def test_known_answer(name, value, expected_json, expected_sha):
    assert canonical_json(value) == expected_json
    assert canonical_hash(value) == expected_sha
    assert canonical_json(value).encode("utf-8").decode("utf-8") == expected_json  # valid UTF-8 round trip


def test_operation_key_known_answer():
    v = OPERATION_KEY_VECTOR
    assert operation_key(v["operation_scope"], v["run_id"], v["node_name"], v["input_and_versions"]) == v["expected"]


def test_canonical_json_does_not_normalize_unicode():
    """NFC and NFD spellings hash differently: callers normalize (norm-v1) before hashing when
    textual equality matters; canonical_json only fixes serialization."""
    nfc = next(v for v in VECTORS if v[0] == "unicode_nfc")[1]
    nfd = next(v for v in VECTORS if v[0] == "unicode_nfd")[1]
    assert canonical_hash(nfc) != canonical_hash(nfd)
    normalized = {k: unicodedata.normalize("NFC", v) for k, v in nfd.items()}
    assert canonical_hash(normalized) == canonical_hash(nfc)


@pytest.mark.parametrize("hash_seed", ["0", "1", "4294967295"])
def test_known_answers_hold_under_other_hash_seeds(hash_seed):
    """Dict/set iteration order depends on PYTHONHASHSEED; the canonical form must not."""
    code = (
        "import json,sys; from medops.core.canonical import canonical_hash, operation_key; "
        "vectors=json.loads(sys.stdin.read()); "
        "print(json.dumps([canonical_hash(v) for v in vectors['values']] + "
        "[operation_key(*vectors['op'][:3], vectors['op'][3])]))"
    )
    payload = {
        "values": [v[1] for v in VECTORS],
        "op": [
            OPERATION_KEY_VECTOR["operation_scope"],
            OPERATION_KEY_VECTOR["run_id"],
            OPERATION_KEY_VECTOR["node_name"],
            OPERATION_KEY_VECTOR["input_and_versions"],
        ],
    }
    import json

    env = {
        **os.environ,
        "PYTHONHASHSEED": hash_seed,
        "PYTHONPATH": os.pathsep.join(p for p in (os.environ.get("PYTHONPATH"), str(_src_dir())) if p),
    }
    proc = subprocess.run(
        [sys.executable, "-c", code], input=json.dumps(payload), capture_output=True, text=True, env=env, check=True
    )
    assert json.loads(proc.stdout) == [v[3] for v in VECTORS] + [OPERATION_KEY_VECTOR["expected"]]


def _src_dir() -> str:
    import medops

    return os.path.dirname(os.path.dirname(os.path.abspath(medops.__file__)))

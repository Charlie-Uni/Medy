import pytest

from medops.core.strict_json import strict_json


def test_shared_parser_preserves_valid_input_and_rejects_duplicates_at_every_depth():
    assert strict_json(b'{"a":[1,true,null]}') == {"a": [1, True, None]}
    for raw in ['{"a":1,"a":2}', '{"a":{"b":1,"b":2}}']:
        with pytest.raises(ValueError, match="^duplicate_json_key$"):
            strict_json(raw)

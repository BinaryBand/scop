"""Comprehensive tests for scop.models.ndjson.NDJSONEvent.

These tests exercise validators, schema constraints and contextual rules
to try and surface edge-cases that could cause the model to accept
invalid events or reject valid ones.
"""

import json
import string

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from scop.models.ndjson import MSGID, NDJSONEvent


def base_event(msgid: MSGID = "SCALAR_SET", room=None, msg: str = "ok") -> dict:
    # Use SCOP facility 16 (pri range 128..135 for severity 0..7); default severity 6 -> pri=128+6=134
    return {"pri": 134, "msgid": msgid, "room": room, "msg": msg}


def test_valid_scalar_set_minimal_and_json_roundtrip():
    ev = base_event("SCALAR_SET", room=None, msg="value")
    ev.update({"id": "m1", "label": "m1", "value": "x", "type": "string"})

    inst = NDJSONEvent.model_validate(ev)
    assert inst.msgid == "SCALAR_SET"

    # roundtrip via JSON string
    j = json.dumps(ev)
    inst2 = NDJSONEvent.model_validate_json(j)
    assert inst2.msg == "value"


@pytest.mark.parametrize("bad_pri", [True, "10", -1, 192, 1.5])
def test_pri_rejects_non_integral_or_out_of_range(bad_pri):
    ev = base_event("SCALAR_SET")
    ev.update({"id": "a", "label": "a", "value": 1, "type": "number"})
    ev["pri"] = bad_pri

    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)


def test_msg_rejects_newlines_and_empty():
    ev = base_event("SCALAR_SET", msg="one\nline")
    ev.update({"id": "a", "label": "a", "value": "v", "type": "string"})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)

    ev2 = base_event("SCALAR_SET", msg="   ")
    ev2.update({"id": "a", "label": "a", "value": "v", "type": "string"})
    # whitespace-only msg should be allowed for PAGE_END but not for other families
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev2)


def test_pid_bool_and_extra_fields_forbidden():
    ev = base_event("SCALAR_SET")
    ev.update({"id": "x", "label": "x", "value": 1, "type": "number", "pid": True})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)

    ev2 = base_event("SCALAR_SET")
    ev2.update({"id": "x", "label": "x", "value": 1, "type": "number", "bogus": 1})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev2)


def test_missing_required_fields_for_msgid():
    ev = base_event("PROCESS_BEGIN")
    # missing id and label
    with pytest.raises((ValidationError, TypeError, ValueError)) as exc:
        NDJSONEvent.model_validate(ev)
    assert "Missing required fields for PROCESS_BEGIN" in str(exc.value)


def test_forbidden_fields_for_page_end():
    ev = base_event("PAGE_END", room=None, msg="")
    ev["title"] = "should not exist"
    with pytest.raises((ValidationError, TypeError, ValueError)) as exc:
        NDJSONEvent.model_validate(ev)
    assert "forbidden for msgid='PAGE_END'" in str(
        exc.value
    ) or "forbidden for msgid" in str(exc.value)


def test_page_begin_icon_format_and_valid_case():
    ev = base_event("PAGE_BEGIN", room=None, msg="ok")
    ev.update({"title": "T", "icon": "smile"})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)

    ev2 = base_event("PAGE_BEGIN", room=None, msg="ok")
    ev2.update({"title": "T", "icon": ":smile:"})
    inst = NDJSONEvent.model_validate(ev2)
    assert inst.icon == ":smile:"


def test_process_update_total_and_current_non_negative():
    ev = base_event("PROCESS_UPDATE")
    ev.update({"id": "p", "current": -1})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)

    ev2 = base_event("PROCESS_BEGIN")
    ev2.update({"id": "p", "label": "L", "total": -5})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev2)


@pytest.mark.parametrize(
    "typ,val,should_pass",
    [
        ("bytes", 1024, True),
        ("bytes", -1, False),
        ("bytes", True, False),
        ("duration", "PT1M30S", True),
        ("duration", "1m", False),
        ("number", 3.14, True),
        ("number", True, False),
        ("string", "x", True),
        ("string", 1, False),
        ("boolean", True, True),
        ("boolean", "true", False),
    ],
)
def test_scalar_set_type_value_matrix(typ, val, should_pass):
    ev = base_event("SCALAR_SET")
    ev.update({"id": "s", "label": "s", "type": typ, "value": val})
    if should_pass:
        NDJSONEvent.model_validate(ev)
    else:
        with pytest.raises((ValidationError, TypeError, ValueError)):
            NDJSONEvent.model_validate(ev)


def test_display_hint_restrictions_for_scalar_and_table():
    ev = base_event("SCALAR_SET")
    ev.update(
        {
            "id": "x",
            "label": "x",
            "type": "string",
            "value": "v",
            "display_hint": "not-badge",
        }
    )
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)

    ev2 = base_event("TABLE_DECLARE")
    ev2.update({"id": "t", "label": "t", "schema": ["a"], "display_hint": "nope"})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev2)


def test_help_item_validation_and_param_ordering():
    # help value must be a dict with command and description
    ev = base_event("LIST_APPEND")
    ev.update({"id": "help", "item_id": "i", "value": "not-a-dict"})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev)

    ev2 = base_event("LIST_APPEND")
    ev2.update({"id": "help", "item_id": "i", "value": {"command": "c"}})
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev2)

    # invalid kind
    ev3 = base_event("LIST_APPEND")
    ev3.update(
        {
            "id": "help",
            "item_id": "i",
            "value": {"command": "c", "description": "d", "kind": "bogus"},
        }
    )
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev3)

    # params must be a list
    ev4 = base_event("LIST_APPEND")
    ev4.update(
        {
            "id": "help",
            "item_id": "i",
            "value": {"command": "c", "description": "d", "params": "nope"},
        }
    )
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev4)

    # ordering violation: required flag before positional
    ev5 = base_event("LIST_APPEND")
    ev5.update(
        {
            "id": "help",
            "item_id": "i",
            "value": {
                "command": "c",
                "description": "d",
                "params": [
                    {"name": "f", "kind": "flag", "required": True},
                    {"name": "p", "kind": "positional"},
                ],
            },
        }
    )
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev5)

    # alphabetical order violation within same group (required flags)
    ev6 = base_event("LIST_APPEND")
    ev6.update(
        {
            "id": "help",
            "item_id": "i",
            "value": {
                "command": "c",
                "description": "d",
                "params": [
                    {"name": "z", "kind": "flag", "required": True},
                    {"name": "a", "kind": "flag", "required": True},
                ],
            },
        }
    )
    with pytest.raises((ValidationError, TypeError, ValueError)):
        NDJSONEvent.model_validate(ev6)


def test_model_is_frozen():
    ev = base_event("SCALAR_SET")
    ev.update({"id": "m", "label": "m", "value": "v", "type": "string"})
    inst = NDJSONEvent.model_validate(ev)
    with pytest.raises((ValidationError, TypeError)):
        inst.msg = "changed"


@given(
    st.integers(min_value=128, max_value=135),
    # Restrict to strings that are not solely whitespace so `msg.strip()` is non-empty
    st.text(alphabet=string.ascii_letters + string.digits + " ", min_size=1).filter(
        lambda s: s.strip() != ""
    ),
)
def test_hypothesis_random_valid_pri_and_msg(pri, msg):
    # Quick property-based check that valid pri/msg combinations validate
    ev = {"pri": pri, "msgid": "SCALAR_SET", "room": None, "msg": msg}
    # Use fixed id/label values so they don't accidentally duplicate the random msg
    ev.update({"id": "fixed-id", "label": "fixed-label", "value": 1, "type": "number"})
    NDJSONEvent.model_validate(ev)

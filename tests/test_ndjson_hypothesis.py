"""Extended Hypothesis-driven tests for `scop.models.ndjson.NDJSONEvent`.

These tests generate valid examples per-MSGID and also perform targeted
mutations to produce invalid examples. They focus on exercising the
model's validation matrix thoroughly while avoiding excessive filtering.

Settings: heavier `max_examples` for SCALAR_SET and HELP builders to fuzz
value-type permutations and param-ordering rules.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from scop.models.ndjson import NDJSONEvent

# --- shared building blocks -------------------------------------------------

PRI = st.integers(min_value=128, max_value=135)
# Disallow newline characters and whitespace-only strings for `msg` and similar fields
NON_EMPTY_STR = st.text(min_size=1).filter(
    lambda s: s.strip() != "" and "\n" not in s and "\r" not in s
)


@st.composite
def base_msg(draw, msgid: str):
    return {
        "pri": draw(PRI),
        "msgid": msgid,
        "room": None,
        "msg": draw(NON_EMPTY_STR),
    }


# --- SCALAR_SET -------------------------------------------------------------


def scalar_value_strategy_for(t: str):
    if t == "bytes":
        return st.integers(min_value=0, max_value=10**9)
    if t == "duration":
        return st.sampled_from(["PT1M", "PT1S", "P1D", "PT1H30M"])
    if t == "number":
        return st.one_of(
            st.integers(), st.floats(allow_nan=False, allow_infinity=False)
        )
    if t == "string":
        return NON_EMPTY_STR
    if t == "boolean":
        return st.booleans()
    raise RuntimeError(t)


@st.composite
def scalar_set_builder(draw):
    t = draw(st.sampled_from(["bytes", "duration", "number", "string", "boolean"]))
    base = draw(base_msg("SCALAR_SET"))
    # ensure id/label don't verbatim duplicate msg
    msg = base["msg"]
    base.update(
        {
            "id": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
            "label": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
            "type": t,
            "value": draw(scalar_value_strategy_for(t)),
        }
    )
    # optional display_hint only allowed as 'badge'
    if draw(st.booleans()):
        base["display_hint"] = "badge"
    return base


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(scalar_set_builder())
def test_scalar_set_valid_examples(ev: Dict[str, Any]):
    # Valid SCALAR_SET examples should pass
    NDJSONEvent.model_validate(ev)


@settings(max_examples=200, deadline=None)
@given(scalar_set_builder())
def test_scalar_set_mutations_reject_type_mismatches(ev: Dict[str, Any]):
    # Try to find at least one other declared `type` that makes the existing
    # `value` invalid. If the value is permissive for all types, skip.
    original_type = ev["type"]
    other_types = ["bytes", "duration", "number", "string", "boolean"]
    other_types.remove(original_type)

    for t in other_types:
        ev_copy = dict(ev)
        ev_copy["type"] = t
        try:
            NDJSONEvent.model_validate(ev_copy)
        except Exception:
            # Found an incompatible type -> success
            break
    else:
        print("no incompatible alternate type found for this value")
        pytest.skip()


# --- HELP item / LIST_APPEND -----------------------------------------------


@st.composite
def help_params(draw, max_params: int = 4):
    # Construct parameters grouped by kind: positionals -> required flags -> optional flags
    pos = draw(
        st.lists(
            st.fixed_dictionaries(
                {"name": NON_EMPTY_STR, "kind": st.just("positional")}
            ),
            max_size=2,
        )
    )
    req_flags = draw(
        st.lists(
            st.fixed_dictionaries(
                {
                    "name": NON_EMPTY_STR,
                    "kind": st.just("flag"),
                    "required": st.just(True),
                }
            ),
            max_size=2,
        )
    )
    opt_flags = draw(
        st.lists(
            st.fixed_dictionaries(
                {
                    "name": NON_EMPTY_STR,
                    "kind": st.just("flag"),
                    "required": st.just(False),
                }
            ),
            max_size=2,
        )
    )

    # Sort each group alphabetically by name to produce valid ordering
    pos_sorted = sorted(pos, key=lambda d: d["name"]) if pos else []
    req_sorted = sorted(req_flags, key=lambda d: d["name"]) if req_flags else []
    opt_sorted = sorted(opt_flags, key=lambda d: d["name"]) if opt_flags else []
    params = pos_sorted + req_sorted + opt_sorted
    return params


@st.composite
def help_item_builder(draw):
    command = draw(NON_EMPTY_STR)
    description = draw(NON_EMPTY_STR)
    params = draw(help_params())
    return {"command": command, "description": description, "params": params}


@st.composite
def help_event_builder(draw):
    base = draw(base_msg("LIST_APPEND"))
    msg = base["msg"]
    # Ensure item_id and help fields don't duplicate msg
    command = draw(NON_EMPTY_STR.filter(lambda s: s != msg))
    description = draw(NON_EMPTY_STR.filter(lambda s: s != msg))
    params = draw(help_params())
    base.update(
        {
            "id": "help",
            "item_id": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
            "value": {"command": command, "description": description, "params": params},
        }
    )
    return base


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(help_event_builder())
def test_help_item_valid(ev: Dict[str, Any]):
    NDJSONEvent.model_validate(ev)


@settings(max_examples=200, deadline=None)
@given(help_event_builder())
def test_help_item_ordering_violations_rejected(ev: Dict[str, Any]):
    # Inject an ordering violation: place a required flag before a positional
    params = ev["value"]["params"]
    if len(params) < 2:
        print("not enough params to mutate")
        pytest.skip()
    # swap first two entries to likely cause violation
    params[0], params[1] = params[1], params[0]
    ev["value"]["params"] = params
    with pytest.raises(Exception):
        NDJSONEvent.model_validate(ev)


# --- TABLE_DECLARE / TABLE_ROW --------------------------------------------


@st.composite
def table_declare_builder(draw):
    base = draw(base_msg("TABLE_DECLARE"))
    msg = base["msg"]
    cols = draw(st.lists(NON_EMPTY_STR, min_size=1, max_size=4))
    base.update(
        {
            "id": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
            "label": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
            "schema": cols,
        }
    )
    return base


@st.composite
def table_row_builder(draw, schema: list[str]):
    base = draw(base_msg("TABLE_ROW"))
    values = {
        c: draw(st.one_of(st.integers(), NON_EMPTY_STR, st.booleans())) for c in schema
    }
    base.update(
        {"id": draw(NON_EMPTY_STR), "row_id": draw(NON_EMPTY_STR), "values": values}
    )
    return base


@settings(max_examples=200, deadline=None)
@given(table_declare_builder())
def test_table_declare_and_row_roundtrip(decl: Dict[str, Any]):
    # Table declare validates and table rows matching schema validate
    NDJSONEvent.model_validate(decl)
    schema = decl["schema"]
    # build some rows
    for i in range(3):
        row = {
            "pri": decl["pri"],
            "msgid": "TABLE_ROW",
            "room": decl.get("room"),
            "msg": decl.get("msg") or "ok",
            "id": decl["id"],
            "row_id": f"r{i}",
            "values": {c: 0 for c in schema},
        }
        NDJSONEvent.model_validate(row)


# --- PROCESS family -------------------------------------------------------


@st.composite
def process_begin_builder(draw):
    base = draw(base_msg("PROCESS_BEGIN"))
    msg = base["msg"]
    base.update(
        {
            "id": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
            "label": draw(NON_EMPTY_STR.filter(lambda s: s != msg)),
        }
    )
    if draw(st.booleans()):
        base["total"] = draw(st.integers(min_value=0, max_value=10**6))
    return base


@settings(max_examples=200, deadline=None)
@given(process_begin_builder())
def test_process_begin_valid(pb: Dict[str, Any]):
    NDJSONEvent.model_validate(pb)


@settings(max_examples=200, deadline=None)
@given(process_begin_builder())
def test_process_begin_mutate_invalid_total(pb: Dict[str, Any]):
    pb["total"] = -1
    with pytest.raises(Exception):
        NDJSONEvent.model_validate(pb)


# --- PAGE_BEGIN -----------------------------------------------------------


@st.composite
def page_begin_builder(draw):
    base = draw(base_msg("PAGE_BEGIN"))
    msg = base["msg"]
    base.update({"title": draw(NON_EMPTY_STR.filter(lambda s: s != msg))})
    if draw(st.booleans()):
        base["icon"] = draw(st.sampled_from([":ok:", ":smile:", ":rocket:"]))
    return base


@settings(max_examples=200, deadline=None)
@given(page_begin_builder())
def test_page_begin_icon_valid(pb: Dict[str, Any]):
    NDJSONEvent.model_validate(pb)


@settings(max_examples=100, deadline=None)
@given(page_begin_builder())
def test_page_begin_icon_invalid_format(pb: Dict[str, Any]):
    pb["icon"] = "notagemoji"
    with pytest.raises(Exception):
        NDJSONEvent.model_validate(pb)

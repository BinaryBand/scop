"""Adversarial stream-level tests for scop.models.stream.validate_stream.

Strategy
--------
* parametrized deterministic tests pin every named violation the spec defines.
* Hypothesis tests build complete valid streams and then:
  - pass them through as-is (they must accept), or
  - apply one targeted mutation (wrong order, missing wrapper, schema mismatch,
    duplicate id, orphaned lifecycle event) and assert SCOPStreamError is raised.

All generated pri values use SCOP facility 16 (128–135).
All generated strings exclude newlines, carriage returns, and empty/whitespace.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from scop.models.ndjson import NDJSONEvent
from scop.models.stream import SCOPStreamError, validate_stream

# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------

PRI = st.integers(min_value=128, max_value=135)
SAFE_STR = st.text(min_size=1, max_size=32).filter(
    lambda s: s.strip() != "" and "\n" not in s and "\r" not in s
)
ROOM = st.one_of(st.none(), SAFE_STR)


def _ev(msgid: str, room: Optional[str] = "room", **kwargs) -> NDJSONEvent:
    """Build a minimal valid NDJSONEvent dict and parse it."""
    base: Dict[str, Any] = {
        "pri": 134,
        "msgid": msgid,
        "room": room,
        "msg": f"ok {msgid}",
    }
    base.update(kwargs)
    # msg must not duplicate id/label/title etc — use prefix to stay safe
    for fld in ("id", "label", "title", "subtitle", "item_id", "row_id", "app"):
        val = base.get(fld)
        if isinstance(val, str) and val == base["msg"]:
            base["msg"] = f"msg for {val}"
    return NDJSONEvent.model_validate(base)


def _validate(events: List[NDJSONEvent]) -> None:
    """Run stream validator; surface violations clearly in test output."""
    validate_stream(events)


# ---------------------------------------------------------------------------
# Helpers to build canonical valid streams
# ---------------------------------------------------------------------------


def minimal_stream(room: Optional[str] = "r") -> List[NDJSONEvent]:
    """PAGE_BEGIN … PAGE_END — the smallest valid SCOP stream."""
    return [
        _ev("PAGE_BEGIN", room=room, title="T", msg="welcome"),
        _ev("PAGE_END", room=room, msg=""),
    ]


def process_stream(
    pid: str = "p",
    room: Optional[str] = "r",
    total: int = 2,
    dry_run: Optional[bool] = None,
) -> List[NDJSONEvent]:
    """Valid PAGE_BEGIN … PROCESS lifecycle … PAGE_END."""
    dry = {"dry_run": True} if dry_run else {}
    return [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "PROCESS_BEGIN", room=room, id=pid, label="Doing", msg=f"begin {pid}", **dry
        ),
        _ev("PROCESS_UPDATE", room=room, id=pid, current=1, msg=f"step {pid}", **dry),
        _ev("PROCESS_END", room=room, id=pid, ok=True, msg=f"done {pid}", **dry),
        _ev("PAGE_END", room=room, msg=""),
    ]


def table_stream(
    tid: str = "t",
    schema: List[str] | None = None,
    room: Optional[str] = "r",
) -> List[NDJSONEvent]:
    schema = schema or ["a", "b"]
    return [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "TABLE_DECLARE",
            room=room,
            id=tid,
            label="TBL",
            schema=schema,
            msg=f"declare {tid}",
        ),
        _ev(
            "TABLE_ROW",
            room=room,
            id=tid,
            row_id="r1",
            values={k: 0 for k in schema},
            msg=f"row1 {tid}",
        ),
        _ev("TABLE_END", room=room, id=tid, msg=f"end {tid}"),
        _ev("PAGE_END", room=room, msg=""),
    ]


def list_stream(
    lid: str = "l",
    room: Optional[str] = "r",
    ordered: bool = False,
) -> List[NDJSONEvent]:
    return [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "LIST_DECLARE",
            room=room,
            id=lid,
            label="List",
            ordered=ordered,
            msg=f"declare {lid}",
        ),
        _ev(
            "LIST_APPEND",
            room=room,
            id=lid,
            item_id="i1",
            value="x",
            msg=f"append {lid}",
        ),
        _ev(
            "LIST_UPDATE",
            room=room,
            id=lid,
            item_id="i1",
            value="y",
            msg=f"update {lid}",
        ),
        _ev("LIST_REMOVE", room=room, id=lid, item_id="i1", msg=f"remove {lid}"),
        _ev("LIST_END", room=room, id=lid, msg=f"end {lid}"),
        _ev("PAGE_END", room=room, msg=""),
    ]


# ---------------------------------------------------------------------------
# Deterministic — valid streams must pass
# ---------------------------------------------------------------------------


def test_minimal_stream_passes():
    _validate(minimal_stream())


def test_process_stream_passes():
    _validate(process_stream())


def test_table_stream_passes():
    _validate(table_stream())


def test_list_stream_passes():
    _validate(list_stream())


def test_multiple_processes_same_room():
    room = "r"
    events = [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev("PROCESS_BEGIN", room=room, id="p1", label="A", msg="begin p1"),
        _ev("PROCESS_BEGIN", room=room, id="p2", label="B", msg="begin p2"),
        _ev("PROCESS_END", room=room, id="p1", ok=True, msg="end p1"),
        _ev("PROCESS_END", room=room, id="p2", ok=False, msg="end p2"),
        _ev("PAGE_END", room=room, msg=""),
    ]
    _validate(events)


def test_dry_run_all_process_events():
    _validate(process_stream(dry_run=True))


def test_scalar_set_inside_valid_stream():
    room = "r"
    events = [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "SCALAR_SET",
            room=room,
            id="v1",
            label="Value",
            type="number",
            value=42,
            msg="v1 is 42",
        ),
        _ev("SCALAR_CLEAR", room=room, id="v1", msg="clear v1"),
        _ev("PAGE_END", room=room, msg=""),
    ]
    _validate(events)


def test_table_with_multiple_rows():
    schema = ["x", "y", "z"]
    room = "r"
    events = [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "TABLE_DECLARE",
            room=room,
            id="t",
            label="L",
            schema=schema,
            msg="declare t",
        ),
        _ev(
            "TABLE_ROW",
            room=room,
            id="t",
            row_id="r1",
            values={"x": 1, "y": 2, "z": 3},
            msg="row1",
        ),
        _ev(
            "TABLE_ROW",
            room=room,
            id="t",
            row_id="r2",
            values={"x": 4, "y": 5, "z": 6},
            msg="row2",
        ),
        _ev(
            "TABLE_UPDATE",
            room=room,
            id="t",
            row_id="r1",
            values={"x": 9, "y": 2, "z": 3},
            msg="upd r1",
        ),
        _ev("TABLE_END", room=room, id="t", msg="end t"),
        _ev("PAGE_END", room=room, msg=""),
    ]
    _validate(events)


def test_null_room_valid():
    """root invocation has room=None — must be valid."""
    _validate(minimal_stream(room=None))


# ---------------------------------------------------------------------------
# Deterministic — structural violations must fail
# ---------------------------------------------------------------------------


def test_empty_stream_raises():
    with pytest.raises(ValueError):
        validate_stream([])


def test_missing_page_begin():
    events = [
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="PAGE_BEGIN"):
        _validate(events)


def test_missing_page_end():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
    ]
    with pytest.raises(SCOPStreamError, match="PAGE_END"):
        _validate(events)


def test_interior_page_begin_rejected():
    room = "r"
    events = [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev("PAGE_BEGIN", room=room, title="X", msg="extra"),  # must not appear here
        _ev("PAGE_END", room=room, msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="PAGE_BEGIN"):
        _validate(events)


def test_interior_page_end_rejected():
    room = "r"
    events = [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev("PAGE_END", room=room, msg=""),  # index 1 — interior
        _ev("PAGE_END", room=room, msg=""),  # must be at tail
    ]
    with pytest.raises(SCOPStreamError):
        _validate(events)


def test_room_mismatch_rejected():
    events = [
        _ev("PAGE_BEGIN", room="room-a", title="T", msg="start"),
        _ev(
            "SCALAR_SET",
            room="room-b",
            id="v",
            label="V",
            type="number",
            value=1,
            msg="v is 1",
        ),
        _ev("PAGE_END", room="room-a", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="Room mismatch"):
        _validate(events)


def test_process_update_without_begin():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_UPDATE", room="r", id="orphan", current=1, msg="update orphan"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="no matching PROCESS_BEGIN"):
        _validate(events)


def test_process_end_without_begin():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_END", room="r", id="ghost", ok=True, msg="end ghost"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="no matching PROCESS_BEGIN"):
        _validate(events)


def test_process_log_without_begin():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_LOG", room="r", id="nobody", msg="log line"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="no matching PROCESS_BEGIN"):
        _validate(events)


def test_unclosed_process_rejected():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_BEGIN", room="r", id="p", label="P", msg="begin p"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="never closed"):
        _validate(events)


def test_duplicate_process_begin_rejected():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_BEGIN", room="r", id="p", label="P", msg="begin p"),
        _ev("PROCESS_BEGIN", room="r", id="p", label="P", msg="re-begin p"),
        _ev("PROCESS_END", room="r", id="p", ok=True, msg="end p"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="Duplicate PROCESS_BEGIN"):
        _validate(events)


def test_process_update_after_end_rejected():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_BEGIN", room="r", id="p", label="P", msg="begin p"),
        _ev("PROCESS_END", room="r", id="p", ok=True, msg="end p"),
        _ev("PROCESS_UPDATE", room="r", id="p", current=99, msg="stale update"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="after PROCESS_END"):
        _validate(events)


def test_dry_run_missing_on_one_process_event():
    """If any PROCESS event carries dry_run=True, all must."""
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("PROCESS_BEGIN", room="r", id="p", label="P", dry_run=True, msg="begin p"),
        _ev(
            "PROCESS_UPDATE", room="r", id="p", current=1, msg="step p"
        ),  # missing dry_run
        _ev("PROCESS_END", room="r", id="p", ok=True, msg="end p"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="dry_run"):
        _validate(events)


def test_table_row_before_declare():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("TABLE_ROW", room="r", id="t", row_id="r1", values={"a": 1}, msg="row1"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="no matching TABLE_DECLARE"):
        _validate(events)


def test_table_row_after_end():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "TABLE_DECLARE", room="r", id="t", label="T", schema=["a"], msg="declare t"
        ),
        _ev("TABLE_ROW", room="r", id="t", row_id="r1", values={"a": 1}, msg="row1"),
        _ev("TABLE_END", room="r", id="t", msg="end t"),
        _ev(
            "TABLE_ROW", room="r", id="t", row_id="r2", values={"a": 2}, msg="late row"
        ),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="after TABLE_END"):
        _validate(events)


def test_table_row_missing_schema_columns():
    schema = ["a", "b", "c"]
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "TABLE_DECLARE", room="r", id="t", label="T", schema=schema, msg="declare t"
        ),
        _ev(
            "TABLE_ROW",
            room="r",
            id="t",
            row_id="r1",
            values={"a": 1},
            msg="sparse row",
        ),
        _ev("TABLE_END", room="r", id="t", msg="end t"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="missing schema columns"):
        _validate(events)


def test_table_row_extra_columns():
    schema = ["a"]
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "TABLE_DECLARE", room="r", id="t", label="T", schema=schema, msg="declare t"
        ),
        _ev(
            "TABLE_ROW",
            room="r",
            id="t",
            row_id="r1",
            values={"a": 1, "z": 99},
            msg="extra col",
        ),
        _ev("TABLE_END", room="r", id="t", msg="end t"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="unexpected columns"):
        _validate(events)


def test_unclosed_table_rejected():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "TABLE_DECLARE", room="r", id="t", label="T", schema=["a"], msg="declare t"
        ),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="never closed"):
        _validate(events)


def test_list_append_before_declare():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("LIST_APPEND", room="r", id="l", item_id="i1", value="x", msg="append"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="no matching LIST_DECLARE"):
        _validate(events)


def test_list_update_unknown_item_id():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "LIST_DECLARE", room="r", id="l", label="L", ordered=False, msg="declare l"
        ),
        _ev(
            "LIST_UPDATE",
            room="r",
            id="l",
            item_id="ghost",
            value="x",
            msg="update ghost",
        ),
        _ev("LIST_END", room="r", id="l", msg="end l"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="unknown item_id"):
        _validate(events)


def test_list_append_duplicate_item_id():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "LIST_DECLARE", room="r", id="l", label="L", ordered=False, msg="declare l"
        ),
        _ev("LIST_APPEND", room="r", id="l", item_id="i1", value="a", msg="append i1"),
        _ev(
            "LIST_APPEND",
            room="r",
            id="l",
            item_id="i1",
            value="b",
            msg="append i1 again",
        ),
        _ev("LIST_END", room="r", id="l", msg="end l"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="duplicate item_id"):
        _validate(events)


def test_unclosed_list_rejected():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev("LIST_DECLARE", room="r", id="l", label="L", ordered=True, msg="declare l"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="never closed"):
        _validate(events)


def test_duplicate_list_end_rejected():
    events = [
        _ev("PAGE_BEGIN", room="r", title="T", msg="start"),
        _ev(
            "LIST_DECLARE", room="r", id="l", label="L", ordered=False, msg="declare l"
        ),
        _ev("LIST_END", room="r", id="l", msg="end l"),
        _ev("LIST_END", room="r", id="l", msg="dup end l"),
        _ev("PAGE_END", room="r", msg=""),
    ]
    with pytest.raises(SCOPStreamError, match="Duplicate LIST_END"):
        _validate(events)


# ---------------------------------------------------------------------------
# Hypothesis — valid stream generators
# ---------------------------------------------------------------------------


@st.composite
def valid_minimal_stream(draw):
    room = draw(ROOM)
    title = draw(SAFE_STR)
    msg_begin = draw(SAFE_STR.filter(lambda s: s != title))
    return [
        _ev("PAGE_BEGIN", room=room, title=title, msg=msg_begin),
        _ev("PAGE_END", room=room, msg=""),
    ]


@st.composite
def valid_process_stream(draw):
    room = draw(ROOM)
    pid = draw(SAFE_STR)
    use_dry = draw(st.booleans())
    dry = {"dry_run": True} if use_dry else {}
    label = draw(SAFE_STR.filter(lambda s: s != pid))
    return [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev("PROCESS_BEGIN", room=room, id=pid, label=label, msg=f"b-{pid}", **dry),
        _ev(
            "PROCESS_END",
            room=room,
            id=pid,
            ok=draw(st.booleans()),
            msg=f"e-{pid}",
            **dry,
        ),
        _ev("PAGE_END", room=room, msg=""),
    ]


@st.composite
def valid_table_stream(draw):
    room = draw(ROOM)
    tid = draw(SAFE_STR)
    # unique column names — use integers-as-strings to guarantee uniqueness
    ncols = draw(st.integers(min_value=1, max_value=4))
    schema = [f"col{i}" for i in range(ncols)]
    row_vals = {k: draw(st.integers()) for k in schema}
    label = draw(SAFE_STR.filter(lambda s: s != tid))
    return [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "TABLE_DECLARE",
            room=room,
            id=tid,
            label=label,
            schema=schema,
            msg=f"d-{tid}",
        ),
        _ev(
            "TABLE_ROW",
            room=room,
            id=tid,
            row_id="r1",
            values=row_vals,
            msg=f"row-{tid}",
        ),
        _ev("TABLE_END", room=room, id=tid, msg=f"te-{tid}"),
        _ev("PAGE_END", room=room, msg=""),
    ]


@st.composite
def valid_list_stream(draw):
    room = draw(ROOM)
    # "help" triggers a per-event validation requiring value to be a dict; exclude it
    lid = draw(SAFE_STR.filter(lambda s: s != "help"))
    ordered = draw(st.booleans())
    label = draw(SAFE_STR.filter(lambda s: s != lid))
    n_items = draw(st.integers(min_value=0, max_value=4))
    item_ids = [f"item{i}" for i in range(n_items)]
    events = [
        _ev("PAGE_BEGIN", room=room, title="T", msg="start"),
        _ev(
            "LIST_DECLARE",
            room=room,
            id=lid,
            label=label,
            ordered=ordered,
            msg=f"d-{lid}",
        ),
    ]
    for iid in item_ids:
        events.append(
            _ev(
                "LIST_APPEND", room=room, id=lid, item_id=iid, value=iid, msg=f"a-{iid}"
            )
        )
    events.append(_ev("LIST_END", room=room, id=lid, msg=f"le-{lid}"))
    events.append(_ev("PAGE_END", room=room, msg=""))
    return events


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_minimal_stream())
def test_hyp_minimal_stream_passes(events):
    _validate(events)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_process_stream())
def test_hyp_process_stream_passes(events):
    _validate(events)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_table_stream())
def test_hyp_table_stream_passes(events):
    _validate(events)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_list_stream())
def test_hyp_list_stream_passes(events):
    _validate(events)


# ---------------------------------------------------------------------------
# Hypothesis — single-mutation negative tests
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_process_stream())
def test_hyp_remove_page_begin_fails(events):
    """Dropping PAGE_BEGIN must always fail."""
    mutated = [e for e in events if e.msgid != "PAGE_BEGIN"]
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_process_stream())
def test_hyp_remove_page_end_fails(events):
    """Dropping PAGE_END must always fail."""
    mutated = [e for e in events if e.msgid != "PAGE_END"]
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_process_stream())
def test_hyp_drop_process_end_fails(events):
    """Removing PROCESS_END must leave the process unclosed → violation."""
    mutated = [e for e in events if e.msgid != "PROCESS_END"]
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_table_stream())
def test_hyp_drop_table_end_fails(events):
    mutated = [e for e in events if e.msgid != "TABLE_END"]
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_table_stream())
def test_hyp_table_row_wrong_schema_fails(events):
    """Inject a TABLE_ROW with a misspelled column key — must fail schema alignment."""
    room = events[0].room
    tid = next(e.id for e in events if e.msgid == "TABLE_DECLARE")
    schema_cols = next(e.table_schema for e in events if e.msgid == "TABLE_DECLARE")

    # Build a bad values dict: use a key not in schema
    bad_values = {f"BOGUS_{k}": 0 for k in schema_cols}
    # Inject after TABLE_DECLARE, before TABLE_END
    inject_at = next(i for i, e in enumerate(events) if e.msgid == "TABLE_END")
    bad_row = _ev(
        "TABLE_ROW", room=room, id=tid, row_id="bad", values=bad_values, msg="bad row"
    )
    mutated = events[:inject_at] + [bad_row] + events[inject_at:]
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_list_stream())
def test_hyp_drop_list_end_fails(events):
    mutated = [e for e in events if e.msgid != "LIST_END"]
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)


@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(valid_process_stream())
def test_hyp_room_mismatch_fails(events: List[NDJSONEvent]):
    """Changing one interior event's room must fail."""
    if len(events) < 2:
        return
    # Find an interior event (not PAGE_BEGIN, not PAGE_END) to mangle
    interior_indices = [
        i for i, e in enumerate(events) if e.msgid not in ("PAGE_BEGIN", "PAGE_END")
    ]
    if not interior_indices:
        return
    idx = interior_indices[0]
    ev = events[idx]
    # Replace room with a clearly different value
    wrong_room = "WRONG_ROOM__XYZZY"
    raw = ev.model_dump(by_alias=True)
    raw["room"] = wrong_room
    raw.setdefault("intent", "query")
    # Re-parse (may fail per-event if room changes msgid requirements — catch that)
    try:
        bad_ev = NDJSONEvent.model_validate(raw)
    except Exception:
        return  # per-event failure is also correct
    mutated = list(events)
    mutated[idx] = bad_ev
    with pytest.raises((SCOPStreamError, ValueError)):
        _validate(mutated)

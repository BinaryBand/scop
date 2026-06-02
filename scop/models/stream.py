"""Stream-level validator for SCOP NDJSON event streams.

A single NDJSONEvent validates that one line is internally consistent.
This module validates cross-event invariants from SCOP.md:

    §5  — every stream starts PAGE_BEGIN, ends PAGE_END; all events share the same room
    §7.2 — PROCESS lifecycle order (BEGIN → UPDATE* → END), no orphan events
    §7.4 — LIST events reference a declared list id
    §7.5 — TABLE_ROW/UPDATE values keys align with TABLE_DECLARE schema for that id
    §8.3 — dry_run: true propagates to every PROCESS_* event when the session uses --dry-run
    §11  — no events before PAGE_BEGIN or after PAGE_END

Usage::

    from scop.models.stream import validate_stream, SCOPStreamError

    events = [NDJSONEvent.model_validate(json.loads(line)) for line in lines]
    validate_stream(events)          # raises SCOPStreamError with a list of violations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from scop.models.ndjson import NDJSONEvent


class SCOPStreamError(ValueError):
    """Raised when one or more cross-event stream constraints are violated.

    ``violations`` is a list of human-readable descriptions.
    """

    def __init__(self, violations: List[str]) -> None:
        self.violations = list(violations)
        super().__init__("\n".join(f"  • {v}" for v in self.violations))


@dataclass
class _ListState:
    """Track open list lifecycle."""

    id: str
    known_item_ids: set = field(default_factory=set)
    closed: bool = False


@dataclass
class _TableState:
    """Track open table lifecycle."""

    id: str
    schema: List[str] = field(default_factory=list)
    closed: bool = False


@dataclass
class _ProcessState:
    """Track open process lifecycle."""

    id: str
    begun: bool = True
    ended: bool = False
    dry_run: bool = False


def validate_stream(events: Sequence[NDJSONEvent]) -> None:
    """Validate cross-event SCOP stream invariants.

    Args:
        events: Ordered sequence of NDJSONEvent objects representing one stream.

    Raises:
        SCOPStreamError: If any stream-level violations are found.  All
            violations are collected before raising so callers see the full picture.
        ValueError: If ``events`` is empty.
    """
    if not events:
        raise ValueError("Stream must contain at least one event")

    violations: List[str] = []

    # --- §11 / §7.1 wrapper checks ------------------------------------------
    if events[0].msgid != "PAGE_BEGIN":
        violations.append(f"Stream must start with PAGE_BEGIN, got '{events[0].msgid}'")
    if events[-1].msgid != "PAGE_END":
        violations.append(f"Stream must end with PAGE_END, got '{events[-1].msgid}'")

    # Detect any PAGE_BEGIN or PAGE_END in the interior
    for i, ev in enumerate(events[1:-1], start=1):
        if ev.msgid == "PAGE_BEGIN":
            violations.append(
                f"Unexpected PAGE_BEGIN at position {i} (only allowed at position 0)"
            )
        if ev.msgid == "PAGE_END":
            violations.append(
                f"Unexpected PAGE_END at position {i} (only allowed at the final position)"
            )

    # --- §5 room consistency -------------------------------------------------
    # All events in a stream share the same room
    if events:
        expected_room: Optional[str] = events[0].room
        for i, ev in enumerate(events):
            if ev.room != expected_room:
                violations.append(
                    f"Room mismatch at position {i}: expected {expected_room!r}, "
                    f"got {ev.room!r} (msgid={ev.msgid!r})"
                )

    # --- state tracking for structural ids -----------------------------------
    lists: dict[str, _ListState] = {}
    tables: dict[str, _TableState] = {}
    processes: dict[str, _ProcessState] = {}

    # Detect whether this stream uses dry_run at all (§8.3)
    stream_uses_dry_run = any(
        ev.msgid in ("PROCESS_BEGIN", "PROCESS_UPDATE", "PROCESS_END", "PROCESS_LOG")
        and ev.dry_run is True
        for ev in events
    )

    for i, ev in enumerate(events):
        mid = ev.msgid

        # --- PROCESS lifecycle (§7.2) ----------------------------------------
        if mid == "PROCESS_BEGIN":
            pid = ev.id
            if pid is None:
                violations.append(
                    f"PROCESS_BEGIN at position {i} is missing required 'id' field"
                )
                continue
            if pid in processes and not processes[pid].ended:
                violations.append(
                    f"Duplicate PROCESS_BEGIN for id={pid!r} at position {i} "
                    f"without a preceding PROCESS_END"
                )
            processes[pid] = _ProcessState(id=pid, dry_run=bool(ev.dry_run))

            if stream_uses_dry_run and not ev.dry_run:
                violations.append(
                    f"§8.3: PROCESS_BEGIN id={pid!r} at position {i} is missing "
                    f"dry_run=true but stream has dry_run events"
                )

        elif mid == "PROCESS_UPDATE":
            pid = ev.id
            if pid not in processes:
                violations.append(
                    f"PROCESS_UPDATE for id={pid!r} at position {i} "
                    f"has no matching PROCESS_BEGIN"
                )
            elif processes[pid].ended:
                violations.append(
                    f"PROCESS_UPDATE for id={pid!r} at position {i} after PROCESS_END"
                )
            if stream_uses_dry_run and not ev.dry_run:
                violations.append(
                    f"§8.3: PROCESS_UPDATE id={pid!r} at position {i} is missing "
                    f"dry_run=true but stream has dry_run events"
                )

        elif mid == "PROCESS_END":
            pid = ev.id
            if pid not in processes:
                violations.append(
                    f"PROCESS_END for id={pid!r} at position {i} "
                    f"has no matching PROCESS_BEGIN"
                )
            elif processes[pid].ended:
                violations.append(
                    f"Duplicate PROCESS_END for id={pid!r} at position {i}"
                )
            else:
                processes[pid].ended = True
            if stream_uses_dry_run and not ev.dry_run:
                violations.append(
                    f"§8.3: PROCESS_END id={pid!r} at position {i} is missing "
                    f"dry_run=true but stream has dry_run events"
                )

        elif mid == "PROCESS_LOG":
            pid = ev.id
            if pid not in processes:
                violations.append(
                    f"PROCESS_LOG for id={pid!r} at position {i} "
                    f"has no matching PROCESS_BEGIN"
                )
            elif processes[pid].ended:
                violations.append(
                    f"PROCESS_LOG for id={pid!r} at position {i} after PROCESS_END"
                )

        # --- LIST lifecycle (§7.4) -------------------------------------------
        elif mid == "LIST_DECLARE":
            lid = ev.id
            if lid is None:
                violations.append(
                    f"LIST_DECLARE at position {i} is missing required 'id' field"
                )
                continue
            if lid in lists and not lists[lid].closed:
                violations.append(
                    f"Duplicate LIST_DECLARE for id={lid!r} at position {i} "
                    f"without a preceding LIST_END"
                )
            lists[lid] = _ListState(id=lid)

        elif mid in ("LIST_APPEND", "LIST_UPDATE", "LIST_REMOVE"):
            lid = ev.id
            if lid not in lists:
                violations.append(
                    f"{mid} for id={lid!r} at position {i} has no matching LIST_DECLARE"
                )
            elif lists[lid].closed:
                violations.append(
                    f"{mid} for id={lid!r} at position {i} after LIST_END"
                )
            else:
                iid = ev.item_id
                if mid == "LIST_APPEND":
                    if iid in lists[lid].known_item_ids:
                        violations.append(
                            f"LIST_APPEND duplicate item_id={iid!r} for list id={lid!r} "
                            f"at position {i}"
                        )
                    lists[lid].known_item_ids.add(iid)
                elif mid in ("LIST_UPDATE", "LIST_REMOVE"):
                    if iid not in lists[lid].known_item_ids:
                        violations.append(
                            f"{mid} references unknown item_id={iid!r} for list "
                            f"id={lid!r} at position {i} (never appended)"
                        )

        elif mid == "LIST_END":
            lid = ev.id
            if lid not in lists:
                violations.append(
                    f"LIST_END for id={lid!r} at position {i} "
                    f"has no matching LIST_DECLARE"
                )
            elif lists[lid].closed:
                violations.append(f"Duplicate LIST_END for id={lid!r} at position {i}")
            else:
                lists[lid].closed = True

        # --- TABLE lifecycle (§7.5) ------------------------------------------
        elif mid == "TABLE_DECLARE":
            tid = ev.id
            if tid is None:
                violations.append(
                    f"TABLE_DECLARE at position {i} is missing required 'id' field"
                )
                continue
            if tid in tables and not tables[tid].closed:
                violations.append(
                    f"Duplicate TABLE_DECLARE for id={tid!r} at position {i} "
                    f"without a preceding TABLE_END"
                )
            tables[tid] = _TableState(id=tid, schema=list(ev.table_schema or []))

        elif mid in ("TABLE_ROW", "TABLE_UPDATE"):
            tid = ev.id
            if tid not in tables:
                violations.append(
                    f"{mid} for id={tid!r} at position {i} "
                    f"has no matching TABLE_DECLARE"
                )
            elif tables[tid].closed:
                violations.append(
                    f"{mid} for id={tid!r} at position {i} after TABLE_END"
                )
            else:
                declared_schema = set(tables[tid].schema)
                provided_keys = set((ev.values or {}).keys())
                # All declared columns must be present in the row
                missing_cols = declared_schema - provided_keys
                extra_cols = provided_keys - declared_schema
                if missing_cols:
                    violations.append(
                        f"{mid} id={tid!r} at position {i}: "
                        f"missing schema columns {sorted(missing_cols)}"
                    )
                if extra_cols:
                    violations.append(
                        f"{mid} id={tid!r} at position {i}: "
                        f"unexpected columns not in schema {sorted(extra_cols)}"
                    )

        elif mid == "TABLE_END":
            tid = ev.id
            if tid not in tables:
                violations.append(
                    f"TABLE_END for id={tid!r} at position {i} "
                    f"has no matching TABLE_DECLARE"
                )
            elif tables[tid].closed:
                violations.append(f"Duplicate TABLE_END for id={tid!r} at position {i}")
            else:
                tables[tid].closed = True

    # --- open lifecycle checks -----------------------------------------------
    for pid, ps in processes.items():
        if not ps.ended:
            violations.append(
                f"PROCESS_BEGIN id={pid!r} was never closed with PROCESS_END"
            )
    for lid, ls in lists.items():
        if not ls.closed:
            violations.append(f"LIST_DECLARE id={lid!r} was never closed with LIST_END")
    for tid, ts in tables.items():
        if not ts.closed:
            violations.append(
                f"TABLE_DECLARE id={tid!r} was never closed with TABLE_END"
            )

    if violations:
        raise SCOPStreamError(violations)

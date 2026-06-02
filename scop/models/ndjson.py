"""Pydantic models for SCOP NDJSON event lines.

This module defines a strict, non-coercing model for a single NDJSON event
line following the SCOP `event_base` rules. Extra keys are forbidden and
basic semantic validations are enforced (single-line `msg`, non-negative
`pri`, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TYPE = Literal["number", "string", "boolean", "duration", "bytes"]

MSGID = Literal[
    "PAGE_BEGIN",
    "PAGE_END",
    "PROCESS_BEGIN",
    "PROCESS_UPDATE",
    "PROCESS_END",
    "PROCESS_LOG",
    "SCALAR_SET",
    "SCALAR_CLEAR",
    "LIST_DECLARE",
    "LIST_APPEND",
    "LIST_UPDATE",
    "LIST_REMOVE",
    "LIST_END",
    "TABLE_DECLARE",
    "TABLE_ROW",
    "TABLE_UPDATE",
    "TABLE_END",
]

# Canonical validation map using spec-compliant JSON keys
MSGID_MAP: dict[MSGID, tuple[set[str], set[str]]] = {
    "PAGE_BEGIN": ({"title"}, {"subtitle", "icon", "intent"}),
    "PAGE_END": (set(), set()),
    "PROCESS_BEGIN": (
        {"id", "label"},
        {"total", "dry_run", "recursive", "force"},
    ),
    "PROCESS_UPDATE": (
        {"id", "current"},
        {"total", "label", "dry_run", "recursive", "force"},
    ),
    "PROCESS_END": (
        {"id", "ok"},
        {"dry_run", "recursive", "force"},
    ),
    "PROCESS_LOG": (
        {"id"},
        {"dry_run", "recursive", "force"},
    ),
    "SCALAR_SET": ({"id", "label", "value", "type"}, {"unit", "display_hint"}),
    "SCALAR_CLEAR": ({"id"}, set()),
    "LIST_DECLARE": ({"id", "label", "ordered"}, set()),
    "LIST_APPEND": ({"id", "item_id", "value"}, set()),
    "LIST_UPDATE": ({"id", "item_id", "value"}, set()),
    "LIST_REMOVE": ({"id", "item_id"}, set()),
    "LIST_END": ({"id"}, set()),
    "TABLE_DECLARE": ({"id", "label", "schema"}, {"display_hint"}),
    "TABLE_ROW": ({"id", "row_id", "values"}, set()),
    "TABLE_UPDATE": ({"id", "row_id", "values"}, set()),
    "TABLE_END": ({"id"}, set()),
}

PROCESS_MSGIDS = ("PROCESS_BEGIN", "PROCESS_UPDATE")
HELP_LIST_MSGIDS = ("LIST_APPEND", "LIST_UPDATE")

DISPLAY_HINT_ALLOWED_BY_MSGID: dict[str, set[str]] = {
    "SCALAR_SET": {"badge"},
    "TABLE_DECLARE": {"table", "chart", "cards"},
}

NON_NEGATIVE_FIELD_RULES: dict[str, tuple[str, ...]] = {
    "PROCESS_BEGIN": ("total",),
    "PROCESS_UPDATE": ("total", "current"),
}


class NDJSONEvent(BaseModel):
    """Strict model for a single SCOP NDJSON event.

    Fields mirror `event_base` in `static/NORTH_STAR.yaml` and enforce full compliance
    with the SCOP v0.1.2-draft specification.
    """

    # strict=True prevents implicit type coercions (e.g., bool -> int or int -> str)
    # populate_by_name=True allows programmatic instantiation using 'table_schema'
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        populate_by_name=True,
    )

    # Core Required Fields (§4.2 & §5)
    pri: int = Field(..., description="RFC 5424 PRI — facility*8 + severity")
    msgid: MSGID = Field(..., description="SCOP message identifier")
    room: Optional[str] = Field(..., description="Derived room path or null")
    msg: str = Field(..., description="Human-readable single-line message")

    # Optional Infrastructure Fields (§4.2)
    ts: Optional[datetime] = Field(None, description="ISO 8601 timestamp")
    app: Optional[str] = Field(None, description="Application name")
    pid: Optional[int] = Field(None, description="Process id")

    # Dynamic Vocabulary Fields (§7)
    title: Optional[str] = Field(None, description="PAGE_BEGIN title")
    subtitle: Optional[str] = Field(None, description="PAGE_BEGIN subtitle")
    icon: Optional[str] = Field(None, description="PAGE_BEGIN icon gemoji code")
    intent: Literal["query", "action"] = Field(
        "query", description="PAGE_BEGIN view integration strategy (default: 'query')"
    )

    id: Optional[str] = Field(
        None, description="Identifier for dynamic structural items"
    )
    label: Optional[str] = Field(None, description="Human readable label")
    total: Optional[int] = Field(None, description="Total expected steps or size")
    current: Optional[int] = Field(None, description="Current progress step")
    ok: Optional[bool] = Field(None, description="Process termination success status")
    dry_run: Optional[bool] = Field(
        None, description="Flag indicating mock action execution"
    )
    recursive: Optional[bool] = Field(
        None, description="Flag indicating recursive modifier context"
    )
    force: Optional[bool] = Field(
        None, description="Flag indicating forced modifier context"
    )

    type: Optional[TYPE] = Field(None, description="Abstract scalar value type")
    value: Optional[Any] = Field(
        None, description="Scalar or structural entry value representation"
    )
    unit: Optional[str] = Field(None, description="Display unit denomination")
    display_hint: Optional[str] = Field(
        None, description="Advisory presentation suggestion"
    )

    item_id: Optional[str] = Field(None, description="Unique list element identifier")
    ordered: Optional[bool] = Field(
        None, description="List item sorting configuration indication"
    )

    # Renamed to avoid protected namespace conflicts while targeting the correct JSON key
    table_schema: Optional[List[str]] = Field(
        None, alias="schema", description="Ordered collection of table schema keys"
    )
    row_id: Optional[str] = Field(None, description="Unique table row entity key")
    values: Optional[Dict[str, Any]] = Field(
        None,
        description="Relational data dictionary mapping schema keys to cell values",
    )

    _TEXT_DUPLICATE_FIELDS: ClassVar[tuple[str, ...]] = (
        "id",
        "label",
        "title",
        "subtitle",
        "item_id",
        "row_id",
        "app",
    )

    @field_validator("pri", mode="before")
    @classmethod
    def _validate_pri(cls, v):
        if isinstance(v, bool):
            raise TypeError("pri must be an integer, not a boolean")
        if not isinstance(v, int):
            raise TypeError("pri must be an integer")
        if v < 0:
            raise ValueError("pri must be non-negative")
        if v > 191:
            raise ValueError("pri must be between 0 and 191 inclusive per RFC 5424")
        # SCOP uses facility 16 per spec — enforce facility bits (facility = pri // 8)
        facility = v // 8
        if facility != 16:
            raise ValueError("pri facility must be 16 for SCOP events")
        return v

    @field_validator("msg", mode="before")
    @classmethod
    def _validate_msg(cls, v):
        if not isinstance(v, str):
            raise TypeError("msg must be a string")
        if "\n" in v or "\r" in v:
            raise ValueError("msg must be a single line (no newlines)")
        return v

    @field_validator("pid", mode="before")
    @classmethod
    def _validate_pid(cls, v):
        if v is None:
            return v
        if isinstance(v, bool):
            raise TypeError("pid must be an integer, not a boolean")
        if not isinstance(v, int):
            raise TypeError("pid must be an integer")
        if v < 0:
            raise ValueError("pid must be non-negative")
        return v

    @model_validator(mode="after")
    def _validate_spec_conformance(self) -> NDJSONEvent:
        # 1. Isolate vocabulary fields while converting Python attribute names to JSON aliases
        provided_vocabulary_fields = self._provided_vocabulary_fields()

        core_fields = {"pri", "msgid", "room", "msg", "ts", "app", "pid"}
        provided_vocabulary_fields -= core_fields

        # 2. Map precise structural boundaries (Required, Optional) fields per MSGID family (§7)
        required_fields, optional_fields = MSGID_MAP[self.msgid]
        allowed_fields = required_fields | optional_fields

        # Enforce non-empty fallback rules universally except for PAGE_END (§7.1)
        if self.msgid != "PAGE_END" and self.msg.strip() == "":
            raise ValueError("msg must not be empty")

        # Catch missing keys per dynamic configuration
        missing = required_fields - provided_vocabulary_fields
        if missing:
            raise ValueError(
                f"Missing required fields for {self.msgid}: {sorted(list(missing))}"
            )

        # Catch keys that shouldn't exist for this specific family
        forbidden = provided_vocabulary_fields - allowed_fields
        if forbidden:
            raise ValueError(
                f"Fields {sorted(list(forbidden))} are forbidden for msgid='{self.msgid}'"
            )

        # 3. Contextual Field Verification Rules
        self._validate_page_begin_icon()
        self._validate_non_negative_process_fields()
        self._validate_scalar_set_value_matrix()
        self._validate_display_hint_rules()

        # 4. Dynamic Help-Item Array Serialization Verification (§8.1)
        self._validate_help_item_structure()

        # 5. Prohibit verbatim duplication: `msg` MUST NOT exactly equal
        # other scalar textual fields (id, label, title, subtitle, command, description, item_id, row_id, app)
        for fname in self._TEXT_DUPLICATE_FIELDS:
            val = getattr(self, fname, None)
            if isinstance(val, str) and val == self.msg:
                raise ValueError(f"msg must not verbatim duplicate field '{fname}'")

        # Additionally check help-item inner fields when present
        if (
            self.msgid in ("LIST_APPEND", "LIST_UPDATE")
            and self.id == "help"
            and isinstance(self.value, dict)
        ):
            cmd = self.value.get("command")
            desc = self.value.get("description")
            if isinstance(cmd, str) and cmd == self.msg:
                raise ValueError("msg must not verbatim duplicate help-item 'command'")
            if isinstance(desc, str) and desc == self.msg:
                raise ValueError(
                    "msg must not verbatim duplicate help-item 'description'"
                )

        return self

    def _provided_vocabulary_fields(self) -> set[str]:
        provided_vocabulary_fields: set[str] = set()
        # model_fields is a class-level attribute; access it from the class to avoid
        # Pydantic deprecation warnings about instance-level access.
        cls_fields = type(self).model_fields
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is not None:
                field_info = cls_fields[field_name]
                json_key = field_info.alias if field_info.alias else field_name
                provided_vocabulary_fields.add(json_key)
        return provided_vocabulary_fields

    def _validate_page_begin_icon(self) -> None:
        if self.msgid != "PAGE_BEGIN" or self.icon is None:
            return
        if not (
            self.icon.startswith(":")
            and self.icon.endswith(":")
            and len(self.icon) > 2
            and " " not in self.icon
        ):
            raise ValueError(
                "icon field MUST be a GitHub gemoji code of the form :name:"
            )

    def _validate_non_negative_process_fields(self) -> None:
        field_names = NON_NEGATIVE_FIELD_RULES.get(self.msgid, ())
        for name in field_names:
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")

    def _validate_scalar_set_value_matrix(self) -> None:
        if self.msgid != "SCALAR_SET":
            return

        t, v = self.type, self.value
        if t == "bytes":
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise TypeError(
                    "For type='bytes', value MUST be a non-negative JSON integer absolute byte count"
                )
        elif t == "duration":
            if not isinstance(v, str):
                raise TypeError(
                    "For type='duration', value MUST be an ISO 8601 duration string"
                )
            if not v.startswith("P") or len(v) < 2:
                raise ValueError(
                    "For type='duration', value MUST be a valid ISO 8601 duration string (e.g. 'PT1M30S')"
                )
        elif t == "number":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError("For type='number', value MUST be an integer or float")
        elif t == "string":
            if not isinstance(v, str):
                raise TypeError("For type='string', value MUST be a string")
        elif t == "boolean":
            if not isinstance(v, bool):
                raise TypeError("For type='boolean', value MUST be a boolean")

    def _validate_display_hint_rules(self) -> None:
        if self.display_hint is None:
            return

        allowed = DISPLAY_HINT_ALLOWED_BY_MSGID.get(self.msgid)
        if allowed is None:
            return

        if self.msgid == "SCALAR_SET" and self.display_hint not in allowed:
            raise ValueError(
                "Producers MUST NOT use display_hint values not defined in this spec ('badge')"
            )

        if self.msgid == "TABLE_DECLARE" and self.display_hint not in allowed:
            raise ValueError(
                "display_hint for TABLE_DECLARE must be 'table', 'chart', or 'cards'"
            )

    def _validate_help_item_structure(self) -> None:
        if self.msgid not in HELP_LIST_MSGIDS or self.id != "help":
            return

        if not isinstance(self.value, dict):
            raise TypeError(
                "Help item value must be a structural JSON dictionary object"
            )

        v = self.value
        for req_key in ("command", "description"):
            if req_key not in v or not isinstance(v[req_key], str):
                raise ValueError(
                    f"Help item value missing required string field '{req_key}'"
                )

        if "kind" in v and v["kind"] not in ("action", "group"):
            raise ValueError("Help item 'kind' must be 'action' or 'group'")

        if "params" in v and v["params"] is not None:
            if not isinstance(v["params"], list):
                raise TypeError("Help item 'params' must be an array list")

            current_stage = 0  # 0: positional, 1: required flag, 2: optional flag
            last_name = ""

            for param in v["params"]:
                if not isinstance(param, dict):
                    raise TypeError("Param entry item must be a dictionary object")
                if "name" not in param or not isinstance(param["name"], str):
                    raise ValueError("Param entry missing required string field 'name'")
                if "kind" not in param or param["kind"] not in ("flag", "positional"):
                    raise ValueError("Param 'kind' must be 'flag' or 'positional'")

                if param["kind"] != "flag" and param.get("short") is not None:
                    raise ValueError("Param 'short' is valid for kind='flag' only")

                # Calculate implied or explicit parameter requirements
                p_req = param.get("required", param["kind"] == "positional")

                if param["kind"] == "positional":
                    stage = 0
                elif param["kind"] == "flag" and p_req:
                    stage = 1
                else:
                    stage = 2

                # Strict validation of order matrix rules (§8.1)
                if stage < current_stage:
                    raise ValueError(
                        "Params ordering violation: positionals MUST precede flags; required flags MUST precede optional flags."
                    )
                if stage == current_stage:
                    if param["name"] < last_name:
                        raise ValueError(
                            f"Params sorting violation: within each group, parameters must be alphabetical by name. Overlap found: '{param['name']}' after '{last_name}'."
                        )

                current_stage = stage
                last_name = param["name"]

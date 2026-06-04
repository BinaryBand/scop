from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MarkdownTable(BaseModel):
    """Generic table renderable as a Markdown table via partials/table.md.j2."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    headers: list[str]
    rows: list[list[str]]
    note: str = ""  # optional footnote rendered below the table

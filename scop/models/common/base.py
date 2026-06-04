"""Shared base model for RFC 7841-style document generation.

BaseRFC holds all fields common across documents that follow RFC 7841 boilerplate
(Independent Submission header, Status of This Memo, Copyright, ToC, numbered
sections, Security Considerations, IANA Considerations, References).

Subclasses override `terms`, `principles`, and defaults to specialise for a
specific document. The `conformance_partial` field controls whether a
Conformance section (§C) is rendered; set it to "" to omit it and shift the
trailing section numbers accordingly.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

_Category = Literal["Draft", "Proposed Standard", "Standard"]
_Shortname = Annotated[str, Field(pattern=r"^[A-Z0-9]+$")]
_Version = Annotated[str, Field(pattern=r"^\d+(\.\d+)*$")]


class RFCSection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str
    body: str = ""
    partial: str = ""
    subsections: list[RFCSection] = []


class ToCEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    number: str
    title: str
    anchor: str


class BaseRFC(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    # Document identity
    title: str
    shortname: _Shortname
    version_no: _Version
    status: _Category
    abstract: str = ""
    license: str = "CC0 1.0 Universal (Public Domain)"

    # RFC 7841 header fields
    working_group: str = "Independent Submission"
    author: str = ""
    author_affiliation: str = ""
    category: str = "Informational"
    stream: str = "Independent Submission"
    date: str = ""
    issn: str = "2070-1721"

    # §1 Introduction body; empty string → template renders its own default
    introduction: str = ""

    # Jinja2 partial path for the Conformance section (§C).
    # Set to "" to omit the section; trailing section numbers shift accordingly.
    conformance_partial: str = "partials/conformance.md.j2"

    north_star: Any = {}

    # Subclasses provide domain-specific defaults
    terms: dict[str, str] = {}
    principles: dict[str, str] = {}
    sections: list[RFCSection] = []

    @computed_field
    @property
    def identifier(self) -> str:
        return f"{self.shortname}-v{self.version}"

    @computed_field
    @property
    def version(self) -> str:
        if self.status == "Draft":
            return self.version_no + "-draft"
        return self.version_no

    @computed_field
    @property
    def toc(self) -> list[ToCEntry]:
        A = 3  # Introduction, Terminology, Design Principles
        C = len(self.sections) + A + 1
        conf = bool(self.conformance_partial)
        offset = 1 if conf else 0

        def entry(n: int, title: str) -> ToCEntry:
            # Replicate GitHub anchor generation: strip non-word/space/hyphen chars,
            # then replace each whitespace individually (no collapse — preserves double
            # hyphens from e.g. "em dash" → stripped char leaves two flanking spaces).
            slug = re.sub(r"[^\w\s-]", "", title.lower())
            slug = re.sub(r"\s", "-", slug.strip())
            return ToCEntry(number=str(n), title=title, anchor=f"#{n}-{slug}")

        entries = [
            entry(1, "Introduction"),
            entry(2, "Terminology"),
            entry(3, "Design Principles"),
        ]
        for i, section in enumerate(self.sections, start=A + 1):
            entries.append(entry(i, section.title))
        if conf:
            entries.append(entry(C, "Conformance"))
        entries += [
            entry(C + offset, "Security Considerations"),
            entry(C + offset + 1, "IANA Considerations"),
            entry(C + offset + 2, "References"),
        ]
        return entries

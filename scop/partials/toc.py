from __future__ import annotations

import re
from typing import Any, Dict, List


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"\s", "-", slug.strip())
    return slug


class ToCGenerator:
    """Generate a nested table-of-contents from a BaseRFC instance.

    Produces a list of dicts with keys: `number`, `title`, `anchor`, `children`.
    """

    def __init__(
        self,
        sections: List[Dict[str, Any]] | None = None,
        *,
        start_index: int = 4,
        preamble: List[Dict[str, Any]] | None = None,
    ):
        # sections: list of RFCSection-like dicts (with `title` and optional `subsections`)
        self.sections = sections or []
        self.start_index = start_index
        self.preamble = preamble or []

    @classmethod
    def from_rfc(cls, model: Any) -> "ToCGenerator":
        # BaseRFC reserves 1..3 for intro, terminology, design principles.
        start = 4
        # model.sections is list of RFCSection instances or dicts
        sections = []
        for s in getattr(model, "sections", []) or []:
            # ensure dict-like access
            if hasattr(s, "model_dump"):
                sd = s.model_dump()
            elif isinstance(s, dict):
                sd = s
            else:
                sd = {
                    "title": getattr(s, "title", ""),
                    "subsections": getattr(s, "subsections", []),
                }
            sections.append(sd)

        # preamble entries mirror BaseRFC.toc leading entries (1..3)
        preamble = [
            {"number": "1", "title": "Introduction", "anchor": "#1-introduction"},
            {"number": "2", "title": "Terminology", "anchor": "#2-terminology"},
            {
                "number": "3",
                "title": "Design Principles",
                "anchor": "#3-design-principles",
            },
        ]
        return cls(sections=sections, start_index=start, preamble=preamble)

    def build_nested(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        # start with preamble
        out.extend(self.preamble)

        for idx, sec in enumerate(self.sections, start=self.start_index):
            title = sec.get("title", "")
            number = str(idx)
            anchor = f"#{number}-{_slugify(title)}"
            node: Dict[str, Any] = {
                "number": number,
                "title": title,
                "anchor": anchor,
                "children": [],
            }
            subsections = sec.get("subsections", []) or []
            for sidx, sub in enumerate(subsections, start=1):
                if hasattr(sub, "model_dump"):
                    sd = sub.model_dump()
                elif isinstance(sub, dict):
                    sd = sub
                else:
                    sd = {"title": getattr(sub, "title", "")}
                sub_title = sd.get("title", "")
                sub_number = f"{number}.{sidx}"
                # GitHub-like anchor for subsection: remove dots from numbering
                anchor_num = sub_number.replace(".", "")
                sub_anchor = f"#{anchor_num}-{_slugify(sub_title)}"
                node["children"].append(
                    {
                        "number": sub_number,
                        "title": sub_title,
                        "anchor": sub_anchor,
                        "children": [],
                    }
                )
            out.append(node)

        # trailing entries: Conformance, Security, IANA, References — compute numbers after sections
        c = self.start_index + len(self.sections)
        out.append(
            {
                "number": str(c),
                "title": "Conformance",
                "anchor": f"#{c}-conformance",
                "children": [],
            }
        )
        out.append(
            {
                "number": str(c + 1),
                "title": "Security Considerations",
                "anchor": f"#{c + 1}-security-considerations",
                "children": [],
            }
        )
        out.append(
            {
                "number": str(c + 2),
                "title": "IANA Considerations",
                "anchor": f"#{c + 2}-iana-considerations",
                "children": [],
            }
        )
        out.append(
            {
                "number": str(c + 3),
                "title": "References",
                "anchor": f"#{c + 3}-references",
                "children": [],
            }
        )
        return out

    def as_context(self) -> List[Dict[str, Any]]:
        return self.build_nested()

    def render_md(self) -> str:
        lines: List[str] = []

        def _render(items: List[Dict[str, Any]], level: int = 0) -> None:
            prefix = "  " * level
            for e in items:
                lines.append(f"{prefix}- [{e['number']}. {e['title']}]({e['anchor']})")
                if e.get("children"):
                    _render(e["children"], level + 1)

        _render(self.build_nested())
        return "\n".join(lines)

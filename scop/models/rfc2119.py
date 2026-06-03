from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
)

_Category = Literal["Draft", "Proposed Standard", "Standard"]
_Shortname = Annotated[str, Field(pattern=r"^[A-Z0-9]+$")]
_Version = Annotated[str, Field(pattern=r"^\d+(\.\d+)*$")]


class RFC2119(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str
    working_group: str
    shortname: _Shortname
    version_no: _Version
    status: _Category
    license: str = "CC0 1.0 Universal (Public Domain)"

    @computed_field
    @property
    def identifier(self) -> str:
        return f"{self.shortname}-v{self.version}"

    @computed_field
    @property
    def version(self) -> str:
        version_str = self.version_no
        if self.status == "Draft":
            version_str += "-draft"

        return version_str

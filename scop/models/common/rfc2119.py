# RFC 2119 defines key words (MUST, SHOULD, MAY …).
# The document boilerplate base model lives in base.py; RFC7841 and RFC5424
# are concrete subclasses for the SCOP spec and Syslog Protocol respectively.
from scop.models.common.base import BaseRFC, RFCSection, ToCEntry
from scop.models.common.rfc7841 import RFC7841, RFC7841Section

__all__ = ["BaseRFC", "RFCSection", "ToCEntry", "RFC7841", "RFC7841Section"]

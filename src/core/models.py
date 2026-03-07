"""src/core/models.py — 핵심 Pydantic 모델"""
import re
from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class LawArticle(BaseModel):
    article_id: str
    law_name: str
    article_number: str = ""
    content: str
    sha256: str
    url: AnyHttpUrl
    updated_at: datetime

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_valid(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError("sha256 must be a 64-character hexadecimal string")
        return v.lower()

    @field_validator("content")
    @classmethod
    def content_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class Citation(BaseModel):
    article_id: str
    law_name: str
    article_number: str
    sha256: str
    url: AnyHttpUrl
    updated_at: datetime

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_valid(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError("sha256 must be a 64-character hexadecimal string")
        return v.lower()

    @property
    def short_sha(self) -> str:
        return self.sha256[:8]

    def format(self) -> str:
        date_str = self.updated_at.strftime("%Y-%m-%d")
        return f"[{self.law_name} {self.article_number} · sha:{self.short_sha} · {date_str}]"


class ComplianceStatus(str, Enum):
    COMPLIANT = "compliant"
    VIOLATION = "violation"


class ComplianceReport(BaseModel):
    status: ComplianceStatus
    description: str
    citations: Annotated[list[Citation], Field(min_length=1)]
    recommendation: str = ""

    @property
    def is_compliant(self) -> bool:
        return self.status == ComplianceStatus.COMPLIANT

    @property
    def is_violation(self) -> bool:
        return self.status == ComplianceStatus.VIOLATION

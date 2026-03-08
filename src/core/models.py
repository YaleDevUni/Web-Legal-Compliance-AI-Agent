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
    article_content: str = ""
    # 판례 출처 필드 추가
    case_number: str | None = None
    court: str | None = None
    decision_date: datetime | None = None

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
        if self.case_number:
            return f"[{self.court} {self.case_number} · {self.decision_date.strftime('%Y-%m-%d') if self.decision_date else ''}]"
        return f"[{self.law_name} {self.article_number} · sha:{self.short_sha} · {date_str}]"


class CaseArticle(BaseModel):
    """판례 모델"""
    case_id: str # 판례일련번호
    case_number: str # 사건번호
    case_name: str # 사건명
    court: str # 법원명
    decision_date: datetime # 선고일자
    decision_type: str # 선고유형 (예: 판결)
    ruling_summary: str # 판시사항
    ruling_text: str # 판결요지
    referenced_articles: list[str] = Field(default_factory=list) # 참조조문
    url: AnyHttpUrl
    sha256: str

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_valid(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError("sha256 must be a 64-character hexadecimal string")
        return v.lower()


class LegalAnswer(BaseModel):
    """최종 법률 답변 모델 (ComplianceReport 대체)"""
    question: str
    answer: str # Reasoning 텍스트
    citations: list[Citation] = Field(default_factory=list)
    related_articles: list[str] = Field(default_factory=list) # 그래프 확장 조문 ID
    session_id: str

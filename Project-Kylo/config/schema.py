"""
Pydantic schema definitions for `config/kylo.config.yaml`.

These models provide validation and a typed interface for the rest of the
services.  Extra fields are allowed so the config can evolve without breaking
older deploys, but required fields are validated explicitly.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class CircuitBreakerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_consecutive_failures: int = Field(default=5, ge=1)
    pause_minutes: int = Field(default=30, ge=1)


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = Field(default=False)
    log_level: str = Field(default="INFO", min_length=1)
    timezone: str = Field(default="America/Chicago", min_length=1)
    watch_interval_secs: int = Field(default=300, ge=1)
    watch_jitter_secs: int = Field(default=15, ge=0)
    circuit_breaker: Optional[CircuitBreakerConfig] = None


class GoogleRetryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=5, ge=1)
    base_delay_secs: float = Field(default=1.5, ge=0)
    max_delay_secs: float = Field(default=60.0, ge=0)


class GoogleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_account_json_path: str = Field(min_length=1)
    retry: Optional[GoogleRetryConfig] = None


class CompanyTabs(BaseModel):
    model_config = ConfigDict(extra="allow")

    intake: str = Field(min_length=1)
    output: str = Field(min_length=1)


class SheetCompany(BaseModel):
    model_config = ConfigDict(extra="allow")

    key: str = Field(min_length=1)
    workbook_url: HttpUrl
    tabs: CompanyTabs

    @field_validator("key")
    @classmethod
    def _upper_key(cls, value: str) -> str:
        return value.strip().upper()


class SheetsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    companies: List[SheetCompany] = Field(default_factory=list)


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str = Field(default="xlsx")
    xlsx_path: Optional[str] = None
    promote_on_load: bool = Field(default=False)
    management_workbook_url: Optional[HttpUrl] = None


class CSVProcessorColumns(BaseModel):
    model_config = ConfigDict(extra="allow")

    date: str = Field(min_length=1)
    description: Optional[str] = None
    amount: Optional[str] = None
    company_hint: Optional[str] = None


class CSVProcessorConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    header_rows: int = Field(ge=0, default=1)
    start_row: int = Field(ge=1, default=2)
    columns: Dict[str, str] = Field(default_factory=dict)
    date_formats: List[str] = Field(default_factory=list)


class IntakeConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    method: str = Field(min_length=1)
    company_default: Optional[str] = None
    sheet_name: Optional[str] = None
    extra_tabs: List[str] = Field(default_factory=list)
    csv_processor: Optional[CSVProcessorConfig] = None


class MoverConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    batch_size: int = Field(default=500, ge=1)
    max_retries: int = Field(default=3, ge=0)
    backoff_seconds: float = Field(default=0.2, ge=0)


class RoutingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    mover: MoverConfig = Field(default_factory=MoverConfig)


class SheetsPostingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    apply: bool = Field(default=False)


class PostingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    sheets: SheetsPostingConfig = Field(default_factory=SheetsPostingConfig)
    append_transactions: bool = Field(default=False)


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    global_dsn: str = Field(min_length=1)
    per_company: bool = Field(default=False)
    company_dsns: Dict[str, str] = Field(default_factory=dict)


class IntakeStaticDatesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    header_row: int = Field(ge=0, default=0)
    first_row: int = Field(ge=0, default=0)
    dates: List[str] = Field(default_factory=list)


class KyloConfigModel(BaseModel):
    """Top-level model for kylo.config.yaml."""

    model_config = ConfigDict(extra="allow")

    version: int = Field(default=1)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    google: GoogleConfig
    sheets: SheetsConfig = Field(default_factory=SheetsConfig)
    rules: Optional[RulesConfig] = None
    intake: Optional[IntakeConfig] = None
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    database: DatabaseConfig
    posting: PostingConfig = Field(default_factory=PostingConfig)
    intake_static_dates: Optional[IntakeStaticDatesConfig] = None


__all__ = [
    "CSVProcessorConfig",
    "DatabaseConfig",
    "GoogleConfig",
    "IntakeConfig",
    "IntakeStaticDatesConfig",
    "KyloConfigModel",
    "PostingConfig",
    "RoutingConfig",
    "RuntimeConfig",
    "SheetsConfig",
    "SheetCompany",
]



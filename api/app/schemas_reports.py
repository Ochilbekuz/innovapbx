"""M2b §5 — analitika (S13) sxemalari (m2b-contract.md). `web/src/api/types.ts`
(`ReportsSummary`/`ReportsQueueRow`/`ReportsAgentRow`/`ReportsHourlyRow`/
`ReportsDailyRow`) bilan maydon nomlari AYNAN mos bo'lishi SHART."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSummaryOut(BaseModel):
    from_: str = Field(alias="from")
    to: str
    timezone: str
    total: int
    inbound: int
    outbound: int
    internal: int
    answered: int
    missed: int
    blocked: int
    avg_wait_seconds: int | None
    avg_talk_seconds: int | None
    sla_percent: float | None
    busiest_hour: int | None

    model_config = {"populate_by_name": True}


class ReportQueueRowOut(BaseModel):
    queue_id: str
    name: str
    entered: int
    answered: int
    abandoned: int
    timeout: int
    avg_wait_seconds: int | None
    max_wait_seconds: int | None
    sla_percent: float | None


class ReportQueuesOut(BaseModel):
    items: list[ReportQueueRowOut]


class ReportAgentRowOut(BaseModel):
    extension: str
    name: str
    answered: int
    missed_ring: int
    talk_seconds: int
    avg_talk_seconds: int | None
    login_seconds: int
    pause_seconds: int


class ReportAgentsOut(BaseModel):
    items: list[ReportAgentRowOut]


class ReportHourlyRowOut(BaseModel):
    hour: int
    inbound: int
    answered: int
    missed: int


class ReportHourlyOut(BaseModel):
    items: list[ReportHourlyRowOut]


class ReportDailyRowOut(BaseModel):
    date: str
    total: int
    answered: int
    missed: int


class ReportDailyOut(BaseModel):
    items: list[ReportDailyRowOut]

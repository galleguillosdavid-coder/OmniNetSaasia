"""
Pydantic v2 schemas for OmniNet API Request & Response validation.
Adopted according to the mature library mandate (docs/Auditorias/3.md).
"""

from __future__ import annotations
import time
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class DeviceIdentity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_id: str = Field(..., min_length=4, max_length=64, description="Pseudonymous hardware identifier")
    platform: str = Field(default="windows", description="Host OS platform")
    hostname: Optional[str] = Field(default=None, description="Optional host computer name")
    os_version: Optional[str] = Field(default=None, description="Operating system release string")


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: str = Field(default="healthy")
    version: str = Field(default="2.9.6")
    service: str = Field(default="OmniNet AI Agent Pro")
    timestamp: float = Field(default_factory=time.time)


class SubagentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., min_length=1, description="Subagent identifier (e.g. redes, antivirus, bleachbit)")
    execute: bool = Field(default=False, description="Whether to execute real operations or dry-run")


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execute: bool = Field(default=False, description="Whether to apply changes to network stack")
    profile: Optional[str] = Field(default="balanced", description="Optimization profile: gaming, streaming, balanced")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(..., min_length=1, description="User question or prompt for the assistant")
    device_id: Optional[str] = Field(default=None, description="Client device identifier")
    conversation_id: Optional[str] = Field(default=None, description="Context conversation ID")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)


class LicenseActivationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    license_key: str = Field(..., min_length=1, description="License key string")
    email: Optional[str] = Field(default="", description="Purchaser email address")
    device_id: Optional[str] = Field(default=None, description="Binding hardware ID")


class TelemetryReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    device_id: str = Field(..., min_length=4, max_length=64)
    timestamp: float = Field(default_factory=time.time)
    overall_health: str = Field(default="healthy")
    latency_ms: Optional[float] = Field(default=None)
    packet_loss_pct: Optional[float] = Field(default=0.0)
    jitter_ms: Optional[float] = Field(default=0.0)
    bufferbloat_grade: Optional[str] = Field(default="A")
    wifi_connected: Optional[bool] = Field(default=None)


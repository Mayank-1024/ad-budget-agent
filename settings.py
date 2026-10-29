"""Runtime configuration, read from environment variables.

`get_settings()` re-reads the environment on every call so tests can change
variables with monkeypatch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    agent_model: str
    agent_effort: str
    model_max_tokens: int
    model_timeout_s: float
    model_max_attempts: int
    max_tool_steps: int
    # USD per million tokens, used for the cost numbers in eval reports
    price_input_per_mtok: float
    price_output_per_mtok: float
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_db: str
    database_url: str


def get_settings() -> Settings:
    env = os.environ.get
    return Settings(
        anthropic_api_key=env("ANTHROPIC_API_KEY") or None,
        agent_model=env("AGENT_MODEL", "claude-haiku-5-5"),
        agent_effort=env("AGENT_EFFORT", "medium"),
        model_max_tokens=int(env("MODEL_MAX_TOKENS", "16000")),
        model_timeout_s=float(env("MODEL_TIMEOUT_S", "60")),
        model_max_attempts=int(env("MODEL_MAX_ATTEMPTS", "3")),
        max_tool_steps=int(env("MAX_TOOL_STEPS", "6")),
        # claude-haiku-5-5 list prices (prompts under 100K tokens), 2026-10
        price_input_per_mtok=float(env("PRICE_INPUT_PER_MTOK", "0.10")),
        price_output_per_mtok=float(env("PRICE_OUTPUT_PER_MTOK", "0.50")),
        clickhouse_host=env("CLICKHOUSE_HOST", "localhost"),
        clickhouse_port=int(env("CLICKHOUSE_PORT", "18123")),
        clickhouse_user=env("CLICKHOUSE_USER", "agent"),
        clickhouse_password=env("CLICKHOUSE_PASSWORD", "agent"),
        clickhouse_db=env("CLICKHOUSE_DB", "ads"),
        database_url=env("DATABASE_URL", "postgresql://agent:agent@localhost:55432/agent_state"),
    )

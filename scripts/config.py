"""Load and expose Cadence configuration from cadence.toml."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import tomli


@dataclass
class Config:
    """Cadence configuration."""
    # Vault
    vault_path: str
    google_credentials_path: str  # Path to OAuth2 client secrets JSON

    # Fetch
    cron_hour: int
    max_state_age_hours: int

    # Context
    token_budget: int
    news_max_items: int

    # Agent
    agent_runtime: str  # "claude_api"
    agent_model: str  # "claude-sonnet-4-6"
    agent_max_tokens: int
    planner_prompt_path: str
    negotiation_prompt_path: str

    # API
    api_host: str
    api_port: int
    allowed_origins: list[str]

    # Logging
    log_level: str


def load_config(path: str = "cadence.toml") -> Config:
    """
    Load configuration from TOML file.

    Args:
        path: Path to cadence.toml (default: relative to cwd)

    Returns:
        Config dataclass instance

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If required fields missing
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "rb") as f:
        data = tomli.load(f)

    # Extract sections
    vault_cfg = data.get("vault", {})
    fetch_cfg = data.get("fetch", {})
    context_cfg = data.get("context", {})
    agent_cfg = data.get("agent", {})
    api_cfg = data.get("api", {})
    logging_cfg = data.get("logging", {})

    return Config(
        vault_path=vault_cfg.get("path", "/home/shu/vault"),
        google_credentials_path=vault_cfg.get(
            "google_credentials_path",
            str(Path(vault_cfg.get("path", "/home/shu/vault")) / ".system" / "config" / "google_credentials.json")
        ),
        cron_hour=fetch_cfg.get("cron_hour", 6),
        max_state_age_hours=fetch_cfg.get("max_state_age_hours", 2),
        token_budget=context_cfg.get("token_budget", 2000),
        news_max_items=context_cfg.get("news_max_items", 10),
        agent_runtime=agent_cfg.get("runtime", "claude_api"),
        agent_model=agent_cfg.get("model", "claude-sonnet-4-6"),
        agent_max_tokens=agent_cfg.get("max_tokens", 1500),
        planner_prompt_path=agent_cfg.get("planner_prompt_path", "daily_template.md"),
        negotiation_prompt_path=agent_cfg.get("negotiation_prompt_path", "negotiation_template.md"),
        api_host=api_cfg.get("host", "0.0.0.0"),
        api_port=api_cfg.get("port", 8420),
        allowed_origins=api_cfg.get("allowed_origins", ["http://localhost:8420"]),
        log_level=logging_cfg.get("level", "INFO"),
    )

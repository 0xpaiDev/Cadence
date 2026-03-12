"""Load and expose Cadence configuration from cadence.toml."""

import logging
import logging.handlers
from dataclasses import dataclass
from pathlib import Path

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


def setup_logging(vault_path: str, log_level: str = "INFO") -> None:
    """
    Configure logging with file handlers for vault logs.

    Creates rotating file handlers for both pipeline and API logs.
    Logs are written to vault/.system/logs/{pipeline,api}.log with rotation
    after 1MB (keeping up to 3 backups).

    Args:
        vault_path: Path to the vault directory
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    vault = Path(vault_path)
    logs_dir = vault / ".system" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Clear existing handlers (important for reloads)
    root_logger.handlers.clear()

    # Format: timestamp | level | module | message
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Pipeline log handler
    pipeline_log = logs_dir / "pipeline.log"
    pipeline_handler = logging.handlers.RotatingFileHandler(
        pipeline_log,
        maxBytes=1_000_000,  # 1MB
        backupCount=3,
        encoding="utf-8"
    )
    pipeline_handler.setFormatter(formatter)
    root_logger.addHandler(pipeline_handler)

    # API log handler (also writes to root, captured via logging in api.server)
    api_log = logs_dir / "api.log"
    api_handler = logging.handlers.RotatingFileHandler(
        api_log,
        maxBytes=1_000_000,  # 1MB
        backupCount=3,
        encoding="utf-8"
    )
    api_handler.setFormatter(formatter)
    root_logger.addHandler(api_handler)

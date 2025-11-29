"""Configuration management for Pausarr."""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

DEFAULT_CONFIG = {
    "jellyfin_url": "http://localhost:8096",
    "jellyfin_api_key": "",
    "check_interval": 30,
    "containers": {},  # container_name: {"enabled": bool, "description": str}
    "enabled": True,  # Global enable/disable
}

CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/config.json")


class Config:
    """Thread-safe configuration manager."""

    _instance = None
    _lock = Lock()

    def __new__(cls) -> "Config":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._config_lock = Lock()
        self._config: dict[str, Any] = DEFAULT_CONFIG.copy()
        self._load()
        self._initialized = True

    def _load(self) -> None:
        """Load configuration from file."""
        config_path = Path(CONFIG_PATH)
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    loaded = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._config = {**DEFAULT_CONFIG, **loaded}
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}, using defaults")
                self._config = DEFAULT_CONFIG.copy()
        else:
            # Check for environment variables for initial setup
            self._config = DEFAULT_CONFIG.copy()
            if os.environ.get("JELLYFIN_URL"):
                self._config["jellyfin_url"] = os.environ["JELLYFIN_URL"]
            if os.environ.get("JELLYFIN_API_KEY"):
                self._config["jellyfin_api_key"] = os.environ["JELLYFIN_API_KEY"]
            if os.environ.get("CHECK_INTERVAL"):
                try:
                    self._config["check_interval"] = int(os.environ["CHECK_INTERVAL"])
                except ValueError:
                    pass
            if os.environ.get("CONTAINERS_TO_PAUSE"):
                containers = os.environ["CONTAINERS_TO_PAUSE"].replace(",", " ").split()
                for container in containers:
                    self._config["containers"][container.strip()] = {
                        "enabled": True,
                        "description": "",
                    }
            self._save()

    def _save(self) -> None:
        """Save configuration to file."""
        config_path = Path(CONFIG_PATH)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(config_path, "w") as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        with self._config_lock:
            return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and save."""
        with self._config_lock:
            self._config[key] = value
            self._save()

    def get_all(self) -> dict[str, Any]:
        """Get all configuration values."""
        with self._config_lock:
            return self._config.copy()

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple configuration values and save."""
        with self._config_lock:
            self._config.update(updates)
            self._save()

    def add_container(
        self, name: str, enabled: bool = True, description: str = ""
    ) -> None:
        """Add a container to manage."""
        with self._config_lock:
            self._config["containers"][name] = {
                "enabled": enabled,
                "description": description,
            }
            self._save()

    def remove_container(self, name: str) -> None:
        """Remove a container from management."""
        with self._config_lock:
            self._config["containers"].pop(name, None)
            self._save()

    def set_container_enabled(self, name: str, enabled: bool) -> None:
        """Enable or disable a container."""
        with self._config_lock:
            if name in self._config["containers"]:
                self._config["containers"][name]["enabled"] = enabled
                self._save()

    def get_enabled_containers(self) -> list[str]:
        """Get list of enabled container names."""
        with self._config_lock:
            return [
                name
                for name, settings in self._config["containers"].items()
                if settings.get("enabled", True)
            ]


# Singleton instance
config = Config()

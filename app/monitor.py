"""Session monitoring and container management for Pausarr."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import config
from .docker_manager import docker_manager
from .jellyfin import JellyfinClient

logger = logging.getLogger(__name__)


@dataclass
class MonitorStatus:
    """Current status of the monitor."""

    running: bool = False
    last_check: Optional[datetime] = None
    last_action: Optional[str] = None
    sessions_active: bool = False
    containers_paused: bool = False
    error: Optional[str] = None
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "running": self.running,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_action": self.last_action,
            "sessions_active": self.sessions_active,
            "containers_paused": self.containers_paused,
            "error": self.error,
            "history": self.history[-20:],  # Keep last 20 entries
        }


class SessionMonitor:
    """Monitors Jellyfin sessions and manages container states."""

    MAX_HISTORY = 50

    def __init__(self) -> None:
        self._scheduler: Optional[BackgroundScheduler] = None
        self._status = MonitorStatus()
        self._lock = Lock()
        self._prev_sessions_active = False
        self._jellyfin_client: Optional[JellyfinClient] = None

    @property
    def status(self) -> MonitorStatus:
        """Get current monitor status."""
        with self._lock:
            return self._status

    def _get_jellyfin_client(self) -> JellyfinClient:
        """Get or create Jellyfin client with current config."""
        url = config.get("jellyfin_url", "")
        api_key = config.get("jellyfin_api_key", "")
        if (
            self._jellyfin_client is None
            or self._jellyfin_client.url != url
            or self._jellyfin_client.api_key != api_key
        ):
            self._jellyfin_client = JellyfinClient(url, api_key)
        return self._jellyfin_client

    def _add_history(self, action: str, details: str = "") -> None:
        """Add an entry to the history log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
        }
        self._status.history.append(entry)
        if len(self._status.history) > self.MAX_HISTORY:
            self._status.history = self._status.history[-self.MAX_HISTORY :]

    def _check_sessions(self) -> None:
        """Check Jellyfin sessions and manage containers accordingly."""
        if not config.get("enabled", True):
            return

        with self._lock:
            self._status.last_check = datetime.now()
            self._status.error = None

            # Get Jellyfin client
            client = self._get_jellyfin_client()

            # Check for active sessions
            has_sessions, error = client.has_active_sessions()

            if error:
                self._status.error = error
                logger.warning(f"Jellyfin API error: {error}")
                self._add_history("error", error)
                return

            self._status.sessions_active = has_sessions

            # Get enabled containers
            enabled_containers = config.get_enabled_containers()

            if not enabled_containers:
                return

            # State transition: no sessions -> sessions (pause containers)
            if has_sessions and not self._prev_sessions_active:
                logger.info("User connected to Jellyfin - pausing containers")
                self._add_history("sessions_started", "User connected to Jellyfin")

                results = docker_manager.pause_containers(enabled_containers)
                for name, (success, message) in results.items():
                    if success:
                        logger.info(message)
                    else:
                        logger.warning(message)
                    self._add_history("pause" if success else "pause_failed", message)

                self._status.containers_paused = True
                self._status.last_action = "Paused containers"

            # State transition: sessions -> no sessions (unpause containers)
            elif not has_sessions and self._prev_sessions_active:
                logger.info(
                    "All users disconnected from Jellyfin - unpausing containers"
                )
                self._add_history("sessions_ended", "All users disconnected")

                results = docker_manager.unpause_containers(enabled_containers)
                for name, (success, message) in results.items():
                    if success:
                        logger.info(message)
                    else:
                        logger.warning(message)
                    self._add_history(
                        "unpause" if success else "unpause_failed", message
                    )

                self._status.containers_paused = False
                self._status.last_action = "Unpaused containers"

            self._prev_sessions_active = has_sessions

    def start(self) -> bool:
        """Start the session monitor."""
        with self._lock:
            if self._scheduler is not None and self._scheduler.running:
                return True

            try:
                interval = config.get("check_interval", 30)
                self._scheduler = BackgroundScheduler()
                self._scheduler.add_job(
                    self._check_sessions,
                    trigger=IntervalTrigger(seconds=interval),
                    id="session_check",
                    name="Check Jellyfin Sessions",
                    replace_existing=True,
                )
                self._scheduler.start()
                self._status.running = True
                self._add_history("started", f"Monitor started (interval: {interval}s)")
                logger.info(f"Session monitor started with {interval}s interval")

                # Run an immediate check
                self._scheduler.add_job(
                    self._check_sessions,
                    id="initial_check",
                    name="Initial Session Check",
                )

                return True
            except Exception as e:
                logger.error(f"Failed to start monitor: {e}")
                self._status.error = str(e)
                return False

    def stop(self) -> bool:
        """Stop the session monitor."""
        with self._lock:
            if self._scheduler is None:
                return True

            try:
                self._scheduler.shutdown(wait=False)
                self._scheduler = None
                self._status.running = False
                self._add_history("stopped", "Monitor stopped")
                logger.info("Session monitor stopped")
                return True
            except Exception as e:
                logger.error(f"Failed to stop monitor: {e}")
                self._status.error = str(e)
                return False

    def restart(self) -> bool:
        """Restart the session monitor (to pick up config changes)."""
        self.stop()
        return self.start()

    def force_pause(self) -> dict[str, tuple[bool, str]]:
        """Manually pause all enabled containers."""
        with self._lock:
            enabled_containers = config.get_enabled_containers()
            results = docker_manager.pause_containers(enabled_containers)
            self._status.containers_paused = True
            self._status.last_action = "Force paused containers"
            self._add_history("force_pause", "Manual pause triggered")
            return results

    def force_unpause(self) -> dict[str, tuple[bool, str]]:
        """Manually unpause all enabled containers."""
        with self._lock:
            enabled_containers = config.get_enabled_containers()
            results = docker_manager.unpause_containers(enabled_containers)
            self._status.containers_paused = False
            self._status.last_action = "Force unpaused containers"
            self._add_history("force_unpause", "Manual unpause triggered")
            return results


# Singleton instance
monitor = SessionMonitor()

"""Jellyfin API client for Pausarr."""

from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class JellyfinSession:
    """Jellyfin session information."""

    id: str
    user_name: str
    client: str
    device_name: str
    is_active: bool
    now_playing: Optional[str] = None


class JellyfinClient:
    """Client for Jellyfin API."""

    def __init__(self, url: str, api_key: str) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key

    def _get_headers(self) -> dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"MediaBrowser Token={self.api_key}",
            "Content-Type": "application/json",
        }

    def test_connection(self) -> tuple[bool, str]:
        """Test connection to Jellyfin server."""
        if not self.api_key:
            return False, "API key not configured"
        try:
            response = requests.get(
                f"{self.url}/System/Info",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                info = response.json()
                server_name = info.get("ServerName", "Jellyfin")
                version = info.get("Version", "unknown")
                return True, f"Connected to {server_name} (v{version})"
            elif response.status_code == 401:
                return False, "Authentication failed - check API key"
            else:
                return False, f"Connection failed: HTTP {response.status_code}"
        except requests.exceptions.ConnectionError:
            return False, f"Cannot connect to {self.url}"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Connection error: {e}"

    def get_sessions(self) -> list[JellyfinSession]:
        """Get all sessions from Jellyfin."""
        try:
            response = requests.get(
                f"{self.url}/Sessions",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code != 200:
                return []

            sessions = []
            for session in response.json():
                now_playing = None
                if "NowPlayingItem" in session:
                    item = session["NowPlayingItem"]
                    now_playing = item.get("Name", "Unknown")
                    if item.get("SeriesName"):
                        now_playing = f"{item['SeriesName']} - {now_playing}"

                sessions.append(
                    JellyfinSession(
                        id=session.get("Id", ""),
                        user_name=session.get("UserName", "Unknown"),
                        client=session.get("Client", "Unknown"),
                        device_name=session.get("DeviceName", "Unknown"),
                        is_active=session.get("IsActive", False),
                        now_playing=now_playing,
                    )
                )
            return sessions
        except Exception as e:
            print(f"Error fetching sessions: {e}")
            return []

    def get_active_sessions(self) -> list[JellyfinSession]:
        """Get only active sessions."""
        return [s for s in self.get_sessions() if s.is_active]

    def get_playing_sessions(self) -> list[JellyfinSession]:
        """Get sessions that are currently playing something."""
        return [s for s in self.get_sessions() if s.now_playing]

    def has_active_sessions(self) -> tuple[bool, Optional[str]]:
        """
        Check if there are any active sessions.
        Returns (has_sessions, error_message).
        """
        try:
            response = requests.get(
                f"{self.url}/Sessions",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code != 200:
                return False, f"API error: HTTP {response.status_code}"

            sessions = response.json()
            active_count = sum(1 for s in sessions if s.get("IsActive", False))
            return active_count > 0, None
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to Jellyfin"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Error: {e}"

    def has_playing_sessions(self) -> tuple[bool, Optional[str]]:
        """
        Check if there are any sessions currently playing.
        Returns (has_sessions, error_message).
        """
        try:
            response = requests.get(
                f"{self.url}/Sessions",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code != 200:
                return False, f"API error: HTTP {response.status_code}"

            sessions = response.json()
            playing_count = sum(1 for s in sessions if "NowPlayingItem" in s)
            return playing_count > 0, None
        except requests.exceptions.ConnectionError:
            return False, "Cannot connect to Jellyfin"
        except requests.exceptions.Timeout:
            return False, "Connection timeout"
        except Exception as e:
            return False, f"Error: {e}"

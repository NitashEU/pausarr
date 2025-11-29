"""Docker container management for Pausarr."""

from dataclasses import dataclass
from typing import Optional

import docker
from docker.errors import APIError, NotFound


@dataclass
class ContainerInfo:
    """Container information."""

    name: str
    id: str
    status: str
    image: str
    state: str

    @property
    def is_running(self) -> bool:
        return self.status == "running"

    @property
    def is_paused(self) -> bool:
        return self.status == "paused"


class DockerManager:
    """Manages Docker container operations."""

    def __init__(self) -> None:
        self._client: Optional[docker.DockerClient] = None

    @property
    def client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def test_connection(self) -> tuple[bool, str]:
        """Test Docker connection."""
        try:
            self.client.ping()
            return True, "Connected to Docker"
        except Exception as e:
            return False, f"Docker connection failed: {e}"

    def list_all_containers(self) -> list[ContainerInfo]:
        """List all containers (running, paused, stopped)."""
        try:
            containers = self.client.containers.list(all=True)
            return [
                ContainerInfo(
                    name=c.name,
                    id=c.short_id,
                    status=c.status,
                    image=c.image.tags[0] if c.image.tags else c.image.short_id,
                    state=c.attrs.get("State", {}).get("Status", "unknown"),
                )
                for c in containers
            ]
        except Exception as e:
            print(f"Error listing containers: {e}")
            return []

    def get_container(self, name: str) -> Optional[ContainerInfo]:
        """Get a specific container by name."""
        try:
            c = self.client.containers.get(name)
            return ContainerInfo(
                name=c.name,
                id=c.short_id,
                status=c.status,
                image=c.image.tags[0] if c.image.tags else c.image.short_id,
                state=c.attrs.get("State", {}).get("Status", "unknown"),
            )
        except NotFound:
            return None
        except Exception as e:
            print(f"Error getting container {name}: {e}")
            return None

    def get_container_status(self, name: str) -> str:
        """Get the status of a container."""
        container = self.get_container(name)
        return container.status if container else "not_found"

    def pause_container(self, name: str) -> tuple[bool, str]:
        """Pause a container."""
        try:
            container = self.client.containers.get(name)
            if container.status == "paused":
                return True, f"{name} is already paused"
            if container.status != "running":
                return False, f"{name} is not running (status: {container.status})"
            container.pause()
            return True, f"Paused {name}"
        except NotFound:
            return False, f"Container {name} not found"
        except APIError as e:
            return False, f"Failed to pause {name}: {e}"

    def unpause_container(self, name: str) -> tuple[bool, str]:
        """Unpause a container."""
        try:
            container = self.client.containers.get(name)
            if container.status == "running":
                return True, f"{name} is already running"
            if container.status != "paused":
                return False, f"{name} is not paused (status: {container.status})"
            container.unpause()
            return True, f"Unpaused {name}"
        except NotFound:
            return False, f"Container {name} not found"
        except APIError as e:
            return False, f"Failed to unpause {name}: {e}"

    def pause_containers(self, names: list[str]) -> dict[str, tuple[bool, str]]:
        """Pause multiple containers."""
        results = {}
        for name in names:
            results[name] = self.pause_container(name)
        return results

    def unpause_containers(self, names: list[str]) -> dict[str, tuple[bool, str]]:
        """Unpause multiple containers."""
        results = {}
        for name in names:
            results[name] = self.unpause_container(name)
        return results


# Singleton instance
docker_manager = DockerManager()

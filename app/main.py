"""Main Flask application for Pausarr."""

import logging
import os

from flask import Flask, jsonify, render_template, request

from .config import config
from .docker_manager import docker_manager
from .jellyfin import JellyfinClient
from .monitor import monitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# --- Web Routes ---


@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")


# --- API Routes ---


@app.route("/api/status")
def api_status():
    """Get current monitor status including playback state."""
    status = monitor.status.to_dict()
    status["config_enabled"] = config.get("enabled", True)
    return jsonify(status)


@app.route("/api/config", methods=["GET"])
def api_get_config():
    """Get current configuration."""
    cfg = config.get_all()
    # Don't expose the full API key
    if cfg.get("jellyfin_api_key"):
        cfg["jellyfin_api_key_set"] = True
        cfg["jellyfin_api_key"] = "********"
    else:
        cfg["jellyfin_api_key_set"] = False
    return jsonify(cfg)


@app.route("/api/config", methods=["POST"])
def api_update_config():
    """Update configuration."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Handle API key specially - don't update if it's masked
    if data.get("jellyfin_api_key") == "********":
        del data["jellyfin_api_key"]

    # Validate check_interval
    if "check_interval" in data:
        try:
            data["check_interval"] = int(data["check_interval"])
            if data["check_interval"] < 5:
                data["check_interval"] = 5
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid check_interval"}), 400

    # Update config
    config.update(data)

    # Restart monitor if interval changed
    if "check_interval" in data and monitor.status.running:
        monitor.restart()

    return jsonify({"success": True})


@app.route("/api/containers")
def api_list_containers():
    """List all Docker containers."""
    containers = docker_manager.list_all_containers()
    managed = config.get("containers", {})

    result = []
    for c in containers:
        result.append(
            {
                "name": c.name,
                "id": c.id,
                "status": c.status,
                "image": c.image,
                "managed": c.name in managed,
                "enabled": managed.get(c.name, {}).get("enabled", False),
                "description": managed.get(c.name, {}).get("description", ""),
            }
        )

    return jsonify(result)


@app.route("/api/containers/<name>/manage", methods=["POST"])
def api_manage_container(name: str):
    """Add a container to management."""
    data = request.get_json() or {}
    enabled = data.get("enabled", True)
    description = data.get("description", "")
    config.add_container(name, enabled, description)
    return jsonify({"success": True})


@app.route("/api/containers/<name>/unmanage", methods=["POST"])
def api_unmanage_container(name: str):
    """Remove a container from management."""
    config.remove_container(name)
    return jsonify({"success": True})


@app.route("/api/containers/<name>/toggle", methods=["POST"])
def api_toggle_container(name: str):
    """Toggle container enabled state."""
    containers = config.get("containers", {})
    if name not in containers:
        return jsonify({"error": "Container not managed"}), 404

    current = containers[name].get("enabled", True)
    config.set_container_enabled(name, not current)
    return jsonify({"success": True, "enabled": not current})


@app.route("/api/containers/<name>/pause", methods=["POST"])
def api_pause_container(name: str):
    """Manually pause a container."""
    success, message = docker_manager.pause_container(name)
    return jsonify({"success": success, "message": message})


@app.route("/api/containers/<name>/unpause", methods=["POST"])
def api_unpause_container(name: str):
    """Manually unpause a container."""
    success, message = docker_manager.unpause_container(name)
    return jsonify({"success": success, "message": message})


@app.route("/api/monitor/start", methods=["POST"])
def api_start_monitor():
    """Start the session monitor."""
    success = monitor.start()
    return jsonify({"success": success})


@app.route("/api/monitor/stop", methods=["POST"])
def api_stop_monitor():
    """Stop the session monitor."""
    success = monitor.stop()
    return jsonify({"success": success})


@app.route("/api/monitor/pause-all", methods=["POST"])
def api_force_pause():
    """Force pause all managed containers."""
    results = monitor.force_pause()
    return jsonify(
        {
            "success": all(r[0] for r in results.values()),
            "results": {
                k: {"success": v[0], "message": v[1]} for k, v in results.items()
            },
        }
    )


@app.route("/api/monitor/unpause-all", methods=["POST"])
def api_force_unpause():
    """Force unpause all managed containers."""
    results = monitor.force_unpause()
    return jsonify(
        {
            "success": all(r[0] for r in results.values()),
            "results": {
                k: {"success": v[0], "message": v[1]} for k, v in results.items()
            },
        }
    )


@app.route("/api/jellyfin/test", methods=["POST"])
def api_test_jellyfin():
    """Test Jellyfin connection."""
    data = request.get_json() or {}
    url = data.get("url") or config.get("jellyfin_url", "")
    api_key = data.get("api_key")
    if api_key == "********" or not api_key:
        api_key = config.get("jellyfin_api_key", "")

    client = JellyfinClient(url, api_key)
    success, message = client.test_connection()
    return jsonify({"success": success, "message": message})


@app.route("/api/jellyfin/sessions")
def api_jellyfin_sessions():
    """Get current Jellyfin sessions."""
    url = config.get("jellyfin_url", "")
    api_key = config.get("jellyfin_api_key", "")
    client = JellyfinClient(url, api_key)

    sessions = client.get_sessions()
    return jsonify(
        [
            {
                "id": s.id,
                "user_name": s.user_name,
                "client": s.client,
                "device_name": s.device_name,
                "is_active": s.is_active,
                "now_playing": s.now_playing,
            }
            for s in sessions
        ]
    )


@app.route("/api/docker/test", methods=["POST"])
def api_test_docker():
    """Test Docker connection."""
    success, message = docker_manager.test_connection()
    return jsonify({"success": success, "message": message})


@app.route("/api/enable", methods=["POST"])
def api_enable():
    """Enable Pausarr globally."""
    config.set("enabled", True)
    return jsonify({"success": True})


@app.route("/api/disable", methods=["POST"])
def api_disable():
    """Disable Pausarr globally."""
    config.set("enabled", False)
    return jsonify({"success": True})


def main():
    """Main entry point."""
    logger.info("Starting Pausarr...")

    # Test Docker connection
    success, message = docker_manager.test_connection()
    if success:
        logger.info(f"Docker: {message}")
    else:
        logger.warning(f"Docker: {message}")

    # Test Jellyfin connection if configured
    api_key = config.get("jellyfin_api_key", "")
    if api_key:
        url = config.get("jellyfin_url", "")
        client = JellyfinClient(url, api_key)
        success, message = client.test_connection()
        if success:
            logger.info(f"Jellyfin: {message}")
        else:
            logger.warning(f"Jellyfin: {message}")

    # Start the monitor
    if config.get("enabled", True) and api_key:
        monitor.start()
    else:
        logger.info("Monitor not started - configure Jellyfin API key first")

    # Run Flask app
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "").lower() in ("true", "1", "yes")

    if debug:
        app.run(host="0.0.0.0", port=port, debug=True)
    else:
        from gunicorn.app.base import BaseApplication

        class StandaloneApplication(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            "bind": f"0.0.0.0:{port}",
            "workers": 1,
            "threads": 2,
            "accesslog": "-",
            "errorlog": "-",
            "loglevel": "info",
        }
        StandaloneApplication(app, options).run()


if __name__ == "__main__":
    main()

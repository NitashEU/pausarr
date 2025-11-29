# Pausarr

[![Docker Hub](https://img.shields.io/docker/v/nitasheu/pausarr?label=Docker%20Hub&logo=docker)](https://hub.docker.com/r/nitasheu/pausarr)
[![Docker Pulls](https://img.shields.io/docker/pulls/nitasheu/pausarr)](https://hub.docker.com/r/nitasheu/pausarr)
[![Docker Image Size](https://img.shields.io/docker/image-size/nitasheu/pausarr/latest)](https://hub.docker.com/r/nitasheu/pausarr)
[![Build Status](https://img.shields.io/github/actions/workflow/status/nitasheu/pausarr/docker-publish.yml?branch=main)](https://github.com/nitasheu/pausarr/actions)

Automatically pause Docker containers when media is playing in Jellyfin.

I prefer to let Tdarr transcode whenever but it can slow down Jellyfin if
someone is streaming. Pausarr detects active playback and pauses resource-heavy
containers to keep Jellyfin smooth. Simply browsing Jellyfin won't trigger a pause—only actual media playback will.

Originally written for Tdarr but can now be used with multiple containers.

## Features

- 🎬 Automatically pause containers when media is playing in Jellyfin
- 🔄 Automatically unpause containers when playback stops
- 🌐 Beautiful web interface for configuration and monitoring
- 🐳 Easy Docker deployment with docker-compose
- 📊 Activity log and session monitoring
- ⚡ Manual pause/unpause controls

## Quick Start (Docker Compose)

### Option 1: Use Docker Hub Image (Recommended)

1. Create a `docker-compose.yml` file:
   ```yaml
   services:
     pausarr:
       image: nitasheu/pausarr:latest
       container_name: pausarr
       restart: unless-stopped
       ports:
         - "5000:5000"
       volumes:
         - ./config:/config
         - /var/run/docker.sock:/var/run/docker.sock:ro
       environment:
         - TZ=UTC
   ```

2. Start Pausarr:
   ```bash
   docker compose up -d
   ```

### Option 2: Build from Source

1. Clone the repository:
   ```bash
   git clone https://github.com/nitasheu/pausarr.git
   cd pausarr
   ```

2. Build and start:
   ```bash
   docker compose -f docker-compose.build.yml up -d --build
   ```

3. Open the web interface at `http://localhost:5000`

4. Configure your Jellyfin URL and API key in Settings

5. Add containers to manage by clicking "Add to Pausarr" on any container

## Configuration

### Web Interface

The easiest way to configure Pausarr is through the web interface at `http://localhost:5000`.

- **Settings**: Configure Jellyfin URL, API key, and check interval
- **Containers**: Select which containers to pause when Jellyfin is in use
- **Quick Actions**: Manually pause or unpause all managed containers

### Environment Variables

You can pre-configure Pausarr using environment variables in `docker-compose.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `JELLYFIN_URL` | URL of your Jellyfin server | `http://localhost:8096` |
| `JELLYFIN_API_KEY` | Your Jellyfin API key | (required) |
| `CONTAINERS_TO_PAUSE` | Comma-separated list of containers | (none) |
| `CHECK_INTERVAL` | Seconds between playback checks | `30` |
| `TZ` | Timezone | `UTC` |

Example:
```yaml
services:
  pausarr:
    build: .
    container_name: pausarr
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./config:/config
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      - TZ=America/New_York
      - JELLYFIN_URL=http://jellyfin:8096
      - JELLYFIN_API_KEY=your_api_key_here
      - CONTAINERS_TO_PAUSE=tdarr,sonarr,radarr
      - CHECK_INTERVAL=10
```

### Getting a Jellyfin API Key

1. Log into Jellyfin as an administrator
2. Go to Dashboard → API Keys
3. Click the "+" button to create a new API key
4. Give it a name (e.g., "Pausarr") and click OK
5. Copy the generated API key

## Docker Networking

Pausarr needs access to the Docker socket to manage containers. The socket is mounted as read-only for security.

If your Jellyfin server is also running in Docker, make sure Pausarr can reach it:

```yaml
services:
  pausarr:
    # ... other config ...
    networks:
      - jellyfin_network  # Join Jellyfin's network

networks:
  jellyfin_network:
    external: true
```

## Manual Installation

If you prefer not to use Docker, you can run Pausarr directly:

1. Install Python 3.12+
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   python -m app.main
   ```

## Legacy Script

The original bash script (`pausarr.sh`) is still included for those who prefer a simple systemd service. See the script comments for usage instructions.

## Screenshots

The web interface provides:
- **Dashboard**: Monitor status, sessions, and container states
- **Container Management**: Toggle which containers to auto-pause
- **Session View**: See active Jellyfin sessions in real-time
- **Activity Log**: Track all pause/unpause actions

## API

Pausarr exposes a REST API at `/api/*`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get monitor status |
| `/api/config` | GET/POST | Get or update configuration |
| `/api/containers` | GET | List all Docker containers |
| `/api/containers/<name>/manage` | POST | Add container to Pausarr |
| `/api/containers/<name>/unmanage` | POST | Remove container from Pausarr |
| `/api/containers/<name>/toggle` | POST | Toggle container enabled state |
| `/api/containers/<name>/pause` | POST | Manually pause container |
| `/api/containers/<name>/unpause` | POST | Manually unpause container |
| `/api/monitor/start` | POST | Start the session monitor |
| `/api/monitor/stop` | POST | Stop the session monitor |
| `/api/monitor/pause-all` | POST | Force pause all managed containers |
| `/api/monitor/unpause-all` | POST | Force unpause all managed containers |
| `/api/jellyfin/test` | POST | Test Jellyfin connection |
| `/api/jellyfin/sessions` | GET | Get current Jellyfin sessions |

## GitHub Actions Setup (For Maintainers)

To enable automatic Docker Hub publishing, add these secrets to your GitHub repository:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Add the following repository secrets:
   - `DOCKERHUB_USERNAME`: Your Docker Hub username (`nitasheu`)
   - `DOCKERHUB_TOKEN`: A Docker Hub access token (create at https://hub.docker.com/settings/security)

The workflow will automatically:
- Build and push on every push to `main`/`master`
- Tag releases when you push version tags (e.g., `v1.0.0`)
- Build for both `linux/amd64` and `linux/arm64` platforms
- Update the Docker Hub README automatically

### Creating a Release

```bash
git tag v1.0.0
git push origin v1.0.0
```

This will automatically create Docker images tagged as:
- `nitasheu/pausarr:latest`
- `nitasheu/pausarr:1.0.0`
- `nitasheu/pausarr:1.0`
- `nitasheu/pausarr:1`

## License

Copyright (c) James Plummer <jamesp2001@live.co.uk>

This project is licensed under the MIT license ([LICENSE](./LICENSE) or <http://opensource.org/licenses/MIT>)
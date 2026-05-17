# Docker Setup - Softspace Changelog System

Two separate Odoo 18 instances simulating Sender (Softspace) and Receiver (Client).

## Ports

| Service | Port | URL |
|---------|------|-----|
| Sender Odoo | 8120 | http://localhost:8120 |
| Receiver Odoo | 8130 | http://localhost:8130 |

## Quick Start

```bash
cd docker

# 1. Start all containers
docker-compose up -d

# 2. Install Sender module
docker exec changelog_sender_odoo odoo --stop-after-init -i softspace_changelog_sender -d sender_db

# 3. Install Receiver module
docker exec changelog_receiver_odoo odoo --stop-after-init -i softspace_changelog_receiver -d receiver_db

# 4. Restart both after install
docker-compose restart sender-odoo receiver-odoo
```

## Access

- Sender: http://localhost:8120 (admin / admin)
- Receiver: http://localhost:8130 (admin / admin)

## Test Flow

1. On **Receiver** (8130): Softspace → API Settings → Generate Token → copy
2. On **Sender** (8120): Softspace → Client Endpoints → New:
   - Name: `Docker Client`
   - Domain: `receiver-odoo:8069` (internal Docker network)
   - Use Https: ❌
   - Paste token
   - Check Health → Healthy ✅
3. On **Sender**: Create Project → enable Changelog Push → select client
4. On **Sender**: Create Task → Changelog tab → set version → Publish
5. On **Receiver**: Softspace → Changelogs → verify entry
6. Public page: http://localhost:8130/changelog

## Stop & Cleanup

```bash
# Stop
docker-compose down

# Stop and remove all data
docker-compose down -v
```

## Moving to VPS

1. Copy the `docker/` folder + `softspace_changelog_sender/` + `softspace_changelog_receiver/` to VPS
2. Update `sender.conf` domain if needed
3. Run same `docker-compose up -d` commands
4. Point your domain DNS to VPS IP

#!/usr/bin/env bash
set -euo pipefail

ROOT="/opt/openclaw/workspace-1/projects/twitter-100k-pet"
AUTO="$ROOT/automation"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

CRON_TMP=$(mktemp)
trap 'rm -f "$CRON_TMP"' EXIT

cat > "$CRON_TMP" <<'CRON'
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Twitter content pipeline (main-agent + timer)
0 */2 * * * cd /opt/openclaw/workspace-1/projects/twitter-100k-pet && [ -f automation/.env ] && source automation/.env; /usr/bin/flock -n /tmp/twitter_pipeline.lock timeout 60m python3 automation/run_daily_pipeline.py --mode quick --limit 6 >> logs/pipeline.log 2>&1
30 12,20 * * * cd /opt/openclaw/workspace-1/projects/twitter-100k-pet && [ -f automation/.env ] && source automation/.env; /usr/bin/flock -n /tmp/twitter_pipeline.lock timeout 60m python3 automation/run_daily_pipeline.py --mode deep --limit 10 >> logs/pipeline.log 2>&1
CRON

crontab "$CRON_TMP"
echo "[ok] cron installed"
crontab -l

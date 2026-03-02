# Automation V1 (Main-Agent + Cron)

## What it does
- Fetch hotspots from configured RSS sources
- Fetch direct hot topics from TopHub and Momoyu APIs/pages
- Analyze with grok2api (`grok-3-mini`) first
- Force `stream=false` for grok text calls (this endpoint may 401 on stream=true)
- Retry 3 times on grok failures
- Auto-fallback to Google 3.1 Flash for analysis
- Generate comic images via Google 3.1 Flash image model
- Persist outputs:
  - `data/hotspots/raw/YYYY-MM-DD/HH.json`
  - `data/hotspots/analysis/YYYY-MM-DD/HH.json`
  - `data/hotspots/daily/YYYY-MM-DD.md`
  - `CONTENT_QUEUE/YYYY-MM-DD.md`

## Setup
1. Copy env file:
   ```bash
   cp automation/.env.example automation/.env
   ```
2. Fill `GOOGLE_API_KEY` in `automation/.env`

## Run once
```bash
python3 automation/run_daily_pipeline.py --mode quick --limit 6
```

## Install cron
```bash
bash automation/install_cron.sh
```

## Schedule
- Quick run: every 2 hours
- Deep run: 12:30 and 20:30 daily
- Timeout: each run is capped at 60 minutes (`timeout 60m`)

## Logs
- `logs/pipeline.log`

## Current source status
- ✅ TopHub: usable via HTML (board entry + board detail parsing)
- ✅ Momoyu: usable via `/api/hot/top`
- ⚠️ 360 `api.mse.360.cn`: currently returns `errno=1001` without browser-session params/signature
- ⚠️ AttentionVC article page: dynamic rendering, requires browser network capture to lock final API path

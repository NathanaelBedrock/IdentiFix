# IdentiFix

OSINT web app that aggregates identity data from multiple tools and APIs into a unified investigation pipeline.

**Stack:** FastAPI + uvicorn · Alpine.js + Tailwind CSS (no build step) · vis-network graph

---

## Pipeline

```
Collectors → Correlator → Graph Builder → AI Enricher → HTML Report
```

---

## Supported Input Types

- `username`
- `email`
- `discord_id`
- `twitter_handle`
- `reddit_username`

---

## Collectors

| Category | Tools |
|---|---|
| Python libraries | sherlock, maigret, holehe, socialscan, socid-extractor, exifread, h8mail |
| Subprocess wrappers | blackbird, gitfive, naminter, linkook, sociopath, sharetrace |
| HTTP APIs | saucenao (key required), scylla (public), nametrace |

All collectors are optional — missing tools are skipped automatically.

---

## API

| Method | Route | Description |
|---|---|---|
| POST | `/api/investigations` | Create investigation |
| GET | `/api/investigations/{id}` | Full data |
| GET | `/api/investigations/{id}/events` | SSE stream |
| GET | `/api/investigations/{id}/report` | HTML report |
| GET | `/api/collectors` | Tool availability |

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# maigret (optional, install separately due to dependency conflicts)
pip install maigret --no-deps aiodns aiohttp_socks alive-progress

# Install OSINT tools as needed (all optional)
pip install sherlock-project maigret holehe socialscan socid-extractor h8mail

# blackbird — no PyPI package, install from source
git clone https://github.com/p1ngul1n0/blackbird.git ~/tools/blackbird
pip install -r ~/tools/blackbird/requirements.txt
# add a wrapper to your PATH:
echo '#!/bin/bash\npython ~/tools/blackbird/blackbird.py "$@"' > ~/.local/bin/blackbird && chmod +x ~/.local/bin/blackbird

# gitfive — pipx install requires building from source (no entry point on PyPI)
git clone https://github.com/mxrch/GitFive.git ~/tools/gitfive
pip install build
cd ~/tools/gitfive && python -m build
pipx install ~/tools/gitfive/dist/gitfive-*.whl

# sociopath — Go-based, requires Go
conda install -c conda-forge go          # skip if Go is already installed
go install github.com/codeGROOVE-dev/sociopath/cmd/sociopath@latest


# naminter, linkook, sharetrace — pip installable
pip install naminter linkook sharetrace

# h8mail — pip installable, but PyPI package has a broken import path
pip3 install h8mail

# Configure API keys
cp .env.example .env

# Run
python main.py
# → http://localhost:8000
```

Data is persisted as JSON files in `./data/`.

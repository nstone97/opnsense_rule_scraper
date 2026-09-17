# OPNsense Rule Scraper

Docker service that polls your OPNsense firewall over the API and writes a **Vector enrichment table**: rule id → human-readable name. Vector can then stamp `fw_rule_name` onto `filterlog` events before they hit Loki (or any other sink). Scraper health and rule counts are exposed as Prometheus metrics for VictoriaMetrics.

## Why this endpoint

Do **not** use `/api/firewall/filter/search_rule`. That only returns rules created under **Firewall → Automation**. The rules you edit under **Firewall → Rules** (what almost everyone uses) are invisible there.

This scraper calls:

```
GET /api/diagnostics/firewall/list_rule_ids
```

That reads the **live pf ruleset** and returns the same identifiers OPNsense puts in syslog:

```
filterlog: 102,,,fae559338f65e11c53669fc3642c93c2,igb0,match,pass,out,...
           ^pf @N     ^ rid (join this)           ^ device
```

| Field | In the log | Stable? | Use it as |
| --- | --- | --- | --- |
| `rulenr` (`102`) | CSV field 1 | No — changes when the ruleset is rebuilt | Display only |
| `rid` (`fae559…`) | CSV field 4 | Yes | Vector lookup key |
| `descr` | not in the log | n/a | `fw_rule_name` after enrichment |

## What it writes

Mounted at `/data` (override with `OUTPUT_DIR`):

| File | Purpose |
| --- | --- |
| `opnsense_rules.csv` | Vector file enrichment table (`rid,descr`) |
| `opnsense_interfaces.csv` | Vector table mapping `igb0` → `WAN` |
| `opnsense_rules.json` | Full dump with `fetched_at` for debugging |

Files are written atomically (temp + rename) and only rewritten when the mapping actually changes, so Vector is not bounced on every poll.

HTTP on port 8080:

| Path | Use |
| --- | --- |
| `/health` | JSON scrape status (503 until the first success) |
| `/metrics` | Prometheus text for VictoriaMetrics |
| `/rules.csv` | Same CSV Vector reads from disk |
| `/rules.json` | Same JSON dump |
| `/interfaces.csv` | Interface name table |

## OPNsense setup

1. **System → Access → Users** — create a dedicated user (or use an existing one).
2. Privileges:
   - **Diagnostics: Firewall** (required)
   - **Diagnostics: Interfaces** (for the interface-name table)
   - On some firmware builds `list_rule_ids` is only reachable with **All Pages**. If you get HTTP 403, that is why.
3. Open the user, **API keys → Create**, download the key + secret.
4. Point **System → Settings → Logging / targets** at your Vector syslog listener (UDP 514, application `filter`). RFC5424 is fine.

## Secrets (`.env` is not committed)

Copy the example file and put the real key in **`.env` only**:

```bash
cp .env.example .env
```

`.env`, `.env.local`, and any other `.env.*` file are gitignored. `.env.example` is the only env file that belongs in git, and it must stay dummy values. After you `git init`, confirm with:

```bash
git check-ignore -v .env
```

You want: `.gitignore:1:.env`. If `git add -p` ever offers `.env`, stop — it is not ignored.

## Test against your firewall

1. In OPNsense: **System → Access → Users → your user → API keys → Create**.
2. Edit `.env`:

```bash
OPNSENSE_URL=https://192.168.1.1
OPNSENSE_API_KEY=paste-the-key
OPNSENSE_API_SECRET=paste-the-secret
OPNSENSE_TLS_VERIFY=false
```

3. One scrape, files land in `./data` on this machine (that directory is also gitignored):

```bash
mkdir -p data
docker compose run --rm --no-deps \
  -e RUN_ONCE=true \
  -e OUTPUT_DIR=/data \
  -v "$PWD/data:/data" \
  opnsense-rule-scraper \
  python -m opnsense_rule_scraper --once
```

4. Check it worked:

```bash
head data/opnsense_rules.csv
python3 -m json.tool data/opnsense_rules.json | head
```

You should see `rid,descr` and real rule names. HTTP 403 means the API user is missing **Diagnostics: Firewall** (or **All Pages** on some firmware). TLS errors with a stock OPNsense cert mean `OPNSENSE_TLS_VERIFY` is still `true`.

Leave it running after that (builds from this source tree):

```bash
docker compose up -d --build
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:8080/rules.csv | head
```

One-shot without the local `./data` bind (writes into the compose volume instead):

```bash
docker compose run --rm -e RUN_ONCE=true opnsense-rule-scraper python -m opnsense_rule_scraper --once
```

### Environment

| Variable | Default | Notes |
| --- | --- | --- |
| `OPNSENSE_URL` | required | `https://192.168.1.1` |
| `OPNSENSE_API_KEY` | required | HTTP basic username |
| `OPNSENSE_API_SECRET` | required | HTTP basic password |
| `OPNSENSE_TLS_VERIFY` | `true` | `false` for the default self-signed cert, or a CA file path |
| `OPNSENSE_TIMEOUT` | `30` | seconds |
| `SCRAPE_INTERVAL` | `60` | seconds |
| `OUTPUT_DIR` | `/data` | shared with Vector |
| `HTTP_PORT` | `8080` | health + metrics |
| `INCLUDE_INTERFACES` | `true` | also scrape device → LAN/WAN names |
| `RUN_ONCE` | `false` | scrape once and exit |

## Container image (GHCR)

Every push to `main` (and every `v*` tag) runs GitHub Actions: pytest, then a Docker build that publishes to GitHub Container Registry. No extra secrets — the workflow uses `GITHUB_TOKEN`.

| Tag | When |
| --- | --- |
| `ghcr.io/nstone97/opnsense_rule_scraper:latest` | each push to `main` |
| `ghcr.io/nstone97/opnsense_rule_scraper:sha-<short>` | each push (immutable) |
| `ghcr.io/nstone97/opnsense_rule_scraper:1.2.3` | git tag `v1.2.3` |

The first run creates the package. If `docker pull` asks you to log in, the package is still private: **GitHub → Packages → opnsense_rule_scraper → Package settings → Change visibility → Public**. After that, production can pull with no token.

## Run in production

You only need this repo (or just `docker-compose.yml` + `.env`) and Docker. Do not build on the box:

```bash
git clone https://github.com/nstone97/opnsense_rule_scraper.git
cd opnsense_rule_scraper
cp .env.example .env
# edit .env with the firewall URL and API key
docker compose pull
docker compose up -d
```

`pull` fetches `ghcr.io/nstone97/opnsense_rule_scraper:latest`. `up --build` is only for developing against local source.

To pick up a new image later:

```bash
docker compose pull && docker compose up -d
```

## Vector

`vector/vector.yaml` is a working fragment. The important bits:

```yaml
enrichment_tables:
  opnsense_rules:
    type: file
    file:
      path: /data/opnsense_rules.csv
      encoding: { type: csv }
    schema:
      rid: string
      descr: string
```

```vrl
row, err = get_enrichment_table_record("opnsense_rules", {"rid": .fw_rid})
if err == null {
  .fw_rule_name = row.descr
}
```

Start Vector with `--watch-enrichment-tables` (Vector 0.49+) so CSV updates are picked up without a restart. Share the `rule-data` volume as in `docker-compose.yml`.

Send the JSON payload to Loki. **Do not** put `fw_rule_name` on Loki labels — every distinct rule name becomes a new stream.

VictoriaMetrics: scrape `http://opnsense-rule-scraper:8080/metrics` (or let Vector remote-write it). Useful series:

- `opnsense_rule_scraper_up`
- `opnsense_rule_scraper_rules`
- `opnsense_rule_scraper_last_success_timestamp_seconds`
- `opnsense_rule_scraper_scrapes_total`

## Develop

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

## License

[GPL-3.0](LICENSE)

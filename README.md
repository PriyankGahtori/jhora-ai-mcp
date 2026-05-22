# JHora AI MCP

Automated pipeline to extract Vedic astrology chart data from JHora software and expose it as structured JSON, a REST API, and an MCP server for LLM tool use.

> **Want a full Vedic astrology app in the browser — no install, no signup, no data leaving your device?**
> Check out **[Hora Prakash](https://github.com/PriyankGahtori/hora-prakash)** — free, open-source Jyotish software with birth charts, divisional charts D1–D60, Vimshottari Dasha, transits, Shadbala, and more. Runs entirely in your browser via WebAssembly. **[→ Open Live App](https://priyankgahtori.github.io/hora-prakash/)**

![Demo](demo.gif)

```
Birth details / JHD file
        ↓
jhora_extract.sh          ← entry point
        ↓
extract_param.ahk         ← AHK GUI automation (via Wine)
  • Ctrl+C → chart_data.txt        (planets, panchang, shadbala, AV)
  • Shift+F10 → A → Up → Enter → divisionals.txt  (D1–D144)
        ↓
jhora_parse.py            ← parser
        ↓
scripts/jhora_data/<name>/<timestamp>/
  chart_data.txt          ← raw clipboard (Ctrl+C)
  divisionals.txt         ← raw divisionals text
  parsed.json             ← raw parsed output (~1MB)
  parsed_dev.json         ← clean, abbreviations kept
  parsed_llm.json         ← fully expanded + ASCII charts (~800KB)
  parsed_core.json        ← 15 core bodies, full names (~80KB)
        ↓
  ┌─────────────────┐     ┌──────────────────────┐
  │  server.py      │     │  mcp_server.py        │
  │  REST API :8080 │     │  stdio MCP (7 tools)  │
  └─────────────────┘     └──────────────────────┘
```

---

## Prerequisites

| Software | Version | Purpose |
|----------|---------|---------|
| Wine | any (tested on 11.0) | Run Windows apps on macOS/Linux |
| Jagannatha Hora (JHora) | 8.0+ | Vedic astrology engine |
| AutoHotkey | **v1.x only** (not v2) | GUI automation inside Wine |
| Python | 3.8+ | Parser + servers (stdlib only, no pip) |
| Node.js | 18+ | `jhora_compare.mjs` only (optional) |

---

## Installation

### 1. Wine

**macOS:**
```bash
brew install wine
```

**Linux (Ubuntu/Debian):**
```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install wine
```

**Windows:** Wine not needed — run JHora and AutoHotkey natively. Run `extract_param.ahk` directly via AutoHotkey, then `jhora_parse.py` manually.

Verify: `wine --version` → `wine-11.x` or similar.

### 2. Jagannatha Hora

1. Download Windows installer from **https://www.vedicastrologer.org/jh/**
2. Install via Wine:
   ```bash
   wine JHoraSetup.exe
   ```
3. Accept all defaults → installs to `C:\Program Files (x86)\Jagannatha Hora\`

Verify:
```bash
ls ~/.wine/drive_c/Program\ Files\ \(x86\)/Jagannatha\ Hora/bin/jhora.exe
```

### 3. AutoHotkey v1.x

> **Must be v1.x** — v2 uses different syntax and will not work.

1. Download **AutoHotkey v1.1.x** from **https://www.autohotkey.com/download/1.1/**
2. Install via Wine:
   ```bash
   wine AutoHotkey_1.1.xx.xx_setup.exe
   ```

Verify:
```bash
ls ~/.wine/drive_c/Program\ Files\ \(x86\)/AutoHotkey/AutoHotkey.exe
```

### 4. Python 3

```bash
brew install python3   # macOS
python3 --version      # verify ≥ 3.8
```

No pip installs needed — entire pipeline uses stdlib only.

---

## Quick Start

```bash
# Make executable (first time only)
chmod +x scripts/jhora_extract.sh

# Run with birth details
./scripts/jhora_extract.sh \
  --name "Mahatma Gandhi" \
  --date 1869-10-02 \
  --time 07:45 \
  --lat 21.6333 \
  --lon 69.6 \
  --tz 5.5 \
  --place "Porbandar"

# Run with existing JHD file
./scripts/jhora_extract.sh --jhd ~/.wine/drive_c/Program\ Files\ \(x86\)/Jagannatha\ Hora/data/Vivekananda.jhd

# Find output
ls scripts/jhora_data/
```

Takes ~30 seconds per chart (JHora startup + clipboard extraction).

---

## Extraction Script (`jhora_extract.sh`)

### Mode 1 — Birth details

```bash
./scripts/jhora_extract.sh \
  --name "Chart Name" \
  --date YYYY-MM-DD \
  --time HH:MM \
  --lat DECIMAL_DEGREES \
  --lon DECIMAL_DEGREES \
  --tz DECIMAL_HOURS \
  [--place "City Name"]
```

| Argument | Format | Example | Notes |
|----------|--------|---------|-------|
| `--name` | string | `"Narendra Modi"` | Output folder name |
| `--date` | YYYY-MM-DD | `1950-09-17` | |
| `--time` | HH:MM | `11:00` | Local time |
| `--lat` | decimal | `22.3` | Positive = North |
| `--lon` | decimal | `70.7833` | Positive = East |
| `--tz` | decimal hours | `5.5` | IST = 5.5, UTC = 0 |
| `--place` | string | `"Vadnagar"` | Optional label |

### Mode 2 — Existing JHD file

```bash
./scripts/jhora_extract.sh --jhd "/path/to/Chart.jhd"
```

JHD files bundled with JHora live at:
```
~/.wine/drive_c/Program Files (x86)/Jagannatha Hora/data/
```

### Environment overrides

| Variable | Default | Purpose |
|----------|---------|---------|
| `JHORA_OUT_DIR` | `scripts/jhora_data` | Output directory |
| `WINE_PREFIX` | `~/.wine` | Wine prefix directory |
| `AHK_EXE` | `$WINE_PREFIX/.../AutoHotkey.exe` | AHK executable path |

```bash
WINE_PREFIX=~/.wine-jhora JHORA_OUT_DIR=~/my-charts ./scripts/jhora_extract.sh --jhd "..."
```

---

## AHK Timing Configuration (`extract_param.ahk`)

Timings are configurable at the top of the script. Default values work on a modern machine (~30s total). Increase on slow machines.

| Variable | Default | Purpose | Slow machine |
|----------|---------|---------|-------------|
| `DELAY_KILL` | 2000ms | After killing jhora.exe | — |
| `DELAY_LAUNCH` | 5000ms | JHora startup | 10000–18000 |
| `DELAY_AFTER_WIN` | 2000ms | Settle after window active | — |
| `DELAY_CHART_COPY` | 6000ms | Ctrl+C clipboard copy | 10000–15000 |
| `DELAY_DIV_MENU1` | 1500ms | First context menu open | — |
| `DELAY_DIV_SELECT` | 2000ms | After pressing 'A' | — |
| `DELAY_DIV_MENU2` | 1500ms | Second context menu open | — |
| `DELAY_DIV_COPY` | 2000ms | Divisionals clipboard copy | 8000–10000 |
| `DELAY_CLOSE` | 1000ms | After WinClose | — |

---

## Output JSON Formats

Four JSON files are produced per extraction run. All four contain the same data — format differs by intended consumer.

### `parsed.json` — Raw

Direct output of the parser. Abbreviations kept (e.g. `"Su"`, `"Mo"`, `"Ar"`). Full planet list including all upagrahas, sphutas, and special lagnas.

```json
{
  "name": "Test Chart",
  "extracted_at": "20260522_200659",
  "chart": {
    "birth_info": { "date": "...", "time": "...", "ayanamsa": "..." },
    "planets": {
      "Su": { "longitude": 37.3, "nakshatra": "Krit", "rasi": "Ta", "navamsa": "Pi" }
    },
    "panchang": { "tithi": "...", "nakshatra": "...", "yoga": "..." },
    "karakas":  { "AK": "Ju", "AmK": "Mo", ... },
    "shadbala": { "Su": { "total": 412.5, ... } },
    "ashtakavarga": { "Su": { "Ar": 3, "Ta": 4, ... } }
  },
  "divisionals": {
    "D1": {
      "Lagna": { "sign": "Sc", "deg": 20, "min": 32, "lon": 230.53 },
      "Su":    { "sign": "Ta", "deg": 7,  "min": 18, "lon": 37.3  }
    },
    "D9": { ... },
    "D10": { ... }
  }
}
```

### `parsed_dev.json` — Dev

Clean version for development. Abbreviations kept, AV totals added, consistent structure.

### `parsed_llm.json` — LLM (full)

Fully expanded — all abbreviations replaced with full names, nakshatra lords added, ASCII chart diagrams embedded. Large (~800KB).

```json
{
  "meta": { "name": "Test Chart", "version": "llm" },
  "birth": { "date": "May 22, 2026", "timezone": "5:30:00 (East of GMT)" },
  "planets": {
    "Sun": {
      "longitude": 37.3,
      "sign": "Taurus",
      "sign_degree": "7°18'",
      "nakshatra": "Krittika",
      "nakshatra_lord": "Sun",
      "house": 7,
      "retrograde": false,
      "combust": false
    }
  },
  "divisionals": {
    "D9 (Navamsa)": {
      "Sun": { "sign": "Pisces", "degree": "5°43'", "longitude": 335.7 }
    }
  },
  "charts": {
    "Rasi": "┌────┬────┬────┐\n│    │ Su │    │\n...",
    "Navamsa": "..."
  }
}
```

### `parsed_core.json` — Core ⭐ recommended for LLMs

15 core bodies only (Lagna, 9 grahas, Maandi, Gulika, Hora Lagna, Ghati Lagna, Bhava Lagna). Full names. ~80KB.

```json
{
  "meta": { "name": "Test Chart", "version": "core" },
  "birth": { ... },
  "panchang": { "tithi": { "name": "Sukla Sapthami", "lord": "Saturn", "remaining_pct": 39.28 } },
  "planets": {
    "Lagna":   { "sign": "Scorpio", "sign_degree": "20°32'", "nakshatra": "Jyeshtha", "nakshatra_lord": "Mercury" },
    "Sun":     { "sign": "Taurus",  "sign_degree": "7°18'",  "nakshatra": "Krittika", "nakshatra_lord": "Sun" },
    "Moon":    { ... },
    ...
  },
  "karakas": { "Atmakaraka": "Jupiter", "Amatyakaraka": "Moon", ... },
  "shadbala": { "Sun": { "total": 412.5 }, ... },
  "ashtakavarga": { "Sun": { "Aries": 3, "Taurus": 4, ... } },
  "divisionals": {
    "D1 (Rasi)":      { "Lagna": { "sign": "Scorpio", "degree": "20°32'", "longitude": 230.53 }, ... },
    "D9 (Navamsa)":   { ... },
    "D10 (Dasamsa)":  { ... }
  },
  "dasha": {
    "Moon": {
      "start": "2025-10-15", "end": "2035-10-15",
      "antardashas": {
        "Moon": { "start": "2025-10-15", "end": "2026-06-15" }
      }
    }
  }
}
```

**Core bodies:** Lagna, Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu, Maandi, Gulika, Hora Lagna, Ghati Lagna, Bhava Lagna

---

## REST API Server (`server.py`)

Web UI + REST API. No dependencies beyond Python stdlib.

```bash
python3 scripts/server.py
# → http://localhost:8080
```

### Web UI

Open `http://localhost:8080` — fill form, click Extract Chart, view result in Raw / Dev / LLM / Core × JSON / Tree modes.

### REST Endpoints

All endpoints return JSON with CORS headers.

#### List extracted charts
```
GET /api/charts
```
```json
{ "charts": [{ "id": "Test_Chart", "name": "Test Chart", "extracted_at": "...", "runs": 20 }] }
```

#### Get full chart
```
GET /api/charts/{name}?format=core
```
`format`: `core` (default) | `dev` | `llm` | `raw`

```bash
curl http://localhost:8080/api/charts/Test_Chart
curl http://localhost:8080/api/charts/Test_Chart?format=llm
```

#### Get planets only
```
GET /api/charts/{name}/planets?format=core
```

#### Get single divisional chart
```
GET /api/charts/{name}/divisionals/{chart}?format=core
```
```bash
curl http://localhost:8080/api/charts/Test_Chart/divisionals/D9
curl http://localhost:8080/api/charts/Test_Chart/divisionals/D10
```

#### Get panchang
```
GET /api/charts/{name}/panchang
```

#### Extract new chart (JSON)
```
POST /api/extract
Content-Type: application/json

{
  "name": "Mahatma Gandhi",
  "date": "1869-10-02",
  "time": "07:45",
  "lat": "21.6333",
  "lon": "69.6",
  "tz": "5.5",
  "place": "Porbandar",
  "format": "core"
}
```

---

## MCP Server (`mcp_server.py`)

Stdio JSON-RPC 2.0 server implementing the [Model Context Protocol](https://modelcontextprotocol.io). Lets any MCP-compatible LLM (Claude Desktop, Claude Code, etc.) query and extract charts as native tools.

```bash
python3 scripts/mcp_server.py
```

### Setup — Claude Desktop

Add to `~/.claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jhora": {
      "command": "python3",
      "args": ["/absolute/path/to/scripts/mcp_server.py"]
    }
  }
}
```

Restart Claude Desktop. A hammer icon appears in chat — confirms server connected.

### Available Tools

| Tool | Description |
|------|-------------|
| `list_charts` | List all extracted charts with metadata |
| `get_chart` | Full chart data — format: `core`/`dev`/`llm`/`raw` |
| `get_planets` | Planetary positions only (sign, degree, house, nakshatra) |
| `get_divisional` | Single divisional chart (e.g. D9, D10) |
| `get_panchang` | Tithi, vara, nakshatra, yoga, karana, kalam timings |
| `get_dasha` | Vimshottari dasha tree (3 levels) |
| `summarize_chart` | **Plain-text LLM-friendly summary** — no JSON parsing needed |
| `extract_chart` | Run JHora extraction (~30s), return new chart |

### `summarize_chart` — LLM-friendly output

Returns structured plain text instead of JSON. Ideal for interpretation, follow-up questions, or feeding into prompts directly.

```
=== VEDIC ASTROLOGY CHART: Test Chart ===
Extracted: 2026-05-22T20:06:59

── BIRTH DETAILS ──
  Date                 May 22, 2026
  Time                 8:06:00 pm
  Timezone             5:30:00 (East of GMT)
  Ayanamsa             24-13-32.45

── PANCHANG ──
  Tithi                Sukla Sapthami (lord: Saturn, 39.28% left)
  Nakshatra            Ashlesha (lord: Mercury, 25.6% left)
  Yoga                 Dhruva (lord: Ketu, 45.84% left)
  Sunrise              5:30:27 am

── PLANETARY POSITIONS (Lagna + 9 Grahas + Upagrahas) ──
  Lagna           Scorpio 20°32', nakshatra Jyeshtha (lord: Mercury)
  Sun             Taurus 7°18', nakshatra Krittika (lord: Sun)
  Moon            Cancer 26°35', nakshatra Ashlesha (lord: Mercury)
  ...

── KARAKAS ──
  Atmakaraka                Jupiter
  Amatyakaraka              Moon
  ...

── VIMSHOTTARI DASHA (current + upcoming) ──
  Moon (2025-10-15–2035-10-15)
    └─ Moon (2025-10-15–2026-06-15)
    ...

── D9 (Navamsa) POSITIONS ──
  Lagna           Capricorn 4°49'
  Sun             Pisces 5°43'
  ...
```

Pass `include_divisionals: false` to skip D1/D9/D10 sections (shorter context).

### `extract_chart` — New chart via JHora

```json
{
  "name": "Mahatma Gandhi",
  "date": "1869-10-02",
  "time": "07:45",
  "lat": 21.6333,
  "lon": 69.6,
  "tz": 5.5,
  "place": "Porbandar"
}
```

Takes ~30s. Requires Wine + JHora installed. Returns core format on success.

### Example LLM prompts

> "List my extracted charts"
> "Summarize the Test Chart"
> "What is the D9 navamsa placement of Moon for Test Chart?"
> "Show me the current dasha for Test Chart"
> "Extract a new chart for Swami Vivekananda, born January 12 1863, 6:55am, Kolkata (22.57°N, 88.37°E, IST +5.9)"

---

## Data Coverage

| Section | Bodies / Items |
|---------|---------------|
| `planets` (raw) | 55+ bodies — 9 grahas, Lagna, upagrahas, sphutas, special lagnas |
| `planets` (core) | 15 — Lagna, Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn, Rahu, Ketu, Maandi, Gulika, Hora Lagna, Ghati Lagna, Bhava Lagna |
| `divisionals` | 56 bodies × 24 charts — D1 through D144 |
| `ashtakavarga` | 8 bodies (Su/Mo/Ma/Me/Ju/Ve/Sa/Lagna) × 12 signs |
| `shadbala` | 7 planets — 6-component strength breakdown |
| `dasha` | Vimshottari — 3 levels (maha → antar → pratyantar) |
| `panchang` | Tithi, vara, nakshatra, yoga, karana, hora lord, sunrise/sunset, kalam |
| `charts` (LLM only) | 23 ASCII chart diagrams (Rasi, Navamsa, Bhava, all divisionals) |

---

## Troubleshooting

### `chart_data.txt` is empty
JHora clipboard copy failed — timing issue.

Increase `DELAY_CHART_COPY` in `extract_param.ahk` (try +3000ms). Re-run.

### `divisionals` empty in output
AHK two-step menu sequence failed. Increase `DELAY_DIV_MENU1`, `DELAY_DIV_SELECT`, `DELAY_DIV_COPY`. Re-run.

### JHora opens wrong chart
Stale files in Wine temp. Delete and re-run:
```bash
rm ~/.wine/drive_c/windows/temp/chart_data.txt
rm ~/.wine/drive_c/windows/temp/divisionals.txt
```

### MCP server not showing in Claude Desktop
1. Check `~/.claude/claude_desktop_config.json` — path must be **absolute**
2. Fully quit Claude Desktop (`Cmd+Q`), reopen
3. Check Settings → Developer for error logs

### Wine / AHK not found
```bash
brew install wine
AHK_EXE="/custom/path/AutoHotkey.exe" ./scripts/jhora_extract.sh --jhd "..."
```

---

## Files

| File | Purpose |
|------|---------|
| `jhora_extract.sh` | Main entry point — orchestrates extraction |
| `extract_param.ahk` | AHK GUI automation (synced to Wine temp automatically) |
| `jhora_parse.py` | Parser — clipboard text → 4 JSON formats |
| `server.py` | REST API + web UI server (port 8080) |
| `mcp_server.py` | MCP stdio server for LLM tool use |
| `jhora_compare.mjs` | Compare parsed.json vs SwissEph calculations (optional) |
| `jhora_data/` | Output directory (gitignored, `.gitkeep` preserves dir) |

## Ceefaxstation Tracker (Web)

Public, no-login website + API that visualizes **TX/RX stations** and **links** (lines) between them, driven by the JSON logs in:
- `ceefax/logs_tx/*.json`
- `ceefax/logs_rx/*.json`

### Run the server locally

Install deps:

```bash
python -m pip install -r ceefax/requirements.txt
```

Start the server (default `http://127.0.0.1:8088`):

```bash
python -m ceefaxweb
```

Open:
- `http://127.0.0.1:8088/`

### Configure upload auth (optional but recommended)

Set an upload token on the server:

```bash
set CEEFAXWEB_UPLOAD_TOKEN=your-secret-token
```

### Upload logs (near real-time)

From any machine running `ceefaxstation`, run:

```bash
ceefaxstation upload --server http://127.0.0.1:8088 --grid IO91WM --callsign M7TJF
```

If server enforces token:

```bash
ceefaxstation upload --server http://127.0.0.1:8088 --token your-secret-token --grid IO91WM --callsign M7TJF
```

The uploader:
- Watches `ceefax/logs_tx` and `ceefax/logs_rx`
- Uploads new/changed JSON files
- Stores a local state file at `ceefax/cache/uploader_state.json` to avoid re-uploading

### Maidenhead grids

Stations appear on the map only if the server knows their **Maidenhead grid**.

You can provide it via:
- `ceefaxstation upload --grid <GRID>`
- or add it to `ceefax/radio_config.json` as `"grid": "IO91WM"` (the uploader will pick it up)

### API endpoints

- `GET /api/map?range=24h|7d|30d`
- `GET /api/link?tx=CALL&rx=CALL&range=24h|7d|30d`
- `POST /api/ingest/log`
- `WS /ws` (pushes `{type:"ingested"}` on new log ingestion)



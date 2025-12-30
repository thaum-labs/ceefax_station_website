from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_sample(
    *,
    tx_callsign: str,
    tx_grid: str,
    rx_callsign: str,
    rx_grid: str,
    generated_at: datetime,
    pages: list[str],
    rx_ok_pages: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    tx_id = str(uuid.uuid4())
    tx = {
        "schema": 1,
        "kind": "ceefax_tx_report",
        "tx_id": tx_id,
        "station_callsign": tx_callsign,
        "station_grid": tx_grid,
        "dest_callsign": "CEEFAX",
        "wav_name": f"sample_{tx_callsign}_{generated_at.strftime('%Y%m%d_%H%M%S')}.wav",
        "generated_at": generated_at.isoformat(),
        "loops": 1,
        "page_ids": pages,
        "page_count": len(pages),
        "fragments_total": 0,
        "ui_frames_total": 0,
    }

    pages_decoded: dict[str, Any] = {}
    for pid in rx_ok_pages:
        if "." in pid:
            page, sub = pid.split(".", 1)
            try:
                sub_i = int(sub)
            except ValueError:
                sub_i = 1
        else:
            page, sub_i = pid, 1
        pages_decoded[f"{tx_id}:{pid}"] = {
            "tx_id": tx_id,
            "page": page,
            "subpage": sub_i,
            "title": "Sample",
            "first_complete_rx_s": 1.0,
        }

    rx = {
        "schema": 1,
        "listener_callsign": rx_callsign,
        "listener_grid": rx_grid,
        "dest_filter": "CEEFAX",
        "started_at": _iso(generated_at + timedelta(minutes=1)),
        "station_callsign": tx_callsign,
        "station_grid": tx_grid,
        "tx_id": tx_id,
        "tx_ids_seen": [tx_id],
        "cfx_frames": 0,
        "stations_heard": {tx_callsign: 1},
        "pages_decoded": pages_decoded,
        "decoded_page_count": len(rx_ok_pages),
        "pages_seen_count": len(pages),
        "partial_page_count": max(0, len(pages) - len(rx_ok_pages)),
        "complete_by_progress_count": len(rx_ok_pages),
        "updated_at": _iso(generated_at + timedelta(minutes=2)),
    }

    return (tx, rx)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate sample Ceefaxstation TX/RX logs and optionally ingest into ceefaxweb server.")
    ap.add_argument("--write", action="store_true", help="Write sample logs into ceefax/logs_tx and ceefax/logs_rx.")
    ap.add_argument("--ingest", default=None, help="Server base URL to ingest into, e.g. http://127.0.0.1:8088")
    ap.add_argument("--token", default="", help="Upload token (if server enforces).")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    # 6 stations: 2 transmitting, 4 listening
    # TX stations: M7TJF, G4ABC
    # RX stations: M0XYZ, G8DEF, G9GHI, M1JKL
    samples = [
        # TX -> RX with some loss
        ("M7TJF", "IO91WM", "M0XYZ", "IO83PR"),  # TX1 -> RX1 (receives some pages)
        ("M7TJF", "IO91WM", "G8DEF", "IO92AB"),  # TX1 -> RX2 (receives some pages)
        ("G4ABC", "IO91VW", "G9GHI", "IO93CD"),   # TX2 -> RX3 (receives some pages)
        ("G4ABC", "IO91VW", "M1JKL", "IO94EF"),   # TX2 -> RX4 (receives some pages)
    ]
    
    # Listening-only stations (no reception)
    listening_only = [
        ("G8DEF", "IO92AB"),  # RX2 also listening independently
        ("G9GHI", "IO93CD"),  # RX3 also listening independently
    ]

    pages = ["200", "300", "301", "402", "503", "503.2", "600"]

    root = _repo_root()
    out_tx = root / "ceefax" / "logs_tx"
    out_rx = root / "ceefax" / "logs_rx"

    server = (args.ingest or "").rstrip("/") if args.ingest else None

    for i, (tx_cs, tx_grid, rx_cs, rx_grid) in enumerate(samples):
        gen_at = now - timedelta(hours=1 + i)
        rx_ok = pages[: max(2, len(pages) - (i + 1))]  # progressively worse reception
        tx, rx = build_sample(
            tx_callsign=tx_cs,
            tx_grid=tx_grid,
            rx_callsign=rx_cs,
            rx_grid=rx_grid,
            generated_at=gen_at,
            pages=pages,
            rx_ok_pages=rx_ok,
        )

        if args.write:
            tx_path = out_tx / f"sample_tx_{tx_cs}_{rx_cs}_{gen_at.strftime('%Y%m%d_%H%M%S')}.json"
            rx_path = out_rx / f"sample_rx_{rx_cs}_from_{tx_cs}_{gen_at.strftime('%Y%m%d_%H%M%S')}.json"
            _write_json(tx_path, tx)
            _write_json(rx_path, rx)

        if server:
            ingest_url = server + "/api/ingest/log"
            for payload, source in ((tx, f"sample:{tx_cs}:{rx_cs}:tx"), (rx, f"sample:{tx_cs}:{rx_cs}:rx")):
                body = {
                    "token": args.token,
                    "uploader": {"callsign": "SAMPLE", "grid": "IO91WM"},
                    "source_path": source,
                    "log": payload,
                }
                r = requests.post(ingest_url, json=body, timeout=20)
                r.raise_for_status()
    
    # Create listening-only logs (no reception)
    for rx_cs, rx_grid in listening_only:
        gen_at = now - timedelta(minutes=30)
        rx_listening = {
            "schema": 1,
            "listener_callsign": rx_cs,
            "listener_grid": rx_grid,
            "dest_filter": "CEEFAX",
            "rx_mode": "live",
            "started_at": _iso(gen_at),
            "updated_at": _iso(gen_at + timedelta(minutes=5)),
            "station_callsign": None,
            "tx_id": None,
            "tx_ids_seen": [],
            "cfx_frames": 0,
            "stations_heard": {},
            "pages_decoded": {},  # Empty - just listening
            "decoded_page_count": 0,
            "pages_seen_count": 0,
            "partial_page_count": 0,
            "complete_by_progress_count": 0,
        }
        
        if args.write:
            rx_path = out_rx / f"sample_rx_{rx_cs}_listening_{gen_at.strftime('%Y%m%d_%H%M%S')}.json"
            _write_json(rx_path, rx_listening)
        
        if server:
            ingest_url = server + "/api/ingest/log"
            body = {
                "token": args.token,
                "uploader": {"callsign": rx_cs, "grid": rx_grid},
                "source_path": f"sample:{rx_cs}:listening",
                "log": rx_listening,
            }
            r = requests.post(ingest_url, json=body, timeout=20)
            r.raise_for_status()

    print("Sample data generated.")
    if args.write:
        print(f"Wrote logs to {out_tx} and {out_rx}")
    if server:
        print(f"Ingested into {server}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



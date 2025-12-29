from __future__ import annotations

import sys


_ALIASES: dict[str, str] = {
    # historical aliases -> historical canonical
    "tx": "tx-now",
    "transmit": "tx-now",
    "send": "tx-now",
    "generate": "tx-now",
    "txh": "tx-hourly",
    "tx-hour": "tx-hourly",
    "broadcast": "tx-hourly",
    "rx": "rx-latest",
    "receive": "rx-latest",
    "listen": "rx-latest",
    "rx-file": "rx-wav",
    "rxf": "rx-wav",
    "decode": "rx-wav",
    "viewer": "view",
    "browse": "view",
}


def main(argv: list[str] | None = None) -> int:
    """
    Back-compat shim.

    The preferred CLI is now:
      python -m ceefaxstation ...
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in _ALIASES:
        argv[0] = _ALIASES[argv[0]]

    # Map old commands onto the new ceefaxstation CLI.
    mapped: list[str] = []
    if not argv:
        mapped = ["--help"]
    else:
        cmd = argv[0]
        if cmd == "tx-now":
            # old: tx-now --loops N --callsign CS
            mapped = ["tx", "now", *argv[1:]]
            # translate flag name if used
            if "--loops" in mapped:
                i = mapped.index("--loops")
                mapped[i] = "--carousel-loops"
        elif cmd == "tx-hourly":
            mapped = ["tx", "hourly", *argv[1:]]
        elif cmd == "rx-latest":
            mapped = ["rx", "latest", *argv[1:]]
        elif cmd == "rx-wav":
            # old: rx-wav <wav> --listener ...
            if len(argv) >= 2:
                mapped = ["rx", "file", argv[1], *argv[2:]]
            else:
                mapped = ["rx", "file", *argv[1:]]
        elif cmd == "view":
            mapped = ["debug", "--no-refresh", "--view", *argv[1:]]
        else:
            mapped = argv

    # Import and run the new CLI in-process.
    try:
        from ceefaxstation.__main__ import main as station_main
    except Exception as exc:  # noqa: BLE001
        print(
            "Failed to load new CLI. Try running: python -m ceefaxstation --help\n"
            f"Error: {exc}",
            file=sys.stderr,
        )
        return 2

    # Note: we intentionally don't print noisy warnings here; this shim exists
    # for scripts and old docs.
    return int(station_main(mapped) or 0)


if __name__ == "__main__":
    raise SystemExit(main())


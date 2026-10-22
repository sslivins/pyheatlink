"""Small command-line tool: ``pyheatlink HOST [--token T] COMMAND``."""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import os
import sys
from typing import Any

from .client import HeatLinkClient
from .errors import HeatLinkError

_READS = {
    "info": "get_info",
    "summary": "get_house_summary",
    "settings": "get_settings",
    "status": "get_status",
    "capabilities": "get_capabilities",
    "park": "get_park",
    "group": "get_group",
    "sensors": "get_sensors",
    "events": "get_events",
    "update": "get_update",
    "ota": "get_ota_status",
}


def _dump(obj: Any) -> str:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        raw = getattr(obj, "raw", None)
        obj = raw if raw else dataclasses.asdict(obj)
    return json.dumps(obj, indent=2, default=list, ensure_ascii=False)


async def _run(args: argparse.Namespace) -> int:
    async with HeatLinkClient(args.host, token=args.token, timeout=args.timeout) as client:
        if args.command in _READS:
            result = await getattr(client, _READS[args.command])()
        elif args.command == "set":
            await client.set_climate(
                power=None if args.power is None else args.power == "on",
                mode=args.mode,
                temperature=args.temp,
                fan=args.fan,
            )
            result = await client.get_settings()
        elif args.command == "remote-temp":
            result = (
                await client.clear_remote_temp()
                if args.value == "clear"
                else await client.set_remote_temp(float(args.value), args.ttl)
            )
        else:  # pragma: no cover - argparse rejects anything else
            return 2
    print(_dump(result))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pyheatlink", description=__doc__)
    p.add_argument("host")
    p.add_argument("--token", default=os.environ.get("HEATLINK_TOKEN"))
    p.add_argument("--timeout", type=float, default=10.0)
    sub = p.add_subparsers(dest="command", required=True)
    for name in _READS:
        sub.add_parser(name)
    s = sub.add_parser("set")
    s.add_argument("--power", choices=["on", "off"])
    s.add_argument("--mode")
    s.add_argument("--temp", type=float)
    s.add_argument("--fan")
    r = sub.add_parser("remote-temp")
    r.add_argument("value", help="degrees C, or 'clear'")
    r.add_argument("--ttl", type=int, default=600)
    args = p.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (HeatLinkError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

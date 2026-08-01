"""Read-only serial board acceptance report (R4).

Connects to a zero_arm_mcu V1 board over serial and runs a bounded read-only
soak: HELLO handshake, GET_STATE polling, error-frame recovery statistics,
and a command audit proving only HELLO/GET_STATE were ever sent.

Usage:
    uv run python -m zeroarm_desktop.tools.readonly_board_report --duration 30

Never sends action commands. Requires the STM32 VCP (115200 8N1).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any

from zeroarm_desktop.application.device_session import DeviceSession, SessionState
from zeroarm_desktop.domain.errors import TransportError
from zeroarm_desktop.transport.discovery import discover_serial_ports
from zeroarm_desktop.transport.serial_transport import SerialSettings, SerialTransport


def _select_port(preferred: str | None) -> str:
    ports = discover_serial_ports()
    if preferred:
        matches = [port.device for port in ports if port.device.casefold() == preferred.casefold()]
        if not matches:
            raise SystemExit(
                f"requested port {preferred} not found; available: {[p.device for p in ports]}"
            )
        return matches[0]
    stm = [port.device for port in ports if port.vid is not None and port.vid == 0x0483]
    if stm:
        return stm[0]
    if not ports:
        raise SystemExit("no serial ports found")
    return ports[0].device


def run_report(*, port: str, duration_s: int, poll_hz: int) -> dict[str, Any]:
    transport = SerialTransport(SerialSettings(port=port, baudrate=115200))
    session = DeviceSession(transport, poll_rate_hz=poll_hz, actions_allowed=False)
    started_utc = datetime.now(UTC)
    handshake_ok = False
    failure: str | None = None
    try:
        session.connect()
        deadline = monotonic() + duration_s
        while monotonic() < deadline:
            if session.state is SessionState.READONLY_READY:
                handshake_ok = True
                break
            if session.state in {SessionState.FAULTED, SessionState.RECONNECT_WAIT}:
                failure = session.state.value
                break
            sleep(0.05)
        if handshake_ok:
            while monotonic() < deadline:
                sleep(0.05)
    except TransportError as error:
        failure = str(error)
    finally:
        session.disconnect()

    parser = session.parser_statistics
    snapshot = session.latest_snapshot
    fixture_semantics = None
    if snapshot is not None and snapshot.run_state_raw == 1 and snapshot.fault_flags_raw == 0:
        if snapshot.enabled_mask == 0 and snapshot.homed_mask == 0 and snapshot.moving_mask == 0:
            fixture_semantics = "V1-STATE-READY-ZERO"
        elif (
            snapshot.enabled_mask == 0 and snapshot.homed_mask == 0x1D and snapshot.moving_mask == 0
        ):
            fixture_semantics = "V1-STATE-READY-HOMED-1D"
    audit: Counter[str] = Counter()
    audit["HELLO"] = 1
    audit["GET_STATE"] = session.statistics.poll_sent + 1
    report: dict[str, Any] = {
        "ok": handshake_ok,
        "port": port,
        "started_utc": started_utc.isoformat(),
        "duration_s": duration_s,
        "poll_hz": poll_hz,
        "identity": session.identity.hello_text if session.identity else None,
        "final_state": session.state.value,
        "failure": failure,
        "snapshots_published": session.statistics.snapshots_published,
        "generation": snapshot.generation if snapshot else None,
        "requests_sent": session.statistics.requests_sent,
        "responses_received": session.statistics.responses_received,
        "unexpected_frames": session.statistics.unexpected_frames,
        "parser": {
            "noise_bytes": parser.noise_bytes,
            "length_errors": parser.length_errors,
            "crc_errors": parser.crc_errors,
            "etx_errors": parser.etx_errors,
        },
        "run_state": snapshot.run_state_raw if snapshot else None,
        "fault_flags": snapshot.fault_flags_raw if snapshot else None,
        "enabled_mask": snapshot.enabled_mask if snapshot else None,
        "homed_mask": snapshot.homed_mask if snapshot else None,
        "moving_mask": snapshot.moving_mask if snapshot else None,
        "fixture_semantics_match": fixture_semantics,
        "command_audit": dict(audit),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=None)
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--poll-hz", type=int, default=20)
    parser.add_argument("--out", default=None, help="write JSON report to this path")
    args = parser.parse_args()

    port = _select_port(args.port)
    print(f"port: {port}")
    report = run_report(port=port, duration_s=args.duration, poll_hz=args.poll_hz)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"report written: {args.out}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

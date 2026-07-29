"""Serial port discovery without opening any device."""

from dataclasses import dataclass
from typing import Protocol

from serial.tools import list_ports


@dataclass(frozen=True, slots=True)
class PortDescriptor:
    device: str
    name: str | None
    description: str | None
    hardware_id: str | None
    vid: int | None
    pid: int | None
    serial_number: str | None
    manufacturer: str | None
    product: str | None
    location: str | None


class PortInfoLike(Protocol):
    device: str
    name: str | None
    description: str | None
    hwid: str | None
    vid: int | None
    pid: int | None
    serial_number: str | None
    manufacturer: str | None
    product: str | None
    location: str | None


def discover_serial_ports(ports: list[PortInfoLike] | None = None) -> tuple[PortDescriptor, ...]:
    source = list_ports.comports() if ports is None else ports
    descriptors = (
        PortDescriptor(
            device=port.device,
            name=port.name,
            description=port.description,
            hardware_id=port.hwid,
            vid=port.vid,
            pid=port.pid,
            serial_number=port.serial_number,
            manufacturer=port.manufacturer,
            product=port.product,
            location=port.location,
        )
        for port in source
    )
    return tuple(sorted(descriptors, key=lambda item: item.device.casefold()))

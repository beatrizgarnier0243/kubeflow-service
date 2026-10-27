"""Resolve IANA service names to canonical port and protocol using the OS services file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ServiceInfo:
    """The canonical record for a service entry from the services file."""

    name: str
    port: int
    protocol: str


# We resolve the services file path at import time, once. The location is
# determined by the operating system and does not change during the life of a
# process. Reading it on-demand per call would be wasteful, and deferring
# resolution into the resolver would complicate the public API for no gain.

_SERVICE_FILES = (
    "/etc/services",  # Linux, macOS, most POSIX
    os.path.join(
        os.environ.get("SystemRoot", r"C:\\WINDOWS"),
        "system32",
        "drivers",
        "etc",
        "services",
    ),  # Windows
)


def _find_services_file() -> str:
    for candidate in _SERVICE_FILES:
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError("No services file found in expected system locations")


def _parse_line(line: str) -> Optional[tuple[str, int, str]]:
    """Parse a single services-file line.

    Returns (name, port, protocol) or None for blank/comment lines.
    The IANA services format is: name port/proto aliases # comment
    We deliberately ignore aliases because resolution is by canonical name only.
    """
    stripped = line.split("#", 1)[0].strip()
    if not stripped:
        return None

    parts = stripped.split()
    if len(parts) < 2:
        return None

    name = parts[0].lower()
    port_proto = parts[1]

    if "/" not in port_proto:
        return None

    port_str, proto = port_proto.split("/", 1)
    try:
        port = int(port_str)
    except ValueError:
        return None

    if port < 0 or port > 65535:
        return None

    return name, port, proto.lower()


class ServiceResolver:
    """Load the OS services file once and answer lookups against it."""

    def __init__(self) -> None:
        self._by_name: dict[tuple[str, str], ServiceInfo] = {}
        self._load()

    def _load(self) -> None:
        path = _find_services_file()
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            # An existing file we cannot read is treated as empty so that
            # lookups deterministically return None rather than failing late.
            return

        for raw in lines:
            parsed = _parse_line(raw)
            if parsed is None:
                continue
            name, port, proto = parsed
            key = (name, proto)
            # The services file can list duplicate name/proto pairs; the first
            # occurrence wins, matching the precedent set by libc getservbyname.
            if key not in self._by_name:
                self._by_name[key] = ServiceInfo(
                    name=name, port=port, protocol=proto
                )

    def lookup(self, name: str, protocol: Optional[str] = None) -> Optional[ServiceInfo]:
        """Look up a service by name, optionally filtered by protocol.

        Returns the matching ServiceInfo or None if no entry exists.
        """
        key_name = name.strip().lower()
        if not key_name:
            return None

        if protocol is not None:
            key_proto = protocol.strip().lower()
            if not key_proto:
                return None
            return self._by_name.get((key_name, key_proto))

        # No protocol specified: return the first tcp entry if present,
        # otherwise the first udp entry, otherwise the first of anything.
        # This is our deliberate choice — see README — for unambiguous behavior.
        for preferred in ("tcp", "udp"):
            info = self._by_name.get((key_name, preferred))
            if info is not None:
                return info

        for key, info in self._by_name.items():
            if key[0] == key_name:
                return info

        return None


_resolver: Optional[ServiceResolver] = None


def resolve(name: str, protocol: Optional[str] = None) -> Optional[ServiceInfo]:
    """Module-level convenience wrapper around a lazily-instantiated resolver."""
    global _resolver
    if _resolver is None:
        _resolver = ServiceResolver()
    return _resolver.lookup(name, protocol)

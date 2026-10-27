# kubeflow-service

Resolves IANA service names to their canonical port numbers and protocols using the built-in operating system services file.

```python
from kubeflow_service import resolve, ServiceResolver, ServiceInfo

info = resolve("http", "tcp")
print(info.port, info.protocol)  # 80 tcp

resolver = ServiceResolver()
ssh = resolver.lookup("ssh")
print(ssh.port)  # 22
```

## Why this exists

When you need the canonical port for a named service and cannot afford a dependency on a network call or a vendored data table, the OS ships a perfectly good source: `/etc/services` on POSIX systems and `C:\WINDOWS\system32\drivers\etc\services` on Windows. This library reads that file once and answers lookups against it.

The trade-off is that the file reflects whatever the local operating system ships, so results are only as accurate as the host. On a typical Linux or macOS machine the IANA data is complete and current; on a stripped container it may be absent, in which case `resolve` raises `FileNotFoundError`. We treat that as an environment failure rather than a lookup miss.

## Exports

- `resolve(name: str, protocol: str | None = None) -> ServiceInfo | None` — module-level convenience function.
- `ServiceResolver` — instantiates once, loads the services file, and exposes `.lookup(name, protocol)`.
- `ServiceInfo` — frozen dataclass with fields `name`, `port`, `protocol`.

## The awkward edge

When you call `resolve("http")` without specifying a protocol, the services file lists both `http 80/tcp` and `http 80/udp`. This library resolves the ambiguity by preferring tcp, then udp, then whatever else appears. That is a deliberate, fixed choice. If you need a specific protocol, pass it explicitly: `resolve("http", "udp")`.

from __future__ import annotations

import socket
from collections.abc import Callable
from ipaddress import IPv4Address, IPv6Address, ip_address
from urllib.parse import urlsplit


class APIBasePolicyError(ValueError):
    """An API Base violates the configured outbound network policy."""


Resolver = Callable[..., list[tuple]]


def _reject(message: str) -> None:
    raise APIBasePolicyError(message)


def _is_public_address(value: str) -> bool:
    try:
        address = ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    return address.is_global


def _resolve_public_addresses(host: str, port: int, resolver: Resolver) -> None:
    try:
        entries = resolver(host, port, type=socket.SOCK_STREAM)
    except (OSError, socket.gaierror) as exc:
        raise APIBasePolicyError("API Base 域名无法解析，公开 Demo 已拒绝该地址") from exc
    addresses = [str(entry[4][0]) for entry in entries if len(entry) > 4 and entry[4]]
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise APIBasePolicyError("公开 Demo 只允许解析到公网地址的 API Base")


def validate_api_base(
    value: str,
    *,
    block_private: bool = False,
    resolver: Resolver | None = None,
) -> str:
    """Validate and normalize an OpenAI-compatible API Base.

    Local mode performs syntax validation only so a developer can use a local
    Ollama-compatible endpoint. Public-demo mode additionally rejects obvious
    local hostnames/IP literals and checks every DNS result with a resolver.
    The latter is a configuration-time guard; production deployment still needs
    network egress policy to prevent DNS rebinding outside the application.
    """

    if not isinstance(value, str):
        _reject("API Base 必须是 URL")
    clean = value.strip().rstrip("/")
    if not clean:
        _reject("API Base 不能为空")
    try:
        parsed = urlsplit(clean)
        port = parsed.port
    except ValueError as exc:
        raise APIBasePolicyError("API Base 的端口格式无效") from exc
    if parsed.scheme.lower() not in {"http", "https"}:
        _reject("API Base 只支持 http 或 https")
    if not parsed.hostname:
        _reject("API Base 必须包含主机名")
    if parsed.username or parsed.password:
        _reject("API Base 不允许在 URL 中嵌入用户名或密码")
    if parsed.query or parsed.fragment:
        _reject("API Base 不允许包含 query 或 fragment")
    if not block_private:
        return clean

    host = parsed.hostname.rstrip(".").lower()
    blocked_names = {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }
    blocked_suffixes = (".localhost", ".local", ".internal", ".home.arpa")
    if host in blocked_names or host.endswith(blocked_suffixes):
        _reject("公开 Demo 不允许使用本机或内部主机名作为 API Base")

    try:
        literal = ip_address(host)
    except ValueError:
        literal = None
    if isinstance(literal, (IPv4Address, IPv6Address)):
        if not literal.is_global:
            _reject("公开 Demo 不允许使用私网、回环或链路本地 API Base")
    else:
        _resolve_public_addresses(host, port or (443 if parsed.scheme.lower() == "https" else 80), resolver or socket.getaddrinfo)
    return clean

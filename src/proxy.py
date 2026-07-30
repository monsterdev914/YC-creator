from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT, _env_bool

DEFAULT_PROXY_FILE = ROOT / "proxy.txt"


@dataclass(frozen=True)
class ProxyEndpoint:
    host: str
    port: int
    username: str = ""
    password: str = ""

    @property
    def server(self) -> str:
        return f"http://{self.host}:{self.port}"

    def as_playwright(self) -> dict:
        cfg: dict = {"server": self.server}
        if self.username:
            cfg["username"] = self.username
            cfg["password"] = self.password
        return cfg

    def label(self) -> str:
        user = f"{self.username}@" if self.username else ""
        return f"{user}{self.host}:{self.port}"


def proxy_enabled() -> bool:
    return _env_bool("PROXY_ENABLED", default=False)


def proxy_file_path() -> Path:
    raw = os.getenv("PROXY_FILE", "proxy.txt").strip() or "proxy.txt"
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def parse_proxy_line(line: str) -> ProxyEndpoint | None:
    """
    Supported formats:
      host:port:username:password
      host:port
      http://user:pass@host:port
      user:pass@host:port
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if "://" in line:
        # http://user:pass@host:port
        without_scheme = line.split("://", 1)[1]
        if "@" in without_scheme:
            auth, hostport = without_scheme.rsplit("@", 1)
            username, password = auth.split(":", 1) if ":" in auth else (auth, "")
            host, port_s = hostport.rsplit(":", 1)
            return ProxyEndpoint(host, int(port_s), username, password)
        host, port_s = without_scheme.rsplit(":", 1)
        return ProxyEndpoint(host, int(port_s))

    if "@" in line:
        auth, hostport = line.rsplit("@", 1)
        username, password = auth.split(":", 1) if ":" in auth else (auth, "")
        host, port_s = hostport.rsplit(":", 1)
        return ProxyEndpoint(host, int(port_s), username, password)

    parts = line.split(":")
    if len(parts) == 2:
        return ProxyEndpoint(parts[0], int(parts[1]))
    if len(parts) >= 4:
        host, port_s, username = parts[0], parts[1], parts[2]
        password = ":".join(parts[3:])
        return ProxyEndpoint(host, int(port_s), username, password)

    raise ValueError(f"Unrecognized proxy format: {line!r}")


def load_proxies(path: Path | None = None) -> list[ProxyEndpoint]:
    path = path or proxy_file_path()
    if not path.exists():
        raise FileNotFoundError(f"Proxy file not found: {path}")

    proxies: list[ProxyEndpoint] = []
    for index, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            parsed = parse_proxy_line(raw)
        except ValueError as exc:
            raise ValueError(f"{path}:{index}: {exc}") from exc
        if parsed:
            proxies.append(parsed)

    if not proxies:
        raise ValueError(f"No proxies found in {path}")
    return proxies


class ProxyPool:
    """Round-robin (optional shuffle) proxy pool for per-account contexts."""

    def __init__(self, proxies: list[ProxyEndpoint], shuffle: bool = True):
        self._proxies = list(proxies)
        if shuffle:
            random.shuffle(self._proxies)
        self._index = 0

    def next(self) -> ProxyEndpoint:
        if not self._proxies:
            raise RuntimeError("Proxy pool is empty")
        proxy = self._proxies[self._index % len(self._proxies)]
        self._index += 1
        return proxy

    def __len__(self) -> int:
        return len(self._proxies)


def get_proxy_pool() -> ProxyPool | None:
    if not proxy_enabled():
        return None
    return ProxyPool(load_proxies())


def context_options(proxy: ProxyEndpoint | None = None) -> dict:
    """kwargs for browser.new_context(...)."""
    opts: dict = {}
    if proxy is not None:
        opts["proxy"] = proxy.as_playwright()
    return opts

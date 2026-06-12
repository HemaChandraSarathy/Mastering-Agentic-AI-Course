"""Resolve a host via DNS-over-HTTPS and pin it for this process.

Workaround for a local resolver that times out on a host the rest of the internet resolves
fine (e.g. a brand-new Supabase project behind Cloudflare, on a flaky router DNS). We fetch
the A record over HTTPS to Cloudflare 1.1.1.1 (whose cert covers the IP, so it validates
without needing DNS), then monkeypatch socket.getaddrinfo so connections to `host` go to that
IP. TLS SNI still uses the real hostname, so certificate validation is unaffected.

No admin, no system DNS change — scoped to this Python process only.
"""
from __future__ import annotations

import json
import socket
import ssl
import urllib.request

# Cloudflare IPs that resolved this project from public DNS — fallback if DoH fails.
_FALLBACK = ["172.64.149.246", "104.18.38.10"]
_pinned: set[str] = set()


def _doh_resolve(host: str) -> list[str]:
    url = f"https://1.1.1.1/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
        data = json.load(r)
    return [a["data"] for a in data.get("Answer", []) if a.get("type") == 1]


def pin_host(host: str) -> str | None:
    """Pin `host` to an IP (via DoH, else fallback) by patching socket.getaddrinfo.

    Always pins via DoH rather than trusting the local resolver — the router DNS here is
    intermittent, and relying on it caused the connection to break when DNS dropped mid-session.
    Idempotent (only pins once per host per process).
    """
    if host in _pinned:
        return None

    ips = []
    try:
        ips = _doh_resolve(host)
    except Exception:
        ips = []
    if not ips:
        ips = _FALLBACK
    ip = ips[0]

    _orig = socket.getaddrinfo

    def _patched(h, *args, **kwargs):
        return _orig(ip if h == host else h, *args, **kwargs)

    socket.getaddrinfo = _patched
    _pinned.add(host)
    return ip

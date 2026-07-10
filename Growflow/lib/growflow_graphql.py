"""
HTTP client for the GrowFlow GraphQL API.

Credentials file (text): key/value lines, JSON object, or a single-line bearer token.

Environment (optional):
- GROWFLOW_ACCESS_TOKEN — bearer token (skips OAuth)
- GROWFLOW_GRAPHQL_URL — full GraphQL POST URL (overrides retail org URL below)
- GROWFLOW_RETAIL_ORG — organization slug for **Retail** GraphQL:
  `https://retail.growflow.com/c/<org>/graphql` (see partner doc `Growflow Retail GraphQL API Documentation.txt`)
- GROWFLOW_TOKEN_URL — default `https://token.growflow.com/oauth/token` (GrowFlow partner OAuth)
- GROWFLOW_OAUTH_AUDIENCE — default `https://growflow.com` when unset (same doc); override via env or `audience:` in creds file
- GROWFLOW_CONNECT_IP — **when DNS fails or name is internal-only**, connect to this IPv4
  but keep TLS SNI + Host header from the URL (e.g. get IP from `nslookup api.growflow.app`
  on a machine/VPN where the name resolves).
- GROWFLOW_HTTP_USER_AGENT — optional; default is a Chrome-like UA (some CDNs block script clients with 403)
- GROWFLOW_DISABLE_DOH — set to 1 to skip DNS-over-HTTPS fallback
- SSL_CERT_FILE — standard OpenSSL env; we also use **certifi** when installed (fixes many
  Windows / sandbox TLS “unable to get local issuer certificate” cases).

Cursor / sandbox note: if `getaddrinfo` fails, we try **Cloudflare DNS-over-HTTPS to 1.1.1.1**
(by IP + SNI) to resolve A records. If the hostname is **not** on public DNS (NXDOMAIN),
set GROWFLOW_CONNECT_IP from a working PC or VPN.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# Retail GraphQL uses /c/<org>/graphql. Without GROWFLOW_RETAIL_ORG or GROWFLOW_GRAPHQL_URL, callers must set one.
DEFAULT_GRAPHQL_URL = "https://api.growflow.app/graphql"
DEFAULT_TOKEN_URL = "https://token.growflow.com/oauth/token"
# Partner docs: POST token.growflow.com with audience=https://growflow.com (client_credentials).
DEFAULT_OAUTH_AUDIENCE = "https://growflow.com"

# Retail CDN may reject requests with Python's default urllib User-Agent.
_DEFAULT_HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 GrowflowScript/1"
)

# Cloudflare DNS-over-HTTPS (connect to 1.1.1.1 by address; SNI for certificate verify)
_DOH_IP = "1.1.1.1"
_DOH_SNI = "cloudflare-dns.com"
_DOH_HOST = "cloudflare-dns.com"


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _build_https_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ssl_context()))


def _is_gaierror(err: BaseException) -> bool:
    if isinstance(err, socket.gaierror):
        return True
    if isinstance(err, OSError) and getattr(err, "errno", None) in (11001, 8, -2):
        return True
    cause = getattr(err, "__cause__", None)
    if cause is not None:
        return _is_gaierror(cause)
    if isinstance(err, urllib.error.URLError) and err.reason is not None:
        return _is_gaierror(err.reason)
    return False


def doh_lookup_ipv4(hostname: str, timeout: float = 15.0) -> str | None:
    """
    Resolve A record via Cloudflare DoH, without using the system stub resolver.
    Returns None if NXDOMAIN or no A record.
    """
    hostname = hostname.strip().rstrip(".")
    if not hostname:
        return None
    path = f"/dns-query?name={urllib.parse.quote(hostname)}&type=A"
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {_DOH_HOST}\r\n"
        f"Accept: application/dns-json\r\n"
        f"Connection: close\r\n\r\n"
    ).encode("ascii")
    ctx = _ssl_context()
    sock = socket.create_connection((_DOH_IP, 443), timeout=timeout)
    try:
        ssock = ctx.wrap_socket(sock, server_hostname=_DOH_SNI)
        ssock.sendall(req)
        buf = b""
        while True:
            chunk = ssock.recv(8192)
            if not chunk:
                break
            buf += chunk
    finally:
        try:
            sock.close()
        except OSError:
            pass
    m = re.search(br"\r\n\r\n", buf)
    if not m:
        return None
    try:
        payload = json.loads(buf[m.end() :].decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if payload.get("Status") != 0:
        return None
    for ans in payload.get("Answer") or []:
        if ans.get("type") == 1 and ans.get("data"):
            return str(ans["data"]).strip()
    return None


def _parse_https_url(url: str) -> tuple[str, int, str]:
    p = urllib.parse.urlparse(url)
    host = p.hostname or ""
    port = p.port or 443
    path = p.path or "/"
    if p.query:
        path = path + "?" + p.query
    return host, port, path


def https_request(
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 300.0,
) -> tuple[int, bytes]:
    """
    HTTPS with certifi context. On getaddrinfo failure, tries DoH then optional
    GROWFLOW_CONNECT_IP for the URL's hostname.
    """
    host, port, path = _parse_https_url(url)
    if not host:
        raise ValueError(f"Invalid URL: {url}")
    hdrs = {k: v for k, v in (headers or {}).items()}
    connect_ip = (os.environ.get("GROWFLOW_CONNECT_IP") or os.environ.get("GROWFLOW_RESOLVE_IPV4") or "").strip()

    def via_resolved(ip: str) -> tuple[int, bytes]:
        conn = http.client.HTTPSConnection(
            ip,
            port,
            timeout=timeout,
            context=_ssl_context(),
            server_hostname=host,
        )
        try:
            h2 = dict(hdrs)
            h2.setdefault("Host", host if port == 443 else f"{host}:{port}")
            conn.request(method, path, body=data, headers=h2)
            resp = conn.getresponse()
            body = resp.read()
            return resp.status, body
        finally:
            conn.close()

    if connect_ip:
        status, body = via_resolved(connect_ip)
        return status, body

    opener = _build_https_opener()
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.getcode() or 200, resp.read()
    except urllib.error.URLError as e:
        if not _is_gaierror(e) or os.environ.get("GROWFLOW_DISABLE_DOH") == "1":
            raise
        ip = doh_lookup_ipv4(host)
        if not ip:
            raise RuntimeError(
                f"DNS failed for {host!r} and Cloudflare DoH returned no A record (NXDOMAIN or empty). "
                f"Confirm GROWFLOW_GRAPHQL_URL (default is api.growflow.app). On a PC/VPN where the name works, run: nslookup {host}  then set "
                f"GROWFLOW_CONNECT_IP=<that IPv4> and retry."
            ) from e
        status, body = via_resolved(ip)
        return status, body


def _parse_credentials_file(path: str) -> dict[str, str]:
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    stripped = raw.strip()
    if stripped.startswith("{"):
        data = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError("Credentials JSON must be an object")
        return {str(k).lower().replace(" ", "_"): str(v) for k, v in data.items()}

    kv: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            key = k.strip().lower().replace(" ", "_")
            kv[key] = v.strip()
    if not kv and stripped and ":" not in stripped:
        return {"access_token": stripped}
    return kv


def _client_credentials_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    *,
    audience: str | None = None,
) -> str:
    form: dict[str, str] = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    aud = (audience or "").strip()
    if aud:
        form["audience"] = aud
    body = urllib.parse.urlencode(form).encode("utf-8")
    hdrs = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        status, resp_body = https_request("POST", token_url, data=body, headers=hdrs, timeout=120.0)
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:500]
        except OSError:
            pass
        raise RuntimeError(
            f"OAuth request failed: HTTP {e.code} {e.reason}. Body: {detail!r}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"OAuth request failed: {e}") from e

    if status >= 400:
        raise RuntimeError(f"OAuth token HTTP {status}: {resp_body[:500]!r}")
    try:
        payload = json.loads(resp_body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OAuth response not JSON: {resp_body[:300]!r}") from e
    token = payload.get("access_token")
    if not token:
        raise RuntimeError(f"OAuth response missing access_token: {payload!r}")
    return str(token)


def resolve_access_token(credentials_path: str | None) -> str:
    env_tok = (os.environ.get("GROWFLOW_ACCESS_TOKEN") or "").strip()
    if env_tok:
        return env_tok
    if not credentials_path:
        raise ValueError("credentials_path or GROWFLOW_ACCESS_TOKEN is required")
    p = Path(credentials_path)
    if not p.is_file():
        raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
    kv = _parse_credentials_file(str(p))
    if kv.get("access_token"):
        return kv["access_token"].strip()
    if kv.get("bearer"):
        return kv["bearer"].strip()
    cid = (kv.get("client_id") or kv.get("clientid") or "").strip()
    csec = (kv.get("client_secret") or kv.get("clientsecret") or "").strip()
    if cid and csec:
        token_url = (
            (os.environ.get("GROWFLOW_TOKEN_URL") or "").strip()
            or kv.get("token_url", "").strip()
            or DEFAULT_TOKEN_URL
        )
        audience = (
            (os.environ.get("GROWFLOW_OAUTH_AUDIENCE") or "").strip()
            or kv.get("audience", "").strip()
            or kv.get("oauth_audience", "").strip()
        )
        if not audience:
            host = urllib.parse.urlparse(token_url).hostname or ""
            if host == "token.growflow.com":
                audience = DEFAULT_OAUTH_AUDIENCE
        return _client_credentials_token(token_url, cid, csec, audience=audience or None)
    raise ValueError(
        "Could not resolve token: set access_token, or client_id + client_secret, "
        "or GROWFLOW_ACCESS_TOKEN"
    )


def resolve_graphql_url(explicit: str | None = None) -> str:
    """
    GraphQL POST URL: explicit arg, then GROWFLOW_GRAPHQL_URL, then retail URL from
    GROWFLOW_RETAIL_ORG, else DEFAULT_GRAPHQL_URL.
    """
    u = (explicit or os.environ.get("GROWFLOW_GRAPHQL_URL") or "").strip()
    if u:
        return u
    org = (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip().strip("/")
    if org:
        return f"https://retail.growflow.com/c/{org}/graphql"
    return DEFAULT_GRAPHQL_URL


def graphql_request(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    credentials_path: str | None = None,
    graphql_url: str | None = None,
) -> dict[str, Any]:
    url = resolve_graphql_url(graphql_url)
    token = resolve_access_token(credentials_path)
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    ua = (os.environ.get("GROWFLOW_HTTP_USER_AGENT") or "").strip() or _DEFAULT_HTTP_USER_AGENT
    hdrs = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": ua,
        "Accept": "application/json",
    }
    try:
        status, body = https_request("POST", url, data=payload, headers=hdrs, timeout=300.0)
    except RuntimeError:
        raise
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", errors="replace")[:1200]
        except OSError:
            detail = str(e.reason)
        raise RuntimeError(
            f"GraphQL HTTP {e.code}: {detail or e.reason!r}. "
            f"URL={url!r} — set GROWFLOW_RETAIL_ORG (e.g. nugzdispensary) or GROWFLOW_GRAPHQL_URL."
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"GraphQL network error ({e.reason}). Check GROWFLOW_GRAPHQL_URL, GROWFLOW_CONNECT_IP, "
            "or connectivity."
        ) from e
    if status >= 400:
        raise RuntimeError(f"GraphQL HTTP {status}: {body[:800]!r}")
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"GraphQL response not JSON: {body[:400]!r}") from e

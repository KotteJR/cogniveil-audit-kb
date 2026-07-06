"""HTTP helpers ported from app/services/cowork_url_fetch.py (sync CLI variant)."""
from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx

FETCH_TIMEOUT = 60.0
MAX_BYTES = 50 * 1024 * 1024

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; Cogniveil-AuditKB-Fetch/1.0; +https://cogniveil.ai)"
    ),
    "Accept": (
        "application/pdf,text/html,application/xhtml+xml,application/json,"
        "text/plain;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "eng, en;q=0.9",
}

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/pdf,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_RETRY_WITH_BROWSER_STATUS = frozenset({202, 401, 403, 406, 408, 425, 429, 503})

_DOCUMENT_EXTENSIONS = frozenset(
    {".pdf", ".csv", ".tsv", ".json", ".txt", ".md", ".xml", ".yaml", ".yml", ".html"}
)

_EURLEX_URI_RE = re.compile(r"(?i)^(celex|oj):(.+)$")

_DISPOSITION_FILENAME_RE = re.compile(
    r"""filename\*=(?:utf-8|UTF-8)''([^;]+)|filename=(?:"([^"]+)"|([^;\s]+))"""
)


def _hostname_resolves_to_blocked_ip(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(
            hostname, None, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        return True
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return True
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return True
    return False


def is_safe_public_https_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host or host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    return not _hostname_resolves_to_blocked_ip(host)


def rewrite_eurlex_to_cellar(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if host not in {"eur-lex.europa.eu", "www.eur-lex.europa.eu"}:
        return None
    uri_values = parse_qs(parsed.query).get("uri") or []
    for raw in uri_values:
        m = _EURLEX_URI_RE.match(unquote(raw).strip())
        if m:
            kind, ident = m.group(1).lower(), m.group(2).strip()
            return f"https://publications.europa.eu/resource/{kind}/{quote(ident)}"
    return None


def cellar_url_for_celex(celex: str) -> str:
    return f"https://publications.europa.eu/resource/celex/{quote(celex.strip())}"


def normalize_fetch_url(url: str) -> str:
    u = (url or "").strip()
    if u.lower().startswith("http://"):
        u = "https://" + u[7:]
    return rewrite_eurlex_to_cellar(u) or u


def filename_from_disposition(disposition: str) -> str:
    m = _DISPOSITION_FILENAME_RE.search(disposition or "")
    if not m:
        return ""
    raw = m.group(1) or m.group(2) or m.group(3) or ""
    name = unquote(raw).strip().strip('"')
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return name[:200]


def filename_from_url(url: str, content_type: str = "") -> str:
    path = urlparse(url).path or ""
    name = unquote(path.rsplit("/", 1)[-1] if "/" in path else "").strip()
    if name and "." in name:
        return name[:200]
    ct = (content_type or "").lower()
    if "pdf" in ct:
        ext = "pdf"
    elif "json" in ct:
        ext = "json"
    elif "csv" in ct:
        ext = "csv"
    elif "html" in ct:
        ext = "html"
    else:
        ext = "txt"
    stem = name[:190] if name else "download"
    return f"{stem}.{ext}"


def mime_from_content_type(content_type: str) -> str:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct:
        return ct
    return "application/octet-stream"


def download_url(
    url: str,
    *,
    accept_language: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Download URL; returns {body, content_type, filename, final_url, etag, error}."""
    normalized = normalize_fetch_url(url)
    if not is_safe_public_https_url(normalized):
        return {
            "body": b"",
            "content_type": "",
            "filename": "",
            "final_url": normalized,
            "etag": "",
            "error": f"URL failed SSRF safety check: {url}",
        }

    headers = dict(_DEFAULT_HEADERS)
    if accept_language:
        headers["Accept-Language"] = accept_language
    if extra_headers:
        headers.update(extra_headers)

    out: dict[str, Any] = {
        "body": b"",
        "content_type": "",
        "filename": filename_from_url(normalized),
        "final_url": normalized,
        "etag": "",
        "error": None,
    }
    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT, follow_redirects=True, max_redirects=8
        ) as client:
            r = client.get(normalized, headers=headers)
            if r.status_code in _RETRY_WITH_BROWSER_STATUS or (
                r.status_code == 200 and not r.content
            ):
                browser = dict(_BROWSER_HEADERS)
                if accept_language:
                    browser["Accept-Language"] = accept_language
                r = client.get(normalized, headers=browser)

            if r.status_code != 200:
                out["error"] = f"HTTP {r.status_code} for {normalized}"
                return out

            body = r.content
            if len(body) > MAX_BYTES:
                out["error"] = f"Response exceeds {MAX_BYTES} bytes"
                return out

            disp = r.headers.get("content-disposition", "")
            fname = filename_from_disposition(disp) or filename_from_url(
                str(r.url), r.headers.get("content-type", "")
            )
            out["body"] = body
            out["content_type"] = r.headers.get("content-type", "")
            out["filename"] = fname
            out["final_url"] = str(r.url)
            out["etag"] = r.headers.get("etag", "")
    except httpx.HTTPError as exc:
        out["error"] = str(exc)
    return out


def download_cellar_resource(
    celex: str,
    *,
    language: str,
    prefer_pdf: bool = True,
) -> dict[str, Any]:
    """Fetch one language variant from Cellar by CELEX id."""
    base = cellar_url_for_celex(celex)
    lang_map = {"en": "eng", "el": "ell", "de": "deu", "fr": "fra"}
    accept_lang = lang_map.get(language.lower(), language)

    if prefer_pdf:
        result = download_url(
            base,
            accept_language=accept_lang,
            extra_headers={"Accept": "application/pdf"},
        )
        if not result["error"] and result["body"]:
            ct = (result["content_type"] or "").lower()
            if "pdf" in ct or result["body"][:4] == b"%PDF":
                result["format"] = "pdf"
                return result

    result = download_url(
        base,
        accept_language=accept_lang,
        extra_headers={"Accept": "text/html,application/xhtml+xml"},
    )
    if not result["error"] and result["body"]:
        result["format"] = "html"
    return result

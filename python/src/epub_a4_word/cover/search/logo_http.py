from __future__ import annotations

import json
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .errors import ImageDownloadError, SearchTimeoutError, SearchTransportError
from .http import USER_AGENT

CONNECT_TIMEOUT_SECONDS = 10
TOTAL_TIMEOUT_SECONDS = 30
MAX_REDIRECTS = 5
MAX_JSON_BYTES = 4 * 1024 * 1024


class _LimitedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        count = int(getattr(req, "_epub2a4_redirect_count", 0)) + 1
        if count > MAX_REDIRECTS:
            raise SearchTransportError("重新導向次數超過 5 次。", url=newurl, params={})
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None:
            setattr(redirected, "_epub2a4_redirect_count", count)
        return redirected


class LogoHttpClient:
    def __init__(self, opener: Any | None = None) -> None:
        self.opener = opener or build_opener(_LimitedRedirectHandler())

    @staticmethod
    def _require_web(url: str) -> None:
        if urlsplit(url).scheme.casefold() not in {"http", "https"}:
            raise SearchTransportError("只允許 HTTP 或 HTTPS 網址。", url=url, params={})

    def _open(self, request: Request):
        try:
            return self.opener.open(request, timeout=CONNECT_TIMEOUT_SECONDS)
        except (TimeoutError, socket.timeout) as exc:
            raise SearchTimeoutError("網路請求逾時。") from exc
        except HTTPError as exc:
            raise SearchTransportError(f"網路服務回傳 HTTP {exc.code}。", url=request.full_url, params={}) from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise SearchTimeoutError("網路請求逾時。") from exc
            raise SearchTransportError("無法連線到網路服務。", url=request.full_url, params={}) from exc
        except OSError as exc:
            raise SearchTransportError("網路請求失敗。", url=request.full_url, params={}) from exc

    def _read(self, response, *, max_bytes: int) -> bytes:
        started = time.monotonic()
        chunks: list[bytes] = []
        total = 0
        while True:
            if time.monotonic() - started > TOTAL_TIMEOUT_SECONDS:
                raise SearchTimeoutError("網路下載超過 30 秒。")
            chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ImageDownloadError(f"下載內容超過 {max_bytes // (1024 * 1024)} MiB 限制。")
            chunks.append(chunk)
        return b"".join(chunks)

    def get_json(self, url: str, params: dict[str, object], headers: dict[str, str] | None = None) -> dict[str, object]:
        self._require_web(url)
        query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
        request_url = f"{url}?{query}" if query else url
        request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        request_headers.update(headers or {})
        request = Request(request_url, headers=request_headers)
        with self._open(request) as response:
            data = self._read(response, max_bytes=MAX_JSON_BYTES)
        try:
            raw = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SearchTransportError("搜尋服務回傳無效 JSON。", url=url, params=params) from exc
        if not isinstance(raw, dict):
            raise SearchTransportError("搜尋服務回應格式無效。", url=url, params=params)
        return raw

    def get_text(self, url: str, *, max_bytes: int) -> str:
        self._require_web(url)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        with self._open(request) as response:
            data = self._read(response, max_bytes=max_bytes)
            charset = response.headers.get_content_charset() or "utf-8"
        return data.decode(charset, errors="replace")

    def download_bytes(self, url: str, *, max_bytes: int) -> tuple[bytes, str, str]:
        self._require_web(url)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
        with self._open(request) as response:
            declared = response.headers.get("Content-Length")
            if declared and int(declared) > max_bytes:
                raise ImageDownloadError(f"Logo 超過 {max_bytes // (1024 * 1024)} MiB 限制。")
            data = self._read(response, max_bytes=max_bytes)
            content_type = str(response.headers.get_content_type() or "application/octet-stream")
            final_url = str(response.geturl() or url)
        return data, content_type, final_url

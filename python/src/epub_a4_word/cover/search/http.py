from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from .errors import (
    ImageDownloadError,
    SearchCredentialError,
    SearchQuotaError,
    SearchTimeoutError,
    SearchTransportError,
)

DEFAULT_TIMEOUT_SECONDS = 12
MAX_JSON_BYTES = 4 * 1024 * 1024
USER_AGENT = "EPUB2A4-CoverTool/0.6"


@dataclass(frozen=True)
class DownloadTransportResult:
    content_type: str
    byte_count: int


class JsonHttpClient:
    def __init__(self, opener: Any | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.opener = opener or build_opener()
        self.timeout = int(timeout)

    @staticmethod
    def _require_https(url: str) -> None:
        if urlsplit(url).scheme.casefold() != "https":
            raise SearchTransportError("只允許 HTTPS 網址。", url=url, params={})

    def _open(self, request: Request, *, url: str, params: dict[str, object]):
        try:
            return self.opener.open(request, timeout=self.timeout)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise SearchCredentialError("搜尋憑證遭拒絕。") from exc
            if exc.code == 429:
                raise SearchQuotaError(
                    "搜尋服務暫時限制請求（HTTP 429），可能是短期限流，不一定代表每日額度已用完。"
                ) from exc
            raise SearchTransportError(
                f"搜尋服務回傳 HTTP {exc.code}。", url=url, params=params
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise SearchTimeoutError("搜尋逾時。") from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise SearchTimeoutError("搜尋逾時。") from exc
            raise SearchTransportError("無法連線到搜尋服務。", url=url, params=params) from exc
        except OSError as exc:
            raise SearchTransportError("網路請求失敗。", url=url, params=params) from exc

    def get_json(
        self,
        url: str,
        params: dict[str, object],
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self._require_https(url)
        query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
        request_url = f"{url}?{query}" if query else url
        request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        request_headers.update(headers or {})
        request = Request(request_url, headers=request_headers)
        with self._open(request, url=url, params=params) as response:
            data = response.read(MAX_JSON_BYTES + 1)
        if len(data) > MAX_JSON_BYTES:
            raise SearchTransportError("搜尋回應過大。", url=url, params=params)
        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SearchTransportError("搜尋服務回傳無效 JSON。", url=url, params=params) from exc
        if not isinstance(decoded, dict):
            raise SearchTransportError("搜尋服務回應格式無效。", url=url, params=params)
        return decoded

    def stream_download(self, url: str, destination: Path, max_bytes: int) -> DownloadTransportResult:
        self._require_https(url)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
        try:
            response = self._open(request, url=url, params={})
            with response:
                content_type = str(response.headers.get_content_type() or "").casefold()
                declared = response.headers.get("Content-Length")
                if declared and int(declared) > max_bytes:
                    raise ImageDownloadError(f"圖片超過 {max_bytes // (1024 * 1024)} MiB 限制。")
                total = 0
                with destination.open("wb") as output:
                    while True:
                        chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise ImageDownloadError(
                                f"圖片超過 {max_bytes // (1024 * 1024)} MiB 限制。"
                            )
                        output.write(chunk)
                return DownloadTransportResult(content_type=content_type, byte_count=total)
        except Exception:
            destination.unlink(missing_ok=True)
            raise

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import socket
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import OpenerDirector, Request, build_opener

from .errors import (
    SearchCredentialError,
    SearchQuotaError,
    SearchResponseError,
    SearchTimeoutError,
    SearchTransportError,
)

DEFAULT_TIMEOUT_SECONDS = 12
MAX_JSON_BYTES = 4 * 1024 * 1024
USER_AGENT = "EPUB2A4-CoverTool/0.6"
SENSITIVE_KEYS = {"key", "api_key", "cx", "search_engine_id"}
_DOWNLOAD_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class DownloadTransportResult:
    path: Path
    byte_count: int
    content_type: str
    final_url: str


def _require_https(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise SearchTransportError("搜尋與下載端點必須使用 HTTPS。")


def _request_url(url: str, params: Mapping[str, object]) -> str:
    parsed = urlsplit(url)
    existing = parse_qsl(parsed.query, keep_blank_values=True)
    supplied = [(str(key), str(value)) for key, value in params.items() if value is not None]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(existing + supplied), parsed.fragment))


def _safe_request_label(url: str, params: Mapping[str, object] | None = None) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    keys = {key for key, _value in parse_qsl(parsed.query, keep_blank_values=True)}
    if params:
        keys.update(str(key) for key in params)
    if not keys:
        return f"{parsed.netloc}{path}"
    rendered = []
    for key in sorted(keys):
        marker = "<redacted>" if key.casefold() in SENSITIVE_KEYS else "<omitted>"
        rendered.append(f"{key}={marker}")
    return f"{parsed.netloc}{path}?{'&'.join(rendered)}"


def _content_type(response: object) -> str:
    headers = getattr(response, "headers", None)
    if headers is None:
        return ""
    get_content_type = getattr(headers, "get_content_type", None)
    if callable(get_content_type):
        return str(get_content_type()).lower()
    value = headers.get("Content-Type", "") if hasattr(headers, "get") else ""
    return str(value).split(";", 1)[0].strip().lower()


class JsonHttpClient:
    def __init__(
        self,
        opener: OpenerDirector | object | None = None,
        timeout_seconds: int | float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必須大於 0。")
        self._opener = opener or build_opener()
        self.timeout_seconds = float(timeout_seconds)

    def get_json(
        self,
        url: str,
        params: Mapping[str, object],
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, object]:
        _require_https(url)
        request_url = _request_url(url, params)
        request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if headers:
            request_headers.update(headers)
        request = Request(request_url, headers=request_headers, method="GET")
        label = _safe_request_label(url, params)

        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                final_url = str(getattr(response, "geturl", lambda: request_url)())
                _require_https(final_url)
                payload = response.read(MAX_JSON_BYTES + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise SearchCredentialError(f"搜尋憑證遭拒絕：{label}") from exc
            if exc.code == 429:
                raise SearchQuotaError(f"搜尋配額已用完：{label}") from exc
            raise SearchTransportError(f"搜尋服務回傳 HTTP {exc.code}：{label}") from exc
        except (socket.timeout, TimeoutError) as exc:
            raise SearchTimeoutError(f"搜尋逾時：{label}") from exc
        except URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise SearchTimeoutError(f"搜尋逾時：{label}") from exc
            raise SearchTransportError(f"無法連線搜尋服務：{label}") from exc
        except SearchTransportError:
            raise
        except OSError as exc:
            raise SearchTransportError(f"無法讀取搜尋服務回應：{label}") from exc

        if len(payload) > MAX_JSON_BYTES:
            raise SearchResponseError("搜尋服務回應超過大小限制。")
        try:
            decoded = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SearchResponseError("搜尋服務回傳無效 JSON。") from exc
        if not isinstance(decoded, dict):
            raise SearchResponseError("搜尋服務 JSON 必須是物件。")
        return decoded

    def stream_download(
        self,
        url: str,
        destination: Path | str,
        max_bytes: int,
    ) -> DownloadTransportResult:
        _require_https(url)
        if max_bytes <= 0:
            raise ValueError("max_bytes 必須大於 0。")
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"}, method="GET")
        label = _safe_request_label(url)
        byte_count = 0
        content_type = ""
        final_url = url

        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                final_url = str(getattr(response, "geturl", lambda: url)())
                _require_https(final_url)
                content_type = _content_type(response)
                with output.open("wb") as handle:
                    while True:
                        chunk = response.read(min(_DOWNLOAD_CHUNK_BYTES, max_bytes - byte_count + 1))
                        if not chunk:
                            break
                        byte_count += len(chunk)
                        if byte_count > max_bytes:
                            raise SearchTransportError("圖片下載超過大小限制。")
                        handle.write(chunk)
        except HTTPError as exc:
            output.unlink(missing_ok=True)
            if exc.code in {401, 403}:
                raise SearchCredentialError(f"圖片下載權限遭拒絕：{label}") from exc
            if exc.code == 429:
                raise SearchQuotaError(f"圖片下載配額已用完：{label}") from exc
            raise SearchTransportError(f"圖片服務回傳 HTTP {exc.code}：{label}") from exc
        except (socket.timeout, TimeoutError) as exc:
            output.unlink(missing_ok=True)
            raise SearchTimeoutError(f"圖片下載逾時：{label}") from exc
        except URLError as exc:
            output.unlink(missing_ok=True)
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise SearchTimeoutError(f"圖片下載逾時：{label}") from exc
            raise SearchTransportError(f"無法下載圖片：{label}") from exc
        except SearchTransportError:
            output.unlink(missing_ok=True)
            raise
        except OSError as exc:
            output.unlink(missing_ok=True)
            raise SearchTransportError(f"無法儲存下載圖片：{label}") from exc

        return DownloadTransportResult(
            path=output,
            byte_count=byte_count,
            content_type=content_type,
            final_url=final_url,
        )

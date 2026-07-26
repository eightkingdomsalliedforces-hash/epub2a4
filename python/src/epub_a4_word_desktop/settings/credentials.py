from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

from epub_a4_word.cover.search.models import ProviderCredential

SERVICE_NAME = "EPUB2A4 Google Books"
LEGACY_SERVICE_NAME = "EPUB2A4 Google Image Search"


class CredentialPersistenceWarning(RuntimeError):
    pass


class CredentialStore(Protocol):
    def load(self) -> ProviderCredential | None: ...
    def save(self, value: ProviderCredential, **kwargs) -> None: ...
    def clear(self) -> None: ...


class SessionCredentialStore:
    def __init__(self) -> None:
        self.value: ProviderCredential | None = None

    def load(self) -> ProviderCredential | None:
        return self.value

    def save(self, value: ProviderCredential, **kwargs) -> None:
        self.value = value

    def clear(self) -> None:
        self.value = None


class KeyringCredentialStore:
    def __init__(self) -> None:
        import keyring
        self.keyring = keyring

    def load(self) -> ProviderCredential | None:
        for service_name in (SERVICE_NAME, LEGACY_SERVICE_NAME):
            api_key = self.keyring.get_password(service_name, "api-key")
            if api_key:
                return ProviderCredential(api_key)
        return None

    def save(self, value: ProviderCredential, **kwargs) -> None:
        if not value.complete:
            raise ValueError("Google Books API Key 必須填寫。")
        self.keyring.set_password(SERVICE_NAME, "api-key", value.api_key)

    def clear(self) -> None:
        for service_name in (SERVICE_NAME, LEGACY_SERVICE_NAME):
            for username in ("api-key", "search-engine-id"):
                try:
                    self.keyring.delete_password(service_name, username)
                except Exception:
                    continue


class PortableCredentialStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> ProviderCredential | None:
        try:
            raw = json.loads(self.path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict):
            return None
        value = ProviderCredential(
            str(raw.get("api_key", "")),
        )
        return value if value.complete else None

    def save(
        self,
        value: ProviderCredential,
        *,
        confirmed_plaintext: bool = False,
        **kwargs,
    ) -> None:
        if not confirmed_plaintext:
            raise CredentialPersistenceWarning("未確認可攜模式明文憑證風險。")
        if not value.complete:
            raise ValueError("Google Books API Key 必須填寫。")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"api_key": value.api_key}, ensure_ascii=False),
            "utf-8",
        )
        os.replace(temporary, self.path)
        if os.name == "posix":
            self.path.chmod(0o600)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


class LayeredCredentialStore:
    """Use persistent credentials when available, otherwise session values."""

    def __init__(self, persistent: CredentialStore | None, session: SessionCredentialStore | None = None) -> None:
        self.persistent = persistent
        self.session = session or SessionCredentialStore()

    def load(self) -> ProviderCredential | None:
        session = self.session.load()
        if session is not None:
            return session
        if self.persistent is None:
            return None
        try:
            return self.persistent.load()
        except Exception:
            return None

    def save_session(self, value: ProviderCredential) -> None:
        self.session.save(value)

    def save_persistent(self, value: ProviderCredential, **kwargs) -> None:
        if self.persistent is None:
            raise RuntimeError("安全憑證儲存目前不可用。")
        self.persistent.save(value, **kwargs)
        self.session.clear()

    def clear(self) -> None:
        self.session.clear()
        if self.persistent is not None:
            self.persistent.clear()

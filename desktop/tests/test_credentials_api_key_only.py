from __future__ import annotations

import json

from epub_a4_word.cover.search.models import ProviderCredential
from epub_a4_word_desktop.settings.credentials import (
    KeyringCredentialStore,
    LEGACY_SERVICE_NAME,
    PortableCredentialStore,
    SERVICE_NAME,
)


class FakeKeyring:
    def __init__(self, values=None) -> None:
        self.values = dict(values or {})
        self.deleted: list[tuple[str, str]] = []

    def get_password(self, service: str, username: str):
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, value: str) -> None:
        self.values[(service, username)] = value

    def delete_password(self, service: str, username: str) -> None:
        self.deleted.append((service, username))
        self.values.pop((service, username), None)


def _keyring_store(fake: FakeKeyring) -> KeyringCredentialStore:
    store = KeyringCredentialStore.__new__(KeyringCredentialStore)
    store.keyring = fake
    return store


def test_provider_credential_is_complete_with_api_key_only() -> None:
    value = ProviderCredential(" BOOKS_KEY ")

    assert value.complete is True
    assert value.search_engine_id == ""
    assert ProviderCredential("  ").complete is False


def test_portable_store_reads_legacy_json_but_saves_only_api_key(tmp_path) -> None:
    path = tmp_path / "credentials.json"
    path.write_text(
        json.dumps({"api_key": "OLD_KEY", "search_engine_id": "LEGACY_CX"}),
        "utf-8",
    )
    store = PortableCredentialStore(path)

    loaded = store.load()
    assert loaded == ProviderCredential("OLD_KEY")

    store.save(ProviderCredential("NEW_KEY"), confirmed_plaintext=True)
    assert json.loads(path.read_text("utf-8")) == {"api_key": "NEW_KEY"}


def test_keyring_loads_new_api_key_without_search_engine_id() -> None:
    fake = FakeKeyring({(SERVICE_NAME, "api-key"): "BOOKS_KEY"})
    store = _keyring_store(fake)

    assert store.load() == ProviderCredential("BOOKS_KEY")


def test_keyring_falls_back_to_legacy_service_api_key() -> None:
    fake = FakeKeyring({(LEGACY_SERVICE_NAME, "api-key"): "LEGACY_KEY"})
    store = _keyring_store(fake)

    assert store.load() == ProviderCredential("LEGACY_KEY")


def test_keyring_save_and_clear_touch_only_supported_names() -> None:
    fake = FakeKeyring()
    store = _keyring_store(fake)

    store.save(ProviderCredential("BOOKS_KEY"))
    assert fake.values == {(SERVICE_NAME, "api-key"): "BOOKS_KEY"}

    store.clear()
    assert (SERVICE_NAME, "api-key") in fake.deleted
    assert (LEGACY_SERVICE_NAME, "api-key") in fake.deleted
    assert (SERVICE_NAME, "search-engine-id") in fake.deleted
    assert (LEGACY_SERVICE_NAME, "search-engine-id") in fake.deleted

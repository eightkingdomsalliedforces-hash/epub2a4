from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_path, user_config_path, user_data_path


class PortableModeUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimePaths:
    mode: str
    config_dir: Path
    cache_dir: Path
    data_dir: Path

    @property
    def portable(self) -> bool:
        return self.mode == "portable"


def resolve_runtime_paths(executable_dir: Path | str) -> RuntimePaths:
    executable = Path(executable_dir).expanduser().resolve()
    if (executable / "portable.flag").is_file():
        data_root = executable / "data"
        try:
            data_root.mkdir(parents=True, exist_ok=True)
            probe = data_root / ".write-probe"
            probe.write_bytes(b"ok")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise PortableModeUnavailable("可攜模式資料夾不可寫入。") from exc
        config = data_root / "config"
        cache = data_root / "cache"
        projects = data_root / "projects"
    else:
        config = Path(user_config_path("EPUB2A4", ensure_exists=True))
        cache = Path(user_cache_path("EPUB2A4", ensure_exists=True))
        projects = Path(user_data_path("EPUB2A4", ensure_exists=True)) / "projects"
    for path in (config, cache, projects):
        path.mkdir(parents=True, exist_ok=True)
    return RuntimePaths(
        "portable" if (executable / "portable.flag").is_file() else "standard",
        config,
        cache,
        projects,
    )

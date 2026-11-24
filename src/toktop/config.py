"""Paths, user config and language.

Config file (optional): ~/.config/toktop/config.toml (Windows: %APPDATA%\\toktop\\config.toml),
or the path in $TOKTOP_CONFIG. See config.example.toml.
"""
import os
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

APP = "toktop"
HOME = Path.home()
WIN = sys.platform == "win32"


def _xdg(var, fallback):
    base = os.environ.get(var)
    return Path(base) if base else HOME / fallback


def default_data_dir():
    if os.environ.get("TOKTOP_DATA_DIR"):
        return Path(os.environ["TOKTOP_DATA_DIR"]).expanduser()
    if WIN and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / APP
    return _xdg("XDG_DATA_HOME", ".local/share") / APP


def config_path():
    if os.environ.get("TOKTOP_CONFIG"):
        return Path(os.environ["TOKTOP_CONFIG"]).expanduser()
    if WIN and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / APP / "config.toml"
    return _xdg("XDG_CONFIG_HOME", ".config") / APP / "config.toml"


def load_config(path=None):
    path = path or config_path()
    if tomllib is None or not path.exists():
        return {}
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except (OSError, ValueError) as e:
        print(f"toktop: ignoring {path}: {e}", file=sys.stderr)
        return {}


CONFIG = load_config()
DATA = default_data_dir()
OFFLINE = False  # demo mode: no network, no app reading


def set_data_dir(path):
    global DATA
    DATA = Path(path)


def history_db():
    return DATA / "history.db"


def cfg_path(key):
    """Path set in [paths] of the config file, or None."""
    v = (CONFIG.get("paths") or {}).get(key)
    return Path(v).expanduser() if v else None


def disabled_sources():
    return set((CONFIG.get("sources") or {}).get("disabled") or [])


def enabled_sources():
    """Names chosen in the first-run picker ([sources] enabled), or None if it was never shown."""
    v = (CONFIG.get("sources") or {}).get("enabled")
    return list(v) if isinstance(v, list) else None


def save_enabled(names, path=None):
    """Write [sources] enabled = [...] keeping the rest of the file as it is."""
    path = path or config_path()
    line = "enabled = [" + ", ".join(f'"{n}"' for n in names) + "]"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    sec, start, done = None, None, False
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith("[") and st.endswith("]"):
            if sec == "sources" and not done:
                j = i
                while j > start + 1 and not lines[j - 1].strip(): j -= 1
                lines.insert(j, line); done = True; break
            sec = st.strip("[]").strip()
            if sec == "sources": start = i
        elif sec == "sources" and st.split("=")[0].strip() == "enabled":
            lines[i] = line; done = True; break
    if not done:
        if start is None:
            lines += (["", "[sources]"] if lines else ["[sources]"])
        lines.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    CONFIG.setdefault("sources", {})["enabled"] = list(names)


def env_dirs():
    return [Path(os.environ[e]) for e in ("LOCALAPPDATA", "APPDATA", "XDG_DATA_HOME") if os.environ.get(e)]

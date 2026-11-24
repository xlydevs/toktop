"""First-run app picker and setup instructions for apps that need a usage log."""
import json
import shutil
import subprocess
import sys

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, SelectionList, Static, TextArea

from . import config, sources
from .common import ALL, COLOR, KIND, LABEL, MUTED
from .i18n import LANG, t

CSS = """
AppsScreen, SetupScreen { align: center middle; background: #0f1420 70%; }
.dialog { width: 72; max-width: 95%; height: auto; max-height: 95%; border: round #f2cc8f; background: #141b2a; padding: 1 2; }
SetupScreen .dialog { width: 100; }
.dialog .title { text-style: bold; color: #eef2fa; }
.dialog .sub { color: #7c879f; margin-bottom: 1; }
#apps { height: auto; max-height: 20; background: #141b2a; border: none; padding: 0; }
#apps:focus { background-tint: transparent; }
#apps > .selection-list--button { color: #1a2335; background: #1a2335; }
#apps > .selection-list--button-highlighted { color: #2a3754; background: #2a3754; }
#apps > .selection-list--button-selected, #apps > .selection-list--button-selected-highlighted { color: #0f1420; background: #a5d68f; text-style: bold; }
#apps > .option-list--option-highlighted { background: #222c42; }
#setup-text { height: 18; margin-bottom: 1; border: round #263044; background: #0f1420; }
#setup-text:focus { border: round #f2cc8f; }
.buttons { height: auto; align-horizontal: right; margin-top: 1; }
.buttons Button { margin-left: 2; }
"""


def copy_text(app, text):
    """Clipboard: the system tool when there is one, OSC 52 through the terminal as well."""
    try:
        app.copy_to_clipboard(text)
    except Exception:
        pass
    cmds = (["pbcopy"],) if sys.platform == "darwin" else (["clip"],) if sys.platform == "win32" else (
        ["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"])
    for cmd in cmds:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text.encode("utf-16le" if cmd[0] == "clip" else "utf-8"), check=True, timeout=5)
                return True
            except (OSError, subprocess.SubprocessError):
                continue
    return False


class AppsScreen(ModalScreen):
    """Pick the apps toktop reads. Returns the chosen keys, or None when cancelled."""

    BINDINGS = [("escape", "cancel", "")]

    def __init__(self, selected, first_run=False):
        super().__init__()
        self.selected, self.first_run = set(selected), first_run

    def compose(self) -> ComposeResult:
        found = sources.detected()
        opts = []
        for k in ALL:
            lbl = Text()
            lbl.append("● ", style=COLOR[k])
            lbl.append(f"{LABEL[k]:<24}", style="#eef2fa")
            if KIND[k] == "manual":
                lbl.append(t("needs a one-time setup"), style="#f2cc8f")
            elif k in found:
                lbl.append(t("found"), style="#a5d68f")
            else:
                lbl.append(t("not found"), style=MUTED)
            opts.append((lbl, k, k in self.selected))
        with Vertical(classes="dialog"):
            yield Static(t("Which apps do you use?"), classes="title")
            yield Static(t("toktop will read the ones you check. You can change this any time with the a key."), classes="sub")
            yield SelectionList(*opts, id="apps")
            with Horizontal(classes="buttons"):
                if not self.first_run:
                    yield Button(t("Cancel"), id="cancel")
                yield Button(t("Save"), id="save", variant="primary")

    def on_mount(self):
        self.query_one("#apps").focus()

    def on_button_pressed(self, event):
        if event.button.id == "save":
            self.dismiss(list(self.query_one("#apps", SelectionList).selected))
        else:
            self.dismiss(None)

    def action_cancel(self):
        if self.first_run:
            self.dismiss(list(self.query_one("#apps", SelectionList).selected))
        else:
            self.dismiss(None)


class SetupScreen(ModalScreen):
    """Instructions to hand to an AI agent for the apps that need a usage log."""

    BINDINGS = [("escape", "close", "")]

    def __init__(self, keys):
        super().__init__()
        self.text = setup_prompt(keys)

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Static(t("One more step for some apps"), classes="title")
            yield Static(t("These apps don't keep a usage record toktop can read. Copy this text and give it to your AI "
                           "agent (Claude Code, Codex…): it will set them up. Their data shows up from then on."), classes="sub")
            yield TextArea(self.text, id="setup-text", read_only=True, soft_wrap=True)
            with Horizontal(classes="buttons"):
                yield Button(t("Done"), id="close")
                yield Button(t("Copy"), id="copy", variant="primary")

    def on_button_pressed(self, event):
        if event.button.id == "copy":
            copy_text(self.app, self.text)
            self.app.notify(t("Copied to the clipboard"), timeout=3)
        else:
            self.dismiss()

    def action_close(self):
        self.dismiss()


# ───────────────────────── instructions ─────────────────────────

DSH_EXAMPLE = {"id": "req_01", "ts": "2026-11-24T18:30:00Z", "session_id": "a1b2c3", "model": "deepseek-v4.1-flash",
               "provider": "deepseek", "input_uncached": 1200, "input_cached": 48000, "cache_write": 0, "output": 850,
               "reasoning": 300}
AIDER_LOG = "aider-analytics.jsonl"


def dsh_log_path():
    return config.cfg_path("dsh_log") or config.DATA / "deepseek-harness.jsonl"


def aider_log_path():
    return config.cfg_path("aider_log") or config.DATA / AIDER_LOG


def setup_prompt(keys):
    parts = []
    ex = json.dumps(DSH_EXAMPLE)
    if "dh" in keys:
        if LANG == "es":
            parts.append(f"""## dsh (deepseek-harness)
Configura dsh para que toktop pueda leer su uso de tokens. Haz que añada una línea JSON por cada petición al modelo al fichero:
  {dsh_log_path()}
Crea la carpeta si no existe y no borres ni reescribas las líneas anteriores. Campos de cada línea:
  id              identificador único de la petición (si se repite, cuenta la última línea)
  ts              fecha y hora ISO 8601 con zona horaria, p. ej. 2026-11-24T18:30:00Z
  session_id      id de la sesión de dsh
  model           id del modelo, p. ej. deepseek-v4.1-flash
  provider        proveedor, p. ej. deepseek
  input_uncached  tokens de entrada que no salieron de la caché
  input_cached    tokens de entrada leídos de la caché
  cache_write     tokens escritos en la caché (0 si no aplica)
  output          tokens de salida, razonamiento incluido
  reasoning       tokens de razonamiento (solo informativo)
Ejemplo de línea:
{ex}
Si dsh tiene plugins o hooks, hazlo así, sin tocar su código fuente. Al terminar, haz una petición de prueba y comprueba que aparece una línea nueva en el fichero.""")
        else:
            parts.append(f"""## dsh (deepseek-harness)
Set up dsh so toktop can read its token usage. Make it append one JSON line per model request to this file:
  {dsh_log_path()}
Create the folder if needed and never delete or rewrite earlier lines. Fields of each line:
  id              unique request id (if it repeats, the last line wins)
  ts              ISO 8601 date and time with a time zone, e.g. 2026-11-24T18:30:00Z
  session_id      dsh session id
  model           model id, e.g. deepseek-v4.1-flash
  provider        provider, e.g. deepseek
  input_uncached  input tokens not served from the cache
  input_cached    input tokens read from the cache
  cache_write     tokens written to the cache (0 if not applicable)
  output          output tokens, reasoning included
  reasoning       reasoning tokens (informational only)
Example line:
{ex}
If dsh has plugins or hooks, use them instead of editing its source. When done, make a test request and check that a new line shows up in the file.""")
    if "ad" in keys:
        if LANG == "es":
            parts.append(f"""## Aider
Configura Aider para que guarde un registro de uso que toktop pueda leer. En el fichero de configuración global de Aider (~/.aider.conf.yml; créalo si no existe) añade esta línea, sin borrar lo que ya haya:
  analytics-log: {aider_log_path()}
Esto solo escribe un registro local; no activa el envío de analíticas. Crea la carpeta si no existe. Al terminar, lanza aider con un mensaje corto y comprueba que en ese fichero aparecen líneas JSON con el evento "message_send".""")
        else:
            parts.append(f"""## Aider
Set up Aider to keep a usage log toktop can read. In Aider's global config file (~/.aider.conf.yml; create it if missing) add this line, keeping whatever is already there:
  analytics-log: {aider_log_path()}
This only writes a local log; it does not turn on sending analytics. Create the folder if needed. When done, run aider with a short message and check that JSON lines with the "message_send" event show up in that file.""")
    return "\n\n".join(parts)

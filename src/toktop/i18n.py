"""Tiny i18n: English by default, Spanish when the locale (or config/flag) says so.

Strings in the code are English; `t()` swaps them for the Spanish entry in ES when LANG == "es".
"""
import locale
import os

from . import config

SUPPORTED = ("en", "es")


def detect():
    v = os.environ.get("TOKTOP_LANG") or config.CONFIG.get("lang")
    if not v:
        for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
            if os.environ.get(var):
                v = os.environ[var]
                break
    if not v:
        try:
            v = locale.getlocale()[0] or ""
        except ValueError:
            v = ""
    v = (v or "en").lower()[:2]
    return v if v in SUPPORTED else "en"


LANG = detect()


def set_lang(lang):
    global LANG
    LANG = lang if lang in SUPPORTED else "en"


def t(s, **kw):
    if LANG == "es":
        s = ES.get(s, s)
    return s.format(**kw) if kw else s


MONTHS = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                 "October", "November", "December"],
          "es": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                 "octubre", "noviembre", "diciembre"]}
MONTHS_S = {"en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
            "es": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]}
DAYS_1 = {"en": ["M", "T", "W", "T", "F", "S", "S"], "es": ["L", "M", "X", "J", "V", "S", "D"]}
DAYS_S = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
          "es": ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]}


def months(): return MONTHS[LANG]
def months_s(): return MONTHS_S[LANG]
def days_1(): return DAYS_1[LANG]
def days_s(): return DAYS_S[LANG]


def long_date(dt):
    if LANG == "es":
        return f"{DAYS_S['es'][dt.weekday()]} {dt.day} de {MONTHS['es'][dt.month - 1]} de {dt.year}"
    return f"{DAYS_S['en'][dt.weekday()]}, {MONTHS['en'][dt.month - 1]} {dt.day}, {dt.year}"


def short_date(dt):
    if LANG == "es":
        return f"{DAYS_S['es'][dt.weekday()]} {dt.day} {MONTHS_S['es'][dt.month - 1]}"
    return f"{DAYS_S['en'][dt.weekday()]} {MONTHS_S['en'][dt.month - 1]} {dt.day}"


# English -> Spanish
ES = {
    # cli
    "Token usage across your AI coding tools, in the terminal.": "Uso de tokens de tus herramientas de IA, en la terminal.",
    "start showing only this source": "empieza mostrando solo esta fuente",
    "plain-text summary, no TUI": "resumen en texto plano, sin TUI",
    "rebuild the history from the installed apps (data from deleted apps is kept)":
        "rehace el histórico desde las apps instaladas (lo de apps borradas se conserva)",
    "explore with made-up data (reads nothing, writes nothing)": "explorar con datos inventados (no lee ni escribe nada)",
    "interface language": "idioma de la interfaz",
    "History rebuilt from: {apps}": "Histórico rehecho desde: {apps}",
    "no app": "ninguna app",
    "error": "error",
    "No data yet.": "Sin datos todavía.",
    # tui / text / stats
    "Home": "Inicio",
    "Calendar": "Calendario",
    "Models": "Modelos",
    "Sessions": "Sesiones",
    "Prices": "Precios",
    "quit": "salir",
    "back": "atrás",
    "forward": "adelante",
    "period": "periodo",
    "sources": "fuentes",
    "search": "buscar",
    "sync": "sincronizar",
    "search by title, project, model or source…": "buscar por título, proyecto, modelo o fuente…",
    "today": "hoy",
    "Error reading an app": "Error leyendo alguna app",
    "reading apps…": "leyendo apps…",
    "history only: {apps}": "solo histórico: {apps}",
    "read now": "leído ahora",
    "app not found, history data": "app no encontrada, datos del histórico",
    "click to show/hide": "clic para mostrar/ocultar",
    "Usage": "Uso",
    "Usage per day": "Uso por día",
    "By source": "Por fuente",
    "Top models": "Top modelos",
    "Last year": "Último año",
    "Daily average": "Media diaria",
    "Input excl. cache": "Input sin caché",
    "Cache read": "Caché leída",
    "per session": "por sesión",
    "peak": "pico",
    "of total": "del total",
    "hits": "aciertos",
    "of input": "del input",
    "no usage in this period": "sin uso en este periodo",
    "sessions": "sesiones",
    "sess": "ses",
    "per active day": "por día activo",
    "updated": "actualizado",
    "Model": "Modelo",
    "Cost": "Coste",
    "built-in table": "tabla de reserva",
    "What if every token had gone through a single model?": "¿Y si todos los tokens hubiesen ido por un solo modelo?",
    "Simulation: the {tokens} tokens of {period}, at real API prices, with no subscriptions or discounts.":
        "Simulación: los {tokens} tokens de {period}, a precio real de API, sin suscripciones ni ofertas.",
    "Simulation: all {tokens} tokens spent so far, at real API prices, with no subscriptions or discounts.":
        "Simulación: los {tokens} tokens gastados hasta la fecha, a precio real de API, sin suscripciones ni ofertas.",
    "used in this period": "usado en este periodo",
    "with the models you actually used": "con los modelos que usaste de verdad",
    "({pct}% of tokens have a known price)": "({pct}% de los tokens con precio conocido)",
    "prices": "precios",
    "Source": "Fuente",
    "Project": "Proyecto",
    "Title": "Título",
    "First": "Inicio",
    "Sess.": "Ses.",
    "Cache": "Caché",
    "models": "modelos",
    "click a header to sort": "clic en una cabecera para ordenar",
    "filter": "filtro",
    "day(s)": "día(s)",
    "(untitled)": "(sin título)",
    "No usage this day.": "Sin uso este día.",
    "MODELS": "MODELOS",
    "SESSIONS": "SESIONES",
    "Last 7 days": "Últimos 7 días",
    "total {tot} · max {mx}": "total {tot} · máximo {mx}",
    "hover over a column, click opens the day": "pasa el ratón por una columna, clic abre el día",
    "less": "menos",
    "more": "más",
    "click a day to open it in the calendar": "clic en un día para abrirlo en el calendario",
    "week of {day} {month}": "semana del {day} {month}",
    "7 days": "7 días",
    "30 days": "30 días",
    "This month": "Este mes",
    "This year": "Este año",
    "All": "Todo",
    "Tokens": "Tokens",
    "tokens": "tokens",
    "Input": "Input",
    "Output": "Output",
    "input {inp} · output {out} · cache {cr}": "input {inp} · output {out} · caché {cr}",
    "input {inp} · output {out} · cache {cr} · reas {reas}": "input {inp} · output {out} · caché {cr} · reas {reas}",
}

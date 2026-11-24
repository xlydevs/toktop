# toktop

**¿A dónde se van tus tokens de IA?** `toktop` es un panel de terminal con los tokens que gastas en tus herramientas de IA para programar: Claude Code, Codex, Gemini CLI, opencode, Cline y diez más. Cubre todas las herramientas, todos los modelos y todos los días, y muestra lo que costaría todo eso a precio de API.

Todo funciona en local. Lee los datos de uso que cada app ya guarda en disco. La única conexión a internet es una descarga anónima, una vez al día, de los precios públicos de los modelos.

[English](README.md)

![Demo de toktop](docs/demo.gif)

## Qué hace

- **Una sola vista para todas las herramientas.** La primera vez eliges de una lista las apps que usas y toktop encuentra sus datos solo. Cada fuente tiene su color y se enciende y apaga por separado.
- **Un histórico que nunca baja.** El uso se copia a una base de datos propia y cada valor se queda con el máximo visto. Si desinstalas una app o borra sesiones antiguas, tus totales se mantienen.
- **Mapa de calor anual, gráfico diario apilado y calendario.** Al pasar el ratón ves el detalle; al hacer clic en un día, lo abres.
- **Tablas de modelos y sesiones.** Se ordenan por cualquier columna y las sesiones se buscan por título, proyecto o modelo.
- **Precios que se actualizan solos.** Los precios públicos se bajan de OpenRouter una vez al día. Con ellos ves lo que costaría cada modelo a precio de API y una comparación de "qué pasaría si todo fuese con el modelo X".
- **Ratón y teclado.** Se adapta a partir de 80 columnas.
- **En inglés y en español.**

## Instalación

Necesitas Python 3.11 o superior.

```bash
pipx install toktop        # o: uv tool install toktop
toktop --lang es
```

Para probarlo sin tener ninguna app instalada, usa el modo demo. Usa datos inventados y no lee ni escribe nada:

```bash
toktop --demo
```

Para dejar el español fijo, pon `lang = "es"` en `~/.config/toktop/config.toml` o exporta `TOKTOP_LANG=es`. Si tu sistema está en español, se elige solo.

## Uso

```text
toktop                 abre el panel
toktop -s claude       empieza mostrando una sola fuente (claude | codex | gemini | opencode | …)
toktop --text          resumen en texto plano (también al redirigir la salida: toktop | less)
toktop --rebuild       vuelve a leer desde cero las apps instaladas (lo de las apps borradas se conserva)
toktop --demo          datos inventados
toktop --lang es       idioma de la interfaz
```

**Teclas:**
- `1`–`5` cambian de pestaña.
- `←` / `→` cambian de mes en el calendario, o de periodo en el resto. `p` pasa al siguiente periodo.
- `o` `z` `c` `e` `b` encienden o apagan una fuente y `t` las enciende todas.
- `a` abre la lista de apps.
- `/` busca sesiones.
- `r` vuelve a leer las apps.
- `q` sale y `Ctrl+P` abre la paleta de comandos.

## Fuentes

Estas se leen solas en cuanto las marcas en la lista de apps (`a`):

| App | Qué lee |
|---|---|
| **Claude Code** | `~/.claude/projects/**/*.jsonl`: el `message.usage` de cada respuesta. Cada mensaje cuenta una vez, aunque llegue repartido en varias líneas. |
| **Codex CLI** | `~/.codex/sessions/**/rollout-*.jsonl`: los `token_count` de cada petición. Lo que repiten las sesiones bifurcadas no se cuenta dos veces. |
| **Gemini CLI** | `~/.gemini/tmp/*/chats/session-*`: los `tokens` de cada mensaje de Gemini. |
| **Qwen Code** | `~/.qwen/projects/*/chats/*.jsonl`: el `usageMetadata` de cada respuesta. |
| **opencode** | `opencode.db` (`session_v2`, o `session` en versiones antiguas): una fila por sesión, con título y carpeta. |
| **Goose** | `goose/sessions/sessions.db`: el `usage_ledger` por petición, o los totales de cada sesión en versiones antiguas. |
| **Amp** | `~/.local/share/amp/threads/T-*.json`: el uso de cada respuesta. |
| **Cline, Roo Code, Kilo Code** | `tasks/*/ui_messages.json` en el almacenamiento de la extensión en VS Code, Cursor, Windsurf, VSCodium y otros derivados. |
| **Zed** | `threads/threads.db`: el uso de cada hilo del agente (los hilos comprimidos con zstd necesitan Python 3.14+ o el paquete `zstandard`). |
| **zcode** | `~/.zcode/cli/db/db.sqlite`, tabla `model_usage`. Su `input_tokens` incluye la caché leída, así que se descuenta. |
| **OpenBot** | Los agentes de OpenBot funcionan sobre Claude Code y opencode. Las sesiones cuya carpeta está en `…/OpenBot/…` cuentan como `openbot` en vez de contarse dos veces, y llevan el nombre del agente. |

Estas hay que configurarlas una vez. Al marcarlas, toktop te da un texto para pegárselo a tu agente de IA y que las configure por ti:

| App | Cómo |
|---|---|
| **dsh** (deepseek-harness) | Un plugin añade una línea JSON por petición a `deepseek-harness.jsonl`, en la carpeta de datos de toktop. |
| **Aider** | `analytics-log:` en `~/.aider.conf.yml` hace que Aider escriba un registro local de eventos (no envía nada). Ese registro no separa la caché. |

Cursor, Windsurf y GitHub Copilot solo guardan el uso en sus servidores, así que no se pueden leer en local. Crush solo guarda los tokens de la última petición, así que tampoco se puede sumar.

Las rutas se detectan en macOS, Linux y Windows. Si alguna app guarda sus datos en otro sitio, o quieres desactivar una fuente, usa [`config.example.toml`](config.example.toml) como plantilla.

## Cómo funciona

- **Histórico.** toktop guarda su propio `history.db` en `~/.local/share/toktop/` (en Windows, `%LOCALAPPDATA%\toktop\`). Cada arranque vuelca lo que dicen las apps y se queda con el máximo de cada contador. El panel abre al momento con el histórico y se actualiza cuando termina la lectura en segundo plano.
- **Precios.** La [lista pública de OpenRouter](https://openrouter.ai/api/v1/models) se guarda 24 h en `prices.json`. Sin conexión se usa esa copia y, si no existe, una tabla interna. El razonamiento se cobra como output. Los planes de suscripción no se facturan por token, así que los costes son orientativos.
- **Privacidad.** Ni telemetría ni cuentas. La petición de precios es un GET anónimo.

## Licencia

[MIT](LICENSE)

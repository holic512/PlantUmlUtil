# PlantUmlUtil

![Logo](res/logo.png)

A modern Python + PyQt6 desktop app for PlantUML with real‑time PNG/SVG preview, quality controls, clipboard copy, and file export. It bundles `jar/plantuml.jar` and uses JPype to start the JVM and call PlantUML APIs.

---

## Highlights
- Instant preview (PNG/SVG) with non‑blocking async rendering
- Quality controls: `DPI` (PNG only) and `scale`
- Smooth mouse‑wheel zoom (25%–600%)
- Copy to clipboard (PNG image or SVG text) and save to files
- Open `.puml/.plantuml/.iuml` files
- Auto‑wrap `@startuml`/`@enduml` if missing
- Heuristic detection for PlantUML texts (arrows, `skinparam`, `class`, etc.)
- Styled UI via QSS; logs written to `logs/app.log`

## Tech Stack
- Python 3.10+
- PyQt6 (desktop GUI)
- PlantUML (`jar/plantuml.jar`) via JPype/JVM
- Windows (developed and verified)

## Requirements
- Python ≥ 3.10
- JRE/JDK 8+ (JPype must be able to locate `jvm.dll`)
- Python packages: `PyQt6`, `JPype1`

## Installation
```bash
pip install -r requirements.txt
```

## Run
```bash
python main.py
```

## Packaging (PyInstaller)
- Option A: spec file (Windows)
  ```bash
  pyinstaller main.spec
  ```
  Includes data files (`jar/plantuml.jar`, `res/logo.png`, `ui/style.qss`) and hidden imports (`PyQt6.QtSvgWidgets`, `PyQt6.QtSvg`); executable name: `PlantUmlUtil`.
- Option B: CLI (Windows)
  ```bash
  pyinstaller \
    --noconsole \
    --name PlantUmlUtil \
    --add-data "jar/plantuml.jar;jar" \
    --add-data "res/logo.png;res" \
    --add-data "ui/style.qss;ui" \
    --hidden-import PyQt6.QtSvgWidgets \
    --hidden-import PyQt6.QtSvg \
    main.py
  ```
- Optional: set EXE icon (Windows requires `.ico`)
  ```bash
  --icon res/logo.ico
  ```

> Note: The packaged app requires a system JRE/JDK. JPype must be able to locate `jvm.dll` at runtime.

## Screenshot
![Screenshot](docx/截图.png)

## Project Structure
```
jar/                # PlantUML engine JAR
res/logo.png        # App icon
ui/main_window.py   # Main window and preview logic
services/           # PlantUML render service (JPype/JVM)
utils/logger.py     # Logging to logs/app.log
main.py             # Entry point
```

## Troubleshooting
- JVM not found: install JRE/JDK and ensure JPype can discover it.
- SVG preview unavailable: automatically falls back to PNG when `PyQt6.QtSvgWidgets` isn’t available.
- Render failures: verify PlantUML syntax or explicitly add `@startuml`/`@enduml`.

## App Icon
The application and window icon are set from `res/logo.png` in `main.py`.

> Chinese documentation: see `README.md`.

# PlantUmlUtil

![Logo](res/logo.png)

PlantUmlUtil is a Python + PyQt6 GUI for PlantUML. It provides real‑time PNG/SVG preview, quality controls (DPI/scale), clipboard copy, and file saving. It ships with `jar/plantuml.jar` and uses JPype to start the JVM and call PlantUML APIs.

---

## Overview
PlantUmlUtil is a desktop application for authoring and previewing PlantUML diagrams with a clean UI and helpful quality controls.

## Features
- Real‑time preview (PNG/SVG) with non‑blocking async rendering
- Quality options: `DPI` (PNG only) and `scale`
- Mouse‑wheel zoom (25%–600%)
- Copy to clipboard (PNG or SVG text) and save to files
- Open `.puml/.plantuml/.iuml` files
- Auto wrap `@startuml/@enduml` if missing
- Heuristic detection for PUML texts (arrows, `skinparam`, `class`, etc.)
- QSS‑styled UI; logs written to `logs/app.log`

## Tech Stack & Environment
- Language: Python 3.10+
- Framework: PyQt6 (desktop GUI)
- Rendering: PlantUML (`jar/plantuml.jar`) via JPype/JVM
- OS: Windows (developed and verified on Windows)

## Requirements
- Python ≥ 3.10
- Java runtime (JRE/JDK 8+); JPype must be able to locate `jvm.dll`
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
- Option A: use the provided `main.spec` (Windows)
  ```bash
  pyinstaller main.spec
  ```
  Includes data files (`jar/plantuml.jar`, `res/logo.png`, `ui/style.qss`) and hidden imports (`PyQt6.QtSvgWidgets`, `PyQt6.QtSvg`) with executable name `PlantUmlUtil`.
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

## Structure (short)
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
- SVG preview unavailable: the app falls back to PNG when `PyQt6.QtSvgWidgets` isn’t available.
- Render failures: verify PlantUML syntax or explicitly add `@startuml/@enduml`.

## App Icon
The application and window icon are set from `res/logo.png` in `main.py`.

> Chinese documentation: see `README.md`.


from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import jpype
from jpype import JClass
import logging
import hashlib
from collections import OrderedDict
from threading import RLock


@dataclass
class RenderResult:
    fmt: str
    file_path: Path
    bytes_data: bytes
    svg_text: Optional[str] = None


class PlantUMLError(Exception):
    pass


class PlantUMLService:
    def __init__(self, jar_path: str):
        self.jar_path = jar_path
        self._jvm_started = False
        self._logger = logging.getLogger(self.__class__.__name__)
        self._classes_loaded = False
        self._SourceStringReader = None
        self._FileFormat = None
        self._FileFormatOption = None
        self._ByteArrayOutputStream = None
        self._lock = RLock()
        self._cache = _LRUCache(32)
        self._target_dir = Path(tempfile.gettempdir()) / "PlanUmlUtil"
        self._target_dir.mkdir(parents=True, exist_ok=True)

    def start_jvm(self) -> None:
        if jpype.isJVMStarted():
            self._jvm_started = True
            return
        jvm_path = jpype.getDefaultJVMPath()
        if not os.path.exists(self.jar_path):
            raise PlantUMLError(f"PlantUML jar not found: {self.jar_path}")
        self._logger.info("Starting JVM with jar: %s", self.jar_path)
        jpype.startJVM(jvm_path, "-ea", classpath=[self.jar_path])
        self._jvm_started = True
        self._load_classes()

    def _load_classes(self) -> None:
        if self._classes_loaded:
            return
        try:
            self._SourceStringReader = JClass("net.sourceforge.plantuml.SourceStringReader")
            self._FileFormat = JClass("net.sourceforge.plantuml.FileFormat")
            self._FileFormatOption = JClass("net.sourceforge.plantuml.FileFormatOption")
            self._ByteArrayOutputStream = JClass("java.io.ByteArrayOutputStream")
            self._classes_loaded = True
        except Exception as e:
            raise PlantUMLError(f"Failed to load PlantUML API classes: {e}")

    def render(self, uml_text: str, fmt: str = "png", dpi: Optional[int] = None, scale: Optional[float] = None) -> RenderResult:
        if fmt not in {"png", "svg"}:
            raise PlantUMLError(f"Unsupported format: {fmt}")

        self.start_jvm()
        if not self._classes_loaded:
            self._load_classes()
        if not jpype.isThreadAttachedToJVM():
            try:
                jpype.attachThreadToJVM()
            except Exception:
                pass

        # 注入质量选项到文本，确保API能统一应用（skinparam dpi、scale）
        processed_text = uml_text
        inject_lines = []
        if dpi is not None and fmt == "png":
            inject_lines.append(f"skinparam dpi {int(dpi)}")
        if scale is not None:
            # PlantUML支持 'scale N'
            inject_lines.append(f"scale {float(scale)}")

        if inject_lines:
            if "@startuml" in processed_text:
                # 在第一个 @startuml 之后插入
                idx = processed_text.find("@startuml")
                idx_end = idx + len("@startuml")
                processed_text = processed_text[:idx_end] + "\n" + "\n".join(inject_lines) + "\n" + processed_text[idx_end:]
            else:
                processed_text = "@startuml\n" + "\n".join(inject_lines) + "\n" + processed_text + "\n@enduml"

        key_src = f"{fmt}|{dpi}|{scale}|" + processed_text
        digest = hashlib.sha1(key_src.encode("utf-8")).hexdigest()[:16]
        cached = None
        with self._lock:
            cached = self._cache.get(digest)
        if cached is not None:
            bytes_data, svg_text_cached = cached
            out_name = f"diagram_{digest}.{fmt}"
            final_path = self._target_dir / out_name
            try:
                final_path.write_bytes(bytes_data)
            except Exception:
                pass
            return RenderResult(fmt=fmt, file_path=final_path, bytes_data=bytes_data, svg_text=svg_text_cached)

        reader = self._SourceStringReader(processed_text)
        fmt_enum = self._FileFormat.PNG if fmt == "png" else self._FileFormat.SVG
        option = self._FileFormatOption(fmt_enum)
        # 尝试设置dpi/scale到选项（若API支持），失败则忽略
        try:
            if dpi is not None and fmt == "png" and hasattr(option, "setDpi"):
                option.setDpi(int(dpi))
        except Exception:
            pass
        try:
            if scale is not None and hasattr(option, "setScale"):
                option.setScale(float(scale))
        except Exception:
            pass

        baos = self._ByteArrayOutputStream()
        try:
            # 返回 DiagramDescription，可用于检查块信息；错误时也通常生成错误图片
            _desc = reader.outputImage(baos, option)
        except Exception as e:
            raise PlantUMLError(f"PlantUML render error: {e}")

        data = bytes(baos.toByteArray())
        if not data:
            raise PlantUMLError("PlantUML未生成输出，可能为语法错误或不支持的指令")

        out_name = f"diagram_{digest}.{fmt}"
        final_path = self._target_dir / out_name
        final_path.write_bytes(data)

        svg_text = None
        if fmt == "svg":
            try:
                svg_text = data.decode("utf-8", errors="ignore")
            except Exception:
                svg_text = None

        with self._lock:
            self._cache.set(digest, (data, svg_text))

        return RenderResult(fmt=fmt, file_path=final_path, bytes_data=data, svg_text=svg_text)

    def shutdown(self) -> None:
        try:
            if jpype.isJVMStarted():
                jpype.shutdownJVM()
        except Exception as e:
            self._logger.warning("Failed to shutdown JVM: %s", e)

    def force_terminate(self) -> None:
        try:
            if jpype.isJVMStarted():
                JClass("java.lang.Runtime").getRuntime().halt(0)
        except Exception:
            os._exit(0)


class _LRUCache:
    def __init__(self, maxsize: int = 32):
        self._maxsize = maxsize
        self._data = OrderedDict()

    def get(self, key):
        if key in self._data:
            value = self._data.pop(key)
            self._data[key] = value
            return value
        return None

    def set(self, key, value):
        if key in self._data:
            self._data.pop(key)
        else:
            if len(self._data) >= self._maxsize:
                self._data.popitem(last=False)
        self._data[key] = value


from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QEvent
from PyQt6.QtGui import QAction, QCloseEvent, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QStackedWidget,
    QProgressBar,
    QScrollArea,
)

try:
    from PyQt6.QtSvgWidgets import QSvgWidget  # type: ignore
    SVG_WIDGET_AVAILABLE = True
except Exception:
    SVG_WIDGET_AVAILABLE = False

from services.plantuml_service import PlantUMLService, PlantUMLError, RenderResult
import logging


class MainWindow(QMainWindow):
    def __init__(self, jar_path: str):
        super().__init__()
        self.setWindowTitle("PlanUML 图形化工具")
        self.resize(1100, 700)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._load_style()

        self.service = PlantUMLService(jar_path)
        self.current_result: Optional[RenderResult] = None
        self._render_worker: Optional[_RenderWorker] = None

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("在此输入/编辑PlantUML代码，例如:\n@startuml\nAlice -> Bob: Hello\n@enduml")

        # PNG 预览滚动容器与标签
        self.png_label = QLabel()
        self.png_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.png_scroll = QScrollArea()
        self.png_scroll.setWidgetResizable(True) # 允许内容自适应，但我们会手动调整 label 大小
        self.png_scroll.setWidget(self.png_label)
        self.png_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter) # 让内容居中

        # SVG 预览滚动容器与部件
        self.svg_widget = QSvgWidget() if SVG_WIDGET_AVAILABLE else None
        self.svg_scroll = QScrollArea()
        self.svg_scroll.setWidgetResizable(True)
        if self.svg_widget:
            self.svg_scroll.setWidget(self.svg_widget)
            self.svg_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1) # 由 QSS 控制外观，这里设个小值
        splitter.setChildrenCollapsible(False)
        
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.addWidget(self.editor)
        splitter.addWidget(editor_container)

        # 预览栈：占位页、加载页、预览页
        self.preview_stack = QStackedWidget()
        self.page_placeholder = QLabel("欢迎使用：在左侧输入PlantUML代码，右侧实时预览")
        self.page_placeholder.setObjectName("previewPlaceholder")
        self.page_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_error = QLabel("")
        self.page_error.setObjectName("errorLabel")
        self.page_error.setWordWrap(True)
        self.page_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_loading = QWidget()
        self.page_loading.setObjectName("previewLoading")
        loading_layout = QVBoxLayout(self.page_loading)
        loading_layout.setContentsMargins(20, 20, 20, 20)
        self.loading_label = QLabel("正在加载资源…")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # 不确定进度，显示动画
        loading_layout.addStretch(1)
        loading_layout.addWidget(self.loading_label)
        loading_layout.addWidget(self.loading_bar)
        loading_layout.addStretch(1)

        # 预览页根据可用性添加
        self.page_png = self.png_scroll
        self.page_svg = self.svg_scroll if self.svg_widget else QWidget()

        self.preview_stack.addWidget(self.page_placeholder)
        self.preview_stack.addWidget(self.page_loading)
        self.preview_stack.addWidget(self.page_error)
        self.preview_stack.addWidget(self.page_png)
        self.preview_stack.addWidget(self.page_svg)

        splitter.addWidget(self.preview_stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        # 底部固定控制栏
        bottom_bar = QWidget()
        bottom_bar.setObjectName("bottomBar")
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0) # 由 QSS padding 控制
        bottom_layout.setSpacing(12)
        bottom_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # bottom_bar.setFixedHeight(64) # 移除固定高度，由内容和 padding 决定

        self.format_combo = QComboBox()
        self.format_combo.addItems(["png", "svg"])
        self.format_combo.setToolTip("选择输出格式")
        self.format_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.format_combo.setMaximumWidth(120)
        bottom_layout.addWidget(QLabel("格式:"))
        bottom_layout.addWidget(self.format_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["自定义", "屏幕 (96dpi, 1x)", "标准 (150dpi, 1x)", "高清 (300dpi, 2x)", "打印 (600dpi, 2x)"])
        self.preset_combo.setCurrentIndex(2)
        self.preset_combo.setToolTip("快速选择渲染质量预设")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.preset_combo.setMaximumWidth(220)
        bottom_layout.addWidget(QLabel("预设:"))
        bottom_layout.addWidget(self.preset_combo)

        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(150)
        self.dpi_spin.setToolTip("设置DPI (仅PNG)")
        self.dpi_spin.valueChanged.connect(lambda: self.preset_combo.setCurrentIndex(0))
        self.dpi_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.dpi_spin.setMaximumWidth(90)
        bottom_layout.addWidget(QLabel("DPI:"))
        bottom_layout.addWidget(self.dpi_spin)

        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(1, 8)
        self.scale_spin.setValue(1)
        self.scale_spin.setToolTip("设置缩放比例")
        self.scale_spin.valueChanged.connect(lambda: self.preset_combo.setCurrentIndex(0))
        self.scale_spin.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.scale_spin.setMaximumWidth(90)
        bottom_layout.addWidget(QLabel("缩放:"))
        bottom_layout.addWidget(self.scale_spin)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bottom_layout.addWidget(spacer)

        render_btn = QPushButton("渲染")
        render_btn.setObjectName("renderButton")
        render_btn.setToolTip("手动渲染当前图表 (Ctrl+R)")
        render_btn.setShortcut("Ctrl+R")
        render_btn.clicked.connect(self.render_preview)
        render_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        render_btn.setMaximumWidth(80)
        bottom_layout.addWidget(render_btn)

        save_btn = QPushButton("保存")
        save_btn.setToolTip("保存为文件 (Ctrl+S)")
        save_btn.setShortcut("Ctrl+S")
        save_btn.clicked.connect(self.save_output)
        save_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        save_btn.setMaximumWidth(80)
        bottom_layout.addWidget(save_btn)

        copy_btn = QPushButton("复制")
        copy_btn.setToolTip("复制图像到剪贴板 (Ctrl+C)")
        copy_btn.setShortcut("Ctrl+C")
        copy_btn.clicked.connect(self.copy_to_clipboard)
        copy_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        copy_btn.setMaximumWidth(80)
        bottom_layout.addWidget(copy_btn)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(splitter)
        layout.addWidget(bottom_bar)
        self.setCentralWidget(central)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.editor.textChanged.connect(self._on_text_changed)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self.render_preview)

        self.menuBar().setVisible(False)
        self._start_resource_loading()
        # 安装滚轮事件过滤器
        self.png_scroll.viewport().installEventFilter(self)
        if self.svg_widget:
            self.svg_scroll.viewport().installEventFilter(self)
        self._zoom = 1.0
        self._original_pixmap = None
        self._base_size_png = None
        self._base_size_svg = None

    def _init_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")

        act_open = QAction("打开", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._open_file)
        file_menu.addAction(act_open)

        act_save_as = QAction("另存为", self)
        act_save_as.setShortcut("Ctrl+Shift+S")
        act_save_as.triggered.connect(self.save_output)
        file_menu.addAction(act_save_as)

        file_menu.addSeparator()

        act_exit = QAction("退出", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

    def _load_style(self) -> None:
        try:
            style_path = Path(__file__).parent / "style.qss"
            if style_path.exists():
                style_content = style_path.read_text(encoding="utf-8")
                # 将样式应用到应用程序实例，确保对话框等也能生效
                app = QApplication.instance()
                if app:
                    app.setStyleSheet(style_content)
                self._logger.info("Loaded style from %s", style_path)
            else:
                self._logger.warning("Style file not found: %s", style_path)
        except Exception as e:
            self._logger.error("Failed to load style: %s", e)

    def _on_preset_changed(self, index: int) -> None:
        # ["自定义", "屏幕 (96dpi, 1x)", "标准 (150dpi, 1x)", "高清 (300dpi, 2x)", "打印 (600dpi, 2x)"]
        if index == 0:
            return
        
        # 临时断开信号连接，防止触发自定义模式
        self.dpi_spin.blockSignals(True)
        self.scale_spin.blockSignals(True)

        if index == 1:   # 屏幕
            self.dpi_spin.setValue(96)
            self.scale_spin.setValue(1)
        elif index == 2: # 标准
            self.dpi_spin.setValue(150)
            self.scale_spin.setValue(1)
        elif index == 3: # 高清
            self.dpi_spin.setValue(300)
            self.scale_spin.setValue(2)
        elif index == 4: # 打印
            self.dpi_spin.setValue(600)
            self.scale_spin.setValue(2)

        self.dpi_spin.blockSignals(False)
        self.scale_spin.blockSignals(False)

    def _on_text_changed(self) -> None:
        self._debounce.start(500)

    def _get_quality_options(self, fmt: str) -> dict:
        dpi = self.dpi_spin.value() if fmt == "png" else None
        scale = self.scale_spin.value()
        return {"dpi": dpi, "scale": scale}

    def render_preview(self) -> None:
        text = self.editor.toPlainText().strip()
        if not text:
            # 空内容不渲染，显示占位
            self.preview_stack.setCurrentWidget(self.page_placeholder)
            return
        if not self._is_puml_text(text):
            self.page_error.setText("当前文本不是有效的PlantUML描述，已跳过渲染")
            self.preview_stack.setCurrentWidget(self.page_error)
            return
        fmt = self.format_combo.currentText()
        opts = self._get_quality_options(fmt)
        preview_fmt = fmt if not (fmt == "svg" and not SVG_WIDGET_AVAILABLE) else "png"
        self._logger.info("Render preview requested: fmt=%s opts=%s", preview_fmt, opts)

        # 自动包裹 @startuml/@enduml，避免用户忘记标记导致渲染异常
        render_text = text
        if "@startuml" not in text:
            render_text = f"@startuml\n{text}\n@enduml"

        # 若已有渲染任务在执行，忽略新的渲染请求以避免竞争
        if self._render_worker is not None and self._render_worker.isRunning():
            return

        # 显示加载页，异步渲染
        self.preview_stack.setCurrentWidget(self.page_loading)
        worker = _RenderWorker(self.service, render_text, preview_fmt, opts.get("dpi"), opts.get("scale"))
        worker.done.connect(self._on_render_done)
        worker.error.connect(self._on_render_error)
        worker.finished.connect(self._clear_render_worker)
        self._render_worker = worker
        worker.start()

    def save_output(self) -> None:
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "提示", "请先输入PlantUML代码")
            return
        fmt = self.format_combo.currentText()
        opts = self._get_quality_options(fmt)
        try:
            self._logger.info("Save output requested: fmt=%s opts=%s", fmt, opts)
            result = self.service.render(text, fmt=fmt, dpi=opts.get("dpi"), scale=opts.get("scale"))
            suffix = ".png" if fmt == "png" else ".svg"
            fn, _ = QFileDialog.getSaveFileName(self, "保存输出", f"diagram{suffix}", f"*.{fmt}")
            if fn:
                Path(fn).write_bytes(result.bytes_data)
                self.status.showMessage(f"已保存: {fn}", 3000)
        except PlantUMLError as e:
            QMessageBox.critical(self, "保存错误", str(e))

    def _on_render_done(self, result: RenderResult) -> None:
        self.current_result = result
        if result.fmt == "png":
            pix = QPixmap()
            pix.loadFromData(result.bytes_data)
            if pix.isNull():
                self.preview_stack.setCurrentWidget(self.page_placeholder)
            else:
                self._original_pixmap = pix
                self._base_size_png = pix.size()
                self._zoom = 1.0
                scaled = self._original_pixmap.scaled(self._base_size_png * self._zoom, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.png_label.setPixmap(scaled)
                self.png_label.resize(scaled.size())
                self.preview_stack.setCurrentWidget(self.page_png)
        else:
            if self.svg_widget:
                try:
                    self.svg_widget.load(result.bytes_data)
                    # 记录基础尺寸并应用缩放
                    try:
                        renderer = self.svg_widget.renderer()
                        self._base_size_svg = renderer.defaultSize()
                    except Exception:
                        self._base_size_svg = None
                    self._zoom = 1.0
                    if self._base_size_svg:
                        self.svg_widget.resize(int(self._base_size_svg.width() * self._zoom), int(self._base_size_svg.height() * self._zoom))
                    self.preview_stack.setCurrentWidget(self.page_svg)
                except Exception:
                    self.preview_stack.setCurrentWidget(self.page_png)
            else:
                self.preview_stack.setCurrentWidget(self.page_png)
        self.status.showMessage("渲染成功", 2000)

    def _on_render_error(self, msg: str) -> None:
        self.page_error.setText(f"渲染错误：\n{msg}")
        self.preview_stack.setCurrentWidget(self.page_error)
        self.status.showMessage("渲染失败", 3000)

    def _clear_render_worker(self) -> None:
        self._render_worker = None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and (obj is self.png_scroll.viewport() or obj is (self.svg_scroll.viewport() if self.svg_widget else None)):
            delta = event.angleDelta().y()
            step = 1.1 if delta > 0 else 1/1.1
            new_zoom = max(0.25, min(6.0, self._zoom * step))
            if abs(new_zoom - self._zoom) > 1e-3:
                self._zoom = new_zoom
                self._apply_zoom()
                self.status.showMessage(f"缩放 {int(self._zoom * 100)}%", 800)
            return True
        return super().eventFilter(obj, event)

    def _apply_zoom(self) -> None:
        if not self.current_result:
            return
        if self.current_result.fmt == "png" and self._original_pixmap and self._base_size_png:
            scaled = self._original_pixmap.scaled(self._base_size_png * self._zoom, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.png_label.setPixmap(scaled)
            self.png_label.resize(scaled.size())
            self.preview_stack.setCurrentWidget(self.page_png)
        elif self.current_result.fmt == "svg" and self.svg_widget and self._base_size_svg:
            self.svg_widget.resize(int(self._base_size_svg.width() * self._zoom), int(self._base_size_svg.height() * self._zoom))
            self.preview_stack.setCurrentWidget(self.page_svg)

    def copy_to_clipboard(self) -> None:
        if not self.current_result:
            QMessageBox.information(self, "提示", "请先渲染以生成预览")
            return
        cb = QApplication.clipboard()
        if self.current_result.fmt == "png":
            pix = QPixmap()
            pix.loadFromData(self.current_result.bytes_data)
            cb.setPixmap(pix)
            self.status.showMessage("PNG已复制到剪贴板", 2000)
        else:
            # 尝试复制栅格化预览；同时复制SVG文本到剪贴板文本通道
            if self.current_result.svg_text:
                cb.setText(self.current_result.svg_text)
            pix = QPixmap()
            pix.loadFromData(self.current_result.bytes_data)
            if not pix.isNull():
                cb.setPixmap(pix)
                self.status.showMessage("SVG图像/文本已复制到剪贴板", 2000)
            else:
                self.status.showMessage("已复制SVG文本到剪贴板", 2000)

    def _open_file(self) -> None:
        fn, _ = QFileDialog.getOpenFileName(self, "打开PlantUML文件", "", "PlantUML (*.puml *.plantuml *.iuml);;所有文件 (*.*)")
        if fn:
            try:
                content = Path(fn).read_text(encoding="utf-8")
                self.editor.setPlainText(content)
                self.status.showMessage(f"已打开: {fn}", 2000)
            except Exception as e:
                QMessageBox.critical(self, "打开错误", str(e))

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._debounce.stop()
        except Exception:
            pass
        try:
            if self._render_worker and self._render_worker.isRunning():
                try:
                    self._render_worker.requestInterruption()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "_jar_loader") and self._jar_loader and self._jar_loader.isRunning():
                try:
                    self._jar_loader.requestInterruption()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.service.force_terminate()
        except Exception:
            pass
        event.accept()

    def _start_resource_loading(self) -> None:
        # 启动时加载JAR，显示加载进度
        self.preview_stack.setCurrentWidget(self.page_loading)
        self.loading_label.setText("正在加载PlantUML引擎…")
        loader = _JarLoader(self.service)
        loader.progress.connect(self._on_load_progress)
        loader.done.connect(self._on_load_done)
        loader.start()
        self._jar_loader = loader

    def _on_load_progress(self, value: int, text: str) -> None:
        self.loading_bar.setRange(0, 100)
        self.loading_bar.setValue(value)
        self.loading_label.setText(text)

    def _on_load_done(self, ok: bool, err: str | None) -> None:
        if ok:
            self.loading_bar.setRange(0, 0)
            self.preview_stack.setCurrentWidget(self.page_placeholder)
            # 首次渲染：确保第一张图片显示
            if not self.editor.toPlainText().strip():
                self.editor.setPlainText("""@startuml
Alice -> Bob: Hello
Bob --> Alice: Hi
@enduml""")
            # 使用轻微延迟触发，确保UI稳定；若已有渲染任务，避免重复
            QTimer.singleShot(200, lambda: (self._render_worker is None or not self._render_worker.isRunning()) and self.render_preview())
        else:
            self.preview_stack.setCurrentWidget(self.page_placeholder)
            QMessageBox.critical(self, "资源加载失败", err or "未知错误")

    def _is_puml_text(self, text: str) -> bool:
        t = text.strip()
        if not t:
            return False
        if "@startuml" in t and "@enduml" in t:
            return True
        # 简单启发式：包含关系箭头或skinparam等关键字时认为是PUML
        keywords = ["->", "-->", "skinparam", "class ", "actor ", "usecase ", "rectangle ", "interface ", "note ", "partition "]
        return any(k in t for k in keywords)


class _JarLoader(QThread):
    progress = pyqtSignal(int, str)
    done = pyqtSignal(bool, str)

    def __init__(self, service: PlantUMLService):
        super().__init__()
        self._service = service

    def run(self) -> None:
        try:
            try:
                import jpype
                if jpype.isJVMStarted() and not jpype.isThreadAttachedToJVM():
                    jpype.attachThreadToJVM()
            except Exception:
                pass
            self.progress.emit(10, "初始化JVM…")
            self._service.start_jvm()
            self.progress.emit(100, "加载完成")
            self.done.emit(True, "")
        except Exception as e:
            self.done.emit(False, str(e))


class _RenderWorker(QThread):
    done = pyqtSignal(RenderResult)
    error = pyqtSignal(str)

    def __init__(self, service: PlantUMLService, text: str, fmt: str, dpi: int | None, scale: float | None):
        super().__init__()
        self._service = service
        self._text = text
        self._fmt = fmt
        self._dpi = dpi
        self._scale = scale

    def run(self) -> None:
        try:
            result = self._service.render(self._text, fmt=self._fmt, dpi=self._dpi, scale=self._scale)
            self.done.emit(result)
        except PlantUMLError as e:
            self.error.emit(str(e))


def create_main_window(jar_path: str) -> MainWindow:
    return MainWindow(jar_path)

import sys, os, json, time, platform
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject, QPoint
from PyQt5.QtGui import QFont, QPalette, QColor, QKeySequence
from deep_translator import GoogleTranslator, YandexTranslator, DeeplTranslator
import pyperclip
import keyboard

# ---------- Определение ОС и пути к конфигу ----------
IS_WINDOWS = platform.system() == "Windows"
IS_MAC = platform.system() == "Darwin"

if IS_WINDOWS:
    CONFIG_DIR = os.path.join(os.environ['APPDATA'], "QuickTranslate")
elif IS_MAC:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "QuickTranslate")
else:
    CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".quicktranslate")

os.makedirs(CONFIG_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

# ---------- Потокобезопасный глобальный хоткей ----------
class GlobalHotkey(QObject):
    activated = pyqtSignal()

    def __init__(self, hotkey_str, parent=None):
        super().__init__(parent)
        self.hotkey_str = hotkey_str
        self._register()

    def _register(self):
        try:
            keyboard.remove_hotkey(self.hotkey_str)
        except:
            pass
        keyboard.add_hotkey(self.hotkey_str, self._on_hotkey)

    def _on_hotkey(self):
        self.activated.emit()

    def update_hotkey(self, new_hotkey):
        self.hotkey_str = new_hotkey
        self._register()

# ---------- Конфигурация ----------
DEFAULT_CONFIG = {
    "service": "Google",
    "yandex_key": "",
    "deepl_key": "",
    "src_lang": "ru",
    "tgt_lang": "en",
    "clear_after_translate": False,
    "history": [],
    "hotkey": "Ctrl+Q"
}

# ---------- Диалог настроек ----------
class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Настройки")
        self.setFixedSize(440, 300)
        self.setStyleSheet("""
            QDialog {
                background: #1e1e2e;
                border-radius: 16px;
                border: 2px solid #7289da;
            }
            QLabel { color: #e0e0e0; font-size: 14px; }
            QComboBox, QLineEdit {
                background: #2a2a3c; color: white;
                border: 1px solid #5a5a7a; border-radius: 8px;
                padding: 8px; font-size: 13px;
            }
            QComboBox:hover, QLineEdit:hover { border-color: #7289da; }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7289da, stop:1 #9b6dff);
                color: white; border: none; padding: 10px 20px;
                border-radius: 10px; font-weight: bold; font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5b6eae, stop:1 #7e55e0);
            }
        """)
        layout = QFormLayout(self)
        layout.setSpacing(14)

        self.service_combo = QComboBox()
        self.service_combo.addItems(["Google", "Yandex", "DeepL"])
        self.service_combo.setCurrentText(config.get("service", "Google"))
        layout.addRow("Сервис перевода:", self.service_combo)

        self.yandex_key_edit = QLineEdit()
        self.yandex_key_edit.setPlaceholderText("API-ключ Яндекс")
        self.yandex_key_edit.setText(config.get("yandex_key", ""))
        layout.addRow("Yandex Key:", self.yandex_key_edit)

        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setPlaceholderText("API-ключ DeepL")
        self.deepl_key_edit.setText(config.get("deepl_key", ""))
        layout.addRow("DeepL Key:", self.deepl_key_edit)

        self.hotkey_edit = QKeySequenceEdit()
        self.hotkey_edit.setKeySequence(QKeySequence(config.get("hotkey", "Ctrl+Q")))
        layout.addRow("Горячая клавиша:", self.hotkey_edit)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        layout.addRow(btn_box)

    def get_data(self):
        return {
            "service": self.service_combo.currentText(),
            "yandex_key": self.yandex_key_edit.text().strip(),
            "deepl_key": self.deepl_key_edit.text().strip(),
            "hotkey": self.hotkey_edit.keySequence().toString()
        }

# ---------- История ----------
class HistoryDialog(QDialog):
    def __init__(self, history, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История переводов")
        self.setFixedSize(560, 420)
        self.setStyleSheet("""
            QDialog {
                background: #1e1e2e;
                border-radius: 16px;
                border: 2px solid #7289da;
            }
            QListWidget {
                background: #2a2a3c; color: #e0e0e0;
                border-radius: 10px; padding: 8px;
                font-size: 13px;
            }
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7289da, stop:1 #9b6dff);
                color: white; border: none;
                padding: 10px 16px; border-radius: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #5b6eae, stop:1 #7e55e0);
            }
        """)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        for entry in reversed(history):
            text = f"{entry['src_lang']} → {entry['tgt_lang']}\n{entry['src']} → {entry['tgt']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        copy_btn = QPushButton("Копировать перевод")
        copy_btn.clicked.connect(self.copy_selected)
        layout.addWidget(copy_btn)

    def copy_selected(self):
        item = self.list_widget.currentItem()
        if item:
            entry = item.data(Qt.UserRole)
            pyperclip.copy(entry['tgt'])
            QMessageBox.information(self, "Скопировано", "Перевод скопирован в буфер")

# ---------- Главное окно (с перетаскиванием и кнопкой swap) ----------
class TranslatorWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ QuickTranslate")
        self.resize(540, 640)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.config = self.load_config()
        self.history = self.config.get("history", [])

        # Потокобезопасный глобальный хоткей
        self.global_hotkey = GlobalHotkey(self.config.get("hotkey", "Ctrl+Q"))
        self.global_hotkey.activated.connect(self.toggle_window)

        self.init_ui()
        self.show()
        self.fade_in()

        self.drag_pos = QPoint()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("""
            QWidget#central {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1a1a2e, stop:1 #16213e);
                border-radius: 24px;
                border: 2px solid #7289da;
            }
        """)
        central.setObjectName("central")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 0)
        central.setGraphicsEffect(shadow)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # Заголовок
        title_layout = QHBoxLayout()
        self.title_label = QLabel("✨ QuickTranslate")
        self.title_label.setStyleSheet("color: white; font-size: 22px; font-weight: bold;")
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(36, 36)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #aaa; font-size: 22px; border: none; border-radius: 18px; }
            QPushButton:hover { background: #ff6b6b; color: white; }
        """)
        close_btn.clicked.connect(lambda: self.hide())
        title_layout.addWidget(close_btn)
        layout.addLayout(title_layout)

        # Выбор языка с кнопкой swap
        lang_layout = QHBoxLayout()
        self.src_combo = self._create_combo(["auto", "en", "ru", "de", "fr", "es", "it", "zh", "ja", "ko"])
        self.src_combo.setCurrentText(self.config.get("src_lang", "ru"))
        lang_layout.addWidget(QLabel("С какого языка:"))
        lang_layout.addWidget(self.src_combo)

        # Кнопка swap ⇄
        self.swap_btn = QPushButton("⇄")
        self.swap_btn.setFixedSize(40, 40)
        self.swap_btn.setToolTip("Поменять языки местами")
        self.swap_btn.setStyleSheet("""
            QPushButton {
                background: #3c3c5c; color: white; border: none;
                border-radius: 10px; font-size: 20px; font-weight: bold;
            }
            QPushButton:hover { background: #5b6eae; }
        """)
        self.swap_btn.clicked.connect(self.swap_languages)
        lang_layout.addWidget(self.swap_btn)

        self.tgt_combo = self._create_combo(["en", "ru", "de", "fr", "es", "it", "zh", "ja", "ko"])
        self.tgt_combo.setCurrentText(self.config.get("tgt_lang", "en"))
        lang_layout.addWidget(QLabel("На какой язык:"))
        lang_layout.addWidget(self.tgt_combo)
        layout.addLayout(lang_layout)

        # Поле ввода
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("Введите текст и нажмите Enter для перевода...")
        self.input_text.setStyleSheet("""
            QTextEdit {
                background: #232741; color: white; border: 1px solid #7289da;
                border-radius: 12px; padding: 14px; font-size: 15px;
            }
            QTextEdit:focus { border-color: #9b6dff; }
        """)
        self.input_text.installEventFilter(self)
        layout.addWidget(self.input_text)

        # Чекбокс очистки
        self.clear_checkbox = QCheckBox("Очищать поле после перевода")
        self.clear_checkbox.setChecked(self.config.get("clear_after_translate", False))
        self.clear_checkbox.setStyleSheet("color: #ccc; font-size: 13px;")
        layout.addWidget(self.clear_checkbox)

        # Кнопка перевода
        self.translate_btn = QPushButton("🌐 Перевести (Enter)")
        self.translate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #7289da, stop:1 #9b6dff);
                color: white; border: none; padding: 14px;
                border-radius: 12px; font-size: 16px; font-weight: bold;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #5b6eae, stop:1 #7e55e0); }
            QPushButton:pressed { padding: 13px; }
        """)
        self.translate_btn.clicked.connect(self.perform_translation)
        layout.addWidget(self.translate_btn)

        # Поле вывода + кнопка копирования
        output_layout = QHBoxLayout()
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background: #232741; color: #e0e0e0; border: 1px solid #7289da;
                border-radius: 12px; padding: 14px; font-size: 15px;
            }
        """)
        output_layout.addWidget(self.output_text)

        self.copy_btn = QToolButton()
        self.copy_btn.setText("📋")
        self.copy_btn.setToolTip("Копировать перевод")
        self.copy_btn.setStyleSheet("""
            QToolButton {
                background: #3c3c5c; color: white; border: none;
                border-radius: 10px; font-size: 22px; padding: 10px;
            }
            QToolButton:hover { background: #5b6eae; }
        """)
        self.copy_btn.clicked.connect(self.copy_translation)
        output_layout.addWidget(self.copy_btn)
        layout.addLayout(output_layout)

        # Нижние кнопки
        btn_layout = QHBoxLayout()
        self.history_btn = QPushButton("📚 История")
        self.history_btn.setStyleSheet("""
            QPushButton { background: #3c3c5c; color: white; border: none;
                          padding: 10px 16px; border-radius: 10px; font-size: 13px; }
            QPushButton:hover { background: #5b6eae; }
        """)
        self.history_btn.clicked.connect(self.show_history)
        btn_layout.addWidget(self.history_btn)
        btn_layout.addStretch()
        self.settings_btn = QPushButton("⚙️ Настройки")
        self.settings_btn.setStyleSheet("""
            QPushButton { background: #3c3c5c; color: white; border: none;
                          padding: 10px 16px; border-radius: 10px; font-size: 13px; }
            QPushButton:hover { background: #5b6eae; }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        btn_layout.addWidget(self.settings_btn)
        layout.addLayout(btn_layout)

    def _create_combo(self, items):
        combo = QComboBox()
        combo.addItems(items)
        combo.setStyleSheet("""
            QComboBox {
                background: #3c3c5c; color: white; border: 1px solid #7289da;
                border-radius: 8px; padding: 8px; font-size: 14px;
            }
            QComboBox:hover { border-color: #9b6dff; }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #2a2a3c; color: white;
                selection-background-color: #7289da;
            }
        """)
        return combo

    def swap_languages(self):
        """Меняем языки местами."""
        src = self.src_combo.currentText()
        tgt = self.tgt_combo.currentText()
        # Если исходный язык "auto", при свапе ставим tgt -> src, а auto -> tgt (обычно неудобно)
        # Лучше: если src == "auto", то просто поменять местами, но auto не должен стать целевым.
        if src == "auto":
            # Делаем целевым "auto" нельзя, оставим как есть или отключим кнопку? Просто не меняем.
            return
        # Устанавливаем новый src = tgt, новый tgt = src
        self.src_combo.setCurrentText(tgt)
        self.tgt_combo.setCurrentText(src)

    def eventFilter(self, obj, event):
        if obj is self.input_text and event.type() == event.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if event.modifiers() == Qt.ControlModifier:
                    self.input_text.insertPlainText('\n')
                    return True
                else:
                    self.perform_translation()
                    return True
        return super().eventFilter(obj, event)

    def perform_translation(self):
        text = self.input_text.toPlainText().strip()
        if not text:
            return
        src_lang = self.src_combo.currentText()
        tgt_lang = self.tgt_combo.currentText()
        service = self.config.get("service", "Google")
        try:
            translated = self.translate_text(text, src_lang, tgt_lang, service)
            self.output_text.setPlainText(translated)
            self.add_to_history({
                "src": text, "tgt": translated,
                "src_lang": src_lang, "tgt_lang": tgt_lang,
                "service": service, "time": time.time()
            })
            if self.clear_checkbox.isChecked():
                self.input_text.clear()
        except Exception as e:
            self.output_text.setPlainText(f"Ошибка: {e}")

    def translate_text(self, text, src, tgt, service):
        if service == "Google":
            return GoogleTranslator(source=src, target=tgt).translate(text)
        elif service == "Yandex":
            key = self.config.get("yandex_key", "")
            if not key:
                raise Exception("Не указан API-ключ Яндекс")
            return YandexTranslator(api_key=key, source=src, target=tgt).translate(text)
        elif service == "DeepL":
            key = self.config.get("deepl_key", "")
            if not key:
                raise Exception("Не указан API-ключ DeepL")
            return DeeplTranslator(api_key=key, source=src, target=tgt).translate(text)
        else:
            raise Exception("Неизвестный сервис")

    def add_to_history(self, entry):
        self.history.insert(0, entry)
        self.history = self.history[:20]
        self.save_config()

    def copy_translation(self):
        text = self.output_text.toPlainText().strip()
        if text:
            pyperclip.copy(text)
            self.copy_btn.setStyleSheet("""
                QToolButton { background: #9b6dff; color: white; border-radius: 10px;
                              font-size: 22px; padding: 10px; }
            """)
            QTimer.singleShot(800, lambda: self.copy_btn.setStyleSheet("""
                QToolButton { background: #3c3c5c; color: white; border-radius: 10px;
                              font-size: 22px; padding: 10px; }
            """))

    def show_history(self):
        dlg = HistoryDialog(self.history, self)
        dlg.exec_()

    def open_settings(self):
        dlg = SettingsDialog(self.config, self)
        if dlg.exec_() == QDialog.Accepted:
            new_data = dlg.get_data()
            self.config.update(new_data)
            self.save_config()
            self.global_hotkey.update_hotkey(new_data["hotkey"])
            QMessageBox.information(self, "Готово",
                "Настройки сохранены.\nНовая горячая клавиша: " + new_data["hotkey"])

    def toggle_window(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()
            self.activateWindow()
            self.fade_in()

    def fade_in(self, duration=300):
        self.setWindowOpacity(0.0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(duration)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()

    # ---------- Перетаскивание ----------
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and not self.drag_pos.isNull():
            self.move(event.globalPos() - self.drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_pos = QPoint()
        super().mouseReleaseEvent(event)

    # ---------- Конфигурация ----------
    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
            except:
                return DEFAULT_CONFIG.copy()
        else:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            return DEFAULT_CONFIG.copy()

    def save_config(self):
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

    def closeEvent(self, event):
        event.ignore()
        self.hide()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(30, 30, 46))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    app.setPalette(dark_palette)

    if IS_MAC:
        app.setWindowIcon(QIcon())

    window = TranslatorWindow()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
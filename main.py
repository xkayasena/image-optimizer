"""
Image Optimizer
---------------
Toplu görseli WebP formatına dönüştüren PySide6 masaüstü uygulaması.
"""

import sys
from pathlib import Path

from PIL import Image, ImageOps
from PySide6.QtCore import Qt, QThread, Signal, QSize, QEvent
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QProgressBar, QSlider,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView
)

# Yalnızca bu uzantılara sahip dosyaları görsel olarak kabul ediyoruz.
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".jfif", ".webp"}


def format_size(size_bytes: int) -> str:
    """Bayt cinsindeki boyutu kullanıcıya okunabilir B / KB / MB biçimine çevirir."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


class ConversionWorker(QThread):
    """
    Dönüştürme işlemini arayüzden ayrı bir iş parçacığında yürütür.
    Böylece büyük görseller işlenirken pencere donmaz.

    Signal'lar, arka plan iş parçacığından arayüze güvenli bilgi taşır.
    """
    progress_changed = Signal(int)  # İlerleme çubuğuna 0-100 arası değer gönderir.
    file_finished = Signal(str, str, str, str, int, int)
    error_occurred = Signal(str, str)  # Kaynak dosyanın yolu ve hata açıklaması.
    all_finished = Signal(int, int, int, int)  # başarılı, hatalı, eski toplam, yeni toplam

    def __init__(self, files, output_dir, quality, resize_enabled, max_width, max_height):
        super().__init__()
        self.files = files
        self.output_dir = Path(output_dir)
        self.quality = quality
        self.resize_enabled = resize_enabled
        self.max_width = max_width
        self.max_height = max_height
        self._cancel_requested = False

    def cancel(self):
        # Bu bayrak, döngünün bir sonraki kontrol noktasında işlemi durdurur.
        self._cancel_requested = True

    def run(self):
        """QThread.start() çağrıldığında otomatik olarak bu metot çalışır."""
        converted = failed = old_total = new_total = 0
        total = len(self.files)

        for index, file_path in enumerate(self.files):
            if self._cancel_requested:
                break

            source = Path(file_path)
            try:
                 # Kaynak dosyayla çakışmayan, benzersiz bir çıktı adı bul.
                output = self.output_dir / f"{source.stem}.webp"
                suffix = 2

                while output.resolve() == source.resolve() or output.exists():
                    output = self.output_dir / f"{source.stem}_{suffix}.webp"
                    suffix += 1

                # Çıktı klasörü yoksa ara klasörlerle beraber oluştur.
                output.parent.mkdir(parents=True, exist_ok=True)

                with Image.open(source) as original:
                    # Fotoğrafın EXIF bilgisindeki yön bilgisini uygulayıp doğru yönde göster.
                    image = ImageOps.exif_transpose(original)

                    # Şeffaflık bilgisi olan PNG/WebP gibi görsellerin şeffaflığını koru.
                    has_alpha = (
                        image.mode in ("RGBA", "LA")
                        or (image.mode == "P" and "transparency" in image.info)
                    )
                    image = image.convert("RGBA" if has_alpha else "RGB")

                    # Thumbnail en-boy oranını korur; görseli verilen sınırların dışına çıkarmaz.
                    if self.resize_enabled:
                        image.thumbnail(
                            (self.max_width, self.max_height),
                            Image.Resampling.LANCZOS
                        )

                    # quality dosya boyutu/kalite dengesini, method sıkıştırma yöntemini etkiler.
                    image.save(output, "WEBP", quality=self.quality, method=6)

                # Boyutları hem dosya başına hem de genel toplam için hesapla.
                old_size = source.stat().st_size
                new_size = output.stat().st_size
                old_total += old_size
                new_total += new_size

                # Pozitif değer küçülmeyi, negatif değer dosyanın büyümesini ifade eder.
                change = (1 - new_size / old_size) * 100 if old_size else 0
                if change >= 0:
                    change_text = f"%{change:.1f} küçülme"
                else:
                    change_text = f"%{abs(change):.1f} büyüme"

                # Arayüze ham bayt değerlerini de gönderiyoruz; toplam tasarruf bunlarla hesaplanır.
                self.file_finished.emit(
                    str(source), source.name, format_size(old_size),
                    format_size(new_size), old_size, new_size
                )
                converted += 1

            except Exception as exc:
                # Bir dosyadaki hata diğer dosyaların dönüştürülmesini durdurmasın.
                failed += 1
                self.error_occurred.emit(str(source), str(exc))

            # Her dosya denemesinden sonra ilerlemeyi güncelle.
            self.progress_changed.emit(int((index + 1) / total * 100))

        self.all_finished.emit(converted, failed, old_total, new_total)


class DropArea(QFrame):
    """Dosyaların Explorer'dan sürüklenip bırakılabildiği alan."""
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)  # Qt'nin bu widget üzerine dosya bırakılmasına izin vermesini sağlar.
        self.setObjectName("dropArea")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Görselleri buraya sürükle ve bırak")
        title.setObjectName("dropTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("veya aşağıdaki “Görsel seç” düğmesini kullan")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

    def dragEnterEvent(self, event: QDragEnterEvent):
        # Sürüklenen içerik dosya bağlantıları içeriyorsa bırakmayı kabul et.
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = []
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() in SUPPORTED_FORMATS:
                paths.append(str(path))
            elif path.is_dir():
                # Klasör bırakılırsa içindeki desteklenen görselleri alt klasörler dahil bul.
                paths.extend(
                    str(p) for p in path.rglob("*")
                    if p.is_file() and p.suffix.lower() in SUPPORTED_FORMATS
                )
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

class ImageTable(QTableWidget):
    """Boş tablo alanına tıklanınca satır seçimini kaldırır."""

    def mousePressEvent(self, event):
        # Tıklanan konumda bir tablo hücresi var mı?
        item = self.itemAt(event.position().toPoint())

        if item is None:
            # Boş alana tıklanmışsa mevcut seçimi kaldır.
            self.clearSelection()
            self.setCurrentItem(None)

        # Qt'nin normal fare davranışını da çalıştır.
        super().mousePressEvent(event)

class MainWindow(QMainWindow):
    """Uygulamanın ana penceresi ve arayüz olaylarının yönetildiği sınıf."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Optimizer")
        self.resize(1100, 800)

        self.files = []  # Arayüze eklenen kaynak dosyaların tam yolları.
        self.worker = None  # QThread nesnesine referans; çalışırken yaşamaya devam etmesi gerekir.
        self.output_dir = str(Path.home() / "Pictures" / "Image Optimizer")
        self.results_by_path = {}  # Tam dosya yolunu tablo satırıyla eşleştirir.

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(14)

        # Başlık bölümü.
        header = QVBoxLayout()
        title = QLabel("Image Optimizer")
        title.setObjectName("appTitle")
        subtitle = QLabel("Görsellerini toplu dönüştür, boyutlarını küçült.")
        subtitle.setObjectName("muted")
        header.addWidget(title)
        header.addWidget(subtitle)
        outer.addLayout(header)

        # Sürükle-bırak alanını dosya ekleme metoduna bağla.
        self.drop_area = DropArea()
        self.drop_area.files_dropped.connect(self.add_files)
        outer.addWidget(self.drop_area)

        action_row = QHBoxLayout()
        self.select_button = QPushButton("Görsel seç")
        self.select_button.clicked.connect(self.choose_files)  # Tıklama olayını metotla eşleştir.
        self.clear_button = QPushButton("Listeyi temizle")
        self.clear_button.setObjectName("secondaryButton")
        self.clear_button.clicked.connect(self.clear_files)

        # Yalnızca seçili görseli listeden kaldıran buton.
        self.remove_button = QPushButton("Seçili görseli kaldır")

        # Diğer ikincil butonlarla aynı görünümü kullanır.
        self.remove_button.setObjectName("secondaryButton")

        # Butona tıklanınca remove_selected_file metodu çalışır.
        self.remove_button.clicked.connect(self.remove_selected_file)

        action_row.addWidget(self.select_button)
        action_row.addWidget(self.clear_button)
        # Yeni butonu diğer butonların yanına yerleştir.
        action_row.addWidget(self.remove_button)

        action_row.addStretch()
        self.count_label = QLabel("Henüz görsel seçilmedi")
        self.count_label.setObjectName("muted")
        action_row.addWidget(self.count_label)
        outer.addLayout(action_row)

        # İlk sütunda dosya adı ve küçük önizleme simgesi yer alır.
        self.table = ImageTable(0, 5)
        # Bir hücre yerine satırın tamamının seçilmesini sağlar.
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        # Aynı anda yalnızca bir satır seçilebilsin.
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        

        self.table.setHorizontalHeaderLabels(
            ["Görsel / dosya adı", "Orijinal boyut", "Çıktı boyutu", "Sonuç", "Durum"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 5):
            self.table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setIconSize(QSize(56, 44))  # Tablo içindeki görsel önizlemelerinin boyutu.
        self.table.setMinimumHeight(230)
        outer.addWidget(self.table, 1)

        # Toplam boyut/tasarruf kartları; dönüştürme bitince gerçek sonuçlarla doldurulur.
        summary = QFrame()
        summary.setObjectName("summaryPanel")
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 12, 16, 12)
        self.original_total_label = QLabel("Orijinal toplam\n0 B")
        self.output_total_label = QLabel("Çıktı toplamı\n0 B")
        self.saving_total_label = QLabel("Toplam değişim\n—")
        for label in (self.original_total_label, self.output_total_label, self.saving_total_label):
            label.setObjectName("summaryValue")
            summary_layout.addWidget(label, 1)
        outer.addWidget(summary)

        # Ayar paneli.
        settings = QFrame()
        settings.setObjectName("settingsPanel")
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(18, 15, 18, 15)
        settings_layout.setSpacing(10)
        settings_title = QLabel("Dönüştürme ayarları")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("WebP kalitesi"))
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(40, 100)
        self.quality_slider.setValue(85)
        self.quality_value = QLabel("85")
        self.quality_value.setMinimumWidth(28)
        # Slider değişince yanındaki sayı anında değişsin.
        self.quality_slider.valueChanged.connect(
            lambda value: self.quality_value.setText(str(value))
        )
        quality_row.addWidget(self.quality_slider, 1)
        quality_row.addWidget(self.quality_value)
        settings_layout.addLayout(quality_row)

        self.resize_checkbox = QCheckBox("Görselleri maksimum 1920 × 1920 boyutuna küçült")
        self.resize_checkbox.setChecked(True)
        settings_layout.addWidget(self.resize_checkbox)

        output_row = QHBoxLayout()
        self.output_label = QLabel(f"Çıktı klasörü: {self.output_dir}")
        self.output_label.setWordWrap(True)
        self.output_label.setObjectName("muted")
        self.output_button = QPushButton("Klasör seç")
        self.output_button.setObjectName("secondaryButton")
        self.output_button.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_label, 1)
        output_row.addWidget(self.output_button)
        settings_layout.addLayout(output_row)
        outer.addWidget(settings)

        bottom = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.convert_button = QPushButton("Dönüştürmeyi başlat")
        self.convert_button.setMinimumHeight(44)
        self.convert_button.clicked.connect(self.start_conversion)

        # İptal butonu başlangıçta etkin olmayacak.
        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("secondaryButton")
        self.cancel_button.setEnabled(False)

        # Tıklanınca ConversionWorker içindeki cancel metodunu çağıracağız.
        self.cancel_button.clicked.connect(self.cancel_conversion)

        bottom.addWidget(self.progress, 1)
        bottom.addWidget(self.convert_button)
        bottom.addWidget(self.cancel_button)
        outer.addLayout(bottom)

        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("muted")
        outer.addWidget(self.status_label)

        # Qt stylesheet ile uygulamanın genel renklerini ve widget görünümlerini belirle.
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #f7f9fc; color: #172033; font-size: 13px; }
            QLabel#appTitle { font-size: 28px; font-weight: 700; }
            QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
            QLabel#muted { color: #68758b; }
            QLabel#summaryValue { font-size: 14px; font-weight: 650; }
            QFrame#dropArea { background: #ffffff; border: 2px dashed #a9c8ff; border-radius: 14px; min-height: 100px; }
            QLabel#dropTitle { color: #1769e0; font-size: 17px; font-weight: 650; }
            QFrame#settingsPanel, QFrame#summaryPanel { background: #ffffff; border: 1px solid #e0e6ef; border-radius: 12px; }
            QTableWidget { background: #ffffff; border: 1px solid #e0e6ef; border-radius: 10px; gridline-color: #edf0f5; }
            QHeaderView::section { background: #f0f4fa; color: #536176; padding: 9px; border: none; font-weight: 600; }
            QPushButton { background: #1769e0; color: white; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
            QPushButton:hover { background: #0f58c5; }
            QPushButton:disabled { background: #aebbd0; }
            QPushButton#secondaryButton { background: #e9eff8; color: #24334d; }
            QPushButton#secondaryButton:hover { background: #dce7f6; }
            QSlider::groove:horizontal { height: 6px; background: #dce5f2; border-radius: 3px; }
            QSlider::handle:horizontal { background: #1769e0; width: 16px; margin: -5px 0; border-radius: 8px; }
            QProgressBar { border: 1px solid #dce5f2; border-radius: 7px; background: #ffffff; text-align: center; min-height: 20px; }
            QProgressBar::chunk { background: #1769e0; border-radius: 6px; }
            QCheckBox { spacing: 8px; }
        """)
        # Uygulama genelindeki fare tıklamalarını izlemeye başla.
        app = QApplication.instance()
        app.installEventFilter(self)


    def eventFilter(self, watched, event):
        # Yalnızca fare tıklamalarını kontrol et.
        if event.type() == QEvent.Type.MouseButtonPress:
            if isinstance(watched, QWidget):
                # Tıklama tablonun içindeyse seçimi koru.
                if (
                    watched == self.table
                    or watched == self.table.viewport()
                    or self.table.isAncestorOf(watched)
                ):
                    return super().eventFilter(watched, event)

                # Seçili görseli kaldır butonunda da seçimi koru.
                if (
                    watched == self.remove_button
                    or self.remove_button.isAncestorOf(watched)
                ):
                    return super().eventFilter(watched, event)

                # Diğer alanlara tıklanınca tablo seçimini kaldır.
                self.table.clearSelection()

        return super().eventFilter(watched, event)

    def add_files(self, paths):
        """Dosyaları tekrarsız biçimde listeye ve tabloya ekler."""
        added = 0
        existing = set(self.files)  # Liste üyeliği kontrolünü hızlandırmak için set kullanılır.
        for path in paths:
            p = Path(path)
            if p.suffix.lower() not in SUPPORTED_FORMATS or not p.is_file() or str(p) in existing:
                continue

            self.files.append(str(p))
            existing.add(str(p))
            row = self.table.rowCount()
            self.table.insertRow(row)

            # QPixmap dosyadan küçük bir görsel önizlemesi üretir; QIcon tablo hücresinde gösterir.
            preview = QPixmap(str(p))
            if not preview.isNull():
                preview = preview.scaled(
                    56, 44, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            name_item = QTableWidgetItem(QIcon(preview), p.name)
            name_item.setToolTip(str(p))  # Üzerine gelince tam dosya yolunu göster.
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(format_size(p.stat().st_size)))
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            self.table.setItem(row, 4, QTableWidgetItem("Bekliyor"))
            self.results_by_path[str(p)] = row
            added += 1

        self.count_label.setText(f"{len(self.files)} görsel seçildi")
        if added:
            self.status_label.setText(f"{added} görsel listeye eklendi.")
        self.reset_summary()

    def reset_summary(self):
        """Yeni dosya listesi oluştuğunda önceki çalıştırmanın toplamlarını temizler."""
        self.original_total_label.setText("Orijinal toplam\n—")
        self.output_total_label.setText("Çıktı toplamı\n—")
        self.saving_total_label.setText("Toplam değişim\nDönüştürme bekleniyor")

    def choose_files(self):
        # getOpenFileNames tek seferde birden fazla dosya seçmeye izin verir.
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Görselleri seç", "",
            "Görseller (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.jfif *.webp)"
        )
        self.add_files(paths)

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Çıktı klasörünü seç", self.output_dir)
        if folder:  # Kullanıcı pencereyi iptal ettiyse mevcut klasörü değiştirme.
            self.output_dir = folder
            self.output_label.setText(f"Çıktı klasörü: {folder}")

    def eventFilter(self, watched, event):
        """Tablo dışındaki tıklamalarda seçimi kaldır."""

        # Yalnızca fareyle basma olaylarını kontrol et.
        if event.type() == QEvent.Type.MouseButtonPress:

            # Tıklanan nesne bir widget ise kontrol et.
            if isinstance(watched, QWidget):

                # Tabloya veya tablonun içindeki bir widget'a tıklandıysa dokunma.
                is_table_area = (
                    watched == self.table
                    or watched == self.table.viewport()
                    or self.table.isAncestorOf(watched)
                )

                # Kaldırma butonunda seçim korunmalı ki seçili dosya silinebilsin.
                is_remove_button = (
                    watched == self.remove_button
                    or self.remove_button.isAncestorOf(watched)
                )

                # Tablo alanı ve kaldırma butonu dışındaki tıklamalarda seçimi kaldır.
                if not is_table_area and not is_remove_button:
                    self.table.clearSelection()

        # Olayın normal şekilde işlenmesine izin ver.
        return super().eventFilter(watched, event)

    def remove_selected_file(self):
        """Seçili görseli hem listeden hem tablodan kaldırır."""

        # Dönüştürme devam ederken listeyi değiştirmeyi engelle.
        if self.worker and self.worker.isRunning():
            return

        # Tabloda seçili olan satırın indeksini al.
        row = self.table.currentRow()

        # -1, seçili satır olmadığı anlamına gelir.
        if row < 0:
            QMessageBox.information(
                self,
                "Görsel seçilmedi",
                "Lütfen kaldırmak istediğin görseli seç."
            )
            return

        # Listedeki dosyanın tam yolunu al ve listeden kaldır.
        file_path = self.files.pop(row)

        # Görsele ait tablo satırını kaldır.
        self.table.removeRow(row)

        # Dosya yolu -> satır numarası eşleştirmesini yeniden oluştur.
        self.results_by_path = {
            path: index
            for index, path in enumerate(self.files)
        }

        # Güncel dosya sayısını ekranda göster.
        self.count_label.setText(
            f"{len(self.files)} görsel seçildi"
        )

        # Önceki dönüştürme sonuçlarını temizle.
        self.reset_summary()

        # Kullanıcıya işlem hakkında bilgi ver.
        self.status_label.setText(
            f"{Path(file_path).name} listeden kaldırıldı."
        )

    def clear_files(self):
        # Çalışma sırasında tabloyu temizlemek worker ile arayüzün eşleşmesini bozabilir.
        if self.worker and self.worker.isRunning():
            return
        self.files.clear()
        self.results_by_path.clear()
        self.table.setRowCount(0)
        self.count_label.setText("Henüz görsel seçilmedi")
        self.progress.setValue(0)
        self.reset_summary()
        self.status_label.setText("Liste temizlendi.")

    def cancel_conversion(self):
        """Çalışan dönüştürme işlemine iptal isteği gönderir."""

        if self.worker and self.worker.isRunning():
            self.worker.cancel()

            # Aynı isteğin tekrar gönderilmesini önle.
            self.cancel_button.setEnabled(False)

            self.status_label.setText(
                "İptal istendi. Devam eden görselin işlemi bitiriliyor..."
            )

    def start_conversion(self):
        if not self.files:
            QMessageBox.information(self, "Görsel seçilmedi", "Önce en az bir görsel seç.")
            return
        if self.worker and self.worker.isRunning():
            return

       # Dönüştürme sırasında normal işlem butonlarını kilitle.
        for button in (
            self.convert_button,
            self.select_button,
            self.clear_button,
            self.output_button,
            self.remove_button,
        ):
            button.setEnabled(False)

        # İşlem başladığında iptal butonu kullanılabilir olsun.
        self.cancel_button.setEnabled(True)

        self.progress.setValue(0)
        for row in range(self.table.rowCount()):
            self.table.setItem(row, 2, QTableWidgetItem("—"))
            self.table.setItem(row, 3, QTableWidgetItem("—"))
            self.table.setItem(row, 4, QTableWidgetItem("İşleniyor"))

        # Arka plan işçisi, arayüzden alınan ayarlarla başlatılır.
        self.worker = ConversionWorker(
            self.files, self.output_dir, self.quality_slider.value(),
            self.resize_checkbox.isChecked(), 1920, 1920
        )

        # Signal-slot bağlantıları: worker sinyali geldiğinde ilgili arayüz metodu çalışır.
        self.worker.progress_changed.connect(self.progress.setValue)
        self.worker.file_finished.connect(self.update_file_result)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.all_finished.connect(self.conversion_finished)
        self.worker.start()
        self.status_label.setText("Görseller dönüştürülüyor...")

    def update_file_result(self, path, name, old_size_text, new_size_text, old_size, new_size):
        """Dönüşen dosyanın tablosunu günceller; aynı adlı dosyalar karışmasın diye tam yol kullanır."""
        row = self.results_by_path.get(path)
        if row is None:
            return

        change = (1 - new_size / old_size) * 100 if old_size else 0
        if change >= 0:
            change_text = f"%{change:.1f} küçülme"
        else:
            change_text = f"%{abs(change):.1f} büyüme"

        self.table.setItem(row, 1, QTableWidgetItem(old_size_text))
        self.table.setItem(row, 2, QTableWidgetItem(new_size_text))
        self.table.setItem(row, 3, QTableWidgetItem(change_text))
        self.table.setItem(row, 4, QTableWidgetItem("Tamamlandı"))

    def show_error(self, path, message):
        """Hatalı dosyayı tabloda işaretle ve durum satırında hatayı göster."""
        row = self.results_by_path.get(path)
        if row is not None:
            self.table.setItem(row, 4, QTableWidgetItem("Hata"))
            self.table.item(row, 4).setToolTip(message)
        self.status_label.setText(f"Hata: {Path(path).name} — {message}")

    def conversion_finished(self, converted, failed, old_total, new_total):
        """İşlem bittiğinde toplam boyutları, tasarrufu ve butonları günceller."""
       # İşlem sona erdiğinde normal butonları yeniden etkinleştir.
        for button in (
            self.convert_button,
            self.select_button,
            self.clear_button,
            self.output_button,
            self.remove_button,
        ):
            button.setEnabled(True)

        # İşlem bittiği için iptal artık mümkün değil.
        self.cancel_button.setEnabled(False)

        self.original_total_label.setText(f"Orijinal toplam\n{format_size(old_total)}")
        self.output_total_label.setText(f"Çıktı toplamı\n{format_size(new_total)}")

        # Toplam tasarrufu tek tek yüzde ortalamasıyla değil, toplam baytlarla hesaplamak doğru olur.
        change = (1 - new_total / old_total) * 100 if old_total else 0
        if change >= 0:
            change_text = f"{change:.1f}% daha küçük"
        else:
            change_text = f"{abs(change):.1f}% daha büyük"
        self.saving_total_label.setText(f"Toplam değişim\n{change_text}")

        if self.worker and self.worker._cancel_requested:
            self.status_label.setText(
                f"İşlem iptal edildi — {converted} başarılı, {failed} hatalı."
            )
        else:
            self.status_label.setText(
                f"İşlem tamamlandı — {converted} başarılı, {failed} hatalı."
            )

        if self.worker and self.worker._cancel_requested:
            QMessageBox.information(
                self,
                "İşlem iptal edildi",
                f"İşlem iptal edildi.\n"
                f"{converted} görsel dönüştürüldü.\n"
                f"{failed} dosyada hata oluştu."
                f"\n\nÇıktı klasörü: {self.output_dir}"
            )
        elif converted or failed:
            QMessageBox.information(
                self,
                "İşlem tamamlandı",
                f"{converted} görsel dönüştürüldü.\n"
                f"{failed} dosyada hata oluştu."
                f"\n\nÇıktı klasörü: {self.output_dir}"
            )


if __name__ == "__main__":
    # QApplication, Qt uygulamasını başlatan ana nesnedir.
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Platformlar arasında daha tutarlı bir temel görünüm.
    window = MainWindow()
    window.show()
    sys.exit(app.exec())  # Olay döngüsünü çalıştır; pencere açık kaldığı sürece uygulamayı canlı tut.

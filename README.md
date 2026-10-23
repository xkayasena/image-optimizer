Image Optimizer

Python, PySide6 ve Pillow kullanılarak geliştirilmiş, toplu görsel dönüştürme ve optimizasyonu sağlayan bir masaüstü uygulaması.

Image Optimizer; birden fazla görseli WebP formatına dönüştürmeyi, görsel kalitesini ayarlamayı, isteğe bağlı boyutlandırma yapmayı ve dosya boyutlarını karşılaştırmayı sağlar.

Özellikler

Toplu Dönüştürme: Birden fazla görseli WebP formatına dönüştürme.

Kalite Ayarı: WebP çıktı kalitesini belirleme.

Görsel Boyutlandırma: En-boy oranını koruyarak görselleri isteğe bağlı olarak en fazla 1920 × 1920 boyutlarına küçültme.

Sürükle ve Bırak: Görselleri uygulamaya sürükleyerek ekleme.

İşlem İlerlemesi: Dönüştürme sürecini takip etme.

İşlem İptali: Devam eden dönüştürme işlemini iptal etme.

Dosya Boyutu Karşılaştırması: Orijinal ve dönüştürülmüş dosyaların boyutlarını karşılaştırma.

Hata Yönetimi: Hatalı görselleri raporlama ve diğer görsellerin işlenmesine devam etme.

Benzersiz Dosya Adları: Mevcut çıktı dosyalarının üzerine yazılmasını önleme.

Çıktı Klasörü Seçimi: Dönüştürülen görsellerin kaydedileceği klasörü belirleme.

Kullanılan Teknolojiler

Python

PySide6

Pillow

QThread

PyInstaller

Gereksinimler

Proje bağımlılıklarıyla uyumlu bir Python sürümü

Paketlenmiş .exe sürümü için Windows

Kurulum

Depoyu bilgisayarına klonla:

git clone https://github.com/xkayasena/image-optimizer.git
cd image-optimizer

Sanal ortam oluştur:

py -3.14 -m venv .venv

Gerekli bağımlılıkları yükle:

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Uygulamayı çalıştır:

.\.venv\Scripts\python.exe main.py

Windows EXE Oluşturma

PyInstaller'ı yükle:

.\.venv\Scripts\python.exe -m pip install pyinstaller

Uygulamayı paketle:

.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --name "ImageOptimizer" main.py

Derleme tamamlandığında uygulama şu konumda oluşur:

dist/ImageOptimizer/ImageOptimizer.exe

Kullanım

Görselleri seç veya sürükleyip uygulamaya bırak.

WebP kalite ayarını belirle.

İsteğe bağlı boyutlandırma seçeneğini etkinleştir veya devre dışı bırak.

Çıktı klasörünü seç.

Dönüştürme işlemini başlat.

İşlem durumunu ve dosya boyutu karşılaştırmalarını incele.

Proje Durumu

Uygulama Windows ortamında geliştirilmiş ve temel işlevleri test edilmiştir. Gelecekte yeni özellikler ve iyileştirmeler eklenebilir.

Lisans

Proje için henüz bir açık kaynak lisansı belirlenmemiştir.

# Image Optimizer

PySide6 ve Pillow kullanılarak geliştirilen, görselleri toplu olarak WebP formatına dönüştüren masaüstü uygulaması.

## Özellikler

- Birden fazla görseli toplu dönüştürme
- WebP kalite ayarı
- Görselleri maksimum boyut sınırına göre yeniden boyutlandırma
- Dönüştürme ilerlemesini takip etme
- İşlemi iptal etme
- Orijinal ve çıktı dosya boyutlarını karşılaştırma
- Hatalı dosyaları raporlama
- Mevcut çıktı dosyalarının üzerine yazılmasını önleyen dosya adı kontrolü

## Teknolojiler

- Python
- PySide6
- Pillow
- QThread

## Kurulum

Python kurulu olmalıdır.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Kullanım

1. Dönüştürülecek görselleri seçin.
2. WebP kalite ayarını belirleyin.
3. İsteğe bağlı olarak yeniden boyutlandırmayı etkinleştirin.
4. Çıktı klasörünü seçin.
5. Dönüştürmeyi başlatın.

## Geliştirme Durumu

Proje geliştirilmeye devam etmektedir.

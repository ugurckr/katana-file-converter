"""Çok dilli arayüz: TR (varsayılan), EN, DE, ES.

Dil seçimi ~/.katana/config.json'da saklanır, kayıt yoksa sistem dilinden
algılanır. Metinler t(key) ile, dönüşüm etiketleri translate_label() ile çevrilir.
"""

import json
import locale
import os
import sys
from pathlib import Path

LANGUAGES = {"tr": "Türkçe", "en": "English", "de": "Deutsch", "es": "Español"}

CONFIG_PATH = Path.home() / ".katana" / "config.json"

# 'Kurulsun mu?' sorusuna evet sayılan yanıtlar; boş yanıt = evet.
YES_ANSWERS = ("", "e", "evet", "y", "yes", "j", "ja", "s", "si", "sí")

_STRINGS: dict[str, dict[str, str]] = {
    # ── Banner ──
    "banner.commands": {"tr": "Komutlar", "en": "Commands", "de": "Befehle", "es": "Comandos"},
    "banner.formats": {"tr": "Formatlar", "en": "Formats", "de": "Formate", "es": "Formatos"},
    "banner.stats_line": {
        "tr": "{routes} rota · {formats} format",
        "en": "{routes} routes · {formats} formats",
        "de": "{routes} Routen · {formats} Formate",
        "es": "{routes} rutas · {formats} formatos",
    },
    "banner.subtitle": {
        "tr": " dosya sürükleyin ya da komut yazın ",
        "en": " drag a file or type a command ",
        "de": " Datei hineinziehen oder Befehl eingeben ",
        "es": " arrastra un archivo o escribe un comando ",
    },
    # ── Komut açıklamaları (banner + help) ──
    "cmd.converts": {
        "tr": "desteklenen tüm dönüşümler",
        "en": "all supported conversions",
        "de": "alle unterstützten Umwandlungen",
        "es": "todas las conversiones disponibles",
    },
    "cmd.tools": {
        "tr": "harici araç durumu",
        "en": "external tool status",
        "de": "Status externer Tools",
        "es": "estado de herramientas externas",
    },
    "cmd.credit": {
        "tr": "geliştirici bilgileri",
        "en": "developer info",
        "de": "Entwickler-Infos",
        "es": "información del desarrollador",
    },
    "cmd.stats": {
        "tr": "oturum istatistikleri",
        "en": "session statistics",
        "de": "Sitzungsstatistiken",
        "es": "estadísticas de la sesión",
    },
    "cmd.open": {
        "tr": "son çıktı klasörünü aç",
        "en": "open last output folder",
        "de": "letzten Ausgabeordner öffnen",
        "es": "abrir la última carpeta de salida",
    },
    "cmd.language": {
        "tr": "dil seçimi",
        "en": "choose language",
        "de": "Sprache wählen",
        "es": "elegir idioma",
    },
    "cmd.theme": {
        "tr": "renk teması seçimi",
        "en": "choose color theme",
        "de": "Farbschema wählen",
        "es": "elegir tema de color",
    },
    "cmd.help": {
        "tr": "yardım ve kullanım",
        "en": "help & usage",
        "de": "Hilfe & Verwendung",
        "es": "ayuda y uso",
    },
    "cmd.clear": {
        "tr": "ekranı temizle",
        "en": "clear the screen",
        "de": "Bildschirm leeren",
        "es": "limpiar pantalla",
    },
    "cmd.undo": {
        "tr": "son dönüşümü geri al",
        "en": "undo last conversion",
        "de": "letzte Umwandlung rückgängig",
        "es": "deshacer última conversión",
    },
    "cmd.q": {"tr": "çıkış", "en": "quit", "de": "Beenden", "es": "salir"},
    # ── Kategori adları ──
    "group.image": {"tr": "Görsel", "en": "Image", "de": "Bild", "es": "Imagen"},
    "group.document": {"tr": "Doküman", "en": "Document", "de": "Dokument", "es": "Documento"},
    "group.data": {"tr": "Veri", "en": "Data", "de": "Daten", "es": "Datos"},
    "group.spreadsheet": {"tr": "Tablo", "en": "Spreadsheet", "de": "Tabelle", "es": "Hoja de cálculo"},
    "group.video": {"tr": "Video", "en": "Video", "de": "Video", "es": "Vídeo"},
    "group.audio": {"tr": "Ses", "en": "Audio", "de": "Audio", "es": "Audio"},
    "group.other": {"tr": "Diğer", "en": "Other", "de": "Sonstiges", "es": "Otros"},
    # ── converts ekranı ──
    "converts.title": {
        "tr": "Desteklenen Dönüşümler",
        "en": "Supported Conversions",
        "de": "Unterstützte Umwandlungen",
        "es": "Conversiones disponibles",
    },
    "unit.routes": {"tr": "rota", "en": "routes", "de": "Routen", "es": "rutas"},
    "converts.col.type": {"tr": "Tür", "en": "Type", "de": "Typ", "es": "Tipo"},
    "converts.col.source": {"tr": "Kaynak", "en": "Source", "de": "Quelle", "es": "Origen"},
    "converts.col.targets": {"tr": "Hedefler", "en": "Targets", "de": "Ziele", "es": "Destinos"},
    "converts.footnote": {
        "tr": "* harici araç gerektirir — kurulum durumu için 'tools' yazın.",
        "en": "* requires an external tool — type 'tools' for installation status.",
        "de": "* benötigt ein externes Tool — Status mit 'tools' anzeigen.",
        "es": "* requiere una herramienta externa — escribe 'tools' para ver el estado.",
    },
    # ── tools ekranı ──
    "tools.title": {
        "tr": "Harici Araçlar",
        "en": "External Tools",
        "de": "Externe Tools",
        "es": "Herramientas externas",
    },
    "tools.col.tool": {"tr": "Araç", "en": "Tool", "de": "Tool", "es": "Herramienta"},
    "tools.col.status": {"tr": "Durum", "en": "Status", "de": "Status", "es": "Estado"},
    "tools.col.location": {
        "tr": "Konum / Kurulum",
        "en": "Location / Install",
        "de": "Pfad / Installation",
        "es": "Ubicación / Instalación",
    },
    "tools.installed": {"tr": "✓ Kurulu", "en": "✓ Installed", "de": "✓ Installiert", "es": "✓ Instalado"},
    "tools.missing": {"tr": "✗ Eksik", "en": "✗ Missing", "de": "✗ Fehlt", "es": "✗ Falta"},
    "tools.optional": {
        "tr": "○ Opsiyonel (kurulu değil)",
        "en": "○ Optional (not installed)",
        "de": "○ Optional (nicht installiert)",
        "es": "○ Opcional (no instalado)",
    },
    "tools.note": {
        "tr": "Eksik araçlar, gerektiren ilk dönüşümde otomatik kurulum önerisiyle sorulur.",
        "en": "Missing tools are offered for automatic installation when a conversion first needs them.",
        "de": "Fehlende Tools werden bei der ersten Umwandlung, die sie benötigt, zur Installation angeboten.",
        "es": "Las herramientas que falten se ofrecerán para instalarse cuando una conversión las necesite.",
    },
    # ── credit ekranı ──
    "credit.title": {"tr": "👤 Credit", "en": "👤 Credits", "de": "👤 Credits", "es": "👤 Créditos"},
    "credit.name": {"tr": "İsim", "en": "Name", "de": "Name", "es": "Nombre"},
    "credit.version": {"tr": "Sürüm", "en": "Version", "de": "Version", "es": "Versión"},
    # ── stats ekranı ──
    "stats.title": {
        "tr": "📈 Oturum İstatistikleri",
        "en": "📈 Session Statistics",
        "de": "📈 Sitzungsstatistiken",
        "es": "📈 Estadísticas de la sesión",
    },
    "stats.empty": {
        "tr": "Bu oturumda henüz dönüştürme yapılmadı.",
        "en": "No conversions in this session yet.",
        "de": "In dieser Sitzung wurde noch nichts umgewandelt.",
        "es": "Aún no se ha convertido nada en esta sesión.",
    },
    "stats.converted": {
        "tr": "Dönüştürülen dosya:",
        "en": "Files converted:",
        "de": "Umgewandelte Dateien:",
        "es": "Archivos convertidos:",
    },
    # ── help ekranı ──
    "help.title": {"tr": "❔ Yardım", "en": "❔ Help", "de": "❔ Hilfe", "es": "❔ Ayuda"},
    "help.usage": {"tr": "Kullanım", "en": "Usage", "de": "Verwendung", "es": "Uso"},
    "help.tip1": {
        "tr": "Dosyaları terminale sürükleyip bırakın (birden fazlasını birlikte seçebilirsiniz).",
        "en": "Drag & drop files into the terminal (you can select several at once).",
        "de": "Dateien ins Terminal ziehen (mehrere gleichzeitig möglich).",
        "es": "Arrastra y suelta archivos en la terminal (puedes seleccionar varios a la vez).",
    },
    "help.tip2": {
        "tr": "Çok sayıda dosya için doğrudan bir klasör yolu verin; içi taranır.",
        "en": "For many files, pass a folder path; it will be scanned.",
        "de": "Für viele Dateien einfach einen Ordnerpfad angeben; er wird durchsucht.",
        "es": "Para muchos archivos, indica una carpeta; se analizará su contenido.",
    },
    "help.tip3": {
        "tr": "Komut satırı modu da var: ",
        "en": "There is also a CLI mode: ",
        "de": "Es gibt auch einen CLI-Modus: ",
        "es": "También hay modo de línea de comandos: ",
    },
    # ── language komutu ──
    "language.prompt": {
        "tr": "Hangi dili kullanmak istersiniz?",
        "en": "Which language would you like to use?",
        "de": "Welche Sprache möchten Sie verwenden?",
        "es": "¿Qué idioma quieres usar?",
    },
    "language.changed": {
        "tr": "Dil değiştirildi: {name}",
        "en": "Language changed: {name}",
        "de": "Sprache geändert: {name}",
        "es": "Idioma cambiado: {name}",
    },
    # ── theme komutu ──
    "theme.title": {
        "tr": "🎨 Renk Temaları",
        "en": "🎨 Color Themes",
        "de": "🎨 Farbschemata",
        "es": "🎨 Temas de color",
    },
    "theme.prompt": {
        "tr": "Hangi temayı kullanmak istersiniz?",
        "en": "Which theme would you like to use?",
        "de": "Welches Farbschema möchten Sie verwenden?",
        "es": "¿Qué tema quieres usar?",
    },
    "theme.changed": {
        "tr": "Tema değiştirildi: {name}",
        "en": "Theme changed: {name}",
        "de": "Farbschema geändert: {name}",
        "es": "Tema cambiado: {name}",
    },
    # ── Ana prompt ──
    "prompt.title": {
        "tr": "📁  Dönüştürülecek dosya(ları) sürükleyip bırakın",
        "en": "📁  Drag & drop the file(s) to convert",
        "de": "📁  Datei(en) zum Umwandeln hierher ziehen",
        "es": "📁  Arrastra los archivos que quieras convertir",
    },
    "prompt.hint1": {
        "tr": "(birden fazla dosyayı birlikte seçip sürükleyebilir, ya da",
        "en": "(you can drag several files at once, or",
        "de": "(mehrere Dateien gleichzeitig ziehen oder",
        "es": "(puedes arrastrar varios archivos a la vez, o",
    },
    "prompt.hint2": {
        "tr": "çok sayıda dosya için doğrudan klasör yolu verebilirsiniz)",
        "en": "pass a folder path for many files)",
        "de": "für viele Dateien einen Ordnerpfad angeben)",
        "es": "indicar una carpeta para muchos archivos)",
    },
    "prompt.hint3": {
        "tr": "Komutlar için {help}, çıkmak için boş bırakıp Enter'a basın.",
        "en": "Type {help} for commands; press Enter on an empty line to quit.",
        "de": "{help} zeigt die Befehle; zum Beenden leer lassen und Enter drücken.",
        "es": "Escribe {help} para ver los comandos; pulsa Enter sin nada para salir.",
    },
    "continue.prompt": {
        "tr": "Yeni dönüşüm için Enter, çıktı klasörünü açmak için 'o', çıkmak için 'q'...",
        "en": "Press Enter for another conversion, 'o' to open the output folder, 'q' to quit...",
        "de": "Enter für eine weitere Umwandlung, 'o' öffnet den Ausgabeordner, 'q' zum Beenden...",
        "es": "Pulsa Enter para otra conversión, 'o' para abrir la carpeta de salida, 'q' para salir...",
    },
    # ── open komutu / çıktı klasörü ──
    "open.none": {
        "tr": "Bu oturumda henüz bir dönüşüm yapılmadı.",
        "en": "No conversions in this session yet.",
        "de": "In dieser Sitzung wurde noch nichts umgewandelt.",
        "es": "Aún no se ha convertido nada en esta sesión.",
    },
    "open.opened": {
        "tr": "Klasör açıldı: {p}",
        "en": "Folder opened: {p}",
        "de": "Ordner geöffnet: {p}",
        "es": "Carpeta abierta: {p}",
    },
    # ── Dönüşüm ayarları (kalite/çözünürlük) ──
    "options.jpeg.question": {
        "tr": "JPEG kalitesi? (varsayılan için Enter)",
        "en": "JPEG quality? (press Enter for default)",
        "de": "JPEG-Qualität? (Enter für Standard)",
        "es": "¿Calidad JPEG? (Enter para el valor predeterminado)",
    },
    "options.jpeg.high": {
        "tr": "yüksek kalite (varsayılan)",
        "en": "high quality (default)",
        "de": "hohe Qualität (Standard)",
        "es": "alta calidad (predeterminada)",
    },
    "options.jpeg.balanced": {
        "tr": "dengeli",
        "en": "balanced",
        "de": "ausgewogen",
        "es": "equilibrada",
    },
    "options.jpeg.small": {
        "tr": "küçük dosya boyutu",
        "en": "small file size",
        "de": "kleine Dateigröße",
        "es": "tamaño de archivo pequeño",
    },
    "options.video.question": {
        "tr": "Video çözünürlüğü? (varsayılan için Enter)",
        "en": "Video resolution? (press Enter for default)",
        "de": "Videoauflösung? (Enter für Standard)",
        "es": "¿Resolución del vídeo? (Enter para el valor predeterminado)",
    },
    "options.video.original": {
        "tr": "Orijinal çözünürlük (varsayılan)",
        "en": "Original resolution (default)",
        "de": "Originalauflösung (Standard)",
        "es": "Resolución original (predeterminada)",
    },
    # ── Araç kurulumu ──
    "install.notfound": {
        "tr": "⚠  {tool} sistemde bulunamadı.",
        "en": "⚠  {tool} was not found on this system.",
        "de": "⚠  {tool} wurde auf diesem System nicht gefunden.",
        "es": "⚠  No se encontró {tool} en el sistema.",
    },
    "install.required": {
        "tr": "Bu dönüşüm için gerekli. {installer} ile otomatik kurulsun mu?",
        "en": "It is required for this conversion. Install automatically via {installer}?",
        "de": "Für diese Umwandlung erforderlich. Automatisch über {installer} installieren?",
        "es": "Es necesario para esta conversión. ¿Instalarlo automáticamente con {installer}?",
    },
    "install.ask": {
        "tr": "Kurulsun mu? [E/h] ➜ ",
        "en": "Install? [Y/n] ➜ ",
        "de": "Installieren? [J/n] ➜ ",
        "es": "¿Instalar? [S/n] ➜ ",
    },
    # ── Format seçimi ──
    "select.question": {
        "tr": "Hangi formata dönüştürmek istersiniz?",
        "en": "Which format would you like to convert to?",
        "de": "In welches Format umwandeln?",
        "es": "¿A qué formato quieres convertir?",
    },
    "select.last_used": {
        "tr": "(son seçim)",
        "en": "(last used)",
        "de": "(zuletzt verwendet)",
        "es": "(última elección)",
    },
    "select.bridge_header": {
        "tr": "ara format üzerinden (köprü)",
        "en": "via an intermediate format (bridge)",
        "de": "über ein Zwischenformat (Brücke)",
        "es": "a través de un formato intermedio (puente)",
    },
    "select.via": {
        "tr": "{inter} üzerinden",
        "en": "via {inter}",
        "de": "über {inter}",
        "es": "vía {inter}",
    },
    "select.instruction": {
        "tr": "(↑↓ ile gezin, Enter ile seçin)",
        "en": "(navigate with ↑↓, select with Enter)",
        "de": "(mit ↑↓ navigieren, mit Enter auswählen)",
        "es": "(navega con ↑↓ y elige con Enter)",
    },
    # ── Sonuç mesajları ──
    "error.prefix": {"tr": "Hata", "en": "Error", "de": "Fehler", "es": "Error"},
    "success.converted": {
        "tr": "✓  Dönüştürüldü!",
        "en": "✓  Converted!",
        "de": "✓  Umgewandelt!",
        "es": "✓  ¡Convertido!",
    },
    "summary.title": {"tr": "Özet", "en": "Summary", "de": "Zusammenfassung", "es": "Resumen"},
    "summary.text": {
        "tr": "Toplam {total} dosyadan {success} tanesi dönüştürüldü.",
        "en": "{success} of {total} files converted.",
        "de": "{success} von {total} Dateien umgewandelt.",
        "es": "Se convirtieron {success} de {total} archivos.",
    },
    "unit.files": {"tr": "dosya", "en": "files", "de": "Dateien", "es": "archivos"},
    "unit.none": {"tr": "yok", "en": "none", "de": "keine", "es": "ninguno"},
    "unit.pages": {"tr": "sayfa", "en": "pages", "de": "Seiten", "es": "páginas"},
    # ── Önizleme & dosya seçimi ──
    "preview.select": {
        "tr": "Hangi dosyalar dönüştürülsün?",
        "en": "Which files should be converted?",
        "de": "Welche Dateien sollen umgewandelt werden?",
        "es": "¿Qué archivos quieres convertir?",
    },
    "preview.instruction": {
        "tr": "(boşlukla işaretle/kaldır, tümü seçili — Enter onayla)",
        "en": "(space to toggle, all selected — Enter to confirm)",
        "de": "(Leertaste zum Umschalten, alle ausgewählt — Enter bestätigt)",
        "es": "(espacio para marcar, todos seleccionados — Enter para confirmar)",
    },
    "preview.none": {
        "tr": "Hiç dosya seçilmedi, atlandı.",
        "en": "No files selected, skipped.",
        "de": "Keine Dateien ausgewählt, übersprungen.",
        "es": "No se seleccionó ningún archivo, omitido.",
    },
    # ── cli.py akış mesajları ──
    "cli.skipped": {"tr": "Atlandı.", "en": "Skipped.", "de": "Übersprungen.", "es": "Omitido."},
    "cli.cancelled": {
        "tr": "İşlem iptal edildi.",
        "en": "Cancelled.",
        "de": "Vorgang abgebrochen.",
        "es": "Operación cancelada.",
    },
    "cli.notfound_skipped": {
        "tr": "'{p}' bulunamadı, atlandı.",
        "en": "'{p}' not found, skipped.",
        "de": "'{p}' nicht gefunden, übersprungen.",
        "es": "'{p}' no encontrado, omitido.",
    },
    "cli.no_convertible": {
        "tr": "'{p}' içinde dönüştürülebilir dosya bulunamadı.",
        "en": "No convertible files found in '{p}'.",
        "de": "Keine umwandelbaren Dateien in '{p}' gefunden.",
        "es": "No se encontraron archivos convertibles en '{p}'.",
    },
    "cli.mixed": {
        "tr": "Klasörleri dosyalarla karışık seçmeyin; klasörü tek başına verin.",
        "en": "Don't mix folders with files; pass the folder on its own.",
        "de": "Ordner nicht mit Dateien mischen; den Ordner separat angeben.",
        "es": "No mezcles carpetas con archivos; indica la carpeta por separado.",
    },
    "cli.no_support": {
        "tr": "'{ext}' formatı için henüz destek yok. Desteklenen kaynak formatlar: {supported}",
        "en": "No support for '{ext}' yet. Supported source formats: {supported}",
        "de": "Für '{ext}' gibt es noch keine Unterstützung. Unterstützte Quellformate: {supported}",
        "es": "Aún no hay soporte para '{ext}'. Formatos de origen admitidos: {supported}",
    },
    "cli.no_support_skipped": {
        "tr": "'{ext}' formatı için destek yok, atlandı: {p}",
        "en": "No support for '{ext}', skipped: {p}",
        "de": "Keine Unterstützung für '{ext}', übersprungen: {p}",
        "es": "Sin soporte para '{ext}', omitido: {p}",
    },
    "cli.converting": {
        "tr": "Dönüştürülüyor: {name}...",
        "en": "Converting: {name}...",
        "de": "Wird umgewandelt: {name}...",
        "es": "Convirtiendo: {name}...",
    },
    "cli.tool_declined": {
        "tr": "{tool} kurulmadan bu dönüşüm yapılamaz. Manuel kurulum: {url}",
        "en": "This conversion requires {tool}. Manual install: {url}",
        "de": "Ohne {tool} ist diese Umwandlung nicht möglich. Manuelle Installation: {url}",
        "es": "Esta conversión requiere {tool}. Instalación manual: {url}",
    },
    "cli.tool_installing": {
        "tr": "{tool} kuruluyor ({installer})...",
        "en": "Installing {tool} ({installer})...",
        "de": "{tool} wird installiert ({installer})...",
        "es": "Instalando {tool} ({installer})...",
    },
    "cli.tool_manual_cmd": {
        "tr": "{tool} bu dönüşüm için gerekli. Şu komutla kurun: {cmd}  (ya da {url})",
        "en": "{tool} is required for this conversion. Install it with: {cmd}  (or {url})",
        "de": "{tool} wird für diese Umwandlung benötigt. Installieren mit: {cmd}  (oder {url})",
        "es": "{tool} es necesario para esta conversión. Instálalo con: {cmd}  (o {url})",
    },
    "cli.chained": {
        "tr": "Zincir: {chain}",
        "en": "Chained: {chain}",
        "de": "Kette: {chain}",
        "es": "Cadena: {chain}",
    },
    "cli.tool_failed": {
        "tr": "{tool} otomatik kurulamadı. Manuel kurulum: {url} (winget kurulumu tamamladıysa, "
              "programı yeniden başlatıp tekrar deneyin.)",
        "en": "Automatic install of {tool} failed. Manual install: {url} (if winget finished, "
              "restart the program and try again.)",
        "de": "{tool} konnte nicht automatisch installiert werden. Manuelle Installation: {url} "
              "(falls winget fertig ist, Programm neu starten und erneut versuchen.)",
        "es": "No se pudo instalar {tool} automáticamente. Instalación manual: {url} (si winget "
              "terminó, reinicia el programa e inténtalo de nuevo.)",
    },
    "cli.tool_installed": {
        "tr": "✓ {tool} kuruldu.",
        "en": "✓ {tool} installed.",
        "de": "✓ {tool} installiert.",
        "es": "✓ {tool} instalado.",
    },
    # ── Çakışma politikası / dry-run / undo / log ──
    "conflict.skipped": {
        "tr": "Hedef zaten var, atlandı.",
        "en": "Target exists, skipped.",
        "de": "Ziel existiert bereits, übersprungen.",
        "es": "El destino ya existe, omitido.",
    },
    "dryrun.skip": {
        "tr": "atlanır (hedef var)",
        "en": "would skip (target exists)",
        "de": "würde überspringen (Ziel existiert)",
        "es": "se omitiría (el destino existe)",
    },
    "dryrun.overwrite": {
        "tr": "üzerine yazılır",
        "en": "would overwrite",
        "de": "würde überschreiben",
        "es": "se sobrescribiría",
    },
    "dryrun.title": {
        "tr": "Deneme çalıştırması — hiçbir dosya yazılmadı.",
        "en": "Dry run — no files were written.",
        "de": "Probelauf — es wurden keine Dateien geschrieben.",
        "es": "Ejecución de prueba — no se escribió ningún archivo.",
    },
    "undo.none": {
        "tr": "Geri alınacak dönüşüm yok.",
        "en": "Nothing to undo.",
        "de": "Nichts rückgängig zu machen.",
        "es": "Nada que deshacer.",
    },
    "undo.about": {
        "tr": "Son dönüşümden {n} çıktı dosyası silinecek:",
        "en": "{n} output file(s) from the last conversion will be deleted:",
        "de": "{n} Ausgabedatei(en) der letzten Umwandlung werden gelöscht:",
        "es": "Se eliminarán {n} archivo(s) de salida de la última conversión:",
    },
    "undo.confirm": {
        "tr": "Silinsin mi? [E/h]",
        "en": "Delete them? [Y/n]",
        "de": "Löschen? [J/n]",
        "es": "¿Eliminar? [S/n]",
    },
    "undo.done": {
        "tr": "{n} dosya silindi.",
        "en": "{n} file(s) deleted.",
        "de": "{n} Datei(en) gelöscht.",
        "es": "{n} archivo(s) eliminado(s).",
    },
    "undo.missing": {
        "tr": "{n} dosya zaten yoktu.",
        "en": "{n} file(s) were already gone.",
        "de": "{n} Datei(en) waren bereits weg.",
        "es": "{n} archivo(s) ya no existían.",
    },
    "log.write_failed": {
        "tr": "Log yazılamadı ({path}): {err}",
        "en": "Could not write log ({path}): {err}",
        "de": "Log konnte nicht geschrieben werden ({path}): {err}",
        "es": "No se pudo escribir el registro ({path}): {err}",
    },
    "summary.failed": {
        "tr": "{n} dosya başarısız oldu.",
        "en": "{n} file(s) failed.",
        "de": "{n} Datei(en) fehlgeschlagen.",
        "es": "{n} archivo(s) fallaron.",
    },
    "summary.skipped": {
        "tr": "{n} dosya atlandı.",
        "en": "{n} file(s) skipped.",
        "de": "{n} Datei(en) übersprungen.",
        "es": "{n} archivo(s) omitidos.",
    },
    # ── Komut satırı (argparse) modu ──
    "cli.args.desc": {
        "tr": "Katana File Converter — komut satırı modu.",
        "en": "Katana File Converter — command line mode.",
        "de": "Katana File Converter — Kommandozeilenmodus.",
        "es": "Katana File Converter — modo de línea de comandos.",
    },
    "cli.args.input": {
        "tr": "Dönüştürülecek dosya veya klasör",
        "en": "File or folder to convert",
        "de": "Zu konvertierende Datei oder Ordner",
        "es": "Archivo o carpeta a convertir",
    },
    "cli.args.output": {
        "tr": "Çıktı dosyası/klasörü",
        "en": "Output file/folder",
        "de": "Ausgabedatei/-ordner",
        "es": "Archivo/carpeta de salida",
    },
    "cli.args.to": {
        "tr": "Hedef format (örn. png, ico)",
        "en": "Target format (e.g. png, ico)",
        "de": "Zielformat (z. B. png, ico)",
        "es": "Formato de destino (p. ej. png, ico)",
    },
    "cli.args.from": {
        "tr": "stdin'den okurken kaynak format (girdi '-' ise gerekir)",
        "en": "Source format when reading stdin (required if input is '-')",
        "de": "Quellformat beim Lesen von stdin (nötig, wenn Eingabe '-')",
        "es": "Formato de origen al leer stdin (necesario si la entrada es '-')",
    },
    "pipe.need_from": {
        "tr": "stdin'den okumak için --from KAYNAK gerekir (ör. --from md).",
        "en": "Reading from stdin requires --from SOURCE (e.g. --from md).",
        "de": "Lesen von stdin benötigt --from QUELLE (z. B. --from md).",
        "es": "Leer desde stdin requiere --from ORIGEN (p. ej. --from md).",
    },
    "pipe.done": {
        "tr": "✓ stdin ({src}) → {dst}",
        "en": "✓ stdin ({src}) → {dst}",
        "de": "✓ stdin ({src}) → {dst}",
        "es": "✓ stdin ({src}) → {dst}",
    },
    "cli.args.recursive": {
        "tr": "Klasörlerde alt klasörleri de tara",
        "en": "Also scan subfolders",
        "de": "Auch Unterordner durchsuchen",
        "es": "Analizar también las subcarpetas",
    },
    "cli.args.list": {
        "tr": "Desteklenen tüm dönüşümleri listele ve çık",
        "en": "List all supported conversions and exit",
        "de": "Alle unterstützten Umwandlungen auflisten und beenden",
        "es": "Listar todas las conversiones admitidas y salir",
    },
    "cli.args.format": {
        "tr": "Liste çıktı biçimi: table (varsayılan), json, md",
        "en": "List output format: table (default), json, md",
        "de": "Ausgabeformat der Liste: table (Standard), json, md",
        "es": "Formato de salida de la lista: table (predeterminado), json, md",
    },
    "cli.args.on_conflict": {
        "tr": "Hedef dosya varsa: overwrite, skip, rename (varsayılan: rename)",
        "en": "When target exists: overwrite, skip, rename (default: rename)",
        "de": "Wenn Ziel existiert: overwrite, skip, rename (Standard: rename)",
        "es": "Si el destino existe: overwrite, skip, rename (predeterminado: rename)",
    },
    "cli.args.name": {
        "tr": "Çıktı adı şablonu, ör. \"{stem}_web.{ext}\" (alanlar: stem, ext, parent, index, date)",
        "en": "Output name template, e.g. \"{stem}_web.{ext}\" (fields: stem, ext, parent, index, date)",
        "de": "Vorlage für Ausgabename, z. B. \"{stem}_web.{ext}\" (Felder: stem, ext, parent, index, date)",
        "es": "Plantilla de nombre de salida, p. ej. \"{stem}_web.{ext}\" (campos: stem, ext, parent, index, date)",
    },
    "cli.args.dry_run": {
        "tr": "Dönüştürmeden, yalnızca planlanan çıktıları göster",
        "en": "Show planned outputs without converting",
        "de": "Geplante Ausgaben anzeigen, ohne zu konvertieren",
        "es": "Mostrar las salidas previstas sin convertir",
    },
    "cli.args.log": {
        "tr": "Sonuçları JSONL log dosyasına ekle",
        "en": "Append results to a JSONL log file",
        "de": "Ergebnisse an eine JSONL-Logdatei anhängen",
        "es": "Añadir los resultados a un archivo de registro JSONL",
    },
    "cli.args.undo": {
        "tr": "Son dönüşümün çıktı dosyalarını sil ve çık",
        "en": "Delete the last conversion's output files and exit",
        "de": "Ausgabedateien der letzten Umwandlung löschen und beenden",
        "es": "Eliminar los archivos de salida de la última conversión y salir",
    },
    "cli.args.pick": {
        "tr": "Tek dosyayı etkileşimli format seçiciyle dönüştür",
        "en": "Convert a single file with the interactive format picker",
        "de": "Einzelne Datei mit interaktivem Formatwähler umwandeln",
        "es": "Convertir un solo archivo con el selector de formato interactivo",
    },
    "cli.args.install_menu": {
        "tr": "Windows sağ-tık menüsüne 'Katana ile dönüştür' ekle",
        "en": "Add 'Convert with Katana' to the Windows right-click menu",
        "de": "'Mit Katana umwandeln' zum Windows-Rechtsklickmenü hinzufügen",
        "es": "Añadir 'Convertir con Katana' al menú contextual de Windows",
    },
    "cli.args.uninstall_menu": {
        "tr": "Windows sağ-tık menüsü girdisini kaldır",
        "en": "Remove the Windows right-click menu entry",
        "de": "Windows-Rechtsklickmenü-Eintrag entfernen",
        "es": "Eliminar la entrada del menú contextual de Windows",
    },
    "cli.args.completion": {
        "tr": "Kabuk tamamlama script'ini yaz (bash/zsh/powershell)",
        "en": "Print a shell completion script (bash/zsh/powershell)",
        "de": "Shell-Vervollständigungsskript ausgeben (bash/zsh/powershell)",
        "es": "Imprimir un script de autocompletado de shell (bash/zsh/powershell)",
    },
    "menu.installed": {
        "tr": "✓ Sağ-tık menüsü eklendi. Bir dosyaya sağ tıklayıp 'Katana ile dönüştür' seçin.",
        "en": "✓ Right-click menu added. Right-click a file and choose 'Convert with Katana'.",
        "de": "✓ Rechtsklickmenü hinzugefügt. Datei rechtsklicken und 'Mit Katana umwandeln' wählen.",
        "es": "✓ Menú contextual añadido. Haz clic derecho en un archivo y elige 'Convertir con Katana'.",
    },
    "menu.uninstalled": {
        "tr": "✓ Sağ-tık menüsü girdisi kaldırıldı.",
        "en": "✓ Right-click menu entry removed.",
        "de": "✓ Rechtsklickmenü-Eintrag entfernt.",
        "es": "✓ Entrada del menú contextual eliminada.",
    },
    "menu.failed": {
        "tr": "Sağ-tık menüsü işlemi başarısız (yalnızca Windows'ta çalışır).",
        "en": "Right-click menu operation failed (Windows only).",
        "de": "Rechtsklickmenü-Vorgang fehlgeschlagen (nur Windows).",
        "es": "Falló la operación del menú contextual (solo Windows).",
    },
    "cli.args.jobs": {
        "tr": "Paralel dönüşüm sayısı (varsayılan: 1)",
        "en": "Number of parallel conversions (default: 1)",
        "de": "Anzahl paralleler Umwandlungen (Standard: 1)",
        "es": "Número de conversiones en paralelo (predeterminado: 1)",
    },
    "cli.args.watch": {
        "tr": "Klasörü izle: düşen/değişen dosyaları otomatik dönüştür (Ctrl-C ile çık)",
        "en": "Watch a folder: auto-convert files as they appear/change (Ctrl-C to stop)",
        "de": "Ordner überwachen: neue/geänderte Dateien automatisch umwandeln (Ctrl-C zum Beenden)",
        "es": "Vigilar una carpeta: convertir automáticamente los archivos nuevos/cambiados (Ctrl-C para salir)",
    },
    "cli.args.profile": {
        "tr": "Kayıtlı profili yükle (açık argümanlar profili ezer)",
        "en": "Load a saved profile (explicit args override it)",
        "de": "Gespeichertes Profil laden (explizite Argumente haben Vorrang)",
        "es": "Cargar un perfil guardado (los argumentos explícitos lo anulan)",
    },
    "cli.args.save_profile": {
        "tr": "Verilen argümanları bu isimle profil olarak kaydet ve çık",
        "en": "Save the given arguments as a profile with this name and exit",
        "de": "Die angegebenen Argumente als Profil unter diesem Namen speichern und beenden",
        "es": "Guardar los argumentos dados como un perfil con este nombre y salir",
    },
    "profile.saved": {
        "tr": "✓ '{name}' profili kaydedildi.",
        "en": "✓ Profile '{name}' saved.",
        "de": "✓ Profil '{name}' gespeichert.",
        "es": "✓ Perfil '{name}' guardado.",
    },
    "profile.notfound": {
        "tr": "'{name}' adlı profil bulunamadı. Mevcut: {available}",
        "en": "Profile '{name}' not found. Available: {available}",
        "de": "Profil '{name}' nicht gefunden. Verfügbar: {available}",
        "es": "Perfil '{name}' no encontrado. Disponibles: {available}",
    },
    "profile.loaded": {
        "tr": "Profil yüklendi: {name}",
        "en": "Profile loaded: {name}",
        "de": "Profil geladen: {name}",
        "es": "Perfil cargado: {name}",
    },
    "watch.start": {
        "tr": "👁  İzleniyor: {dir}  (hedef: {to}) — çıkmak için Ctrl-C",
        "en": "👁  Watching: {dir}  (target: {to}) — Ctrl-C to stop",
        "de": "👁  Überwacht: {dir}  (Ziel: {to}) — Ctrl-C zum Beenden",
        "es": "👁  Vigilando: {dir}  (destino: {to}) — Ctrl-C para salir",
    },
    "watch.need_to": {
        "tr": "İzleme modu --to hedef formatını gerektirir.",
        "en": "Watch mode requires a --to target format.",
        "de": "Der Überwachungsmodus benötigt ein --to Zielformat.",
        "es": "El modo de vigilancia requiere un formato de destino --to.",
    },
    "watch.not_dir": {
        "tr": "İzleme modu bir klasör yolu gerektirir: {p}",
        "en": "Watch mode requires a folder path: {p}",
        "de": "Der Überwachungsmodus benötigt einen Ordnerpfad: {p}",
        "es": "El modo de vigilancia requiere una ruta de carpeta: {p}",
    },
    "watch.converted": {
        "tr": "✓ {src} → {dst}",
        "en": "✓ {src} → {dst}",
        "de": "✓ {src} → {dst}",
        "es": "✓ {src} → {dst}",
    },
    "watch.failed": {
        "tr": "✗ {src}: {err}",
        "en": "✗ {src}: {err}",
        "de": "✗ {src}: {err}",
        "es": "✗ {src}: {err}",
    },
    "watch.stopped": {
        "tr": "İzleme durduruldu.",
        "en": "Watching stopped.",
        "de": "Überwachung beendet.",
        "es": "Vigilancia detenida.",
    },
    "watch.polling": {
        "tr": "(watchdog yok — 2 sn'lik tarama moduna geçildi)",
        "en": "(watchdog not installed — using 2s polling)",
        "de": "(watchdog nicht installiert — 2s-Abfragemodus)",
        "es": "(watchdog no instalado — usando sondeo de 2s)",
    },
    # ── Görsel/av ince ayar bayrakları ──
    "cli.args.quality": {
        "tr": "JPEG/WEBP kalitesi (1-100)",
        "en": "JPEG/WEBP quality (1-100)",
        "de": "JPEG/WEBP-Qualität (1-100)",
        "es": "Calidad JPEG/WEBP (1-100)",
    },
    "cli.args.resize": {
        "tr": "Görseli yeniden boyutlandır: 800x600, 800x, x600 ya da 50%",
        "en": "Resize image: 800x600, 800x, x600 or 50%",
        "de": "Bild skalieren: 800x600, 800x, x600 oder 50%",
        "es": "Redimensionar imagen: 800x600, 800x, x600 o 50%",
    },
    "cli.args.watermark": {
        "tr": "Görsele köşe filigran metni bas",
        "en": "Stamp a corner watermark text on the image",
        "de": "Wasserzeichen-Text in die Bildecke setzen",
        "es": "Estampar un texto de marca de agua en la esquina",
    },
    "cli.args.video_height": {
        "tr": "Video çıktı yüksekliği (px), en-boy oranı korunur",
        "en": "Video output height (px), aspect ratio kept",
        "de": "Videohöhe der Ausgabe (px), Seitenverhältnis bleibt",
        "es": "Altura de salida del vídeo (px), se mantiene la proporción",
    },
    "cli.args.audio_bitrate": {
        "tr": "Ses bit hızı, ör. 192k",
        "en": "Audio bitrate, e.g. 192k",
        "de": "Audio-Bitrate, z. B. 192k",
        "es": "Tasa de bits de audio, p. ej. 192k",
    },
    "cli.args.trim_start": {
        "tr": "Ses/video kırpma başlangıcı, ör. 00:00:05 veya 5",
        "en": "Audio/video trim start, e.g. 00:00:05 or 5",
        "de": "Audio-/Video-Startzeit, z. B. 00:00:05 oder 5",
        "es": "Inicio del recorte de audio/vídeo, p. ej. 00:00:05 o 5",
    },
    "cli.args.trim_end": {
        "tr": "Ses/video kırpma bitişi, ör. 00:00:20",
        "en": "Audio/video trim end, e.g. 00:00:20",
        "de": "Audio-/Video-Endzeit, z. B. 00:00:20",
        "es": "Fin del recorte de audio/vídeo, p. ej. 00:00:20",
    },
    # ── Arşiv & PDF araçları ──
    "cli.args.zip_output": {
        "tr": "Dönüşüm çıktılarını tek arşive topla (.zip/.tar.gz)",
        "en": "Bundle conversion outputs into one archive (.zip/.tar.gz)",
        "de": "Umwandlungsausgaben in ein Archiv packen (.zip/.tar.gz)",
        "es": "Agrupar las salidas de conversión en un archivo (.zip/.tar.gz)",
    },
    "cli.args.extract": {
        "tr": "Girdi bir arşivse (zip/tar) içeriğini çıkar",
        "en": "If input is an archive (zip/tar), extract its contents",
        "de": "Wenn die Eingabe ein Archiv (zip/tar) ist, den Inhalt entpacken",
        "es": "Si la entrada es un archivo (zip/tar), extraer su contenido",
    },
    "cli.args.merge": {
        "tr": "Klasördeki tüm PDF'leri tek dosyada birleştir (-o hedef)",
        "en": "Merge all PDFs in the folder into one file (-o target)",
        "de": "Alle PDFs im Ordner zu einer Datei zusammenführen (-o Ziel)",
        "es": "Combinar todos los PDF de la carpeta en un archivo (-o destino)",
    },
    "cli.args.pages": {
        "tr": "PDF'ten sayfa aralığı seç, ör. 1-3,5",
        "en": "Select a PDF page range, e.g. 1-3,5",
        "de": "PDF-Seitenbereich wählen, z. B. 1-3,5",
        "es": "Seleccionar un rango de páginas del PDF, p. ej. 1-3,5",
    },
    "cli.args.compress": {
        "tr": "PDF'i yeniden yazarak sıkıştır",
        "en": "Compress the PDF by rewriting it",
        "de": "PDF durch Neuschreiben komprimieren",
        "es": "Comprimir el PDF reescribiéndolo",
    },
    "cli.args.rotate": {
        "tr": "PDF sayfalarını döndür (90'ın katı derece)",
        "en": "Rotate PDF pages (degrees, multiple of 90)",
        "de": "PDF-Seiten drehen (Grad, Vielfaches von 90)",
        "es": "Rotar las páginas del PDF (grados, múltiplo de 90)",
    },
    "arch.bundled": {
        "tr": "✓ {n} dosya arşive eklendi → {dst}",
        "en": "✓ {n} file(s) bundled → {dst}",
        "de": "✓ {n} Datei(en) archiviert → {dst}",
        "es": "✓ {n} archivo(s) agrupados → {dst}",
    },
    "arch.extracted": {
        "tr": "✓ {n} dosya çıkarıldı → {dst}",
        "en": "✓ {n} file(s) extracted → {dst}",
        "de": "✓ {n} Datei(en) entpackt → {dst}",
        "es": "✓ {n} archivo(s) extraídos → {dst}",
    },
    "arch.not_archive": {
        "tr": "'{p}' bir arşiv değil (zip/tar/tar.gz beklenir).",
        "en": "'{p}' is not an archive (expected zip/tar/tar.gz).",
        "de": "'{p}' ist kein Archiv (zip/tar/tar.gz erwartet).",
        "es": "'{p}' no es un archivo (se esperaba zip/tar/tar.gz).",
    },
    "arch.need_output": {
        "tr": "Bu işlem -o ile bir çıktı yolu gerektirir.",
        "en": "This operation requires an -o output path.",
        "de": "Dieser Vorgang benötigt einen -o Ausgabepfad.",
        "es": "Esta operación requiere una ruta de salida -o.",
    },
    "pdf.merged": {
        "tr": "✓ {n} sayfa birleştirildi → {dst}",
        "en": "✓ {n} pages merged → {dst}",
        "de": "✓ {n} Seiten zusammengeführt → {dst}",
        "es": "✓ {n} páginas combinadas → {dst}",
    },
    "pdf.done": {
        "tr": "✓ {dst}",
        "en": "✓ {dst}",
        "de": "✓ {dst}",
        "es": "✓ {dst}",
    },
    "pdf.need_pdf": {
        "tr": "Bu işlem bir PDF girdisi gerektirir: {p}",
        "en": "This operation requires a PDF input: {p}",
        "de": "Dieser Vorgang benötigt eine PDF-Eingabe: {p}",
        "es": "Esta operación requiere una entrada PDF: {p}",
    },
    "pdf.no_pdfs": {
        "tr": "'{p}' içinde PDF bulunamadı.",
        "en": "No PDFs found in '{p}'.",
        "de": "Keine PDFs in '{p}' gefunden.",
        "es": "No se encontraron PDF en '{p}'.",
    },
    "cli.notfound": {
        "tr": "'{p}' bulunamadı.",
        "en": "'{p}' not found.",
        "de": "'{p}' nicht gefunden.",
        "es": "'{p}' no encontrado.",
    },
    "cli.target_unsupported": {
        "tr": "Hata: '{src}' -> '{dst}' desteklenmiyor. Olası hedefler: {options}",
        "en": "Error: '{src}' -> '{dst}' is not supported. Possible targets: {options}",
        "de": "Fehler: '{src}' -> '{dst}' wird nicht unterstützt. Mögliche Ziele: {options}",
        "es": "Error: '{src}' -> '{dst}' no es compatible. Destinos posibles: {options}",
    },
    "cli.multi_target": {
        "tr": "Hata: '{src}' için birden fazla hedef format var, --to ile belirtin: {options}",
        "en": "Error: '{src}' has multiple target formats, specify one with --to: {options}",
        "de": "Fehler: '{src}' hat mehrere Zielformate, mit --to angeben: {options}",
        "es": "Error: '{src}' tiene varios formatos de destino, indícalo con --to: {options}",
    },
}

# Dönüşüm etiketleri (route.label) Türkçe tanımlı; buradan diğer dillere çevrilir.
_LABELS: dict[str, dict[str, str]] = {
    "PNG görsel": {"en": "PNG image", "de": "PNG-Bild", "es": "Imagen PNG"},
    "JPEG görsel": {"en": "JPEG image", "de": "JPEG-Bild", "es": "Imagen JPEG"},
    "JPEG görsel (beyaz zemin)": {
        "en": "JPEG image (white background)",
        "de": "JPEG-Bild (weißer Hintergrund)",
        "es": "Imagen JPEG (fondo blanco)",
    },
    "PNG görsel (ilk kare)": {
        "en": "PNG image (first frame)",
        "de": "PNG-Bild (erstes Einzelbild)",
        "es": "Imagen PNG (primer fotograma)",
    },
    "PNG görsel (sayfa başına)": {
        "en": "PNG image (one per page)",
        "de": "PNG-Bild (pro Seite)",
        "es": "Imagen PNG (por página)",
    },
    "JPEG görsel (sayfa başına)": {
        "en": "JPEG image (one per page)",
        "de": "JPEG-Bild (pro Seite)",
        "es": "Imagen JPEG (por página)",
    },
    "PNG görsel (en yüksek çözünürlük)": {
        "en": "PNG image (highest resolution)",
        "de": "PNG-Bild (höchste Auflösung)",
        "es": "Imagen PNG (máxima resolución)",
    },
    "SVG konteyner (gömülü PNG)": {
        "en": "SVG container (embedded PNG)",
        "de": "SVG-Container (eingebettetes PNG)",
        "es": "Contenedor SVG (PNG incrustado)",
    },
    "PDF belge": {"en": "PDF document", "de": "PDF-Dokument", "es": "Documento PDF"},
    "WEBP görsel (web optimizasyonu)": {
        "en": "WEBP image (web-optimized)",
        "de": "WEBP-Bild (weboptimiert)",
        "es": "Imagen WEBP (optimizada para web)",
    },
    "Windows ICO ikonu": {"en": "Windows ICO icon", "de": "Windows-ICO-Symbol", "es": "Icono ICO de Windows"},
    "macOS ICNS ikonu": {"en": "macOS ICNS icon", "de": "macOS-ICNS-Symbol", "es": "Icono ICNS de macOS"},
    "MP3 ses (videodan ses ayıklama)": {
        "en": "MP3 audio (extracted from video)",
        "de": "MP3-Audio (aus Video extrahiert)",
        "es": "Audio MP3 (extraído del vídeo)",
    },
    "WAV ses (videodan ses ayıklama)": {
        "en": "WAV audio (extracted from video)",
        "de": "WAV-Audio (aus Video extrahiert)",
        "es": "Audio WAV (extraído del vídeo)",
    },
    "MP3 ses (sıkıştırılmış)": {
        "en": "MP3 audio (compressed)",
        "de": "MP3-Audio (komprimiert)",
        "es": "Audio MP3 (comprimido)",
    },
    "MP3 ses": {"en": "MP3 audio", "de": "MP3-Audio", "es": "Audio MP3"},
    "WAV ses (kayıpsız)": {
        "en": "WAV audio (lossless)",
        "de": "WAV-Audio (verlustfrei)",
        "es": "Audio WAV (sin pérdida)",
    },
    "MP4 video": {"en": "MP4 video", "de": "MP4-Video", "es": "Vídeo MP4"},
    "MP4 video (uyumlu format)": {
        "en": "MP4 video (compatible format)",
        "de": "MP4-Video (kompatibles Format)",
        "es": "Vídeo MP4 (formato compatible)",
    },
    "WEBM video (web optimizasyonu)": {
        "en": "WEBM video (web-optimized)",
        "de": "WEBM-Video (weboptimiert)",
        "es": "Vídeo WEBM (optimizado para web)",
    },
    "GIF animasyon": {"en": "GIF animation", "de": "GIF-Animation", "es": "Animación GIF"},
    "CSV tablo": {"en": "CSV table", "de": "CSV-Tabelle", "es": "Tabla CSV"},
    "CSV tablo (ilk sayfa)": {
        "en": "CSV table (first sheet)",
        "de": "CSV-Tabelle (erstes Blatt)",
        "es": "Tabla CSV (primera hoja)",
    },
    "JSON dizisi": {"en": "JSON array", "de": "JSON-Array", "es": "Matriz JSON"},
    "JSON": {"en": "JSON", "de": "JSON", "es": "JSON"},
    "YAML config": {"en": "YAML config", "de": "YAML-Konfiguration", "es": "Configuración YAML"},
    "TOML config": {"en": "TOML config", "de": "TOML-Konfiguration", "es": "Configuración TOML"},
    "HTML sayfa": {"en": "HTML page", "de": "HTML-Seite", "es": "Página HTML"},
    "PDF rapor": {"en": "PDF report", "de": "PDF-Bericht", "es": "Informe PDF"},
    "XML belge": {"en": "XML document", "de": "XML-Dokument", "es": "Documento XML"},
    "Markdown tablosu": {"en": "Markdown table", "de": "Markdown-Tabelle", "es": "Tabla Markdown"},
    "Markdown belge": {"en": "Markdown document", "de": "Markdown-Dokument", "es": "Documento Markdown"},
    "Düzenlenebilir Word belgesi": {
        "en": "Editable Word document",
        "de": "Bearbeitbares Word-Dokument",
        "es": "Documento Word editable",
    },
    "Word belgesi": {"en": "Word document", "de": "Word-Dokument", "es": "Documento Word"},
    "EPUB e-kitap": {
        "en": "EPUB e-book",
        "de": "EPUB-E-Book",
        "es": "Libro EPUB",
    },
    "Düz metin (metin çıkarma)": {
        "en": "Plain text (text extraction)",
        "de": "Reiner Text (Textextraktion)",
        "es": "Texto plano (extracción de texto)",
    },
    "Excel tablosu": {"en": "Excel spreadsheet", "de": "Excel-Tabelle", "es": "Hoja de cálculo Excel"},
}


def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_config(**updates) -> None:
    config = _load_config()
    config.update(updates)
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # config yazılamıyorsa dil yalnızca bu oturum için geçerli olur


def _detect_system_language() -> str:
    """Sistem dilini desteklenen dillerden birine eşler; eşleşme yoksa 'en'."""
    candidates: list[str] = []

    if sys.platform == "win32":
        try:
            import ctypes
            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            candidates.append({0x1F: "tr", 0x07: "de", 0x0A: "es", 0x09: "en"}.get(langid & 0xFF, ""))
        except Exception:
            pass

    for env_var in ("LC_ALL", "LANG"):
        value = os.environ.get(env_var) or ""
        candidates.append(value[:2].lower())

    try:
        loc = (locale.getlocale()[0] or "").lower()
        candidates.append(loc[:2])
        # Windows locale isimleri dil kodu yerine tam ad taşıyabilir.
        for name, code in (("turkish", "tr"), ("german", "de"), ("deutsch", "de"),
                           ("spanish", "es"), ("español", "es"), ("english", "en")):
            if loc.startswith(name):
                candidates.append(code)
    except Exception:
        pass

    for candidate in candidates:
        if candidate in LANGUAGES:
            return candidate
    return "en"


_lang: str = _load_config().get("language") or _detect_system_language()
if _lang not in LANGUAGES:
    _lang = "en"


def current_language() -> str:
    return _lang


def set_language(code: str) -> None:
    """Dili değiştirir ve seçimi config dosyasına kalıcı olarak yazar."""
    global _lang
    if code not in LANGUAGES:
        raise ValueError(f"Desteklenmeyen dil kodu: {code}")
    _lang = code
    _save_config(language=code)


def t(key: str, **fmt) -> str:
    """`key` için aktif dildeki metni döner; format alanları varsa doldurur."""
    entry = _STRINGS[key]
    text = entry.get(_lang) or entry["tr"]
    return text.format(**fmt) if fmt else text


def translate_label(label: str) -> str:
    """Dönüşüm etiketini (route.label, Türkçe) aktif dile çevirir."""
    if _lang == "tr":
        return label
    translations = _LABELS.get(label)
    if not translations:
        return label
    return translations.get(_lang) or translations.get("en") or label

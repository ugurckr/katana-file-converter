"""PDF araçları — birleştir, sayfa seç, sıkıştır, döndür (PyMuPDF ile)."""

from pathlib import Path

import fitz


def parse_pages(spec: str, page_count: int) -> list[int]:
    """'1-3,5' aralığını 0-tabanlı sayfa indekslerine çevirir, sınır dışını kırpar."""
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            try:
                start, end = int(a), int(b)
            except ValueError:
                continue
            for n in range(start, end + 1):
                if 1 <= n <= page_count:
                    pages.append(n - 1)
        else:
            try:
                n = int(part)
            except ValueError:
                continue
            if 1 <= n <= page_count:
                pages.append(n - 1)
    return pages


def merge(sources: list[Path], dst: Path) -> int:
    """PDF'leri sırayla birleştirir, toplam sayfa sayısını döner."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    out = fitz.open()
    try:
        for src in sources:
            with fitz.open(src) as doc:
                out.insert_pdf(doc)
        out.save(dst, garbage=4, deflate=True)
        return out.page_count
    finally:
        out.close()


def select_pages(src: Path, dst: Path, spec: str) -> int:
    """Verilen sayfa aralığından yeni bir PDF üretir, sayfa sayısını döner."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as doc:
        pages = parse_pages(spec, doc.page_count)
        if not pages:
            raise ValueError(f"Seçilen aralık boş ya da geçersiz: {spec}")
        out = fitz.open()
        try:
            for p in pages:
                out.insert_pdf(doc, from_page=p, to_page=p)
            out.save(dst, garbage=4, deflate=True)
            return out.page_count
        finally:
            out.close()


def compress(src: Path, dst: Path) -> None:
    """PDF'i yeniden yazarak boyutunu küçültür."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as doc:
        doc.save(dst, garbage=4, deflate=True, clean=True)


def rotate(src: Path, dst: Path, degrees: int) -> None:
    """Tüm sayfaları verilen açıyla döndürür."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(src) as doc:
        for page in doc:
            page.set_rotation((page.rotation + degrees) % 360)
        doc.save(dst, garbage=4, deflate=True)

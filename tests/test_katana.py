"""Katana çekirdek testleri: registry, adlandırma/çakışma, geçmiş, arşiv, PDF, görsel."""

import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from katana.core import naming  # noqa: E402
from katana.tools import archive, pdf_tools  # noqa: E402
from katana.converters import (  # noqa: E402
    all_source_extensions,
    conversion_matrix,
    find_chain,
    routes_for,
)


# ── Registry bütünlüğü ────────────────────────────────────────────────────────

def test_registry_has_routes():
    assert routes_for(".png"), "png için rota bekleniyor"
    assert len(all_source_extensions()) > 10


def test_matrix_routes_are_callable():
    for row in conversion_matrix():
        for route in routes_for(row["source"]):
            assert callable(route.convert)


def test_find_chain_or_direct():
    # png'nin en az bir doğrudan hedefi olmalı.
    assert routes_for(".png")
    # Zincir bulunursa ara adımlar multi_output olmamalı.
    chain = find_chain(".png", ".pdf")
    if chain:
        assert all(not r.multi_output for r in chain[:-1])


# ── Adlandırma şablonu ───────────────────────────────────────────────────────

def test_render_default_name(tmp_path):
    src = tmp_path / "photo.png"
    out = naming.render_output_name(src, ".jpg")
    assert out.name == "photo.jpg"
    assert out.parent == tmp_path


def test_render_template_fields(tmp_path):
    src = tmp_path / "photo.png"
    out = naming.render_output_name(src, "jpg", template="{stem}_web.{ext}", index=0)
    assert out.name == "photo_web.jpg"


def test_render_template_index(tmp_path):
    src = tmp_path / "a.png"
    out = naming.render_output_name(src, "jpg", template="img_{index}.{ext}", index=4)
    assert out.name == "img_5.jpg"  # index 1-tabanlı


def test_render_template_without_ext_gets_target(tmp_path):
    src = tmp_path / "a.png"
    out = naming.render_output_name(src, "jpg", template="{stem}_x")
    assert out.suffix == ".jpg"


# ── Çakışma politikası ───────────────────────────────────────────────────────

def test_conflict_overwrite(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_text("x")
    assert naming.resolve_conflict(p, "overwrite") == p


def test_conflict_skip(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_text("x")
    assert naming.resolve_conflict(p, "skip") is None
    assert naming.resolve_conflict(tmp_path / "new.jpg", "skip") == tmp_path / "new.jpg"


def test_conflict_rename(tmp_path):
    p = tmp_path / "a.jpg"
    p.write_text("x")
    (tmp_path / "a (1).jpg").write_text("y")
    result = naming.resolve_conflict(p, "rename")
    assert result.name == "a (2).jpg"


# ── Geçmiş / undo ────────────────────────────────────────────────────────────

def test_history_roundtrip(tmp_path, monkeypatch):
    from katana.core import history
    monkeypatch.setattr(history, "HISTORY_DIR", tmp_path / "hist")
    out = tmp_path / "out.jpg"
    out.write_text("data")
    history.start_batch()
    history.record(tmp_path / "in.png", out)
    manifest = history.commit_batch()
    assert manifest is not None
    deleted, missing = history.undo_last()
    assert out in deleted
    assert not out.exists()


# ── Arşiv ────────────────────────────────────────────────────────────────────

def test_archive_bundle_and_extract(tmp_path):
    a = tmp_path / "a.txt"; a.write_text("A")
    b = tmp_path / "b.txt"; b.write_text("B")
    zip_path = tmp_path / "bundle.zip"
    n = archive.bundle([a, b], zip_path)
    assert n == 2
    assert set(zipfile.ZipFile(zip_path).namelist()) == {"a.txt", "b.txt"}

    dest = tmp_path / "out"
    files = archive.extract(zip_path, dest)
    assert {f.name for f in files} == {"a.txt", "b.txt"}
    assert (dest / "a.txt").read_text() == "A"


def test_archive_is_archive():
    assert archive.is_archive(Path("x.zip"))
    assert archive.is_archive(Path("x.tar.gz"))
    assert not archive.is_archive(Path("x.png"))


# ── PDF araçları ─────────────────────────────────────────────────────────────

def _make_pdf(path: Path, pages: int):
    import fitz
    doc = fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"page {i + 1}")
    doc.save(path)
    doc.close()


def test_pdf_select_pages(tmp_path):
    src = tmp_path / "src.pdf"
    _make_pdf(src, 5)
    dst = tmp_path / "sub.pdf"
    n = pdf_tools.select_pages(src, dst, "1-3")
    assert n == 3


def test_pdf_merge(tmp_path):
    a = tmp_path / "a.pdf"; _make_pdf(a, 2)
    b = tmp_path / "b.pdf"; _make_pdf(b, 3)
    dst = tmp_path / "m.pdf"
    assert pdf_tools.merge([a, b], dst) == 5


def test_parse_pages():
    assert pdf_tools.parse_pages("1-3,5", 10) == [0, 1, 2, 4]
    assert pdf_tools.parse_pages("8-20", 10) == [7, 8, 9]  # kırpılır


# ── Görsel işlemleri ─────────────────────────────────────────────────────────

def test_image_resize_option(tmp_path):
    from PIL import Image
    from katana.converters import image_extra, options

    src = tmp_path / "big.png"
    Image.new("RGB", (400, 300), "navy").save(src)
    dst = tmp_path / "small.png"
    options.set_option("resize", "50%")
    try:
        image_extra.png_to_webp  # kayıtlı olduğundan emin
        image_extra._convert_via_pillow(src, dst, mode="RGB", fmt="PNG")
    finally:
        options.set_option("resize", None)
    assert Image.open(dst).size == (200, 150)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

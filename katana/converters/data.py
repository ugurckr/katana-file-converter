"""Veri & Kod dönüştürücüleri: json, csv, yaml, toml, xml, md, sql.

Saf Python + PyYAML, tomli-w, markdown-it-py, xhtml2pdf ile yapılır.
"""

import csv
import json
import sqlite3
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.dom import minidom

import tomli_w
import yaml
from markdown_it import MarkdownIt
from xhtml2pdf import pisa

from .base import register

_md = MarkdownIt("commonmark", {"html": True})


def _load_json_records(src: Path) -> list[dict]:
    data = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError("JSON, bir obje listesi (veya tek bir obje) olmalı.")
    return data


@register(".json", ".csv", "CSV tablo")
def json_to_csv(src: Path, dst: Path) -> None:
    records = _load_json_records(src)
    fieldnames = list(dict.fromkeys(key for row in records for key in row))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


@register(".csv", ".json", "JSON dizisi")
def csv_to_json(src: Path, dst: Path) -> None:
    with src.open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


@register(".json", ".yaml", "YAML config")
def json_to_yaml(src: Path, dst: Path) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


@register(".yaml", ".json", "JSON")
def yaml_to_json(src: Path, dst: Path) -> None:
    data = yaml.safe_load(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@register(".yml", ".json", "JSON")
def yml_to_json(src: Path, dst: Path) -> None:
    yaml_to_json(src, dst)


@register(".md", ".html", "HTML sayfa")
def md_to_html(src: Path, dst: Path) -> None:
    html_body = _md.render(src.read_text(encoding="utf-8"))
    html = f"<!doctype html>\n<meta charset=\"utf-8\">\n{html_body}\n"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(html, encoding="utf-8")


@register(".md", ".pdf", "PDF rapor")
def md_to_pdf(src: Path, dst: Path) -> None:
    html_body = _md.render(src.read_text(encoding="utf-8"))
    html = f"<!doctype html>\n<meta charset=\"utf-8\">\n{html_body}\n"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        result = pisa.CreatePDF(html, dest=f)
    if result.err:
        raise RuntimeError(f"'{src}' PDF'e dönüştürülürken {result.err} hata oluştu.")


@register(".csv", ".xml", "XML belge")
def csv_to_xml(src: Path, dst: Path) -> None:
    with src.open(newline="", encoding="utf-8") as f:
        records = list(csv.DictReader(f))

    root = ET.Element("records")
    for row in records:
        record_el = ET.SubElement(root, "record")
        for key, value in row.items():
            field_el = ET.SubElement(record_el, key)
            field_el.text = value

    rough = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(pretty, encoding="utf-8")


@register(".xml", ".csv", "CSV tablo")
def xml_to_csv(src: Path, dst: Path) -> None:
    root = ET.parse(src).getroot()
    records = [
        {field.tag: field.text or "" for field in record_el}
        for record_el in root
    ]
    fieldnames = list(dict.fromkeys(key for row in records for key in row))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


@register(".toml", ".json", "JSON")
def toml_to_json(src: Path, dst: Path) -> None:
    with src.open("rb") as f:
        data = tomllib.load(f)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@register(".json", ".toml", "TOML config")
def json_to_toml(src: Path, dst: Path) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("TOML kök seviyede bir tablo gerektirir; JSON bir obje olmalı.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("wb") as f:
        tomli_w.dump(data, f)


@register(".csv", ".md", "Markdown tablosu")
def csv_to_md(src: Path, dst: Path) -> None:
    with src.open(newline="", encoding="utf-8") as f:
        rows = [[cell.replace("|", "\\|") for cell in row] for row in csv.reader(f)]
    if not rows:
        raise ValueError(f"'{src}' boş, dönüştürülecek satır yok.")

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
        *("| " + " | ".join(row) + " |" for row in rows[1:]),
    ]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


@register(".sql", ".csv", "CSV tablo")
def sql_to_csv(src: Path, dst: Path) -> None:
    # .sql dosyasını bellek içi bir SQLite veritabanında çalıştırır, ardından
    # oluşan her tabloyu ayrı bir CSV olarak yazar (ilk/tek tablo dst'ye,
    # varsa diğerleri dst_stem__tablo.csv olarak).
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(src.read_text(encoding="utf-8"))
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        if not tables:
            raise ValueError(f"'{src}' içinde herhangi bir tablo bulunamadı.")

        dst.parent.mkdir(parents=True, exist_ok=True)
        for i, table in enumerate(tables):
            cursor = conn.execute(f'SELECT * FROM "{table}"')
            columns = [d[0] for d in cursor.description]
            out_path = dst if i == 0 else dst.with_name(f"{dst.stem}__{table}{dst.suffix}")
            with out_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(cursor.fetchall())
    finally:
        conn.close()
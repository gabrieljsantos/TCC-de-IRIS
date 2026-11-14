"""Add the pseudonyms from the three response exports to the general workbook.

Uses only the Python standard library so it can run without openpyxl. The source
workbook is left untouched; the result is written to a separate XLSX file.
"""

from __future__ import annotations

import html
import posixpath
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


BASE = Path(__file__).resolve().parent
GENERAL = BASE / "O Perigo de uma História Única_original(Responses) (1).xlsx"
OUTPUT = BASE / "O Perigo de uma História Única_com_pseudônimos.xlsx"
SOURCE_FILES = [
    ("O Perigo de uma História Única (Responses).xlsx", 7),
    (
        "Na sua perspectiva, que princípios são determinantes para uma educação inclusiva(Responses) .xlsx",
        8,
    ),
    (
        "Que relações você faria entre a conferência “O Perigo de uma História Única” de Chimamanda Ngozi Adichie e o tema inclusão(1).xlsx",
        9,
    ),
]
SOURCE_DIR = BASE / "o perigo com peseudononimo"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"m": MAIN_NS, "r": REL_NS, "p": PKG_REL_NS}
ET.register_namespace("", MAIN_NS)
ET.register_namespace("r", REL_NS)


def normalize(value: object) -> str:
    """Normalize whitespace and Unicode for response matching."""
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).casefold()


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group()
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number - 1


def get_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relmap = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
    first_sheet = workbook.find("m:sheets/m:sheet", NS)
    if first_sheet is None:
        raise ValueError("O arquivo não contém planilhas.")
    target = relmap[first_sheet.attrib[f"{{{REL_NS}}}id"]]
    return target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))


def read_sheet(archive: zipfile.ZipFile) -> tuple[str, list[tuple[int, dict[int, str]]]]:
    sheet_path = get_sheet_path(archive)
    shared_strings: list[str] = []
    if "xl/sharedStrings.xml" in archive.namelist():
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(node.text or "" for node in item.findall(".//m:t", NS))
            for item in shared_root.findall("m:si", NS)
        ]

    sheet_root = ET.fromstring(archive.read(sheet_path))
    rows: list[tuple[int, dict[int, str]]] = []
    for row in sheet_root.findall(".//m:sheetData/m:row", NS):
        values: dict[int, str] = {}
        for cell in row.findall("m:c", NS):
            kind = cell.attrib.get("t")
            if kind == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//m:t", NS))
            else:
                raw = cell.find("m:v", NS)
                value = raw.text if raw is not None and raw.text is not None else ""
                if kind == "s" and value:
                    value = shared_strings[int(value)]
                elif kind == "b":
                    value = "TRUE" if value == "1" else "FALSE"
            values[column_index(cell.attrib["r"])] = value
        rows.append((int(row.attrib["r"]), values))
    return sheet_path, rows


def find_column(header: dict[int, str], contains: str) -> int:
    needle = normalize(contains)
    for index, title in header.items():
        if needle in normalize(title):
            return index
    raise ValueError(f"Não encontrei uma coluna com o título {contains!r}.")


def load_rows(path: Path) -> tuple[str, list[tuple[int, dict[int, str]]]]:
    with zipfile.ZipFile(path) as archive:
        sheet_path, rows = read_sheet(archive)
    return sheet_path, rows


def set_inline_cell(row: ET.Element, reference: str, value: str) -> None:
    cell = next((c for c in row.findall("m:c", NS) if c.attrib.get("r") == reference), None)
    if cell is None:
        cell = ET.SubElement(row, f"{{{MAIN_NS}}}c", {"r": reference})
    cell.attrib["t"] = "inlineStr"
    for child in list(cell):
        cell.remove(child)
    inline = ET.SubElement(cell, f"{{{MAIN_NS}}}is")
    text = ET.SubElement(inline, f"{{{MAIN_NS}}}t")
    text.set(f"{{{XML_NS}}}space", "preserve")
    text.text = value


def main() -> None:
    if not GENERAL.exists():
        raise FileNotFoundError(GENERAL)

    main_sheet_path, main_rows = load_rows(GENERAL)
    if len(main_rows) < 2:
        raise ValueError("A planilha geral não tem respostas para atualizar.")

    main_header_row, main_header = main_rows[0]
    q_columns = {
        7: find_column(main_header, "7. Quais suas concepções/compreensões sobre inclusão?"),
        8: find_column(main_header, "8. Na sua perspectiva, que princípios são determinantes"),
        9: find_column(main_header, "9. Que relações você faria entre a conferência"),
    }
    pseudonym_column = find_column(main_header, "Pseudônimo")
    main_data = main_rows[1:]

    # Every copy must have exactly one row per general response, match that
    # question's answer in order, and agree on each pseudonym before any write.
    pseudonyms_by_source: list[list[str]] = []
    for filename, question_number in SOURCE_FILES:
        path = SOURCE_DIR / filename
        if not path.exists():
            raise FileNotFoundError(path)
        _, rows = load_rows(path)
        if not rows:
            raise ValueError(f"A cópia {filename!r} está vazia.")
        _, header = rows[0]
        source_pseudonym_col = find_column(header, "Pseudônimo")
        source_answer_col = find_column(header, f"{question_number}.")
        source_data = rows[1:]
        if len(source_data) != len(main_data):
            raise ValueError(
                f"Quantidade de respostas diferente em {filename!r}: "
                f"{len(source_data)} versus {len(main_data)}. Nenhum arquivo foi alterado."
            )
        source_names: list[str] = []
        for position, ((main_row_number, main_values), (source_row_number, source_values)) in enumerate(
            zip(main_data, source_data), start=1
        ):
            expected = normalize(main_values.get(q_columns[question_number], ""))
            actual = normalize(source_values.get(source_answer_col, ""))
            if expected != actual:
                raise ValueError(
                    f"A resposta {position} não corresponde entre a planilha geral "
                    f"e {filename!r} (linhas {main_row_number} e {source_row_number}). "
                    "Nenhum arquivo foi alterado."
                )
            name = str(source_values.get(source_pseudonym_col, "")).strip()
            if not name:
                raise ValueError(f"Pseudônimo vazio na linha {source_row_number} de {filename!r}.")
            source_names.append(name)
        pseudonyms_by_source.append(source_names)

    final_names: list[str] = []
    for position, names in enumerate(zip(*pseudonyms_by_source), start=1):
        normalized_names = {normalize(name) for name in names}
        if len(normalized_names) != 1:
            raise ValueError(
                f"Os três arquivos discordam sobre o pseudônimo da resposta {position}: "
                f"{names!r}. Nenhum arquivo foi alterado."
            )
        final_names.append(names[0])

    # Modify only the sheet XML in a copy of the original workbook.
    with zipfile.ZipFile(GENERAL) as source_zip:
        sheet_root = ET.fromstring(source_zip.read(main_sheet_path))
        xml_rows = {
            int(row.attrib["r"]): row
            for row in sheet_root.findall(".//m:sheetData/m:row", NS)
        }
        if main_header_row not in xml_rows:
            raise ValueError("Não encontrei o cabeçalho na planilha de saída.")

        # Normalize the dedicated column title and fill one pseudonym per row.
        set_inline_cell(xml_rows[main_header_row], f"{column_letters(pseudonym_column)}{main_header_row}", "Pseudônimo")
        for (row_number, _), pseudonym in zip(main_data, final_names):
            if row_number not in xml_rows:
                raise ValueError(f"Não encontrei a linha {row_number} na planilha de saída.")
            reference = f"{column_letters(pseudonym_column)}{row_number}"
            set_inline_cell(xml_rows[row_number], reference, pseudonym)

        updated_sheet = ET.tostring(sheet_root, encoding="utf-8", xml_declaration=True)
        with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as result_zip:
            for item in source_zip.infolist():
                payload = updated_sheet if item.filename == main_sheet_path else source_zip.read(item.filename)
                result_zip.writestr(item, payload)

    print(f"Arquivo criado: {OUTPUT}")
    print(f"Respostas vinculadas e pseudônimos conferidos nos três arquivos: {len(final_names)}")
    print("A planilha geral original foi preservada.")


def column_letters(index: int) -> str:
    number = index + 1
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


if __name__ == "__main__":
    main()

"""Create a comparison workbook grouped by pseudonym from the two surveys.

The XLSX reader and writer use Python's standard library. Repeated pseudonyms
are intentionally grouped; distinct answers are retained as separate lines in
the relevant cell. Email addresses, timestamps, and consent fields are omitted
from this analysis copy.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


BASE = Path(__file__).resolve().parent
PERIGO_FILE = BASE / "O Perigo de uma História Única_original(Responses) (1).xlsx"
WICKED_FILE = BASE / "Wicked_original (Responses).xlsx"
OUTPUT = BASE / "Unificacao_geral_por_pseudonimo.xlsx"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
NS = {"m": MAIN_NS, "r": REL_NS}


def normalize(value: object) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split()).casefold()


def read_workbook(path: Path) -> tuple[str, list[tuple[int, dict[int, str]]]]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relmap = {node.attrib["Id"]: node.attrib["Target"] for node in relationships}
        sheet = workbook.find("m:sheets/m:sheet", NS)
        if sheet is None:
            raise ValueError(f"Não encontrei uma planilha em {path.name}.")
        target = relmap[sheet.attrib[f"{{{REL_NS}}}id"]]
        sheet_path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))

        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(text.text or "" for text in item.findall(".//m:t", NS))
                for item in strings.findall("m:si", NS)
            ]

        root = ET.fromstring(archive.read(sheet_path))
        rows: list[tuple[int, dict[int, str]]] = []
        for row in root.findall(".//m:sheetData/m:row", NS):
            values: dict[int, str] = {}
            for cell in row.findall("m:c", NS):
                column = column_index(cell.attrib["r"])
                kind = cell.attrib.get("t")
                if kind == "inlineStr":
                    value = "".join(text.text or "" for text in cell.findall(".//m:t", NS))
                else:
                    raw = cell.find("m:v", NS)
                    value = raw.text if raw is not None and raw.text is not None else ""
                    if kind == "s" and value:
                        value = shared[int(value)]
                    elif kind == "b":
                        value = "TRUE" if value == "1" else "FALSE"
                values[column] = value
            rows.append((int(row.attrib["r"]), values))
        return sheet.attrib["name"], rows


def column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group()
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - ord("A") + 1
    return number - 1


def column_letters(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def header_columns(header: dict[int, str]) -> dict[int, str]:
    return {index: normalize(title) for index, title in header.items()}


def find_one(headers: dict[int, str], fragment: str) -> int:
    needle = normalize(fragment)
    matches = [index for index, title in headers.items() if needle in title]
    if len(matches) != 1:
        raise ValueError(f"Esperava uma coluna correspondente a {fragment!r}, encontrei {len(matches)}.")
    return matches[0]


def find_all_prefix(headers: dict[int, str], prefix: str) -> list[int]:
    needle = normalize(prefix)
    return [index for index, title in headers.items() if title.startswith(needle)]


def row_value(row: dict[int, str], column: int) -> str:
    return str(row.get(column, "") or "").strip()


def add_value(bucket: dict[str, list[str]], field: str, value: str) -> None:
    value = value.strip()
    if value and normalize(value) not in {normalize(item) for item in bucket[field]}:
        bucket[field].append(value)


def add_record(
    groups: dict[str, dict[str, object]],
    pseudonym: str,
    source: str,
    values: dict[str, str],
) -> None:
    key = normalize(pseudonym)
    if not key:
        raise ValueError("Há uma resposta sem pseudônimo; parei sem gerar a planilha.")
    if key not in groups:
        groups[key] = {
            "name": pseudonym.strip(),
            "perigo_count": 0,
            "wicked_count": 0,
            "values": {field: [] for field in OUTPUT_FIELDS},
        }
    group = groups[key]
    group[f"{source}_count"] = int(group[f"{source}_count"]) + 1
    target: dict[str, list[str]] = group["values"]  # type: ignore[assignment]
    for field, value in values.items():
        add_value(target, field, value)


PERIGO_FIELDS = [
    "Idade",
    "Sexo",
    "Curso",
    "Período letivo",
    "Outra graduação",
    "Atuação profissional",
    "Concepções sobre inclusão",
    "Princípios da educação inclusiva",
    "Relação entre a palestra e inclusão",
]
WICKED_FIELDS = [
    "Já respondeu ao formulário do Perigo?",
    "Idade",
    "Sexo",
    "Curso",
    "Período letivo",
    "Outra graduação",
    "Atuação profissional",
    "Concepções sobre inclusão",
    "Princípios da educação inclusiva",
    "Relação entre o filme e inclusão",
]
OUTPUT_FIELDS = [f"Perigo | {field}" for field in PERIGO_FIELDS] + [
    f"Wicked | {field}" for field in WICKED_FIELDS
]
OUTPUT_HEADERS = [
    "Pseudônimo",
    *OUTPUT_FIELDS,
    "Perigo | Nº de respostas reunidas",
    "Wicked | Nº de respostas reunidas",
]


def survey_column_maps() -> tuple[dict[str, int], dict[str, list[int]], dict[str, object]]:
    _, perigo_rows = read_workbook(PERIGO_FILE)
    _, wicked_rows = read_workbook(WICKED_FILE)
    if not perigo_rows or not wicked_rows:
        raise ValueError("Um dos arquivos está sem cabeçalho.")
    perigo_headers = header_columns(perigo_rows[0][1])
    wicked_headers = header_columns(wicked_rows[0][1])

    perigo_map = {
        "pseudonym": find_one(perigo_headers, "pseudônimo"),
        "Idade": find_one(perigo_headers, "1. idade"),
        "Sexo": find_one(perigo_headers, "2. sexo"),
        "Curso": find_one(perigo_headers, "3. curso"),
        "Período letivo": find_one(perigo_headers, "4. período letivo"),
        "Outra graduação": find_one(perigo_headers, "5. possui outra graduação"),
        "Atuação profissional": find_one(perigo_headers, "6. atua profissionalmente"),
        "Concepções sobre inclusão": find_one(perigo_headers, "7. quais suas concepções"),
        "Princípios da educação inclusiva": find_one(perigo_headers, "8. na sua perspectiva"),
        "Relação entre a palestra e inclusão": find_one(perigo_headers, "9. que relações você faria"),
    }
    wicked_map: dict[str, object] = {
        "pseudonyms": [index for index, title in wicked_headers.items() if "pseudônimo" in title],
        "Já respondeu ao formulário do Perigo?": find_one(wicked_headers, "você já respondeu ao formulário"),
        "Idade": find_all_prefix(wicked_headers, "1. idade"),
        "Sexo": find_all_prefix(wicked_headers, "2. sexo"),
        "Curso": find_all_prefix(wicked_headers, "3. curso"),
        "Período letivo": find_all_prefix(wicked_headers, "4. período letivo"),
        "Outra graduação": find_all_prefix(wicked_headers, "5. possui outra graduação"),
        "Atuação profissional": find_all_prefix(wicked_headers, "6. atua profissionalmente"),
        "Concepções sobre inclusão": find_all_prefix(wicked_headers, "7. quais suas concepções"),
        "Princípios da educação inclusiva": find_all_prefix(wicked_headers, "8. na sua perspectiva"),
        "Relação entre o filme e inclusão": [
            index
            for index, title in wicked_headers.items()
            if "relação" in title and "wicked" in title and "inclusão" in title
        ],
    }
    if len(wicked_map["pseudonyms"]) != 2:
        raise ValueError("Esperava encontrar as duas colunas de pseudônimo do arquivo Wicked.")
    return perigo_map, wicked_map, {"perigo_rows": perigo_rows, "wicked_rows": wicked_rows}


def merge_data() -> tuple[list[list[str]], dict[str, int]]:
    perigo_map, wicked_map, source_rows = survey_column_maps()
    perigo_rows = source_rows["perigo_rows"]
    wicked_rows = source_rows["wicked_rows"]
    groups: dict[str, dict[str, object]] = {}

    for _, row in perigo_rows[1:]:
        pseudonym = row_value(row, perigo_map["pseudonym"])
        values = {
            f"Perigo | {field}": row_value(row, column)
            for field, column in perigo_map.items()
            if field != "pseudonym"
        }
        add_record(groups, pseudonym, "perigo", values)

    pseudonym_columns: list[int] = wicked_map["pseudonyms"]  # type: ignore[assignment]
    for _, row in wicked_rows[1:]:
        names = [row_value(row, col) for col in pseudonym_columns]
        names = [name for name in names if name]
        normalized_names = {normalize(name) for name in names}
        if len(normalized_names) != 1:
            raise ValueError(f"Pseudônimo ausente ou divergente numa resposta Wicked: {names!r}")
        values: dict[str, str] = {}
        for field in WICKED_FIELDS:
            columns = wicked_map[field]
            columns = columns if isinstance(columns, list) else [columns]
            field_values = [row_value(row, int(col)) for col in columns]
            field_values = [value for value in field_values if value]
            values[f"Wicked | {field}"] = "\n\n---\n\n".join(field_values)
        add_record(groups, names[0], "wicked", values)

    ordered = sorted(groups.values(), key=lambda group: normalize(str(group["name"])))
    output = [OUTPUT_HEADERS]
    for group in ordered:
        values: dict[str, list[str]] = group["values"]  # type: ignore[assignment]
        row = [str(group["name"])]
        row.extend("\n\n---\n\n".join(values[field]) for field in OUTPUT_FIELDS)
        row.extend([str(group["perigo_count"]), str(group["wicked_count"])])
        output.append(row)
    counts = {
        "perigo_submissions": sum(int(group["perigo_count"]) for group in ordered),
        "wicked_submissions": sum(int(group["wicked_count"]) for group in ordered),
        "unique_pseudonyms": len(ordered),
        "shared_pseudonyms": sum(
            int(group["perigo_count"]) > 0 and int(group["wicked_count"]) > 0
            for group in ordered
        ),
        "repeated_groups": sum(
            int(group["perigo_count"]) > 1 or int(group["wicked_count"]) > 1
            for group in ordered
        ),
    }
    return output, counts


def xml_text(value: object) -> str:
    from xml.sax.saxutils import escape

    return escape(str(value), {"\"": "&quot;"})


def make_styles() -> bytes:
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{MAIN_NS}">
 <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>
 <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFDCE6F1"/><bgColor indexed="64"/></patternFill></fill></fills>
 <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"><color rgb="FFD9E1EA"/></left><right style="thin"><color rgb="FFD9E1EA"/></right><top style="thin"><color rgb="FFD9E1EA"/></top><bottom style="thin"><color rgb="FFD9E1EA"/></bottom><diagonal/></border></borders>
 <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
 <cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs>
 <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''
    return xml.encode("utf-8")


def write_xlsx(rows: list[list[str]], path: Path) -> None:
    last_col = column_letters(len(OUTPUT_HEADERS) - 1)
    last_row = len(rows)
    sheet_parts = [
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">',
        f'<dimension ref="A1:{last_col}{last_row}"/>',
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/><selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView></sheetViews>',
        '<sheetFormatPr defaultRowHeight="30"/>',
        '<cols>',
    ]
    for col, header in enumerate(OUTPUT_HEADERS, start=1):
        width = 44 if any(word in header for word in ("Concepções", "Princípios", "Relação")) else 24
        if header == "Pseudônimo":
            width = 26
        sheet_parts.append(f'<col min="{col}" max="{col}" width="{width}" customWidth="1"/>')
    sheet_parts.append("</cols><sheetData>")
    for row_num, values in enumerate(rows, start=1):
        sheet_parts.append(f'<row r="{row_num}" customHeight="1" ht="{36 if row_num == 1 else 42}">')
        for col_num, value in enumerate(values, start=1):
            ref = f"{column_letters(col_num - 1)}{row_num}"
            style = 2 if row_num == 1 else 1
            text = xml_text(value)
            sheet_parts.append(
                f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'
            )
        sheet_parts.append("</row>")
    sheet_parts.append(f'</sheetData><autoFilter ref="A1:{last_col}{last_row}"/><pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/></worksheet>')
    worksheet_xml = "".join(sheet_parts).encode("utf-8")
    content_types = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>'''.encode("utf-8")
    root_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'''
    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}"><sheets><sheet name="Unificação por pseudônimo" sheetId="1" r:id="rId1"/></sheets></workbook>'''.encode("utf-8")
    workbook_rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{PKG_REL_NS}"><Relationship Id="rId1" Type="{REL_NS}/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="{REL_NS}/styles" Target="styles.xml"/></Relationships>'''.encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", make_styles())
        archive.writestr("xl/worksheets/sheet1.xml", worksheet_xml)


def main() -> None:
    for path in (PERIGO_FILE, WICKED_FILE):
        if not path.exists():
            raise FileNotFoundError(path)
    rows, counts = merge_data()
    write_xlsx(rows, OUTPUT)
    with zipfile.ZipFile(OUTPUT) as archive:
        if archive.testzip() is not None:
            raise ValueError("O arquivo XLSX gerado falhou na validação do pacote.")
        ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))
        ET.fromstring(archive.read("xl/styles.xml"))
    print(f"Arquivo criado: {OUTPUT}")
    print(f"Linhas agrupadas por pseudônimo: {counts['unique_pseudonyms']}")
    print(f"Pseudônimos presentes nos dois estudos: {counts['shared_pseudonyms']}")
    print(f"Pseudônimos com respostas repetidas agrupadas: {counts['repeated_groups']}")
    print(f"Respostas reunidas: Perigo {counts['perigo_submissions']}; Wicked {counts['wicked_submissions']}.")


if __name__ == "__main__":
    main()

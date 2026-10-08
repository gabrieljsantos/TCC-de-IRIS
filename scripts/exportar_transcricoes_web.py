#!/usr/bin/env python3
"""Exporta apenas os campos necessários pelas páginas web de transcrição."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dashboard" / "transcricoes" / "dados"


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def export_segments(source_path: Path, destination: Path, position_audio: bool = False) -> int:
    source = read_json(source_path)
    segments = []
    for row in source.get("falas", []):
        segment = {
            "id": row.get("id") or row.get("id_origem"),
            "bloco": row.get("bloco"),
            "inicio_ms": row.get("inicio_ms"),
            "fim_ms": row.get("fim_ms"),
            "inicio_hms": row.get("inicio_hms"),
            "fim_hms": row.get("fim_hms"),
            "texto": row.get("texto", ""),
            "participante_id": row.get("participante_id") or row.get("participante_indice") or "P00",
            "identificacao_confianca_percentual": row.get("identificacao_confianca_percentual", 0),
        }
        if position_audio:
            for key in ("posicao_1_inicio_ms", "posicao_1_fim_ms", "posicao_2_inicio_ms", "posicao_2_fim_ms"):
                segment[key] = row.get(key)
        segments.append(segment)
    write_json(destination, {"falas": segments})
    return len(segments)


def export_index(source_path: Path, destination: Path) -> None:
    source = read_json(source_path)
    people = source.get("participantes", [])
    write_json(destination, {"participantes": [
        {"id": person.get("id", "P00"), "nome": person.get("nome", "Pessoa não identificada")}
        for person in people
    ]})


def export_legacy_resources() -> None:
    source = (ROOT / "dashboard" / "data.js").read_text(encoding="utf-8")
    prefix = "window.DASHBOARD_DATA = "
    if not source.startswith(prefix):
        raise ValueError("dashboard/data.js não está no formato esperado")
    data = json.loads(source[len(prefix):].strip().removesuffix(";"))
    participant_by_id = {
        person["id"]: {
            "evento": person.get("evento", ""),
            "curso": person.get("curso", ""),
            "periodo": person.get("periodo"),
        }
        for person in data.get("registros", [])
    }
    event_counts: dict[str, int] = {}
    for person in data.get("registros", []):
        event = person.get("evento", "")
        event_counts[event] = event_counts.get(event, 0) + 1
    export = {
        "transcricao": data.get("transcricao", []),
        "respostas": data.get("respostas", []),
        "palavras": data.get("palavras", []),
        "temas": data.get("temas", []),
        "participantes": participant_by_id,
        "contagem_participantes_evento": event_counts,
    }
    write_json(ROOT / "dashboard" / "recursos" / "dados.json", export)


def main() -> None:
    material = ROOT / "material"
    posicoes = material / "transcricao_evento_posicoes"
    reflexao = material / "transcricao_reflexao"
    counts = [
        export_segments(posicoes / "transcricao_por_id.json", OUTPUT / "perigo-historia-unica.json", position_audio=True),
        export_segments(reflexao / "transcricao_com_participantes.json", OUTPUT / "reflexao-wicked.json"),
    ]
    export_index(posicoes / "indice_participantes.json", OUTPUT / "indice-perigo-historia-unica.json")
    export_index(reflexao / "indice_participantes.json", OUTPUT / "indice-reflexao-wicked.json")
    export_legacy_resources()
    print(f"Exportadas {counts[0]} falas de Posições e {counts[1]} falas de Reflexão para {OUTPUT}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Prepara os arquivos de transcrição e áudio para o grupo Falas de ACESSO."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "material" / "transcricao_acesso"
DATA = ROOT / "dashboard" / "transcricoes" / "dados"
MEDIA = ROOT / "dashboard" / "media" / "falas-acesso"

AUDIO_GROUPS = [
    {
        "key": "acesso-alana",
        "slug": "AC01",
        "label": "Alana, Giselle e Lesley",
        "transcript": "Alana.txt",
        "audio": "Alana, Giselle e Lesley.m4a",
        "output_audio": "acesso-01-alana-giselle-lesley.m4a",
    },
    {
        "key": "acesso-dayane",
        "slug": "AC02",
        "label": "Dayane, Juliano, Lara e Laura",
        "transcript": "Dayane.txt",
        "audio": "Dayane, Juliano, Lara e Laura.m4a",
        "output_audio": "acesso-02-dayane-juliano-lara-laura.m4a",
    },
    {
        "key": "acesso-joao-vitor",
        "slug": "AC03",
        "label": "João Victor, Luís Antônio, Mathias, Sergio e Ysadora",
        "transcript": "João Vitor.txt",
        "audio": "João Victor, Luís Antônio, Mathias, Sergio e Ysadora.m4a",
        "output_audio": "acesso-03-joao-victor-luis-antonio-mathias-sergio-ysadora.m4a",
    },
    {
        "key": "acesso-felipe-gabriel-jeanderson",
        "slug": "AC04",
        "label": "Felipe, Gabriel e Jeanderson",
        "transcript": "Felipe, Gabriel e Jeanderson.txt",
        "audio": "Felipe, Gabriel e Jeanderson.m4a",
        "output_audio": "acesso-04-felipe-gabriel-jeanderson.m4a",
    },
]

BLOCK_RE = re.compile(
    r"^Participante\s+(?P<speaker>\d+)\s+\((?P<time>\d{2}:\d{2})\)\s*\n"
    r"(?P<text>.*?)(?=^Participante\s+\d+\s+\(\d{2}:\d{2}\)|\Z)",
    re.MULTILINE | re.DOTALL,
)


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def timestamp_ms(value: str) -> int:
    minutes, seconds = (int(part) for part in value.split(":"))
    return (minutes * 60 + seconds) * 1000


def duration_ms(path: Path) -> int:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return round(float(result.stdout.strip()) * 1000)


def parse_blocks(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = []
    for match in BLOCK_RE.finditer(text):
        spoken_text = " ".join(match.group("text").split())
        if not spoken_text:
            continue
        blocks.append({
            "speaker_number": int(match.group("speaker")),
            "start_ms": timestamp_ms(match.group("time")),
            "text": spoken_text,
        })
    if not blocks:
        raise ValueError(f"Nenhum bloco com marcador Participante (MM:SS) encontrado em {path}")
    return blocks


def main() -> None:
    MEDIA.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)
    segments = []
    participants: dict[str, dict[str, str]] = {}
    for group in AUDIO_GROUPS:
        source_audio = SOURCE / group["audio"]
        output_audio = MEDIA / group["output_audio"]
        shutil.copy2(source_audio, output_audio)
        length = duration_ms(source_audio)
        blocks = parse_blocks(SOURCE / group["transcript"])
        if any(right["start_ms"] < left["start_ms"] for left, right in zip(blocks, blocks[1:])):
            raise ValueError(f"Os marcadores de tempo não estão em ordem em {group['transcript']}")
        for index, block in enumerate(blocks):
            pid = f"{group['slug']}-P{block['speaker_number']:02d}"
            participant_name = (
                "Gisele" if group["slug"] == "AC01" and block["speaker_number"] == 1
                else "Gabriel" if group["slug"] == "AC04" and block["speaker_number"] == 1
                else f"Participante {block['speaker_number']}"
            )
            participants[pid] = {"id": pid, "nome": participant_name}
            next_start = blocks[index + 1]["start_ms"] if index + 1 < len(blocks) else length
            end_ms = next_start if next_start > block["start_ms"] else min(length, block["start_ms"] + 1500)
            end_ms = min(length, max(block["start_ms"] + 1, end_ms))
            segments.append({
                "id": f"{group['slug'].lower()}-{index + 1:04d}",
                "audio_id": group["key"],
                "inicio_ms": block["start_ms"],
                "fim_ms": end_ms,
                "texto": block["text"],
                "participante_id": pid,
            })

    transcript = {"falas": segments}
    index = {
        "participantes": list(participants.values()),
        "audios": [{"id": group["key"], "nome": group["label"]} for group in AUDIO_GROUPS],
    }
    write_json(DATA / "falas-acesso.json", transcript)
    write_json(DATA / "indice-falas-acesso.json", index)
    bundle = {"page": "acesso", "transcript": transcript, "index": index}
    encoded = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    encoded = encoded.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (DATA / "dados-acesso.js").write_text(f"window.CINEPET_TRANSCRIPTION_DATA = {encoded};\n", encoding="utf-8")
    print(f"Preparados {len(segments)} blocos de fala em {len(AUDIO_GROUPS)} áudios.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Transcreve o áudio Reflexão em blocos sobrepostos e tempos absolutos.

As margens dão contexto ao ASR. Um segmento só pertence ao bloco cujo núcleo
contém o seu ponto médio, impedindo duplicatas sem perder falas nos cortes.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from faster_whisper import WhisperModel


RAIZ = Path(__file__).resolve().parent
AUDIO = RAIZ / "Reflexão_ Will, Rita, Iris e Lene.m4a"
SAIDA = RAIZ / "transcricao_reflexao"
PREFIXO_ID = "reflexao"


@dataclass
class Bloco:
    indice: int
    nucleo_inicio: float
    nucleo_fim: float
    janela_inicio: float
    janela_fim: float
    arquivo: str


def duracao(caminho: Path) -> float:
    valor = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(caminho)],
        text=True,
    )
    return float(valor.strip())


def hms(segundos: float) -> str:
    total_ms = max(0, round(segundos * 1000))
    horas, resto = divmod(total_ms, 3_600_000)
    minutos, resto = divmod(resto, 60_000)
    seg, ms = divmod(resto, 1000)
    return f"{horas:02d}:{minutos:02d}:{seg:02d}.{ms:03d}"


def criar_blocos(tamanho: float, nucleo: float, margem: float) -> list[Bloco]:
    pasta = SAIDA / "blocos_contexto"
    pasta.mkdir(parents=True, exist_ok=True)
    blocos: list[Bloco] = []
    indice = 0
    inicio = 0.0
    while inicio < tamanho:
        fim = min(inicio + nucleo, tamanho)
        janela_inicio = max(0.0, inicio - margem)
        janela_fim = min(tamanho, fim + margem)
        arquivo = pasta / f"bloco_{indice:03d}.wav"
        blocos.append(Bloco(indice, inicio, fim, janela_inicio, janela_fim,
                            str(arquivo)))
        inicio = fim
        indice += 1
    return blocos


def extrair(bloco: Bloco) -> None:
    destino = Path(bloco.arquivo)
    if destino.exists():
        return
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", str(bloco.janela_inicio), "-i", str(AUDIO),
         "-t", str(bloco.janela_fim - bloco.janela_inicio),
         "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destino)],
        check=True,
    )


def transcrever(modelo: WhisperModel, bloco: Bloco, forcar: bool) -> Path:
    pasta = SAIDA / "bruto"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"bloco_{bloco.indice:03d}.json"
    if destino.exists() and not forcar:
        return destino
    segmentos, info = modelo.transcribe(
        bloco.arquivo,
        language="pt",
        beam_size=5,
        vad_filter=False,
        word_timestamps=True,
        condition_on_previous_text=False,
    )
    itens = []
    for numero, segmento in enumerate(segmentos):
        inicio = bloco.janela_inicio + segmento.start
        fim = bloco.janela_inicio + segmento.end
        meio = (inicio + fim) / 2
        # O núcleo é fechado à direita apenas no último bloco.
        pertence = bloco.nucleo_inicio <= meio < bloco.nucleo_fim
        if bloco.nucleo_fim >= duracao(AUDIO) - 0.01:
            pertence = bloco.nucleo_inicio <= meio <= bloco.nucleo_fim + 0.01
        itens.append({
            "id_local": numero,
            "texto": segmento.text.strip(),
            "inicio": round(inicio, 3),
            "fim": round(fim, 3),
            "inicio_ms": round(inicio * 1000),
            "fim_ms": round(fim * 1000),
            "inicio_hms": hms(inicio),
            "fim_hms": hms(fim),
            "pertence_ao_nucleo": bool(pertence),
            "palavras": [
                {
                    "texto": palavra.word,
                    "inicio_ms": round((bloco.janela_inicio + palavra.start) * 1000),
                    "fim_ms": round((bloco.janela_inicio + palavra.end) * 1000),
                    "probabilidade": round(palavra.probability, 4),
                }
                for palavra in (segmento.words or [])
                if palavra.start is not None and palavra.end is not None
            ],
        })
    payload = {"bloco": asdict(bloco), "idioma": info.language,
               "probabilidade_idioma": info.language_probability,
               "segmentos": itens}
    destino.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    return destino


def consolidar(blocos: list[Bloco]) -> None:
    falas = []
    for bloco in blocos:
        origem = SAIDA / "bruto" / f"bloco_{bloco.indice:03d}.json"
        if not origem.exists():
            continue
        dados = json.loads(origem.read_text(encoding="utf-8"))
        for item in dados["segmentos"]:
            if not item.pop("pertence_ao_nucleo") or not item["texto"]:
                continue
            # Revisão manual: o mesmo enunciado foi duplicado em dois
            # segmentos contíguos no bloco 008. Mantém uma ocorrência e
            # estende o intervalo para cobrir a fala inteira.
            if (item["inicio_ms"] == 2_406_560
                    and item["texto"].strip() == "Entre 10, 15 pessoas."):
                anterior = next((fala for fala in reversed(falas)
                                 if fala["fim_ms"] == 2_406_520
                                 and fala["texto"].strip() == "Entre 10, 15 pessoas."), None)
                if anterior:
                    anterior["fim"] = item["fim"]
                    anterior["fim_ms"] = item["fim_ms"]
                    anterior["fim_hms"] = item["fim_hms"]
                continue
            item["bloco"] = bloco.indice
            item["id"] = f"{PREFIXO_ID}-{len(falas) + 1:05d}"
            item["participante"] = None
            falas.append(item)
    pacote = {
        "audio": AUDIO.name,
        "duracao": duracao(AUDIO),
        "bloco_nucleo_segundos": 300,
        "sobreposicao_contexto_segundos": 15,
        "falas": falas,
    }
    (SAIDA / "transcricao_indexada.json").write_text(
        json.dumps(pacote, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    texto = []
    for fala in falas:
        texto.append(f"[{fala['inicio_hms']} --> {fala['fim_hms']}] {fala['texto']}")
    (SAIDA / "transcricao_indexada.txt").write_text(
        "\n\n".join(texto) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--modelo", default="deepdml/faster-whisper-large-v3-turbo-ct2")
    parser.add_argument("--bloco", type=int, action="append",
                        help="processa apenas este índice; pode ser repetido")
    parser.add_argument("--forcar", action="store_true")
    args = parser.parse_args()
    if not AUDIO.exists():
        raise FileNotFoundError(AUDIO)
    SAIDA.mkdir(parents=True, exist_ok=True)
    blocos = criar_blocos(duracao(AUDIO), 300.0, 15.0)
    selecionados = [b for b in blocos if args.bloco is None or b.indice in args.bloco]
    for bloco in selecionados:
        extrair(bloco)
    modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8",
                          cpu_threads=8, num_workers=1)
    for bloco in selecionados:
        print(f"Transcrevendo bloco {bloco.indice:03d}...", flush=True)
        destino = transcrever(modelo, bloco, args.forcar)
        print(f"Salvo: {destino}", flush=True)
    consolidar(blocos)
    print(f"Consolidado: {SAIDA / 'transcricao_indexada.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

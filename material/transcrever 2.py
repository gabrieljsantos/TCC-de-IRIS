"""Transcrição local com GPU, timestamps e separação de participantes.

Instalação sugerida (Python 3.11):
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128
    pip install whisperx

Para diarização, configure HF_TOKEN com um token do Hugging Face que tenha
acesso aos modelos pyannote/speaker-diarization e pyannote/segmentation.
"""
from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path

import torch
import whisperx


RAIZ = Path(__file__).resolve().parent
AUDIOS = [RAIZ / "posição 1.m4a", RAIZ / "posição 2.m4a"]


def hms(valor: float) -> str:
    total = max(0, int(round(valor)))
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def limpar_gpu() -> None:
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def agrupar_falas(segmentos: list[dict]) -> list[dict]:
    """Agrupa segmentos consecutivos da mesma pessoa sem perder timestamps."""
    falas: list[dict] = []
    for segmento in segmentos:
        texto = str(segmento.get("text", "")).strip()
        if not texto:
            continue
        participante = segmento.get("speaker") or "SPEAKER_DESCONHECIDO"
        inicio = float(segmento.get("start", 0))
        fim = float(segmento.get("end", inicio))
        if (falas and falas[-1]["speaker"] == participante
                and inicio - falas[-1]["end"] <= 1.2):
            falas[-1]["end"] = fim
            falas[-1]["text"] += " " + texto
        else:
            falas.append({"speaker": participante, "start": inicio,
                          "end": fim, "text": texto})
    return falas


def normalizar_participantes(falas: list[dict]) -> list[dict]:
    mapa: dict[str, str] = {}
    for fala in falas:
        rotulo = fala["speaker"]
        if rotulo not in mapa:
            mapa[rotulo] = f"Participante {len(mapa) + 1}"
        fala["speaker"] = mapa[rotulo]
    return falas


def salvar(audio: Path, falas: list[dict]) -> Path:
    destino = audio.with_name(audio.stem + " - transcrição local GPU.txt")
    linhas = [
        "TRANSCRIÇÃO DO EVENTO",
        f"Áudio de referência: {audio.name}",
        "Formato de tempo: HH:MM:SS",
        "Idioma: Português do Brasil",
        "",
    ]
    for fala in falas:
        linhas.extend([
            f"{fala['speaker']} ({hms(fala['start'])} - {hms(fala['end'])})",
            fala["text"],
            "",
        ])
    destino.write_text("\n".join(linhas).strip() + "\n", encoding="utf-8")
    return destino


def processar(audio_path: Path, modelo, diarizador, device: str,
              batch_size: int) -> Path:
    print(f"\nCarregando: {audio_path.name}")
    audio = whisperx.load_audio(str(audio_path))

    print("  1/3 Transcrevendo na GPU...")
    bruto = modelo.transcribe(audio, batch_size=batch_size, language="pt")

    print("  2/3 Refinando os tempos por palavra...")
    alinhador, metadados = whisperx.load_align_model(
        language_code=bruto["language"], device=device
    )
    alinhado = whisperx.align(
        bruto["segments"], alinhador, metadados, audio, device,
        return_char_alignments=False,
    )
    del alinhador
    limpar_gpu()

    print("  3/3 Identificando os participantes...")
    diarizacao = diarizador(audio)
    resultado = whisperx.assign_word_speakers(diarizacao, alinhado)
    falas = normalizar_participantes(agrupar_falas(resultado["segments"]))
    destino = salvar(audio_path, falas)

    del audio, bruto, alinhado, diarizacao, resultado
    limpar_gpu()
    print(f"  Salvo: {destino.name}")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transcreve os dois áudios localmente usando GPU e diarização."
    )
    parser.add_argument("--modelo", default="large-v3",
                        help="Modelo Whisper (padrão: large-v3).")
    parser.add_argument("--batch-size", type=int, default=4,
                        help="Lote da GPU; use 2 se faltar VRAM (padrão: 4).")
    parser.add_argument("--cpu-threads", type=int, default=os.cpu_count() or 8,
                        help="Threads de CPU para decodificação.")
    parser.add_argument("--min-speakers", type=int)
    parser.add_argument("--max-speakers", type=int, default=8)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA não está disponível no PyTorch instalado.")
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if not token:
        raise RuntimeError(
            "Configure HF_TOKEN para permitir a diarização de participantes."
        )
    ausentes = [str(audio) for audio in AUDIOS if not audio.is_file()]
    if ausentes:
        raise FileNotFoundError("Arquivos não encontrados: " + ", ".join(ausentes))

    torch.set_num_threads(args.cpu_threads)
    torch.set_num_interop_threads(max(1, min(4, args.cpu_threads // 2)))
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.backends.cudnn.benchmark = True

    device = "cuda"
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Threads de CPU: {args.cpu_threads}")
    print(f"Modelo: {args.modelo} | batch size: {args.batch_size}")

    modelo = whisperx.load_model(
        args.modelo,
        device,
        compute_type="int8",
        language="pt",
        asr_options={"beam_size": 5},
        threads=args.cpu_threads,
    )
    diarizador = whisperx.DiarizationPipeline(
        token=token,
        device=device,
    )

    for audio in AUDIOS:
        try:
            processar(audio, modelo, diarizador, device, args.batch_size)
        except RuntimeError as erro:
            if "memory" in str(erro).lower() or "cuda" in str(erro).lower():
                print("Falta de VRAM. Tente novamente com --batch-size 2.", file=sys.stderr)
            raise

    print("\nAs duas transcrições foram concluídas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

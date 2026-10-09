#!/usr/bin/env python3
from pathlib import Path
import subprocess
import shutil
import sys
import argparse

# =========================
# CONFIGURAÇÃO
# =========================

PASTA = Path(__file__).resolve().parent

ARQUIVOS = [
    PASTA / "Reflexão_ Will, Rita, Iris e Lene.m4a" ,
]

# Duração de cada pedaço em segundos
# 600 segundos = 5 minutos
DURACAO = 600


def segundos(valor: str) -> float:
    """Converte SS, MM:SS ou HH:MM:SS em segundos."""
    try:
        partes = [float(p) for p in valor.split(":")]
        if len(partes) == 1:
            return partes[0]
        if len(partes) == 2:
            minutos, segundos = partes
            return minutos * 60 + segundos
        if len(partes) == 3:
            horas, minutos, segundos = partes
            return horas * 3600 + minutos * 60 + segundos
    except ValueError:
        pass
    raise argparse.ArgumentTypeError(
        "use segundos, MM:SS ou HH:MM:SS (ex.: 01:30:00)"
    )


parser = argparse.ArgumentParser(
    description="Divide os áudios em partes a partir de um momento inicial específico."
)
parser.add_argument(
    "--inicio", type=segundos, default=38.0,
    help="momento inicial do corte: segundos, MM:SS ou HH:MM:SS (padrão: 0)",
)
args = parser.parse_args()


# =========================
# VERIFICA FFMPEG
# =========================

ffmpeg = shutil.which("ffmpeg")

if ffmpeg is None:
    print("ERRO: ffmpeg não foi encontrado no PATH.")
    print()
    print("Instale o ffmpeg e tente novamente.")
    sys.exit(1)


# =========================
# DIVISÃO
# =========================

for arquivo in ARQUIVOS:

    if not arquivo.exists():
        print(f"Arquivo não encontrado: {arquivo}")
        continue

    pasta_saida = PASTA / f"{arquivo.stem} - partes"
    pasta_saida.mkdir(parents=True, exist_ok=True)

    saida = pasta_saida / f"{arquivo.stem} - parte %03d.m4a"

    print()
    print("=" * 70)
    print(f"Dividindo: {arquivo.name}")
    print(f"Destino:   {pasta_saida}")
    print("=" * 70)

    comando = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "warning",

        "-i", str(arquivo),

        # ignora o trecho anterior ao momento inicial escolhido
        "-ss", str(args.inicio),

        # divide em intervalos fixos
        "-f", "segment",
        "-segment_time", str(DURACAO),
        "-reset_timestamps", "1",

        # mantém o áudio sem recomprimir
        "-c", "copy",

        str(saida)
    ]

    resultado = subprocess.run(comando)

    if resultado.returncode == 0:
        print(f"OK: {arquivo.name} dividido.")
    else:
        print(f"ERRO ao dividir {arquivo.name}")


print()
print("=" * 70)
print("PROCESSO CONCLUÍDO")
print("=" * 70)

"""Transcreve separadamente as duas gravações com a API Gemini.

Requisitos: py -m pip install google-genai
             variável GEMINI_API_KEY configurada
"""
from __future__ import annotations

import argparse
import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from google import genai

RAIZ = Path(__file__).resolve().parent
PASTAS = {
    "posição 1": RAIZ / "posição 1 - partes",
    "posição 2": RAIZ / "posição 2 - partes",
}
MODELO_TRANSCRICAO = "gemini-3.5-transcribe"


@dataclass(frozen=True)
class Parte:
    posicao: str
    caminho: Path
    indice: int
    inicio: float
    duracao: float


def hms(segundos: float) -> str:
    total = max(0, int(round(segundos)))
    horas, resto = divmod(total, 3600)
    minutos, segundos = divmod(resto, 60)
    return f"{horas:02d}:{minutos:02d}:{segundos:02d}"


def duracao(caminho: Path) -> float:
    try:
        saida = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(caminho)],
            text=True,
        )
        return float(saida.strip())
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as erro:
        raise RuntimeError("ffprobe não foi encontrado no PATH.") from erro


def listar_partes(posicao: str, pasta: Path) -> list[Parte]:
    arquivos = sorted(pasta.glob("*.m4a"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum .m4a encontrado em {pasta}")
    resultado, inicio = [], 0.0
    for indice, arquivo in enumerate(arquivos):
        tamanho = duracao(arquivo)
        resultado.append(Parte(posicao, arquivo, indice, inicio, tamanho))
        inicio += tamanho
    return resultado


def cliente() -> genai.Client:
    # Aceita também o nome criado acidentalmente com barras invertidas.
    chave = os.environ.get("GEMINI_API_KEY") or os.environ.get(r"GEMINI\_API\_KEY")
    if not chave and sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as registro:
                for nome in ("GEMINI_API_KEY", r"GEMINI\_API\_KEY"):
                    try:
                        chave = winreg.QueryValueEx(registro, nome)[0]
                        if chave:
                            break
                    except FileNotFoundError:
                        continue
        except OSError:
            pass
    if not chave:
        raise RuntimeError("A chave Gemini não foi encontrada no ambiente.")
    return genai.Client(api_key=chave)


def checkpoint(parte: Parte) -> Path:
    pasta = RAIZ / ".transcricoes-gemini" / parte.posicao
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{parte.indice:03d}.txt"


def transcrever_parte(parte: Parte, forcar: bool) -> tuple[Parte, str]:
    cache = checkpoint(parte)
    if cache.exists() and not forcar:
        return parte, cache.read_text(encoding="utf-8")

    ultimo_erro = None
    temporario = Path(tempfile.gettempdir()) / (
        f"gemini_audio_{parte.posicao[-1]}_{parte.indice:03d}.m4a"
    )
    shutil.copyfile(parte.caminho, temporario)
    try:
        for tentativa in range(1, 6):
            remoto = None
            try:
                api = cliente()
                remoto = api.files.upload(file=str(temporario))
                resposta = api.interactions.create(
                    model=MODELO_TRANSCRICAO,
                    input=[{"type": "audio", "uri": remoto.uri,
                            "mime_type": remoto.mime_type or "audio/m4a"}],
                    generation_config={"transcription_config": {
                    "language_codes": ["pt-BR"],
                        "mode": {"type": "verbatim",
                                 "timestamp_granularities": ["word"],
                                 "diarization_mode": "speaker"},
                    }},
                )
                texto = (resposta.output_text or "").strip()
                if not texto:
                    raise RuntimeError("Resposta vazia do Gemini.")
                cache.write_text(texto + "\n", encoding="utf-8")
                return parte, texto
            except Exception as erro:
                ultimo_erro = erro
                if tentativa == 5:
                    break
                espera = min(60, 3 * 2 ** tentativa)
                print(f"Falha em {parte.caminho.name}; nova tentativa em {espera}s: {erro}",
                      file=sys.stderr)
                time.sleep(espera)
            finally:
                if remoto is not None:
                    try:
                        api.files.delete(name=remoto.name)
                    except Exception:
                        pass
    finally:
        temporario.unlink(missing_ok=True)
    raise RuntimeError(f"Falha ao transcrever {parte.caminho.name}") from ultimo_erro


def somar_timestamps(texto: str, deslocamento: float) -> str:
    padrao = re.compile(
        r"(?<!\d)(?:(\d{1,2}):)?(\d{2}):(\d{2})(?:[.,](\d{1,3}))?(?!\d)"
    )

    def troca(m: re.Match[str]) -> str:
        local = (int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60
                 + int(m.group(3)) + int((m.group(4) or "0").ljust(3, "0")) / 1000)
        return hms(local + deslocamento)

    return padrao.sub(troca, texto)


def salvar_individual(posicao: str, itens: list[tuple[Parte, str]]) -> Path:
    destino = RAIZ / f"{posicao} - transcrição Gemini.txt"
    linhas = ["TRANSCRIÇÃO DO EVENTO", f"Áudio: {posicao}.m4a",
              "Formato: participante, início, fim e texto", ""]
    for parte, texto in sorted(itens, key=lambda x: x[0].indice):
        linhas += [f"--- Parte {parte.indice:03d} | {hms(parte.inicio)} a "
                   f"{hms(parte.inicio + parte.duracao)} ---",
                   somar_timestamps(texto, parte.inicio), ""]
    destino.write_text("\n".join(linhas).strip() + "\n", encoding="utf-8")
    return destino


def transcrever_posicao(posicao: str, partes: list[Parte], workers: int,
                        forcar: bool) -> Path:
    print(f"Transcrevendo {posicao} ({len(partes)} partes)...")
    itens = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = {executor.submit(transcrever_parte, p, forcar): p for p in partes}
        for futuro in concurrent.futures.as_completed(futuros):
            parte, texto = futuro.result()
            itens.append((parte, texto))
            print(f"  Concluída: {parte.caminho.name}")
    destino = salvar_individual(posicao, itens)
    print(f"Salva: {destino.name}")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trabalhadores", type=int, default=3)
    parser.add_argument("--forcar", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.trabalhadores <= 8:
        parser.error("--trabalhadores deve estar entre 1 e 8")

    partes = {nome: listar_partes(nome, pasta) for nome, pasta in PASTAS.items()}
    transcrever_posicao("posição 1", partes["posição 1"],
                        args.trabalhadores, args.forcar)
    transcrever_posicao("posição 2", partes["posição 2"],
                        args.trabalhadores, args.forcar)
    print("Processamento concluído.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

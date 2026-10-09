#!/usr/bin/env python3
"""Transcreve o evento usando posição 2 como relógio e posição 1 como apoio.

Alinhamento acústico validado:
    tempo_posicao_2 = tempo_posicao_1 + 142.600 segundos

Os arquivos anteriores não são modificados. A transcrição é gravada em uma
pasta nova e conserva blocos de 5 minutos com 15 segundos de contexto.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import transcrever_reflexao as motor


RAIZ = Path(__file__).resolve().parent
POSICAO_1 = RAIZ / "posição 1.m4a"
POSICAO_2 = RAIZ / "posição 2.m4a"
SAIDA = RAIZ / "transcricao_evento_posicoes"


def salvar_mapa_fontes() -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    mapa = {
        "linha_do_tempo_oficial": POSICAO_2.name,
        "motivo": (
            "posição 2 é mais completa, mais alta nas amostras e contém "
            "integralmente o intervalo compartilhado"
        ),
        "fontes": [
            {
                "arquivo": POSICAO_2.name,
                "inicio_na_linha_do_tempo": 0.0,
                "papel": "primaria",
            },
            {
                "arquivo": POSICAO_1.name,
                "inicio_na_linha_do_tempo": 142.6,
                "formula": "tempo_posicao_2 = tempo_posicao_1 + 142.600",
                "papel": "apoio para conferência e recuperação de falas",
            },
        ],
        "validacao_alinhamento": {
            "metodo": "correlação do envelope acústico a 10 Hz",
            "offset_inicio": 142.6,
            "offset_meio": 142.6,
            "offset_fim": 142.6,
            "deriva_detectada": False,
        },
    }
    (SAIDA / "mapa_fontes.json").write_text(
        json.dumps(mapa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    if not POSICAO_1.exists() or not POSICAO_2.exists():
        raise FileNotFoundError("As duas gravações são necessárias.")
    salvar_mapa_fontes()
    motor.AUDIO = POSICAO_2
    motor.SAIDA = SAIDA
    motor.PREFIXO_ID = "evento-posicoes"
    return motor.main()


if __name__ == "__main__":
    raise SystemExit(main())

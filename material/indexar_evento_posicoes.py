#!/usr/bin/env python3
"""Indexa professoras e estudantes nas duas gravações sincronizadas."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
PASTA = RAIZ / "transcricao_evento_posicoes"
ORIGEM = PASTA / "transcricao_indexada.json"
DESTINO = PASTA / "transcricao_por_id.json"
DESTINO_TXT = PASTA / "transcricao_por_id.txt"
DESTINO_INDICE = PASTA / "indice_participantes.json"
OFFSET_POSICAO_1 = 142.6
FIM_POSICAO_1_NA_POSICAO_2 = OFFSET_POSICAO_1 + 3822.677


PARTICIPANTES = [
    {"id": "P00", "nome": "Pessoa não identificada", "papel": "transição/sobreposição"},
    {"id": "P01", "nome": "Profa. Marcela", "papel": "professora"},
    {"id": "P02", "nome": "Profa. Bella", "papel": "professora"},
    {"id": "P03", "nome": "Profa. Adriana", "papel": "professora"},
    {"id": "P04", "nome": "Aluno/a 01", "papel": "estudante"},
    {"id": "P05", "nome": "Aluno/a 02", "papel": "estudante"},
    {"id": "P06", "nome": "Aluno/a 03", "papel": "estudante"},
    {"id": "P07", "nome": "Aluno/a 04", "papel": "estudante"},
    {"id": "P08", "nome": "Aluno/a 05", "papel": "estudante"},
    {"id": "P09", "nome": "Aluno/a 06", "papel": "estudante"},
    {"id": "P10", "nome": "Aluno/a 07", "papel": "estudante"},
]

# Intervalos confirmados pelo conteúdo, pela ordem fornecida e pela diarização
# Samsung. O primeiro intervalo compatível determina a identidade.
INTERVALOS = [
    (2.0, 579.5, "P01", 95, "exposição inicial confirmada pela transcrição auxiliar"),
    (579.5, 858.0, "P02", 95, "Marcela é chamada pelo nome; passagem explícita para Adriana"),
    (858.0, 1480.0, "P03", 95, "passagem explícita de Bella para Adriana"),
    (1540.0, 1615.0, "P04", 90, "primeira intervenção longa de estudante"),
    (1626.0, 1705.0, "P03", 90, "retorno da professora após a primeira intervenção"),
    (1705.0, 1795.0, "P02", 90, "retorno da professora; referência explícita a Adriana"),
    (1795.0, 1867.0, "P05", 90, "segunda intervenção longa de estudante"),
    (1867.0, 1986.0, "P06", 90, "terceira intervenção longa de estudante"),
    (1986.0, 2196.0, "P01", 90, "retorno de Marcela confirmado pela diarização Samsung"),
    (2196.0, 2238.0, "P02", 90, "retorno de Bella"),
    (2238.0, 2404.0, "P03", 90, "retorno de Adriana"),
    (2404.0, 2611.0, "P07", 90, "quarta intervenção longa de estudante"),
    (2611.0, 2813.0, "P08", 90, "quinta intervenção longa de estudante"),
    (2813.0, 3015.0, "P09", 90, "sexta intervenção longa de estudante"),
    (3015.0, 3126.0, "P02", 90, "retorno de Bella"),
    (3126.0, 3422.0, "P01", 90, "retorno de Marcela"),
    (3422.0, 3509.0, "P03", 90, "retorno de Adriana"),
    (3509.0, 3577.0, "P10", 95, "estudante se apresenta como aluno de Química"),
    (3577.0, 3717.0, "P02", 90, "resposta de Bella sobre a disciplina"),
    (3720.0, 3808.0, "P01", 90, "resposta de Marcela sobre licenciaturas de exatas"),
    (3808.0, 3898.0, "P03", 90, "complemento de Adriana sobre currículo e sala de recursos"),
]


def identificar(segundo: float) -> tuple[str, int, str]:
    for inicio, fim, pid, confianca, evidencia in INTERVALOS:
        if inicio <= segundo < fim:
            return pid, confianca, evidencia
    return "P00", 0, "transição, sobreposição ou atividade posterior ao debate"


def main() -> None:
    dados = json.loads(ORIGEM.read_text(encoding="utf-8"))
    falas = sorted(dados["falas"], key=lambda x: (x["inicio"], x["fim"], x["id"]))
    dados["falas"] = falas
    for numero, fala in enumerate(falas, 1):
        fala["id_origem"] = fala["id"]
        fala["id"] = f"evento-posicoes-{numero:05d}"
        meio = (float(fala["inicio"]) + float(fala["fim"])) / 2
        pid, confianca, evidencia = identificar(meio)
        fala.pop("participante", None)
        fala["participante_id"] = pid
        fala["identificacao_confianca_percentual"] = confianca
        fala["identificacao_evidencia"] = evidencia
        fala["posicao_2_inicio_ms"] = fala["inicio_ms"]
        fala["posicao_2_fim_ms"] = fala["fim_ms"]
        if OFFSET_POSICAO_1 <= fala["inicio"] <= FIM_POSICAO_1_NA_POSICAO_2:
            fala["posicao_1_inicio_ms"] = round(
                (fala["inicio"] - OFFSET_POSICAO_1) * 1000
            )
            fala["posicao_1_fim_ms"] = max(
                fala["posicao_1_inicio_ms"],
                round((min(fala["fim"], FIM_POSICAO_1_NA_POSICAO_2)
                       - OFFSET_POSICAO_1) * 1000),
            )
        else:
            fala["posicao_1_inicio_ms"] = None
            fala["posicao_1_fim_ms"] = None

    dados["linha_do_tempo_oficial"] = "posição 2.m4a"
    dados["offset_posicao_1_segundos"] = OFFSET_POSICAO_1
    dados["indice_participantes_arquivo"] = DESTINO_INDICE.name
    dados["contagem_por_participante_id"] = dict(
        Counter(f["participante_id"] for f in falas)
    )
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

    linhas = []
    for fala in falas:
        linhas.append(
            f"[{fala['inicio_hms']} --> {fala['fim_hms']}] "
            f"{fala['participante_id']} "
            f"[{fala['identificacao_confianca_percentual']}%]\n"
            f"{fala['texto']}"
        )
    DESTINO_TXT.write_text("\n\n".join(linhas) + "\n", encoding="utf-8")

    indice = {
        "evento": "O Perigo de uma História Única",
        "linha_do_tempo_oficial": "posição 2.m4a",
        "fonte_auxiliar": "posição 1.m4a",
        "offset_fonte_auxiliar_segundos": OFFSET_POSICAO_1,
        "participantes": PARTICIPANTES,
        "escala_confianca": {
            "95": "identificação apoiada por apresentação ou referência explícita",
            "90": "identificação apoiada por continuidade e diarização anterior",
            "0": "não identificado, transição ou falas sobrepostas",
        },
        "pendencia": (
            "Os materiais disponíveis registram apenas os primeiros nomes das "
            "professoras. Acrescentar sobrenomes após confirmação da pesquisadora."
        ),
    }
    DESTINO_INDICE.write_text(
        json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"JSON: {DESTINO}")
    print(f"TXT: {DESTINO_TXT}")
    print(f"Índice: {DESTINO_INDICE}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Adiciona participantes à transcrição sem modificar o resultado bruto.

As âncoras foram obtidas do próprio discurso (apresentação de Rita, menções a
Will, passagem explícita para Iris e interlocução em que a aluna chama Rita).
Trechos curtos de transição permanecem não identificados.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


RAIZ = Path(__file__).resolve().parent
ORIGEM = RAIZ / "transcricao_reflexao" / "transcricao_indexada.json"
DESTINO = RAIZ / "transcricao_reflexao" / "transcricao_com_participantes.json"
DESTINO_TXT = RAIZ / "transcricao_reflexao" / "transcricao_com_participantes.txt"
DESTINO_TXT_ID = RAIZ / "transcricao_reflexao" / "transcricao_por_id.txt"
DESTINO_INDICE = RAIZ / "transcricao_reflexao" / "indice_participantes.json"

PARTICIPANTES = {
    "Will": {"indice": "P01", "nome": "Will"},
    "Rita": {"indice": "P02", "nome": "Rita"},
    "Iris": {"indice": "P03", "nome": "Iris"},
    "Lene": {"indice": "P04", "nome": "Lene"},
    "Pessoa não identificada": {
        "indice": "P00", "nome": "Pessoa não identificada"
    },
}

PERCENTUAL_CONFIANCA = {
    "alta": 95,
    "media": 75,
    "baixa": 50,
    "nao_identificado": 0,
}


def identidade(ordem: int, fala: dict) -> tuple[str, str, str]:
    """Retorna nome, confiança e evidência para uma fala (ordem iniciada em 1)."""
    if ordem == 1:
        return "Pessoa não identificada", "nao_identificado", "saudação isolada"
    if 2 <= ordem <= 82:
        return "Will", "alta", "exposição masculina e menção posterior a Will"
    if 83 <= ordem <= 88:
        return "Pessoa não identificada", "nao_identificado", "conversa curta e sobreposta"
    if 89 <= ordem <= 102:
        return "Lene", "media", "mediação e apresentação curricular de Rita"
    if 103 <= ordem <= 116:
        return "Rita", "alta", "fala iniciada após apresentação nominal de Rita"
    if 117 <= ordem <= 132:
        return "Iris", "media", "nova reflexão antes da fala da outra mediadora"
    if 133 <= ordem <= 136:
        return "Lene", "alta", "fala sobre o professor Will na terceira pessoa"
    if ordem == 137:
        return "Will", "alta", "resposta direta sobre seu campo de atuação"
    if 138 <= ordem <= 166:
        return "Lene", "alta", "continuação da mediação e agradecimento a Will e Rita"
    if 167 <= ordem <= 216:
        return "Rita", "alta", "relato em que a aluna se dirige à narradora como Rita"
    if 217 <= ordem <= 218:
        return "Rita", "media", "continuação da passagem explícita da palavra para Iris"
    if 219 <= ordem <= 221:
        return "Pessoa não identificada", "nao_identificado", "negociação curta e sobreposta"
    if 222 <= ordem <= 229:
        return "Iris", "alta", "dinâmica apresentada após passagem nominal para Iris"
    if ordem >= 230:
        # O bloco final foi revisto após a legenda automática repetir a mesma
        # frase em vários intervalos. Vozes de movimentação/fotografia sem
        # identificação segura permanecem neutras.
        inicio = float(fala.get("inicio", 0))
        if inicio < 2428:
            return "Iris", "media", "continuidade da explicação da dinâmica"
        if inicio < 2651:
            return "Pessoa não identificada", "nao_identificado", "falas de movimentação e fotografia sem identificação segura"
        return "Iris", "media", "continuação da explicação da dinâmica"
    return "Pessoa não identificada", "nao_identificado", "fora das âncoras revisadas"


def main() -> None:
    dados = json.loads(ORIGEM.read_text(encoding="utf-8"))
    falas = dados["falas"]
    for ordem, fala in enumerate(falas, 1):
        nome, confianca, evidencia = identidade(ordem, fala)
        fala["participante"] = nome
        fala["participante_indice"] = PARTICIPANTES[nome]["indice"]
        fala["identificacao_confianca"] = confianca
        fala["identificacao_confianca_percentual"] = PERCENTUAL_CONFIANCA[confianca]
        fala["identificacao_evidencia"] = evidencia

    contagem = Counter(f["participante"] for f in falas)
    dados["participantes"] = list(PARTICIPANTES.values())
    dados["indexacao_participantes"] = {
        "metodo": "âncoras textuais e continuidade discursiva",
        "revisao_humana_recomendada": True,
        "contagem_falas": dict(contagem),
        "observacao": (
            "Confiança média e trechos não identificados devem ser conferidos "
            "auditivamente antes de uso acadêmico definitivo."
        ),
    }
    DESTINO.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

    linhas = []
    for fala in falas:
        linhas.append(
            f"[{fala['inicio_hms']} --> {fala['fim_hms']}] "
            f"{fala['participante']} [{fala['identificacao_confianca']}]\n"
            f"{fala['texto']}"
        )
    DESTINO_TXT.write_text("\n\n".join(linhas) + "\n", encoding="utf-8")

    # Versão destinada ao site: a transcrição contém somente o ID estável.
    linhas_id = []
    for fala in falas:
        linhas_id.append(
            f"[{fala['inicio_hms']} --> {fala['fim_hms']}] "
            f"{fala['participante_indice']} "
            f"[{fala['identificacao_confianca_percentual']}%]\n{fala['texto']}"
        )
    DESTINO_TXT_ID.write_text("\n\n".join(linhas_id) + "\n", encoding="utf-8")

    indice = {
        "evento": "Reflexão",
        "participantes": [
            {"id": "P01", "nome": "Prof. Will"},
            {"id": "P02", "nome": "Profa. Rita"},
            {"id": "P03", "nome": "Profa. Iris"},
            {"id": "P04", "nome": "Profa. Lene"},
            {"id": "P00", "nome": "Pessoa não identificada"},
        ],
        "observacao_tecnica": (
            "O percentual é uma confiança heurística da identificação do "
            "participante: alta=95%, média=75%, baixa=50% e não identificado=0%. "
            "As evidências detalhadas permanecem em "
            "transcricao_com_participantes.json."
        ),
    }
    DESTINO_INDICE.write_text(
        json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"JSON: {DESTINO}")
    print(f"TXT:  {DESTINO_TXT}")
    print(f"TXT por ID: {DESTINO_TXT_ID}")
    print(f"Índice: {DESTINO_INDICE}")
    print("Contagem:", dict(contagem))


if __name__ == "__main__":
    main()

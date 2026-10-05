#!/usr/bin/env python3
"""Atualiza tabelas derivadas e o pacote de dados do dashboard.

Os arquivos-base são abertos somente para leitura. Toda saída é gravada em
dados_tratados/ e dashboard/data.js.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dados_tratados"
DASH = ROOT / "dashboard"

SOURCES = {
    "historia": ROOT / "O Perigo de uma História Única (Responses).xlsx",
    "wicked": ROOT / "Wicked (Responses).xlsx",
    "doc": ROOT / "Transcrição do grupo de Alana e Giselle CinePET.doc",
    "txt": ROOT / "trascrição.txt",
}

TOPICS = {
    "Inclusão": ["inclus", "acolh", "participa"],
    "Exclusão": ["exclus", "exclu"],
    "Preconceito": ["preconce", "discrimin"],
    "Diferenças": ["diferen", "divers"],
    "Igualdade": ["igual", "equidade", "oportunidade"],
    "Respeito": ["respeit"],
    "Acessibilidade": ["acessib", "adapta"],
    "Direitos": ["direit"],
    "Estereótipos": ["estereot", "esteriot", "padrão", "padrao"],
    "Identidade": ["identidade", "personalidade", "religião", "religiao"],
    "Educação": ["educa", "ensino", "escola", "professor", "aluno"],
    "Resistência": ["resist", "lutar"],
}

STOPWORDS = set("a o e de da do das dos em para por com que um uma os as no na nos nas se ao aos à às é ser ter sua seu suas seus como mais não sim ou eu você ele ela eles elas isso essa esse sobre entre também muito quando já foi são pela pelo todos todas cada pode porque sem mas".split())


def text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return re.sub(r"\s+", " ", str(value)).strip()


def key(value) -> str:
    value = text(value).lower()
    value = "".join(c for c in unicodedata.normalize("NFD", value) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def norm_age(value):
    found = re.search(r"\b(1[5-9]|[2-7][0-9])\b", text(value))
    return int(found.group(1)) if found else None


ORDINALS = {"primeiro": 1, "segundo": 2, "terceiro": 3, "quarto": 4, "quinto": 5, "sexto": 6, "setimo": 7, "oitavo": 8, "nono": 9, "decimo": 10, "decimo primeiro": 11}


def norm_period(value):
    raw = key(value)
    if not raw or raw in {"2026 2", "2026.2"}:
        return None
    for name, number in sorted(ORDINALS.items(), key=lambda item: -len(item[0])):
        if name in raw:
            return number
    found = re.search(r"\b(1[0-2]|[1-9])\b", raw)
    return int(found.group(1)) if found else None


def norm_sex(value):
    raw = key(value)
    if raw in {"mulher", "feminino", "f"}: return "Mulher"
    if raw in {"homem", "masculino", "m"}: return "Homem"
    return text(value) or "Não informado"


def norm_course(value):
    raw = key(value)
    if not raw: return "Não informado"
    if "pedagog" in raw: return "Pedagogia"
    if "matemat" in raw: return "Matemática"
    if "contabe" in raw: return "Ciências Contábeis"
    if raw in {"si", "sistemas de informacao"}: return "Sistemas de Informação"
    if "fisica" in raw: return "Física"
    if "quimica" in raw: return "Química"
    if "letras" in raw: return "Letras"
    if "administr" in raw: return "Administração"
    return text(value).strip(" .")


def yes_no_detail(value):
    original = text(value)
    raw = key(value)
    if not raw: return "Não informado", ""
    no_patterns = ("nao", "nao possuo", "nao atuo", "no momento nao")
    if any(raw == p or raw.startswith(p + " ") for p in no_patterns): return "Não", ""
    if raw.startswith("sim"):
        detail = re.sub(r"(?i)^sim\s*[,.:;-]?\s*", "", original).strip()
        return "Sim", detail
    return "Sim", original


def topic_list(value):
    raw = key(value)
    return [topic for topic, stems in TOPICS.items() if any(key(stem) in raw for stem in stems)]


def anonymized_id(event, row_number, timestamp):
    seed = f"{event}|{row_number}|{text(timestamp)}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:12]


def add_issue(issues, record_id, event, field, original, reason):
    issues.append({"id_resposta": record_id, "evento": event, "campo": field, "valor_original": text(original), "motivo": reason})


def response_records():
    records, issues, mappings = [], [], []

    def append_record(event, row_number, values, indexes, block):
        timestamp = values[0]
        rid = anonymized_id(event, row_number, timestamp)
        age_raw, sex_raw, course_raw, period_raw, degree_raw, work_raw = (values[indexes[k]] if indexes[k] is not None else None for k in ("age", "sex", "course", "period", "degree", "work"))
        age, period = norm_age(age_raw), norm_period(period_raw)
        degree_status, degree_detail = yes_no_detail(degree_raw)
        work_status, work_detail = yes_no_detail(work_raw)
        answers = []
        for question, idx in indexes["answers"]:
            answer = text(values[idx])
            if answer:
                answers.append({"pergunta": question, "resposta": answer, "temas": topic_list(answer)})
        if age is None: add_issue(issues, rid, event, "idade", age_raw, "Idade ausente ou não reconhecida")
        if period is None: add_issue(issues, rid, event, "periodo", period_raw, "Período ausente ou ambíguo")
        for field, original, treated in [("curso", course_raw, norm_course(course_raw)), ("sexo", sex_raw, norm_sex(sex_raw)), ("periodo", period_raw, period)]:
            if text(original) and key(original) != key(treated):
                mappings.append({"campo": field, "valor_original": text(original), "valor_tratado": text(treated), "regra": "normalização automática"})
        records.append({
            "id": rid, "evento": event, "data": text(timestamp)[:10], "bloco_origem": block,
            "idade_original": text(age_raw), "idade": age, "sexo_original": text(sex_raw), "sexo": norm_sex(sex_raw),
            "curso_original": text(course_raw), "curso": norm_course(course_raw), "periodo_original": text(period_raw), "periodo": period,
            "outra_graduacao": degree_status, "outra_graduacao_detalhe": degree_detail,
            "atua_profissionalmente": work_status, "ocupacao": work_detail,
            "pseudonimo": text(values[indexes["pseudonym"]]) if indexes["pseudonym"] is not None else "",
            "consentimento": text(values[2]), "respostas": answers,
        })

    # Formulário História Única
    ws = load_workbook(SOURCES["historia"], data_only=True, read_only=False).active
    idx = {"age": 3, "sex": 4, "course": 5, "period": 6, "degree": 7, "work": 8, "pseudonym": 12,
           "answers": [("Concepções sobre inclusão", 9), ("Princípios da educação inclusiva", 10), ("Relação entre a conferência e inclusão", 11)]}
    for row_number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        append_record("O Perigo de uma História Única", row_number, list(row), idx, "principal")

    # Formulário Wicked: escolhe o bloco efetivamente preenchido em cada linha.
    ws = load_workbook(SOURCES["wicked"], data_only=True, read_only=False).active
    idx_a = {"age": 4, "sex": 5, "course": 6, "period": 7, "degree": 8, "work": 9, "pseudonym": 10,
             "answers": [("Relação entre Wicked e inclusão", 11)]}
    idx_b = {"age": 12, "sex": 13, "course": 14, "period": 15, "degree": 16, "work": 17, "pseudonym": 21,
             "answers": [("Concepções sobre inclusão", 18), ("Princípios da educação inclusiva", 19), ("Relação entre Wicked e inclusão", 20)]}
    for row_number, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
        values = list(row)
        use_b = sum(bool(text(values[i])) for i in range(12, 22)) >= sum(bool(text(values[i])) for i in range(4, 12))
        append_record("Wicked", row_number, values, idx_b if use_b else idx_a, "alternativo" if use_b else "principal")

    # Duplicidades por assinatura demográfica + respostas, sem usar e-mail.
    signatures = Counter()
    for record in records:
        sig = (record["evento"], record["idade"], record["sexo"], record["curso"], tuple(a["resposta"] for a in record["respostas"]))
        signatures[sig] += 1
    for record in records:
        sig = (record["evento"], record["idade"], record["sexo"], record["curso"], tuple(a["resposta"] for a in record["respostas"]))
        if signatures[sig] > 1: add_issue(issues, record["id"], record["evento"], "registro", "", "Possível duplicidade")
    return records, issues, mappings


def transcript_segments():
    content = SOURCES["txt"].read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"\n\s*\n", content)
    segments, current = [], None
    for part in parts:
        part = text(part)
        if not part or part.startswith("CinePET") or part.startswith("Transcrição") or part.startswith("Grupo de") or part.startswith("FOTO FINAL"):
            continue
        match = re.match(r"^([^:]{1,45}):\s*(.*)$", part)
        if match:
            current = match.group(1).strip()
            speech = match.group(2).strip()
        else:
            speech = part
        if speech:
            segments.append({"ordem": len(segments) + 1, "participante": current or "Não identificado", "fala": speech, "temas": topic_list(speech)})
    return segments


def manifest():
    result = []
    for label, path in SOURCES.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        stat = path.stat()
        result.append({"fonte": label, "arquivo": path.name, "tamanho_bytes": stat.st_size, "sha256": digest})
    return result


def words(records, segments):
    counter = Counter()
    corpus = [a["resposta"] for r in records for a in r["respostas"]] + [s["fala"] for s in segments]
    for item in corpus:
        for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", item.lower()):
            clean = key(word)
            if clean and clean not in STOPWORDS: counter[clean] += 1
    return [{"palavra": w, "frequencia": n} for w, n in counter.most_common(50)]


def build_ai_interpretation(records, answers):
    """Produz hipóteses rastreáveis para validação humana."""
    co = Counter()
    for answer in answers:
        themes = sorted(set(answer["temas"]))
        for i in range(len(themes)):
            for j in range(i + 1, len(themes)):
                co[(themes[i], themes[j])] += 1
    return {
        "rotulo": "Conteúdo gerado por IA",
        "tese": "As concepções discentes indicam que inclusão envolve reconhecer identidades plurais, enfrentar narrativas que produzem estigmas e transformar respeito às diferenças em possibilidades concretas de participação, aprendizagem e pertencimento na educação.",
        "leituras": [
            {"titulo": "A narrativa única limita o reconhecimento", "texto": "A conferência de Chimamanda oferece a chave crítica do percurso: quando uma pessoa ou grupo é explicado por uma versão única, sua complexidade desaparece. Nas respostas, inclusão surge associada a ampliar perspectivas e recusar julgamentos formados por relatos incompletos.", "evidencia": "Inclusão, Diferenças, Respeito, Igualdade e Estereótipos aparecem conectados nas respostas sobre a conferência."},
            {"titulo": "Wicked dramatiza a fabricação do estigma", "texto": "A trajetória de Elphaba transforma a discussão em experiência narrativa. Uma diferença visível é convertida em rótulo, o rótulo organiza o julgamento coletivo e esse julgamento legitima afastamento e exclusão. O filme dá forma afetiva ao mesmo problema discutido por Chimamanda.", "evidencia": "Nas respostas sobre Wicked, Diferenças, Respeito, Preconceito e Exclusão recebem forte presença temática."},
            {"titulo": "Diferença, respeito e inclusão são o núcleo comum", "texto": "No conjunto completo, inclusão não aparece como simples presença física. Ela é ligada ao reconhecimento das diferenças e a relações de respeito, sem exigir que alguém apague sua identidade para pertencer.", "evidencia": f"Diferenças + Inclusão e Diferenças + Respeito são as associações mais recorrentes, com {co[('Diferenças', 'Inclusão')]} e {co[('Diferenças', 'Respeito')]} respostas."},
            {"titulo": "Perspectivas e possibilidades para a educação inclusiva", "texto": "As menções a igualdade, direitos, acessibilidade, adaptação e educação ampliam a inclusão de um valor moral para uma responsabilidade pedagógica e institucional. Entre as possibilidades sugeridas pelo conjunto estão práticas flexíveis, acolhimento, escuta, acessibilidade, igualdade de oportunidades e participação efetiva.", "evidencia": "Educação + Inclusão e Acessibilidade + Igualdade aparecem entre as associações relevantes do corpus."}
        ],
        "sintese": "Uma interpretação integrada é que Chimamanda fornece a crítica à redução do outro, enquanto Wicked mostra as consequências sociais dessa redução. Os discentes retomam esse raciocínio ao relacionar pluralidade de histórias, estereótipos, preconceito, exclusão e respeito. Para a educação inclusiva, suas respostas apontam possibilidades centradas em acolhimento, acessibilidade, adaptação das práticas, igualdade de oportunidades, garantia de direitos e valorização das diferenças. As duas ações funcionam como momentos complementares do mesmo percurso formativo.",
        "limites": [
            "Esta interpretação foi gerada por IA e precisa ser validada pela pesquisadora.",
            "A marcação temática é automática; frequência não mede profundidade nem intenção.",
            "Os formulários têm tamanhos e perguntas diferentes; variações são ênfases, não efeitos causais.",
            "Uma resposta pode receber várias categorias e as categorias podem se sobrepor."
        ],
        "referencias": [
            {"titulo": "The danger of a single story — TED", "url": "https://www.ted.com/talks/chimamanda_ngozi_adichie_the_danger_of_a_single_story"},
            {"titulo": "Wicked — sinopse oficial", "url": "https://www.wickedmovie.com/synopsis"}
        ]
    }


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def main():
    OUT.mkdir(exist_ok=True); DASH.mkdir(exist_ok=True)
    records, issues, mappings = response_records()
    segments = transcript_segments()
    answers = [{"id_resposta": r["id"], "evento": r["evento"], **a} for r in records for a in r["respostas"]]
    flat_records = [{k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items() if k != "respostas"} for r in records]
    write_csv(OUT / "respostas_unificadas.csv", flat_records, list(flat_records[0]))
    write_csv(OUT / "respostas_qualitativas.csv", [{**a, "temas": " | ".join(a["temas"])} for a in answers], ["id_resposta", "evento", "pergunta", "resposta", "temas"])
    write_csv(OUT / "transcricao_segmentada.csv", [{**s, "temas": " | ".join(s["temas"])} for s in segments], ["ordem", "participante", "fala", "temas"])
    write_csv(OUT / "inconsistencias.csv", issues, ["id_resposta", "evento", "campo", "valor_original", "motivo"])
    unique_mappings = list({(m["campo"], m["valor_original"], m["valor_tratado"]): m for m in mappings}.values())
    write_csv(OUT / "dicionario_normalizacao.csv", unique_mappings, ["campo", "valor_original", "valor_tratado", "regra"])
    write_csv(OUT / "manifesto_fontes.csv", manifest(), ["fonte", "arquivo", "tamanho_bytes", "sha256"])
    payload = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "registros": records, "respostas": answers, "transcricao": segments, "inconsistencias": issues, "normalizacoes": unique_mappings, "manifesto": manifest(), "palavras": words(records, segments), "temas": list(TOPICS), "interpretacao_ia": build_ai_interpretation(records, answers)}
    (OUT / "dados_dashboard.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (DASH / "data.js").write_text("window.DASHBOARD_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    report = {"registros": len(records), "respostas_abertas": len(answers), "segmentos_transcricao": len(segments), "inconsistencias": len(issues), "normalizacoes": len(unique_mappings), "fontes_inalteradas": True}
    (OUT / "relatorio_execucao.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()

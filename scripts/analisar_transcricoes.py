#!/usr/bin/env python3
"""Analisa as três transcrições com reconhecimento morfológico pt_BR."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dashboard" / "transcricoes" / "dados" / "analises_textuais.json"
TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
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
STOPWORDS = set((
    "a ao aos aquela aquelas aquele aqueles aquilo as até com como da das de dela delas dele deles depois do dos e ela elas ele eles em entre essa essas esse esses esta estas este estes eu foi foram há isso isto já lhe lhes mais me mesmo meu meus minha minhas na nas nem no nos nós nossa nossas nosso nossos num numa o os ou outra outras outro outros para pela pelas pelo pelos por qual quando que quem se sem ser seu seus sua suas também te tem ter teu teus toda todas todo todos tu um uma umas uns você vocês vos vai vão né tá tô pra pro num numa naquele naquela naquilo contigo comigo convosco consigo"
).split())


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def key(value: str) -> str:
    value = str(value or "").lower()
    value = "".join(char for char in unicodedata.normalize("NFD", value) if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def read_dashboard_data() -> dict:
    source = (ROOT / "dashboard" / "data.js").read_text(encoding="utf-8")
    prefix = "window.DASHBOARD_DATA = "
    if not source.startswith(prefix):
        raise ValueError("dashboard/data.js não está no formato esperado")
    return json.loads(source[len(prefix):].strip().removesuffix(";"))


def load_corpora() -> dict[str, dict]:
    old = read_dashboard_data()
    position_path = ROOT / "material" / "transcricao_evento_posicoes"
    reflection_path = ROOT / "material" / "transcricao_reflexao"
    positions = read_json(position_path / "transcricao_por_id.json")
    positions_index = read_json(position_path / "indice_participantes.json")
    reflection = read_json(reflection_path / "transcricao_com_participantes.json")
    reflection_index = read_json(reflection_path / "indice_participantes.json")

    def normalized_rows(data: dict, index: dict) -> tuple[list[dict], list[dict]]:
        names = {person["id"]: person["nome"] for person in index.get("participantes", [])}
        rows = [{
            "id": row.get("id") or row.get("id_origem"),
            "texto": row.get("texto", ""),
            "participante_id": row.get("participante_id") or row.get("participante_indice") or "P00",
        } for row in data.get("falas", [])]
        return rows, [{"id": person["id"], "nome": person["nome"]} for person in index.get("participantes", [])]

    position_rows, position_people = normalized_rows(positions, positions_index)
    reflection_rows, reflection_people = normalized_rows(reflection, reflection_index)
    old_rows = [{
        "id": f"legado-{row.get('ordem', i + 1):04d}",
        "texto": row.get("fala", ""),
        "participante_id": row.get("participante") or "Não identificado",
    } for i, row in enumerate(old.get("transcricao", []))]
    old_people = list(dict.fromkeys(row["participante_id"] for row in old_rows))
    return {
        "antiga": {"falas": old_rows, "participantes": [{"id": name, "nome": name} for name in old_people]},
        "posicoes": {"falas": position_rows, "participantes": position_people},
        "reflexao": {"falas": reflection_rows, "participantes": reflection_people},
    }


def hunspell_lemmas(tokens: set[str]) -> dict[str, str]:
    executable = shutil.which("hunspell")
    if not executable:
        raise RuntimeError("Hunspell não está instalado. Instale o Hunspell com o dicionário pt_BR.")
    ordered = sorted(tokens)
    result = subprocess.run(
        [executable, "-m", "-d", "pt_BR"],
        input="\n".join(ordered) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Hunspell não conseguiu abrir o dicionário pt_BR.")

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in result.stdout.splitlines():
        if line.strip():
            current.append(line)
        else:
            blocks.append(current)
            current = []
    if current or len(blocks) < len(ordered):
        blocks.append(current)
    if len(blocks) != len(ordered):
        raise RuntimeError(f"Resposta inesperada do Hunspell: {len(blocks)} blocos para {len(ordered)} formas.")

    lemmas: dict[str, str] = {}
    for token, lines in zip(ordered, blocks):
        candidates = [lemma for line in lines for lemma in re.findall(r"(?:^|\s)st:([^\s]+)", line)]
        if candidates:
            lemmas[token] = unicodedata.normalize("NFC", candidates[0].casefold())
    return lemmas


def classify_topics(text: str) -> list[str]:
    normalized = key(text)
    return [topic for topic, stems in TOPICS.items() if any(key(stem) in normalized for stem in stems)]


def analyze_corpus(corpus: dict, lemmas: dict[str, str]) -> dict:
    word_counts: Counter[str] = Counter()
    phrase_counts: Counter[str] = Counter()
    speaker_counts: dict[str, Counter[str]] = defaultdict(Counter)
    theme_counts: Counter[str] = Counter()
    raw_tokens = recognized_tokens = meaningful_tokens = 0
    recognized_forms: set[str] = set()

    for row in corpus["falas"]:
        speaker_id = row["participante_id"]
        source_tokens = [token.casefold() for token in TOKEN_RE.findall(row["texto"])]
        raw_tokens += len(source_tokens)
        row_lemmas: list[str] = []
        for token in source_tokens:
            lemma = lemmas.get(token)
            if not lemma:
                continue
            recognized_tokens += 1
            recognized_forms.add(token)
            lookup = key(lemma)
            if len(lookup) < 3 or lookup in STOPWORDS:
                continue
            row_lemmas.append(lemma)
            word_counts[lemma] += 1
            speaker_counts[speaker_id]["words"] += 1
            meaningful_tokens += 1
        speaker_counts[speaker_id]["segments"] += 1
        for size in (2, 3):
            for start in range(len(row_lemmas) - size + 1):
                phrase_counts[" ".join(row_lemmas[start:start + size])] += 1
        theme_counts.update(classify_topics(row["texto"]))

    total_segments = len(corpus["falas"])
    participant_names = {person["id"]: person["nome"] for person in corpus["participantes"]}
    participants = []
    for person in corpus["participantes"]:
        participant_id = person["id"]
        stats = speaker_counts[participant_id]
        participants.append({
            "id": participant_id,
            "nome": participant_names[participant_id],
            "falas": stats["segments"],
            "palavras": stats["words"],
            "percentual_palavras": round(stats["words"] / meaningful_tokens * 100, 1) if meaningful_tokens else 0,
        })
    for speaker_id, stats in speaker_counts.items():
        if speaker_id not in participant_names:
            participants.append({
                "id": speaker_id,
                "nome": speaker_id,
                "falas": stats["segments"],
                "palavras": stats["words"],
                "percentual_palavras": round(stats["words"] / meaningful_tokens * 100, 1) if meaningful_tokens else 0,
            })

    words = [{"palavra": word, "frequencia": count} for word, count in word_counts.most_common(50)]
    phrases = [{"frase": phrase, "frequencia": count} for phrase, count in phrase_counts.most_common(20) if count > 1]
    themes = [{
        "tema": topic,
        "falas": count,
        "percentual_falas": round(count / total_segments * 100, 1) if total_segments else 0,
    } for topic, count in theme_counts.most_common()]
    return {
        "metricas": {
            "falas": total_segments,
            "tokens_originais": raw_tokens,
            "tokens_reconhecidos": recognized_tokens,
            "formas_reconhecidas": len(recognized_forms),
            "lemas_distintos": len(word_counts),
            "tokens_analisados": meaningful_tokens,
            "formas_nao_reconhecidas": max(0, raw_tokens - recognized_tokens),
        },
        "palavras": words,
        "combinacoes": phrases,
        "temas": themes,
        "participantes": participants,
        "metodo": "Hunspell pt_BR: reconhecimento lexical e lematização morfológica; frequências calculadas sobre lemas, sem palavras funcionais.",
    }


def main() -> None:
    corpora = load_corpora()
    all_tokens = {
        token.casefold()
        for corpus in corpora.values()
        for row in corpus["falas"]
        for token in TOKEN_RE.findall(row["texto"])
    }
    lemmas = hunspell_lemmas(all_tokens)
    result = {key_name: analyze_corpus(corpus, lemmas) for key_name, corpus in corpora.items()}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    for corpus_id, analysis in result.items():
        metrics = analysis["metricas"]
        print(f"{corpus_id}: {metrics['falas']} falas, {metrics['tokens_reconhecidos']} tokens reconhecidos, {metrics['lemas_distintos']} lemas")
    print(f"Arquivo gerado: {OUTPUT}")


if __name__ == "__main__":
    main()

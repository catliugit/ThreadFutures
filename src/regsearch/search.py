"""Retrieval over the EU rules on unsold products, with an evaluation and cited answers.

The corpus is Regulation (EU) 2024/1781, chunked by article paragraph (Articles 23-26,
key Article 2 definitions, Annex VII). Two retrievers are compared on a hand-written set
of 22 questions with a known correct paragraph:
  - TF-IDF with cosine similarity (scikit-learn)
  - BM25 (implemented here, k1=1.5, b=0.75)
Metrics: hit@1, hit@3 and mean reciprocal rank (MRR).

`answer()` sends the top passages to an LLM and accepts the answer only if every
citation it makes is one of the retrieved passages. It needs LLM_API_KEY / LLM_MODEL
(see .env.example); retrieval and evaluation run without any API key.

    python -m regsearch.search            # run the evaluation
    python -m regsearch.search "Can we destroy stock a charity refused?"
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "data" / "regulation" / "espr_unsold_products.json"
EVAL = ROOT / "data" / "regulation" / "eval_questions.json"
OUT = ROOT / "models" / "regsearch_eval.json"


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words if w not in ENGLISH_STOP_WORDS]


def load_chunks() -> list[dict]:
    return json.loads(CORPUS.read_text())["chunks"]


def _doc(c: dict) -> str:
    return f"{c['title']}. {c['text']}"


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.toks = [tokens(d) for d in docs]
        self.k1, self.b = k1, b
        self.avgdl = np.mean([len(t) for t in self.toks])
        df = Counter(w for t in self.toks for w in set(t))
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.tf = [Counter(t) for t in self.toks]

    def scores(self, query: str) -> np.ndarray:
        q = tokens(query)
        out = np.zeros(len(self.toks))
        for i, (tf, t) in enumerate(zip(self.tf, self.toks)):
            norm = self.k1 * (1 - self.b + self.b * len(t) / self.avgdl)
            out[i] = sum(self.idf.get(w, 0) * tf[w] * (self.k1 + 1) / (tf[w] + norm) for w in q if w in tf)
        return out


class TfIdf:
    def __init__(self, docs: list[str]):
        self.vec = TfidfVectorizer(tokenizer=tokens, lowercase=False, token_pattern=None, sublinear_tf=True)
        self.m = self.vec.fit_transform(docs)

    def scores(self, query: str) -> np.ndarray:
        return (self.m @ self.vec.transform([query]).T).toarray().ravel()


def search(query: str, k: int = 3, retriever=None, chunks=None) -> list[dict]:
    chunks = chunks or load_chunks()
    retriever = retriever or BM25([_doc(c) for c in chunks])
    s = retriever.scores(query)
    return [chunks[i] | {"score": round(float(s[i]), 3)} for i in np.argsort(-s)[:k]]


def evaluate() -> dict:
    chunks = load_chunks()
    docs = [_doc(c) for c in chunks]
    qs = json.loads(EVAL.read_text())
    res = {}
    for name, r in {"tfidf": TfIdf(docs), "bm25": BM25(docs)}.items():
        ranks = []
        for item in qs:
            order = [chunks[i]["id"] for i in np.argsort(-r.scores(item["q"]))]
            ranks.append(order.index(item["expect"]) + 1)
        ranks = np.array(ranks)
        res[name] = {"hit@1": round(float(np.mean(ranks == 1)), 3), "hit@3": round(float(np.mean(ranks <= 3)), 3),
                     "mrr": round(float(np.mean(1 / ranks)), 3)}
    res["questions"] = len(qs)
    res["passages"] = len(chunks)
    OUT.write_text(json.dumps(res, indent=2))
    return res


PROMPT = """Answer the question using ONLY the passages below from EU Regulation 2024/1781.
Cite every claim with the passage id in square brackets, e.g. [Art 25(5)].
If the passages don't answer it, say so. This is general information, not legal advice.

{passages}

Question: {question}"""


def check_citations(answer: str, retrieved: list[dict]) -> list[str]:
    """Return citations in the answer that don't match a retrieved passage."""
    allowed = {c["id"] for c in retrieved}
    return [c for c in re.findall(r"\[([^\]]+)\]", answer) if c not in allowed]


def answer(question: str, k: int = 3) -> dict:
    import anthropic  # optional dependency, only needed for generated answers

    hits = search(question, k)
    passages = "\n\n".join(f"[{h['id']}] {h['title']}: {h['text']}" for h in hits)
    client = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"])
    msg = client.messages.create(model=os.environ["LLM_MODEL"], max_tokens=800,
                                 messages=[{"role": "user", "content": PROMPT.format(passages=passages, question=question)}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    bad = check_citations(text, hits)
    return {"answer": text, "sources": [h["id"] for h in hits], "unsupported_citations": bad, "accepted": not bad}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for h in search(" ".join(sys.argv[1:])):
            print(f"[{h['id']}] ({h['score']}) {h['text'][:160]}...")
    else:
        print(json.dumps(evaluate(), indent=2))

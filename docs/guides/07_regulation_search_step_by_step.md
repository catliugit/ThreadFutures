# Part 07: Regulation search, step by step

**Status:** Built · **Data label:** Retrieval prototype over REAL EU LAW TEXT (Regulation (EU) 2024/1781, © European Union, EUR-Lex). General information, not legal advice.
**Code:** `src/regsearch/search.py`; data in `data/regulation/espr_unsold_products.json` and `data/regulation/eval_questions.json`; tests in `tests/test_stock.py`
**Numbers from:** `models/regsearch_eval.json` (plus a read-only per-question check, labelled)

---

## 1. The question this stage answers

Given a plain-English question about unsold products, can I find the exact paragraph of EU law that answers it, and if a language model writes an answer, can I check that every citation it makes is real?

A fashion brand cares because, from 19 July 2026, large companies may no longer destroy unsold clothing and footwear in the EU outside limited exceptions, and must disclose what they discard (Articles 24 and 25). Teams will ask questions like "can we destroy stock a charity refused?" and the answer has to point to the article, not be invented.

---

## 2. The pipeline, step by step

### Step 1. Build a small, hand-chunked corpus

**Where:** `data/regulation/espr_unsold_products.json`

The corpus is 22 passages from Regulation (EU) 2024/1781: Articles 23 to 26 split by paragraph, key Article 2 definitions (such as 2(34) "destruction" and 2(37) "unsold consumer product") and Annex VII (the list of products covered). Each chunk has an `id` (like `Art 25(1)`), a `title` and the `text`.

**Why chunk by paragraph:** the paragraph is the unit a lawyer cites. If a chunk is a whole article, the answer is buried; if it's a sentence, context is lost.

### Step 2. Write the evaluation set first

**Where:** `data/regulation/eval_questions.json`

22 hand-written questions, each with the id of the paragraph that answers it:

```json
{"q": "When does the ban on destroying unsold clothes start?", "expect": "Art 25(1)"}
```

**Why first:** so I can see where search fails before tuning anything, and so any change can be measured.

### Step 3. Tokenise

```python
def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words if w not in ENGLISH_STOP_WORDS]
```

- Lowercase and split into runs of letters and digits.
- Drop common English stop words ("the", "of", "is").
- A very light stemmer: strip a trailing "s" from words longer than 3 letters, so "products" matches "product".

**Why so simple:** it's transparent and good enough for a 22-passage corpus. It also explains some misses (section 5): "meaning" doesn't match "means".

### Step 4. Retriever 1: BM25 (written by hand)

```python
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
        ...
            norm = self.k1 * (1 - self.b + self.b * len(t) / self.avgdl)
            out[i] = sum(self.idf.get(w, 0) * tf[w] * (self.k1 + 1) / (tf[w] + norm) for w in q if w in tf)
```

- `avgdl`: average passage length in tokens.
- `df`: in how many passages each word appears.
- `idf`: rare words get a high weight, common words a low one.
- `tf`: how often each word appears in each passage.
- In `scores`, for each query word found in a passage: idf x a saturating function of term frequency, adjusted for passage length (`norm`). Long passages are penalised a bit (`b = 0.75`), and repeating a word gives diminishing returns (`k1 = 1.5`).

Each passage is indexed as `title + ". " + text` (`_doc()`), so the title words count too.

### Step 5. Retriever 2: TF-IDF with cosine similarity

The `TfIdf` class uses scikit-learn's `TfidfVectorizer` with the same `tokens()` function and `sublinear_tf=True` (log-scaled term counts). Score = dot product of the query vector with each passage vector. Because the vectoriser normalises vectors to unit length by default, that dot product is the cosine similarity.

### Step 6. Search

```python
def search(query: str, k: int = 3, retriever=None, chunks=None) -> list[dict]:
    chunks = chunks or load_chunks()
    retriever = retriever or BM25([_doc(c) for c in chunks])
    s = retriever.scores(query)
    return [chunks[i] | {"score": round(float(s[i]), 3)} for i in np.argsort(-s)[:k]]
```

- Default retriever is BM25. Return the top k passages with their scores. This is what the API endpoint (part 09) calls.

### Step 7. Evaluate both retrievers

```python
for name, r in {"tfidf": TfIdf(docs), "bm25": BM25(docs)}.items():
    ranks = []
    for item in qs:
        order = [chunks[i]["id"] for i in np.argsort(-r.scores(item["q"]))]
        ranks.append(order.index(item["expect"]) + 1)
    ranks = np.array(ranks)
    res[name] = {"hit@1": ..., "hit@3": ..., "mrr": round(float(np.mean(1 / ranks)), 3)}
```

- For each question, rank all 22 passages and record the position of the correct one (1 = top).
- hit@1: share where it's first. hit@3: share where it's in the top 3. MRR: average of 1 / rank.

### Step 8. Optional: generated answer with a citation check

```python
PROMPT = """Answer the question using ONLY the passages below from EU Regulation 2024/1781.
Cite every claim with the passage id in square brackets, e.g. [Art 25(5)].
If the passages don't answer it, say so. This is general information, not legal advice.
...
def check_citations(answer: str, retrieved: list[dict]) -> list[str]:
    """Return citations in the answer that don't match a retrieved passage."""
    allowed = {c["id"] for c in retrieved}
    return [c for c in re.findall(r"\[([^\]]+)\]", answer) if c not in allowed]
```

- `answer()` retrieves the top 3 passages, sends them to an LLM API with the prompt, then runs `check_citations`.
- `check_citations` pulls out everything in square brackets and returns any id that isn't one of the retrieved passages.
- The answer is marked `accepted` only if that list is empty.

**Why:** a language model can cite an article that sounds right but wasn't in front of it. This check catches that mechanically. It needs `LLM_API_KEY` and `LLM_MODEL`; retrieval and evaluation run without any key.

A unit test (`test_citation_check_flags_unretrieved_articles`) checks that `[Art 25(1)]` and `[Annex VII]` pass when retrieved, and `[Art 25(5)]` is flagged when it wasn't.

---

## 3. Concepts, from scratch

### Information retrieval
**Definition:** finding the documents most relevant to a query from a collection. Search engines are the familiar example.

### Lexical (keyword) search
**Definition:** matching on the words themselves. Fast, explainable, but blind to synonyms ("charity" vs "donation").

### Tokenisation, stop words, stemming
- **Tokenisation:** splitting text into words.
- **Stop words:** very common words removed because they carry little meaning.
- **Stemming:** reducing words to a common form ("products" to "product"). Mine only strips a trailing "s".

### TF-IDF
**Definition:** term frequency x inverse document frequency. A word scores high in a passage if it appears often there but rarely elsewhere.
**Worked example:** "destruction" appears in many of the 22 passages, so it has low IDF. "donation" appears in very few, so it's a strong signal when it matches.

### Cosine similarity
**Definition:** treat the query and each passage as vectors of word weights, and measure the angle between them. 1 = same direction, 0 = nothing in common. Length doesn't matter, only the mix of words.

### BM25
**Definition:** a ranking function that improves on TF-IDF in two ways: term frequency saturates (the 10th mention of a word adds much less than the 2nd), and long documents are normalised so they don't win just by containing more words.
**Parameters:** `k1` controls saturation (1.5 here), `b` controls length normalisation (0.75 here). Those are common defaults.
**Why it matters:** it's the standard baseline for keyword search, and the retrieval half of many RAG systems.

### hit@k
**Definition:** share of questions where the right passage is in the top k.
**Example:** 21 of 22 in the top 3 is 0.955.

### Mean reciprocal rank (MRR)
**Definition:** average of 1 / (rank of the correct answer).
**Worked example:** three questions with correct answers at ranks 1, 2 and 4: (1 + 0.5 + 0.25) / 3 = 0.58.
**Why use it:** it rewards getting the right answer near the top, not just somewhere in the top k.

### Evaluation set ("golden set")
**Definition:** a fixed set of questions with known right answers, used to measure a system.
**Why it matters:** without one, every tweak is a matter of opinion.

### Retrieval-augmented generation (RAG)
**Definition:** retrieve relevant passages first, then give them to a language model to write an answer grounded in them.
**Analogy:** an open-book exam. The model is only allowed to answer from the pages you hand it.
**Why it matters:** it reduces invented answers and makes every claim traceable.

### Hallucination
**Definition:** a language model producing confident but unsupported content, including made-up citations.

### Citation checking
**Definition:** a mechanical check that every citation in an answer refers to a passage that was actually retrieved.
**Limit:** it checks the citation exists in the set, not that the passage really supports the claim. That needs a second check (human or model-based).

### Embeddings (not used yet)
**Definition:** numeric vectors that represent meaning, so "charity" and "donation" end up close together.
**Why mention it:** it's the obvious fix for the vocabulary gap, usually combined with BM25 (hybrid search).

---

## 4. The real results, and how to read them

From `models/regsearch_eval.json` (22 questions, 22 passages):

| Retriever | hit@1 | hit@3 | MRR |
|---|---|---|---|
| TF-IDF + cosine | 0.727 | 0.955 | 0.832 |
| BM25 | 0.727 | 0.955 | 0.825 |

**How to read it:**

- **21 of 22** questions have the right paragraph in the top 3 (95.5%). **16 of 22** have it first (72.7%).
- The two retrievers are essentially tied. TF-IDF has a slightly higher MRR (0.832 vs 0.825), so where both miss first place, TF-IDF tends to have the right answer a little higher. The README's "MRR 0.83" is the rounded TF-IDF figure; BM25, the default used by the API, rounds to 0.83 or 0.82 depending on rounding convention. I'd quote both to be exact.
- With only 22 passages, a random ranking would get hit@3 of about 14% (3/22), so this is far above chance. But the corpus is tiny: the real test is a larger corpus with more similar passages.

**Per-question check (read-only, run while writing this guide).** The six questions where the right passage is not first are the same for both retrievers:

| Question | Expected | BM25 rank |
|---|---|---|
| When does the ban on destroying unsold clothes start? | Art 25(1) | 3 |
| Can stock be destroyed if a charity refuses the donation? | Art 25(5) | 2 |
| What is the legal meaning of destruction of a product? | Art 2(34) | **7** |
| Can a company pass stock to a smaller firm to destroy it and get around the ban? | Art 25(2) | 3 |
| Will the Commission publish data on how much unsold stock is destroyed? | Art 26 | 2 |
| Is remanufacturing defined in the regulation? | Art 2(16) | 3 |

The single top-3 miss is "What is the legal meaning of destruction of a product?" (rank 7).

---

## 5. What went wrong or surprised me, and what it taught me

### Vocabulary gaps
Keyword search misses when the question uses different words from the law. The "charity" question is the clearest example: Article 25(5) talks about "non-acceptance of products offered for donation" and never says "charity". Because "donation" is also in the question, it still came second, but the word "charity" contributed nothing. The definition question failed worst: "meaning" doesn't match "means" with my simple stemmer, and "destruction" and "product" appear in so many passages that they barely discriminate. Meanwhile "legal" does appear, but in the wrong place: Article 2(32), the definition of a digital product passport service provider, says "natural or legal person" and repeats "product" several times. So that paragraph came first and the actual definition of destruction, Article 2(34), came 7th. The word matched; the meaning didn't.

**A correction to the summary:** the subproject summary says it "misses when the question uses different words from the law (e.g. 'charity' vs 'donation')". The per-question check shows the charity question isn't a top-3 miss (it ranks 2nd); the one top-3 miss is the definition question. Both are vocabulary problems, so the lesson holds, but the precise example is worth getting right.

**What it taught me:** build the evaluation set first, then read the failures one by one. The aggregate score hides what's actually going wrong.

**Fixes I'd try:** a small synonym glossary (charity to donation, clothes to apparel), proper stemming or lemmatisation, embeddings with hybrid ranking, and expanding the evaluation set with paraphrased questions.

### BM25 didn't beat TF-IDF
I expected BM25 to win. On 22 short, similar-length passages, its length normalisation and term saturation have little to work with. On a larger corpus with long and short passages, I'd expect it to matter more.

---

## 6. Honest limits

- **Retrieval prototype.** 22 passages and 22 hand-written questions, all written by me, so there's a risk the questions unconsciously match the wording I'd read.
- Lexical search only; no embeddings yet.
- The generated-answer path (`answer()`) is optional and needs an LLM API key. It isn't evaluated on a set of questions; only the citation check is unit-tested.
- The citation check confirms a cited passage was retrieved, not that it supports the claim.
- **General information, not legal advice.** It also doesn't cover delegated acts that the Commission will adopt for the derogations in Article 25(5).
- Not fashion-specific beyond the regulation itself; not used by a customer.

---

## 7. How to run it yourself

```bash
make regsearch                                                        # python -m regsearch.search: evaluation -> models/regsearch_eval.json
PYTHONPATH=src python -m regsearch.search "Can we destroy stock a charity refused?"   # top 3 passages
make api   # then GET http://127.0.0.1:8000/v1/regulation/search?q=destruction%20ban
```

Generated answers (optional): copy `.env.example` to `.env`, set `LLM_API_KEY` and `LLM_MODEL`, `pip install -r requirements-llm.txt`, then call `regsearch.search.answer("your question")` from Python.

---

## 8. Glossary

- **ESPR:** Ecodesign for Sustainable Products Regulation, Regulation (EU) 2024/1781.
- **Chunk / passage:** one retrievable unit of text, here a paragraph.
- **Corpus:** the collection being searched.
- **Tokenisation:** splitting text into words.
- **Stop words:** common words removed before matching.
- **Stemming:** reducing words to a shared root.
- **TF-IDF:** word weighting by frequency in a passage and rarity across passages.
- **IDF:** inverse document frequency, high for rare words.
- **Cosine similarity:** similarity of two vectors by angle.
- **BM25:** a ranking function with term saturation and length normalisation.
- **k1 / b:** BM25's saturation and length-normalisation parameters.
- **hit@k:** share of queries with the right answer in the top k.
- **MRR:** mean reciprocal rank.
- **Evaluation / golden set:** questions with known correct answers.
- **RAG:** retrieval-augmented generation.
- **Hallucination:** confident, unsupported model output.
- **Citation check:** verifying cited ids were among the retrieved passages.
- **Embeddings:** vectors that capture meaning.
- **Hybrid search:** combining keyword and embedding scores.
- **Derogation:** a legal exception to a rule.

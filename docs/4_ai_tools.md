# 4. AI tools

Language-model and retrieval work: regulation search over EU law text (Part 07) and the purchase-order agent (Part 08, earlier exploratory work for a previous idea, garment factories, not the product).

Thread Futures is a B2B resale service for fashion brands: we act as their sales team for stock they can't sell themselves, and give them the money from each sale plus a report of where every item went. The code described here is earlier, exploratory technical work, not the product. Nothing new is built during customer discovery (to early 2027), and any early pilot runs by hand (spreadsheet and email). See [ARCHITECTURE.md](ARCHITECTURE.md) for how the parts fit together.

Each part starts with a header block (discipline, methodology, tools, status), then the short part note, then the full step-by-step guide.

## Contents

- [Part 07: Regulation search](#part-07-regulation-search)
  - [Part 07 step by step](#part-07-step-by-step)
- [Part 08: Purchase-order agent](#part-08-purchase-order-agent)
  - [Part 08 step by step](#part-08-step-by-step)

---

## Part 07: Regulation search

**Discipline:** AI Engineering / Data Science (primary / secondary)  
**Methodology:** `src/regsearch/search.py` tokenises hand-chunked articles of Regulation (EU) 2024/1781 and ranks them with a hand-written BM25 (k1 = 1.5, b = 0.75) and with scikit-learn TF-IDF plus cosine similarity. Both are scored on 22 evaluation questions (hit@k, MRR); an optional LLM answer has its citations checked against the retrieved articles.  
**Tools:** Python, scikit-learn, NumPy, LLM API (optional)  
**Status:** Live: an internal research aid. It rebuilds its index on each call, which is fine at this size.

**Build state:** Built · **Data label:** Retrieval prototype  

### In one line
Finds the paragraph of EU law that answers a question about unsold products, and only accepts an AI answer if every citation is one of the passages it found.

### Why it matters
Brands ask which exception applies to a batch. Answers must be traceable to the article, not invented. Part of the earlier, exploratory technical work, not the product; later it could check the legal references in a batch report (part 18).

### Data
Regulation (EU) 2024/1781 (ESPR): Articles 23 to 26, key Article 2 definitions, Annex VII. 22 passages. © European Union, EUR-Lex.

### Method
Two retrievers compared: TF-IDF with cosine similarity, and BM25 (implemented by hand). Evaluated on 22 hand-written questions with a known correct paragraph: hit@1, hit@3, mean reciprocal rank. Optional LLM answer with a citation check.

### Tools
Python, scikit-learn (TF-IDF), BM25, LLM API (optional), FastAPI endpoint

### Result
Right article in the top 3 for 21 of 22 questions (95%), first for 73%, MRR 0.83. Its one top-3 miss in the test set is a definitions question ("What is the legal meaning of destruction?").

### Honest limits
Lexical search; embeddings or a short glossary of legal terms would help with paraphrased questions. General information, not legal advice.

### Where it lives
src/regsearch/search.py, data/regulation/, models/regsearch_eval.json

### Part 07 step by step

**Build state:** Built · **Data label:** Retrieval prototype over REAL EU LAW TEXT (Regulation (EU) 2024/1781, © European Union, EUR-Lex). General information, not legal advice.
**Code:** `src/regsearch/search.py`; data in `data/regulation/espr_unsold_products.json` and `data/regulation/eval_questions.json`; tests in `tests/test_stock.py`
**Numbers from:** `models/regsearch_eval.json` (plus a read-only per-question check, labelled)

---

#### 1. The question this stage answers

Given a plain-English question about unsold products, can I find the exact paragraph of EU law that answers it, and if a language model writes an answer, can I check that every citation it makes is real?

A fashion brand cares because, from 19 July 2026, large companies may no longer destroy unsold clothing and footwear in the EU outside limited exceptions, and must disclose what they discard (Articles 24 and 25). Teams will ask questions like "can we destroy stock a charity refused?" and the answer has to point to the article, not be invented.

---

#### 2. The pipeline, step by step

##### Step 1. Build a small, hand-chunked corpus

**Where:** `data/regulation/espr_unsold_products.json`

The corpus is 22 passages from Regulation (EU) 2024/1781: Articles 23 to 26 split by paragraph, key Article 2 definitions (such as 2(34) "destruction" and 2(37) "unsold consumer product") and Annex VII (the list of products covered). Each chunk has an `id` (like `Art 25(1)`), a `title` and the `text`.

**Why chunk by paragraph:** the paragraph is the unit a lawyer cites. If a chunk is a whole article, the answer is buried; if it's a sentence, context is lost.

##### Step 2. Write the evaluation set first

**Where:** `data/regulation/eval_questions.json`

22 hand-written questions, each with the id of the paragraph that answers it:

```json
{"q": "When does the ban on destroying unsold clothes start?", "expect": "Art 25(1)"}
```

**Why first:** so I can see where search fails before tuning anything, and so any change can be measured.

##### Step 3. Tokenise

```python
def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in words if w not in ENGLISH_STOP_WORDS]
```

- Lowercase and split into runs of letters and digits.
- Drop common English stop words ("the", "of", "is").
- A very light stemmer: strip a trailing "s" from words longer than 3 letters, so "products" matches "product".

**Why so simple:** it's transparent and good enough for a 22-passage corpus. It also explains some misses (section 5): "meaning" doesn't match "means".

##### Step 4. Retriever 1: BM25 (written by hand)

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

##### Step 5. Retriever 2: TF-IDF with cosine similarity

The `TfIdf` class uses scikit-learn's `TfidfVectorizer` with the same `tokens()` function and `sublinear_tf=True` (log-scaled term counts). Score = dot product of the query vector with each passage vector. Because the vectoriser normalises vectors to unit length by default, that dot product is the cosine similarity.

##### Step 6. Search

```python
def search(query: str, k: int = 3, retriever=None, chunks=None) -> list[dict]:
    chunks = chunks or load_chunks()
    retriever = retriever or BM25([_doc(c) for c in chunks])
    s = retriever.scores(query)
    return [chunks[i] | {"score": round(float(s[i]), 3)} for i in np.argsort(-s)[:k]]
```

- Default retriever is BM25. Return the top k passages with their scores. This is what the API endpoint (part 09) calls.

##### Step 7. Evaluate both retrievers

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

##### Step 8. Optional: generated answer with a citation check

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

#### 3. Concepts, from scratch

##### Information retrieval
**Definition:** finding the documents most relevant to a query from a collection. Search engines are the familiar example.

##### Lexical (keyword) search
**Definition:** matching on the words themselves. Fast, explainable, but blind to synonyms ("charity" vs "donation").

##### Tokenisation, stop words, stemming
- **Tokenisation:** splitting text into words.
- **Stop words:** very common words removed because they carry little meaning.
- **Stemming:** reducing words to a common form ("products" to "product"). Mine only strips a trailing "s".

##### TF-IDF
**Definition:** term frequency x inverse document frequency. A word scores high in a passage if it appears often there but rarely elsewhere.
**Worked example:** "destruction" appears in many of the 22 passages, so it has low IDF. "donation" appears in very few, so it's a strong signal when it matches.

##### Cosine similarity
**Definition:** treat the query and each passage as vectors of word weights, and measure the angle between them. 1 = same direction, 0 = nothing in common. Length doesn't matter, only the mix of words.

##### BM25
**Definition:** a ranking function that improves on TF-IDF in two ways: term frequency saturates (the 10th mention of a word adds much less than the 2nd), and long documents are normalised so they don't win just by containing more words.
**Parameters:** `k1` controls saturation (1.5 here), `b` controls length normalisation (0.75 here). Those are common defaults.
**Why it matters:** it's the standard baseline for keyword search, and the retrieval half of many RAG systems.

##### hit@k
**Definition:** share of questions where the right passage is in the top k.
**Example:** 21 of 22 in the top 3 is 0.955.

##### Mean reciprocal rank (MRR)
**Definition:** average of 1 / (rank of the correct answer).
**Worked example:** three questions with correct answers at ranks 1, 2 and 4: (1 + 0.5 + 0.25) / 3 = 0.58.
**Why use it:** it rewards getting the right answer near the top, not just somewhere in the top k.

##### Evaluation set ("golden set")
**Definition:** a fixed set of questions with known right answers, used to measure a system.
**Why it matters:** without one, every tweak is a matter of opinion.

##### Retrieval-augmented generation (RAG)
**Definition:** retrieve relevant passages first, then give them to a language model to write an answer grounded in them.
**Analogy:** an open-book exam. The model is only allowed to answer from the pages you hand it.
**Why it matters:** it reduces invented answers and makes every claim traceable.

##### Hallucination
**Definition:** a language model producing confident but unsupported content, including made-up citations.

##### Citation checking
**Definition:** a mechanical check that every citation in an answer refers to a passage that was actually retrieved.
**Limit:** it checks the citation exists in the set, not that the passage really supports the claim. That needs a second check (human or model-based).

##### Embeddings (not used yet)
**Definition:** numeric vectors that represent meaning, so "charity" and "donation" end up close together.
**Why mention it:** it's the obvious fix for the vocabulary gap, usually combined with BM25 (hybrid search).

---

#### 4. The real results, and how to read them

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

#### 5. What went wrong or surprised me, and what it taught me

##### Vocabulary gaps
Keyword search misses when the question uses different words from the law. The "charity" question is the clearest example: Article 25(5) talks about "non-acceptance of products offered for donation" and never says "charity". Because "donation" is also in the question, it still came second, but the word "charity" contributed nothing. The definition question failed worst: "meaning" doesn't match "means" with my simple stemmer, and "destruction" and "product" appear in so many passages that they barely discriminate. Meanwhile "legal" does appear, but in the wrong place: Article 2(32), the definition of a digital product passport service provider, says "natural or legal person" and repeats "product" several times. So that paragraph came first and the actual definition of destruction, Article 2(34), came 7th. The word matched; the meaning didn't.

**A correction to the summary:** the subproject summary says it "misses when the question uses different words from the law (e.g. 'charity' vs 'donation')". The per-question check shows the charity question isn't a top-3 miss (it ranks 2nd); the one top-3 miss is the definition question. Both are vocabulary problems, so the lesson holds, but the precise example is worth getting right.

**What it taught me:** build the evaluation set first, then read the failures one by one. The aggregate score hides what's actually going wrong.

**Fixes I'd try:** a small synonym glossary (charity to donation, clothes to apparel), proper stemming or lemmatisation, embeddings with hybrid ranking, and expanding the evaluation set with paraphrased questions.

##### BM25 didn't beat TF-IDF
I expected BM25 to win. On 22 short, similar-length passages, its length normalisation and term saturation have little to work with. On a larger corpus with long and short passages, I'd expect it to matter more.

---

#### 6. Honest limits

- **Retrieval prototype.** 22 passages and 22 hand-written questions, all written by me, so there's a risk the questions unconsciously match the wording I'd read.
- Lexical search only; no embeddings yet.
- The generated-answer path (`answer()`) is optional and needs an LLM API key. It isn't evaluated on a set of questions; only the citation check is unit-tested.
- The citation check confirms a cited passage was retrieved, not that it supports the claim.
- **General information, not legal advice.** It also doesn't cover delegated acts that the Commission will adopt for the derogations in Article 25(5).
- Not fashion-specific beyond the regulation itself; not used by a customer.

---

#### 7. How to run it yourself

```bash
make regsearch                                                        # python -m regsearch.search: evaluation -> models/regsearch_eval.json
PYTHONPATH=src python -m regsearch.search "Can we destroy stock a charity refused?"   # top 3 passages
make api   # then GET http://127.0.0.1:8000/v1/regulation/search?q=destruction%20ban
```

Generated answers (optional): copy `.env.example` to `.env`, set `LLM_API_KEY` and `LLM_MODEL`, `pip install -r requirements-llm.txt`, then call `regsearch.search.answer("your question")` from Python.

---

#### 8. Glossary

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

---

## Part 08: Purchase-order agent

**Discipline:** AI Engineering / Machine Learning (primary / secondary)  
**Methodology:** `src/offcut/agent.py` gives an LLM one tool, `plan_offcuts`, which wraps the deterministic `service.py` (forecast, `grading.py` lot codes, and `matching.py` hard constraints followed by weighted recycler scoring). The model extracts the order and flags its assumptions; invalid inputs come back as tool errors, and every number comes from tested code.  
**Tools:** Anthropic Python SDK (tool use), Python, pytest  
**Status:** Parked: earlier exploratory work for a previous idea (garment factories), not the product.

**Build state:** Built, parked. Earlier exploratory work for a previous idea (garment factories), not the product · **Data label:** Prototype  

### In one line
Reads a messy production order note, states its assumptions, and calls tested tools for every number.

### Why it matters
Real orders arrive as emails and messages. The agent does the language work; code does the maths, so results are reproducible. Part of the earlier, exploratory technical work, not the product; the same pattern could later turn brands' messy stock lists into batch records for the batch report (part 18).

### Data
Free-text order notes.

### Method
An LLM with tool use calls a deterministic planning tool (forecast, grading, recycler matching). Invalid inputs come back as tool errors so the model can correct them.

### Tools
Python, LLM API with tool use (provider set by environment variables)

### Result
Every figure in the reply comes from tested code; assumptions are flagged explicitly.

### Honest limits
Needs an API key; not evaluated on a large set of real orders yet.

### Where it lives
src/offcut/agent.py, src/offcut/service.py

### Part 08 step by step

**Build state:** Built, parked. Earlier exploratory work for a previous idea (garment factories), not the product · **Data label:** Prototype. The forecast it calls is trained on SIMULATED cutting runs (part 01). Recycler profiles are fictional samples.
**Code:** `src/offcut/agent.py`, `src/offcut/service.py`, `src/offcut/grading.py`, `src/offcut/matching.py`, `data/recyclers_sample.json`
**Tests:** `tests/test_offcut.py` (TestModelExport::test_service_plan, test_service_rejects_bad_order, TestGradingMatching)

---

#### 1. The question this stage answers

Production orders arrive as messy emails and chat messages, not tidy forms. Can a language model read one, work out the order, say what it had to assume, and produce an offcut plan where every number comes from tested code?

A fashion brand (or its factory) cares because the useful information is locked in free text: "PO 4471: 22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka". Retyping it into a form is the step people skip, so the forecast never gets used. The agent removes that step without letting the model make up numbers.

---

#### 2. The pipeline, step by step

##### Step 1. A deterministic "plan" service

**Where:** `src/offcut/service.py`, `forecast()` and `plan()`

```python
def plan(order: Dict) -> Dict:
    """Forecast, grade and match in one call."""
    fc = forecast(order)
    colour = order.get("colour", "mixed")
    region = order.get("region", "South Asia")
    lots = build_lots(order.get("run_id", "RUN"), order["fibre"], colour,
                      GARMENTS[order["garment"]].knit, fc["offcut_kg"])
    recyclers = load_recyclers()
    return {
        "forecast": fc,
        "lots": [dict(l.as_dict(), matches=match_lot(l, region, recyclers)[:3]) for l in lots],
    }
```

- `forecast(order)`: validates the order, encodes it, and runs the exported part 01 model (the JSON trees, via `predict_json`) for P10, P50 and P90. It also returns the 15% rule-of-thumb kg for comparison.
- Defaults: colour "mixed", region "South Asia" if not given.
- `build_lots`: splits the forecast into lots by physical form.
- `match_lot`: ranks sample recyclers for each lot; keep the top 3.

**Why:** this function is plain Python, tested, and gives the same answer every time for the same order. It's what the API, the agent and the tests all call.

##### Step 2. Validate the order strictly

```python
def validate_order(order: Dict) -> None:
    for c in PRE_MARKER:
        if c not in order:
            raise ValueError(f"order is missing '{c}'")
    for c, allowed in CATEGORIES.items():
        if order[c] not in allowed:
            raise ValueError(f"{c} must be one of {allowed}, got {order[c]!r}")
    if not 1.2 <= float(order["fabric_width_m"]) <= 2.2:
        raise ValueError("fabric_width_m must be between 1.2 and 2.2")
```

- Every required field must be present, categories must be known, and numbers must be within the ranges the model was trained on (also 60 to 500 gsm and 500 to 60,000 metres).
- The error messages are written to be read by a person or a model: they say what's allowed.

**Why:** the model only knows the ranges it saw. Refusing out-of-range orders is safer than extrapolating silently.

##### Step 3. Turn the forecast into graded lots

**Where:** `src/offcut/grading.py`

```python
FORM_SHARE = {"knit": {"strips": 0.0, "remnant": 0.20, "cutting": 0.80},
              "woven": {"strips": 0.07, "remnant": 0.18, "cutting": 0.75}}
```

- Offcuts are split by form, because form drives recyclability: strips (selvedge trim, only on wovens), remnants (roll ends, often reusable) and cutting waste (small irregular pieces, most of the volume).
- Grade code = fibre class + colour class, e.g. `C1-W` for 100% cotton, white.
- Notes are added automatically, for example "Elastane content limits mechanical recycling; confirm % before offer."

A test checks the lots add back up to the forecast (`test_lots_sum_to_forecast`).

##### Step 4. Match lots to recyclers: filter, then score

**Where:** `src/offcut/matching.py`, `match_lot()`

```python
        if lot.kg_p10 >= r["min_lot_kg"]:
            size_score, size_note = 1.0, "P10 clears minimum lot"
        elif lot.kg_p50 >= r["min_lot_kg"]:
            size_score, size_note = 0.6, "P50 clears minimum; consolidate to be safe"
        elif lot.kg_p90 >= r["min_lot_kg"]:
            size_score, size_note = 0.3, "Only P90 clears minimum; consolidate with other runs"
        else:
            size_score, size_note = 0.0, "Below minimum; consolidate across runs"
        score = round(0.6 * size_score + 0.25 * r["process_fit"].get(lot.fibre, 0.5)
                      + 0.15 * (1 - min(r["lead_time_days"], 60) / 60), 3)
```

- First, hard constraints (earlier in the function): the recycler must accept the grade, the form, and serve the region. If not, skip it.
- Then the size score uses the **forecast range**: if even the pessimistic P10 clears the recycler's minimum lot, that's the safest match. This is where quantile forecasting pays off.
- Final score: 60% size, 25% how well the recycler's process suits the fibre, 15% lead time (faster is better, capped at 60 days).
- Every match carries a plain-English "why".

The five recycler profiles in `data/recyclers_sample.json` are fictional, each labelled "(sample)".

##### Step 5. Expose the plan as a tool for the language model

**Where:** `src/offcut/agent.py`, `plan_offcuts()`

```python
@beta_tool
def plan_offcuts(garment: str, fibre: str, size_mix: str, fabric_width_m: float,
                 gsm: float, fabric_metres: float, colour: str = "mixed",
                 region: str = "South Asia", run_id: str = "RUN") -> str:
    """Forecast pre-cut offcuts for a production run, split them into graded lots,
    and rank sample recyclers for each lot.
    ...
    try:
        return json.dumps(service.plan(order))
    except (ValueError, KeyError) as e:
        # Returned to the model as a tool error so it can correct the order.
        return json.dumps({"error": str(e)})
```

- The decorator from the LLM provider's SDK turns the function's typed signature and docstring into a tool definition the model can see: name, parameters, types, and the allowed values listed in the docstring.
- The function just calls `service.plan`.
- If validation fails, the error goes back to the model as the tool's result instead of crashing. The model can read "gsm must be between 60 and 500" and fix the order.

##### Step 6. Instruct the model with a system prompt

```python
SYSTEM = """You help garment factories plan what happens to their cutting-room offcuts \
before a production run is cut.
...
2. If a required field is missing or ambiguous, state your assumption explicitly \
(e.g. "denim assumed 1.55 m wide") rather than inventing precision.
3. Call plan_offcuts with the order. Never compute forecast numbers yourself.
4. Reply with: the order you used (with assumptions flagged), the forecast range \
(P10-P90 kg) next to the 15% rule of thumb, each lot with its best recycler match and why, \
and a 4-6 sentence lot offer the factory could send. Note that recycler profiles are samples."""
```

- Step 1 of the prompt (not shown) lists the allowed values for every field.
- Step 2: flag assumptions instead of guessing silently.
- Step 3: the key rule. The model never does the maths.
- Step 4: a fixed reply structure, including the rule-of-thumb comparison and a draft offer to a recycler.

##### Step 7. Run the tool-use loop

```python
def run(note: str) -> str:
    if not MODEL:
        raise SystemExit("Set LLM_MODEL and LLM_API_KEY (see .env.example).")
    ...
    final = runner.until_done()
    if final.stop_reason == "refusal":
        return "The request was declined."
    return "".join(b.text for b in final.content if b.type == "text")
```

- The model name and API key come from environment variables (`LLM_MODEL`, `LLM_API_KEY`), set in a local `.env` file that is never committed. `.env.example` shows the variable names with empty values.
- The SDK's tool runner handles the loop: send the note, the model asks to call `plan_offcuts`, the code runs it, the result goes back, and so on until the model writes its final reply.
- If the model declines, the function says so rather than returning nothing.
- The final reply is the text blocks joined together.

---

#### 3. Concepts, from scratch

##### Large language model (LLM)
**Definition:** a model trained on large amounts of text that predicts likely next words. Good at reading messy language and writing; unreliable at precise arithmetic and facts it hasn't been given.

##### Tool use (function calling)
**Definition:** the model is given descriptions of functions it may call. Instead of answering directly, it can output "call this function with these arguments"; your code runs it and returns the result.
**Analogy:** a sharp assistant with a calculator and a filing system. They decide what to look up; the calculator does the sums.
**Why it matters here:** the model does extraction and drafting; tested code does every number.

##### Agent and the agent loop
**Definition:** an LLM that can take several steps, calling tools and reading results, until a task is done.
**Here:** a small agent with one tool. Read note, call tool, maybe correct and call again, then write the reply.

##### System prompt
**Definition:** instructions given to the model before the user's message, setting its role and rules.

##### Structured extraction
**Definition:** turning free text into fields with defined types and allowed values.
**Worked example:** "22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka" becomes garment `tee`, fibre `cotton`, colour `white`, fabric_metres 22,000, gsm 180, fabric_width_m 1.8, size_mix `standard` (XS to XXL is closest), region `South Asia`. The size mix is a judgement the model should flag as an assumption, since "S-XXL" isn't exactly any template.

##### Deterministic vs probabilistic components
**Definition:** deterministic code gives the same output for the same input. An LLM may phrase things differently each time.
**Design principle:** put anything that must be reproducible or auditable (forecasts, lot sizes, scores) in deterministic code.

##### Stating assumptions
**Definition:** when information is missing, say what was assumed, so a person can correct it.
**Why it matters:** a confident wrong width gives a confident wrong forecast. A flagged assumption invites a check.

##### Tool errors as feedback
**Definition:** return validation errors to the model as tool results instead of raising them.
**Why it matters:** the model can correct itself (for example, convert "180 g" or change an unknown fibre to the nearest allowed one and say so).

##### Input validation and allowed ranges
**Definition:** reject inputs outside what the system supports. Here, the same ranges as the training data contract in part 01.

##### Hard constraints then scoring
**Definition:** first remove options that can't work (wrong grade, wrong region), then rank the rest by a weighted score.
**Why it matters:** it keeps the ranking explainable: every match has a reason.

##### Environment variables and secrets
**Definition:** configuration passed in from outside the code. API keys belong here, never in the source.
**Here:** `.env` (ignored by git) holds the real key; `.env.example` documents what's needed.

---

#### 4. The real results, and how to read them

There's no metrics file for the agent, and I won't invent one. What is true and checkable:

- Every figure in the reply comes from `service.plan`, which is covered by tests: `test_service_plan` checks P10 <= P50 <= P90 and that lots are produced for a jeans order; `test_service_rejects_bad_order` checks a "sock" garment is rejected; `test_lots_sum_to_forecast` and `test_matching_respects_constraints` check the lot split and the recycler filter.
- The forecast inside it carries the part 01 accuracy: 8.8% mean error on 1,600 held-out **simulated** runs, P10 to P90 coverage 76.8%.
- The agent itself has **not been evaluated** on a set of real order notes. That's the obvious next step: 30 to 50 real or realistic notes with the correct extracted order, measuring field-level accuracy and how often assumptions are flagged.

To see it work on the deterministic side without any API key:

```bash
PYTHONPATH=src python -m offcut.service
```

That prints the forecast, lots and top recycler matches for a demo tee order.

---

#### 5. What went wrong or surprised me, and what it taught me

- **The temptation to let the model do the maths.** It would have been quicker to ask the model "how much offcut will this produce?". It would also have been unreproducible and unauditable. Making the model call a tool for every number was the key design decision.
- **Error messages are part of the interface.** Once tool errors go back to the model, the wording of `ValueError` messages matters. "gsm must be between 60 and 500" lets the model fix the problem; a stack trace wouldn't.
- **Assumptions are a feature.** Real notes leave things out (width is often missing for denim). The prompt makes the model say "denim assumed 1.55 m wide", which turns a hidden risk into something a planner can correct.
- **Inherited from part 01:** the float32 export fix matters here too, because the agent's tool uses the same exported JSON model.

---

#### 6. Honest limits

- **Prototype.** Needs an LLM API key, and isn't evaluated on a large set of real orders.
- The underlying forecast is trained on **simulated** runs.
- Recycler profiles are **fictional samples**; the form shares in `grading.py` come from the simulator, and the grade standard is a v0 written for illustration, not agreed with recyclers.
- One tool only. A real version would need tools for looking up the factory's fabric library, checking recycler capacity, and so on.
- Language models can still mis-extract a field confidently. Flagged assumptions and human review are the safeguards, not a guarantee.
- Not used by a customer.

---

#### 7. How to run it yourself

Deterministic part (no key needed):

```bash
make offcuts                        # trains and exports the forecast model
PYTHONPATH=src python -m offcut.service
make test
```

Agent (needs an LLM API key):

```bash
cp .env.example .env                # then fill in LLM_API_KEY and LLM_MODEL
pip install -r requirements-llm.txt
PYTHONPATH=src python -m offcut.agent "PO 4471: 22k metres white cotton jersey, 180gsm, 1.8m wide, tees S-XXL, Dhaka"
```

Make sure the variables in `.env` are loaded into your shell (for example `set -a; source .env; set +a`) before running.

---

#### 8. Glossary

- **LLM:** large language model.
- **Tool use / function calling:** the model asks your code to run a function and reads the result.
- **Agent:** an LLM that takes several tool-using steps towards a goal.
- **Agent loop / tool runner:** the code that passes tool calls and results back and forth.
- **System prompt:** standing instructions for the model.
- **Structured extraction:** turning free text into typed fields.
- **Deterministic:** same input, same output.
- **Assumption flagging:** stating what was guessed when information was missing.
- **Tool error:** a validation message returned to the model so it can correct itself.
- **Input validation:** rejecting inputs outside the supported range.
- **Graded lot:** a batch of offcuts with a fibre and colour grade and a physical form.
- **Grade code:** fibre class plus colour class, such as C1-W.
- **Hard constraint:** a rule that must be met for an option to be considered.
- **Weighted score:** a ranking combining several factors with fixed weights.
- **Minimum lot:** the smallest batch a recycler will accept.
- **Environment variable:** configuration supplied from outside the code.
- **`.env` / `.env.example`:** local secrets file (never committed) / template showing required variables.
- **PO:** purchase order.

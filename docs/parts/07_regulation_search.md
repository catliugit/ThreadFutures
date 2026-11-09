# Thread Futures part 07: Regulation search

**Status:** Built · **Label:** Retrieval prototype  

## In one line
Finds the paragraph of EU law that answers a question about unsold products, and only accepts an AI answer if every citation is one of the passages it found.

## Why it matters
Brands ask which exception applies to a batch. Answers must be traceable to the article, not invented.

## Data
Regulation (EU) 2024/1781 (ESPR): Articles 23 to 26, key Article 2 definitions, Annex VII. 22 passages. © European Union, EUR-Lex.

## Method
Two retrievers compared: TF-IDF with cosine similarity, and BM25 (implemented by hand). Evaluated on 22 hand-written questions with a known correct paragraph: hit@1, hit@3, mean reciprocal rank. Optional LLM answer with a citation check.

## Tools
Python, scikit-learn (TF-IDF), BM25, LLM API (optional), FastAPI endpoint

## Result
Right article in the top 3 for 21 of 22 questions (95%), first for 73%, MRR 0.83. Its one top-3 miss in the test set is a definitions question ("What is the legal meaning of destruction?").

## Honest limits
Lexical search; embeddings or a short glossary of legal terms would help with paraphrased questions. General information, not legal advice.

## Where it lives
src/regsearch/search.py, data/regulation/, models/regsearch_eval.json

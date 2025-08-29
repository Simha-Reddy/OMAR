import os
import re
import json
import numpy as np
from tqdm import tqdm
from collections import defaultdict
from openai import AzureOpenAI
from dotenv import load_dotenv
import ast  # for use with the function get_retrieval_queries
import math
from datetime import datetime, timezone

# Optional FAISS support
try:
    import faiss  # faiss-cpu
    FAISS_AVAILABLE = True
except ImportError:  # pragma: no cover
    FAISS_AVAILABLE = False

# Remove sklearn dependency if FAISS present; keep as fallback
try:
    from sklearn.neighbors import NearestNeighbors
    SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    SKLEARN_AVAILABLE = False

load_dotenv()  # Load .env at the top

# --- Helpers ---------------------------------------------------------------

def tag_chunks_with_page(chunks, full_text):
    """
    Assign page numbers to chunks based on markers found in the full_text and
    the recorded chunk["start"] global offsets. Supports several common page markers.

    Mutates chunks to add:
      - page: int (defaults to 1 if not found)
      - page_offset: character offset from start of the detected page block
    """
    if not isinstance(full_text, str):
        full_text = str(full_text or '')

    page_regex = re.compile(
        r'(?:Page\s+(\d+)\s+of\s+\d+|##\s*Page\s+(\d+)|Page\s+(\d+)|-+\s*Page\s+(\d+)\s*-+|\f)',
        re.IGNORECASE,
    )

    page_markers = []  # tuples: (position, page_number_or_None)
    for m in page_regex.finditer(full_text):
        # Find the first non-None group (the page number)
        page_num = next((int(g) for g in m.groups() if g and str(g).isdigit()), None)
        page_markers.append((m.start(), page_num))
    # Sentinel at end
    page_markers.append((len(full_text), None))

    # If no explicit markers, default everything to page 1
    if len(page_markers) <= 1:
        for chunk in chunks:
            chunk["page"] = chunk.get("page", 1)
            chunk["page_offset"] = chunk.get("start", 0)
        return chunks

    for chunk in chunks:
        chunk_start = int(chunk.get("start", 0))
        # Find interval [pos, next_pos) containing this start
        for i, (pos, page_num) in enumerate(page_markers[:-1]):
            next_pos = page_markers[i + 1][0]
            if pos <= chunk_start < next_pos:
                chunk["page"] = page_num if page_num is not None else 1
                chunk["page_offset"] = max(0, chunk_start - pos)
                break
        else:
            # Fallback
            chunk["page"] = 1
            chunk["page_offset"] = chunk_start
    return chunks


def sliding_window_chunk(text, window_size=2000, step_size=1000):
    """
    Splits text into overlapping chunks using a sliding window.
    Each chunk is window_size characters, sliding by step_size.
    Adds 'start' (global offset), 'chunk_id', and assigns correct 'page' using tag_chunks_with_page.
    """
    chunks = []
    n = len(text)
    start = 0
    chunk_num = 1
    while start < n:
        chunk_text = text[start:start + window_size]
        if chunk_text.strip():
            chunks.append({
                "chunk_id": f"chunk-{chunk_num}",
                "section": f"Window {chunk_num}",
                "text": chunk_text.strip(),
                "start": start  # global offset in chart text
                # 'page' will be assigned below
            })
        if start + window_size >= n:
            break
        start += step_size
        chunk_num += 1
    # Assign correct page numbers to each chunk
    chunks = tag_chunks_with_page(chunks, text)
    return chunks


def get_retrieval_queries(client, deploy_chat, user_question):
    """
    Use GPT to generate multiple focused retrieval queries from a user question.
    """
    prompt = f"""Rewrite the following clinical question as 3-5 short, keyword-focused queries for retrieving relevant medical record text. Focus on key terms, medications, diagnoses, or concepts.

Output ONLY a valid Python list of strings. Do not include any explanation or extra text.

Question: {user_question}
Queries:"""
    response = client.chat.completions.create(
        model=deploy_chat,
        messages=[
            {"role": "system", "content": "You are a clinical information retrieval assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    print("[DEBUG] Raw model output for queries:", response.choices[0].message.content.strip())
    # Expecting output like: ["midodrine indication", "midodrine orthostatic hypotension", ...]
    raw = response.choices[0].message.content.strip()
    # Remove code block markers if present
    if raw.startswith("```"):
        raw = raw.split("```")[-2].strip() if "```" in raw else raw
    try:
        queries = ast.literal_eval(raw)
        if isinstance(queries, list):
            return queries
    except Exception as e:
        print(f"[ERROR] Could not parse AI queries: {e}")
    # Fallback: just use the original question
    return [user_question]


def clean_and_split_chunks(chunks, max_length=8000):
    """
    Remove empty chunks and split any chunk longer than max_length into smaller pieces.
    """
    cleaned = []
    for chunk in chunks:
        text = chunk["text"].strip()
        if not text:
            continue
        if len(text) <= max_length:
            cleaned.append(chunk)
        else:
            # Split long chunk into smaller subchunks
            for i in range(0, len(text), max_length):
                subtext = text[i:i + max_length]
                cleaned.append({
                    "section": chunk["section"] + f" (part {i // max_length + 1})",
                    "text": subtext,
                    "page": chunk.get("page", 1)
                })
    return cleaned


def clean_chunks_remove_duplicates_and_boilerplate(chunks, boilerplate_patterns=None):
    """
    Remove duplicate and boilerplate chunks.
    """
    if boilerplate_patterns is None:
        boilerplate_patterns = [
            r"electronically signed by",
            r"dictated by",
            r"this note was generated by",
            r"page \d+ of \d+",
            r"^date[:\s]",  # lines starting with 'Date:'
            r"^time[:\s]",  # lines starting with 'Time:'
            r"^signed[:\s]",  # lines starting with 'Signed:'
            r"for official use only \(fouo\)",
            r"disclaimer:.*the information contained in this document may contain privileged and confidential information including patient information protected by federal and state privacy laws\.",
            # Add more as needed
        ]
    seen = set()
    cleaned = []
    for chunk in chunks:
        text = chunk["text"].strip().lower()
        if not text or text in seen:
            continue
        if any(re.search(pat, text) for pat in boilerplate_patterns):
            continue
        cleaned.append(chunk)
        seen.add(text)
    return cleaned


def remove_boilerplate_phrases(text, boilerplate_patterns=None):
    """
    Remove boilerplate phrases from within a text chunk.
    """
    if boilerplate_patterns is None:
        boilerplate_patterns = [
            r"for official use only \(fouo\)",
            r'disclaimer:.*the information contained in this document may contain privileged and confidential information including patient information protected by federal and state privacy laws\.',
            r"electronically signed by",
            r"dictated by",
            r"this note was generated by",
            r"page \d+ of \d+",
            r"^date[:\s].*?$",  # lines starting with 'Date:'
            r"^time[:\s].*?$",  # lines starting with 'Time:'
            r"^signed[:\s].*?$",  # lines starting with 'Signed:'
            # Add more as needed
        ]
    cleaned = text
    for pat in boilerplate_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE | re.MULTILINE)
    return cleaned.strip()


def get_embeddings_batched(client, deploy_embed, texts, batch_size=300):
    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
        batch = texts[i:i + batch_size]
        try:
            response = client.embeddings.create(
                input=batch,
                model=deploy_embed
            )
            # Ensure float32 for FAISS compatibility
            embeddings.extend([np.array(d.embedding, dtype=np.float32) for d in response.data])
        except Exception as e:
            print(f"[ERROR] Embedding batch {i // batch_size + 1} failed: {e}")
    return np.vstack(embeddings) if embeddings else np.empty((0,))


def build_inverted_index(chunks):
    index = defaultdict(set)
    for i, chunk in enumerate(chunks):
        words = set(re.findall(r'\b\w+\b', chunk['text'].lower()))
        for word in words:
            index[word].add(i)
    return index


def build_faiss_index(vectors):
    """Build a FAISS inner-product (cosine via L2-normalized vectors) index. Returns (index, normalized_vectors).
    vectors: np.ndarray shape (N, dim) dtype float32.
    """
    if not FAISS_AVAILABLE:
        raise RuntimeError("FAISS not available; cannot build index")
    if vectors.dtype != np.float32:
        vectors = vectors.astype(np.float32)
    # Normalize for cosine similarity via inner product
    faiss.normalize_L2(vectors)
    dim = vectors.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vectors)
    return index, vectors  # normalized vectors returned


# --- Tokenization / ngrams -------------------------------------------------

def _tokenize(text):
    return re.findall(r"\b[\w'-]+\b", (text or '').lower())

def _bigrams(tokens):
    return [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens)-1)]

# --- BM25 ------------------------------------------------------------------

def build_bm25_index(chunks, use_bigrams=True, k1=1.5, b=0.75):
    """Build a lightweight BM25 index for chunks.
    Returns a dict with postings, doc_len, avgdl, k1, b, and flags.
    """
    postings = defaultdict(lambda: defaultdict(int))  # term -> {doc_id: tf}
    doc_len = []
    for i, ch in enumerate(chunks):
        toks = _tokenize(ch.get('text'))
        if use_bigrams:
            toks = toks + _bigrams(toks)
        doc_len.append(len(toks))
        for t in toks:
            postings[t][i] += 1
    N = len(chunks) if chunks else 0
    df = {t: len(docs) for t, docs in postings.items()}
    avgdl = (sum(doc_len) / N) if N else 0.0
    return {
        'postings': postings,
        'df': df,
        'N': N,
        'doc_len': doc_len,
        'avgdl': avgdl,
        'k1': float(k1),
        'b': float(b),
        'use_bigrams': bool(use_bigrams)
    }

def bm25_score_query(query, bm25):
    if not bm25 or not query:
        return {}
    toks = _tokenize(query)
    if bm25.get('use_bigrams'):
        toks = toks + _bigrams(toks)
    N = bm25['N'] or 1
    avgdl = bm25['avgdl'] or 1.0
    k1 = bm25['k1']
    b = bm25['b']
    df = bm25['df']
    postings = bm25['postings']
    doc_len = bm25['doc_len']
    scores = defaultdict(float)
    # Unique query terms to avoid overweighting duplicates
    for t in set(toks):
        n_qi = df.get(t, 0)
        if n_qi == 0:
            continue
        idf = max(0.0, math.log(((N - n_qi + 0.5) / (n_qi + 0.5)) + 1e-9))
        for doc_id, tf in postings.get(t, {}).items():
            dl = doc_len[doc_id] or 1
            denom = tf + k1 * (1 - b + b * (dl / avgdl))
            scores[doc_id] += idf * ((tf * (k1 + 1)) / denom)
    return scores  # dict doc_id -> score


def hybrid_search(client, deploy_embed, query, chunks, vectors, inverted_index, top_k=20, semantic_ratio=0.75, faiss_index=None, normalized_vectors=None, semantic_exclude_indices=None, bm25_index=None, section_boosts=None, per_note_cap=2):
    """Hybrid keyword + semantic search with BM25 if available.
    Combines z-normalized BM25 and cosine scores; applies optional section boosts; enforces note diversity.
    """
    if semantic_exclude_indices is None:
        semantic_exclude_indices = set()
    if section_boosts is None:
        section_boosts = {
            'assessment_plan': 0.15,
            'history_present_illness': 0.12,
            'subjective': 0.10,
            'hospital_course': 0.08,
        }

    # --- Keyword/BM25 ---
    bm25_scores = {}
    if bm25_index is not None:
        bm25_scores = bm25_score_query(query, bm25_index)
        keyword_doc_ids = set(bm25_scores.keys())
    else:
        # Fallback: boolean keyword hits using inverted index
        STOPWORDS = set([
            'find','patient','how','where','when','why','who','what','which','the','and','for','or','any','of','to','in','on','with','a','an','by','at','as','is','are','was','were','be','has','have','had','that','this','these','those','from','it','but','not',
            # clinical fillers
            'mg','mcg','po','iv','im','bid','tid','qid','qhs','prn','pm','am'
        ])
        words = set(re.findall(r'\b\w+\b', query.lower())) - STOPWORDS
        keyword_hits = set()
        for word in words:
            keyword_hits.update(inverted_index.get(word, set()))
        keyword_doc_ids = set(keyword_hits)

    # --- Semantic ---
    # Get k candidates for semantic side
    if FAISS_AVAILABLE and faiss_index is not None and normalized_vectors is not None:
        qvec = get_embeddings_batched(client, deploy_embed, [query])
        if qvec.ndim == 1:
            qvec = qvec.reshape(1, -1)
        q = qvec.astype(np.float32)
        try:
            import faiss as _fa
            _fa.normalize_L2(q)
        except Exception:
            pass
        k = min(max(top_k*3, top_k), len(chunks))
        try:
            _, I = faiss_index.search(q, k)
            semantic_indices = [i for i in I[0].tolist() if i not in semantic_exclude_indices]
        except Exception as e:
            # Fallback to brute if FAISS fails
            vecs = vectors.astype(np.float32)
            qn = q[0] / (np.linalg.norm(q[0]) + 1e-8)
            vn = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8)
            sims = vn @ qn
            ordered = sims.argsort()[::-1].tolist()
            semantic_indices = [i for i in ordered if i not in semantic_exclude_indices][:min(k, len(vectors))]
            cosine_scores = sims
    else:
        # Non-FAISS path
        qvec = get_embeddings_batched(client, deploy_embed, [query])
        if qvec.ndim == 1:
            qvec = qvec.reshape(1, -1)
        vecs = vectors.astype(np.float32)
        q = qvec[0].astype(np.float32)
        qn = q / (np.linalg.norm(q) + 1e-8)
        vn = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-8)
        sims = vn @ qn
        ordered = sims.argsort()[::-1].tolist()
        k = min(max(top_k*3, top_k), len(vectors))
        semantic_indices = [i for i in ordered if i not in semantic_exclude_indices][:k]
        cosine_scores = sims

    # Compute cosine scores if not set (FAISS branch without fallback)
    if 'cosine_scores' not in locals():
        # Recompute cosine scores for ranking transparency
        qvec2 = get_embeddings_batched(client, deploy_embed, [query])
        if qvec2.ndim == 1:
            qvec2 = qvec2.reshape(1, -1)
        q2 = qvec2[0].astype(np.float32)
        vn = (vectors.astype(np.float32)) / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-8)
        qn2 = q2 / (np.linalg.norm(q2) + 1e-8)
        cosine_scores = vn @ qn2

    # --- Score fusion ---
    # Gather candidate doc ids: union of semantic and keyword
    cand_ids = set(semantic_indices)
    cand_ids.update(keyword_doc_ids)
    if not cand_ids:
        return []

    # z-normalize helpers
    def z_norm(vals):
        if not vals:
            return {}
        arr = np.array(list(vals.values()), dtype=np.float32)
        mu, sigma = float(arr.mean()), float(arr.std() + 1e-6)
        return {k: (v - mu) / sigma for k, v in vals.items()}

    # Collect per-doc scores for candidates
    cos_map = {i: float(cosine_scores[i]) for i in cand_ids}
    bm_map = {i: float(bm25_scores.get(i, 0.0)) for i in cand_ids}
    cos_z = z_norm(cos_map)
    bm_z = z_norm(bm_map) if any(v > 0 for v in bm_map.values()) else {i: 0.0 for i in cand_ids}

    w_sem, w_kw = 0.65, 0.35
    w_rec = 0.08  # mild recency weight
    now = datetime.now(timezone.utc)
    combined = {}
    for i in cand_ids:
        base = w_sem * cos_z.get(i, 0.0) + w_kw * bm_z.get(i, 0.0)
        # section boost
        sec = (chunks[i].get('section') or '').lower()
        boost = 0.0
        if sec in section_boosts:
            boost += section_boosts[sec]
        # recency boost (decays with age in years)
        dt = _parse_any_date(chunks[i].get('date'))
        if dt:
            if not dt.tzinfo:  # assume UTC if naive
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
            recency = math.exp(-age_days / 365.0)  # ~0.37 at 1 year
            boost += w_rec * recency
        combined[i] = base + boost

    # Rank by combined and enforce per-note diversity
    # Map chunk index -> note_id (fallback to chunk_id when missing)
    note_map = [str(c.get('note_id') or c.get('chunk_id') or idx) for idx, c in enumerate(chunks)]
    per_note_counts = defaultdict(int)
    ordered_ids = sorted(combined.keys(), key=lambda x: combined[x], reverse=True)
    results = []
    for i in ordered_ids:
        nid = note_map[i]
        if per_note_counts[nid] >= max(1, int(per_note_cap)):
            continue
        results.append(chunks[i])
        per_note_counts[nid] += 1
        if len(results) >= top_k:
            break

    return results


def postprocess_citations_excerpt_only(answer, chunks):
    """
    Replace any (Page N), (Pages N,M,...), or ambiguous citations with (Excerpt N) using chunk metadata.
    Also replaces (Unknown Page) with (Unknown Excerpt).
    """
    # Replace (Page N) and (Pages N,M,...)
    answer = re.sub(r"\(Page (\d+)\)", r"(Excerpt \1)", answer)
    answer = re.sub(r"\(Pages ([\d, ]+)\)", r"(Excerpts \1)", answer)
    # Replace (Unknown Page)
    answer = re.sub(r"\(Unknown Page\)", "(Unknown Excerpt)", answer)
    # Replace any remaining lowercase variants
    answer = re.sub(r"\(page (\d+)\)", r"(Excerpt \1)", answer)
    answer = re.sub(r"\(pages ([\d, ]+)\)", r"(Excerpts \1)", answer)
    answer = re.sub(r"\(unknown page\)", "(Unknown Excerpt)", answer)
    return answer


def ask_gpt(client, deploy_chat, top_chunks, query=None, qa_history=None):
    # Build conversation context with explicit page for each chunk
    history_str = ""
    if qa_history:
        for i, qa in enumerate(qa_history):
            history_str += f"Previous Q{i+1}: {qa['question']}\nA{i+1}: {qa['answer']}\n"
    context = "\n\n".join([
        (f"### Source: (Excerpt {c.get('page','?')}, Date: {c.get('date')})\n{c['text']}" if c.get('date') else f"### Source: (Excerpt {c.get('page','?')})\n{c['text']}")
        for c in top_chunks
    ])
    citation_instruction = (
        "\n\nIMPORTANT: For every fact or statement, include a parenthetical citation in the format (Excerpt N). "
        "Always include the source date next to time-sensitive facts (e.g., meds, diagnoses): write “as of MM-DD-YYYY” when available. "
        "Treat mentions older than 12 months as historical unless corroborated by newer evidence; avoid using “currently” unless supported by a note within the past 6 months. "
        "Prefer the most recent evidence when summarizing conflicting information.\n"
    )
    if query:
        prompt = f"""You are a clinical assistant. Given the medical record segments below, answer the following question. Use the previous questions and answers for context if relevant.{citation_instruction}\nQuestion: \"{query}\"\n\nBelow are excerpts from the medical chart that can be used in answering the query:\n{history_str}{context}\n"""
    else:
        prompt = f"""You are a clinical assistant. Given the medical record segments below, write a concise narrative summary of the patient's active medical problems, treatments, and complications. Use the previous questions and answers for context if relevant.{citation_instruction}\n{history_str}{context}\n"""

    print("\n==== PROMPT SENT TO OPENAI ====\n")
    print(prompt)
    print("\n==== END PROMPT ====\n")

    try:
        response = client.chat.completions.create(
            model=deploy_chat,
            messages=[
                {"role": "system", "content": "You are a clinical reasoning assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        answer = response.choices[0].message.content
        # --- Post-process: replace any Window N, offsets, or ambiguous citations with (Excerpt N) ---
        answer = postprocess_citations_excerpt_only(answer, top_chunks)
        return answer
    except Exception as e:
        print(f"[ERROR] GPT call failed: {e}")
        return None


def postprocess_citations_page_only(answer, chunks):
    """
    Replace citations like (Window N) with the corresponding (Page N) using chunk metadata.
    Also normalizes any variants like (page N, Offset K) -> (Page N).
    """
    section_map = {c.get('section'): c.get('page', '?') for c in chunks}

    def repl(match):
        inner = match.group(1)
        # Window N -> Page <mapped>
        m = re.match(r"Window\s+(\d+)", inner, re.IGNORECASE)
        if m:
            sec = f"Window {m.group(1)}"
            page = section_map.get(sec, '?')
            return f"(Page {page})"
        # page n, optional offset -> Page n
        m2 = re.match(r"[Pp]age\s+(\d+)(?:,\s*Offset\s*\d+)?", inner)
        if m2:
            return f"(Page {m2.group(1)})"
        return f"({inner})"

    return re.sub(r"\(([^)]+)\)", repl, answer)


def tag_chunk_with_datetime(chunk):
    """
    Extracts date and time from chunk text if present and tags the chunk.
    """
    # Simple regex for common date and time formats
    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', chunk["text"])
    time_match = re.search(r'(\d{1,2}:\d{2}(?:\s*[APMapm]{2})?)', chunk["text"])
    if date_match:
        chunk["date"] = date_match.group(1)
    if time_match:
        chunk["time"] = time_match.group(1)
    return chunk


def sentence_density_score(chunk):
    """
    Returns the number of sentences in the chunk as a proxy for narrative density.
    """
    # Count sentences using period, exclamation, or question mark as end
    sentences = re.split(r'[.!?]', chunk['text'])
    return sum(1 for s in sentences if s.strip())


def _parse_any_date(s: str):
    if not s: return None
    s = str(s).strip()
    try:
        # Handle Z suffix
        if s.endswith('Z'):
            return datetime.fromisoformat(s.replace('Z', '+00:00'))
        return datetime.fromisoformat(s)
    except Exception:
        for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y'):
            try: return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            except Exception: pass
    return None
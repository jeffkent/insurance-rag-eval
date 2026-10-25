"""Shared helpers: config, DB connection, text extraction, Ollama calls."""
import glob, os, re, time
from html.parser import HTMLParser

import psycopg
import requests
import logging
logging.disable(logging.WARNING)

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")
DSN = os.environ.get("RAG_DSN", "host=127.0.0.1 port=5544 user=rag dbname=ragdemo")
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
GEN_MODEL = os.environ.get("GEN_MODEL", "glm-5.3:cloud")
CONFIGS = {"A": {"size": 1200, "overlap": 0}, "B": {"size": 600, "overlap": 100}}


def connect():
    return psycopg.connect(DSN, autocommit=True)


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form"}
    BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "tr", "section", "article"}

    def __init__(self):
        super().__init__()
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def clean(t):
    t = t.replace("\x00", "")
    t = re.sub(r"[ \t\r\f\v]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


def extract_pages(path):
    """Return list of (page_number, text). HTML files count as one page (page 1)."""
    if path.endswith(".pdf"):
        import pypdf
        r = pypdf.PdfReader(path)
        return [(i + 1, clean(p.extract_text() or "")) for i, p in enumerate(r.pages)]
    raw = open(path, encoding="utf-8", errors="replace").read()
    p = _Text()
    p.feed(raw)
    return [(1, clean("".join(p.out)))]


def doc_files():
    return sorted(glob.glob(os.path.join(DOCS, "*.pdf")) + glob.glob(os.path.join(DOCS, "*.html")))


def chunk_text(text, size, overlap):
    """Split on whitespace boundaries near `size` chars; overlap in chars."""
    text = re.sub(r"\s+", " ", text).strip()
    out, i = [], 0
    while i < len(text):
        end = min(i + size, len(text))
        if end < len(text):
            sp = text.rfind(" ", i + size // 2, end)
            if sp > 0:
                end = sp
        piece = text[i:end].strip()
        if len(piece) > 40:
            out.append(piece)
        if end >= len(text):
            break
        nxt = end - overlap if overlap else end
        i = max(nxt, i + 1)
        if overlap:
            sp = text.find(" ", i)
            i = sp + 1 if 0 <= sp < end else i
    return out


def embed(texts, prefix):
    """Embed a list of strings with the nomic prefix. Returns (vectors, prompt_tokens)."""
    r = requests.post(f"{OLLAMA}/api/embed", json={
        "model": EMBED_MODEL, "input": [prefix + t for t in texts], "truncate": True}, timeout=300)
    r.raise_for_status()
    j = r.json()
    return j["embeddings"], j.get("prompt_eval_count", 0)


def vec_literal(v):
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"

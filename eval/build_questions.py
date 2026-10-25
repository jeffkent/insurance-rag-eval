"""Builds eval/questions.jsonl. The builder (Claude) wrote these questions after reading the
documents. Each answerable question carries a verbatim `anchor` phrase; this script finds every
page of the expected document that contains the anchor, so page numbers are looked up in the
extracted text and never typed by hand. Page numbers are PDF page indexes (1 = first page of the
file), not printed page labels. HTML documents are a single page (1).
Run: .venv/bin/python -I eval/build_questions.py"""
import json, os, re, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import common

N, CO, OP, PR = "nydfs_cl7.html", "co_reg_10-1-1_amended.pdf", "eiopa_ai_opinion_2025.pdf", "eiopa_ai_principles_2021.pdf"
DG, GA, FS, BS = "eiopa_digitalisation_report.pdf", "eiopa_genai_survey_2025.pdf", "boe_fsif_ai_2025.pdf", "boe_fca_ai_survey_2024.html"
Q = [
 (CO, "When did the amended Colorado Regulation 10-1-1 become effective?", "shall become effective on October 15, 2025"),
 (CO, "What must a life insurer's annual Colorado compliance report say about the people responsible for compliance?", "title and qualifications of each individual responsible"),
 (CO, "What is the maximum length of the compliance report under Colorado Regulation 10-1-1?", "no more than ten (10) pages"),
 (CO, "What must an insurer that does not use ECDIS file with the Colorado Division of Insurance?", "attestation signed by an officer indicating that the insurer does not use ECDIS"),
 (CO, "For health benefit plan insurers, is an individual's medical record counted as ECDIS under the Colorado regulation?", "ECDIS does not include an individual"),
 (OP, "Which insurance uses of AI does the EU AI Act classify as high-risk, according to EIOPA's 2025 Opinion?", "risk assessment and pricing in relation to natural persons in the case"),
 (OP, "What areas should insurers cover in their AI governance and risk management systems under the EIOPA Opinion?", "Accuracy, robustness and cybersecurity"),
 (OP, "What records does the EIOPA Opinion say undertakings should keep so that AI models can be reproduced and traced?", "records of the training and testing data and the modelling methodologies"),
 (OP, "Which two techniques does the EIOPA Opinion name as examples for explaining AI outputs?", "LIME (Local Interpretable Model-Agnostic Explanations)"),
 (N,  "How often should the board or senior management review and approve AI and external data policies under NYDFS Circular Letter No. 7?", "review and approve the insurer"),
 (PR, "What does EIOPA's 2021 principle of proportionality ask insurance firms to do?", "proportionate to the potential impact of a specific AI use case"),
 (GA, "How many insurance undertakings answered EIOPA's 2025 generative AI survey?", "347 insurance undertakings"),
 (GA, "What share of generative AI use cases reported to EIOPA are internal back-office applications?", "64% of the reported use cases are for internal"),
 (DG, "What share of non-life and life insurers use AI, according to EIOPA's 2024 digitalisation report?", "AI is used by 50% of the respondents in non-life"),
 (BS, "What share of firms said they only partly understand the AI technologies they use in the Bank of England and FCA 2024 survey?", "46% of respondent firms reported having only"),
 (FS, "Which risk was cited as the top risk in recent IMF outreach on wider adoption of generative AI in capital markets?", "Herding and market concentration was the top risk"),
 (BS, "How much of the cloud, model and data provider markets do the top three third-party providers hold, per the Bank of England and FCA 2024 survey?", "The top three third-party providers account for 73%"),
]
REFUSE = [
 "What dollar amount of civil penalty per violation does Colorado Regulation 10-1-1 set?",
 "What must insurers include in the written AIS Program required by the NAIC Model Bulletin on artificial intelligence?",
 "What is the maximum fine, as a percentage of worldwide turnover, under the EU AI Act for breaching high-risk requirements?",
]
norm = lambda s: re.sub(r"\s+", "", s).lower()
cache = {}
def pages(doc):
    if doc not in cache:
        cache[doc] = common.extract_pages(os.path.join(common.DOCS, doc))
    return cache[doc]
out = []
for i, (doc, q, anchor) in enumerate(Q, 1):
    pg = [p for p, t in pages(doc) if norm(anchor) in norm(t)]
    assert pg, (doc, anchor)
    out.append({"id": f"q{i:02d}", "question": q, "expected_doc": doc, "expected_pages": pg, "anchor": anchor, "answerable": True})
for j, q in enumerate(REFUSE, len(Q) + 1):
    out.append({"id": f"q{j:02d}", "question": q, "expected_doc": None, "expected_pages": [], "anchor": None, "answerable": False})
with open(os.path.join(HERE, "eval", "questions.jsonl"), "w") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
for r in out: print(r["id"], r["expected_doc"], r["expected_pages"])

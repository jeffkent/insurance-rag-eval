#!/usr/bin/env bash
# Download the 9 regulator documents listed in docs/SOURCES.md into docs/.
# The documents are not stored in this repo; each stays under its publisher's terms.
set -euo pipefail
cd "$(dirname "$0")/docs"
UA="Mozilla/5.0 (insurance-rag-eval; research)"
get() { echo "fetching $1"; curl -fsSL -A "$UA" -o "$1" "$2"; }
get nydfs_cl7.html "https://www.dfs.ny.gov/industry-guidance/circular-letters/cl2024-07"
get co_reg_10-1-1_amended.pdf "https://doi.colorado.gov/sites/doi/files/documents/Amended%20Regulation%2010-1-1.pdf"
get eiopa_ai_opinion_2025.pdf "https://www.eiopa.europa.eu/document/download/88342342-a17f-4f88-842f-bf62c93012d6_en?filename=OpiniononArtificialIntelligencegovernanceandriskmanagement.pdf"
get eiopa_ai_principles_2021.pdf "https://www.eiopa.europa.eu/system/files/2021-06/eiopa-ai-governance-principles-june-2021.pdf"
get eiopa_digitalisation_report.pdf "https://www.eiopa.europa.eu/document/download/6ca9e171-42b9-44d7-a2e6-beaf0134ecb8_en?filename=Report+on+the+digitalisation+of+the+European+insurance+sector.pdf"
get eiopa_genai_survey_2025.pdf "https://www.eiopa.europa.eu/document/download/bec886e2-dea0-4bbe-9624-d5f23f85700a_en?filename=EIOPA-BoS-25-679-GenAI-Report.pdf"
get boe_fsif_ai_2025.pdf "https://www.bankofengland.co.uk/-/media/boe/files/financial-stability-in-focus/2025/financial-stability-in-focus-artificial-intelligence-in-the-financial-system.pdf"
get boe_fca_ai_survey_2024.html "https://www.bankofengland.co.uk/report/2024/artificial-intelligence-in-uk-financial-services-2024"
get fca_ai_research_note.html "https://www.fca.org.uk/publications/research-notes/ai-uk-financial-services"
echo "done: $(ls *.pdf *.html | wc -l | tr -d ' ') files"

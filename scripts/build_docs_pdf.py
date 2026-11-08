#!/usr/bin/env python3
"""JobPilot Enterprise Documentation PDF Generator.

Builds individual A4 PDFs for all six core documents and compiles a master
consolidated document `Job-Pilot-Complete-Documentation.pdf`.
"""

import os
import re
import json
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright
import pypdf

ROOT = Path("/home/ahmad10raza/Documents/Mastering/JobPilot")
DOCS_DIR = ROOT / "docs"
SOURCE_DIR = DOCS_DIR / "source"
OUTPUT_DIR = DOCS_DIR / "output"
TOOLS_DIR = DOCS_DIR / "tools"
ASSETS_DIR = DOCS_DIR / "assets"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Document Registry & Metadata
DOCUMENTS = [
    {
        "id": "JOBPILOT-DOC-01-PRD",
        "file": "01-PRD.md",
        "out_pdf": "01-PRD.pdf",
        "title": "01 — Product Requirements Document (PRD)",
        "subtitle": "Comprehensive functional, non-functional, user story, and business rule specifications for the JobPilot Autonomous Candidate Platform.",
        "badge": "Product Requirements Specification",
        "version": "v0.1.0-beta.1 (PROD)",
        "date": "November 2026",
    },
    {
        "id": "JOBPILOT-DOC-02-TRD",
        "file": "02-TRD.md",
        "out_pdf": "02-TRD.pdf",
        "title": "02 — Technical Requirements Document (TRD)",
        "subtitle": "Engineering architecture, PySide6 desktop MVVM runtime, 24 domain services, ATS finite-state machine, and Q&A provenance engine.",
        "badge": "System Architecture Specification",
        "version": "v0.1.0-beta.1 (PROD)",
        "date": "November 2026",
    },
    {
        "id": "JOBPILOT-DOC-03-FLOW",
        "file": "03-App-Flow.md",
        "out_pdf": "03-App-Flow.pdf",
        "title": "03 — Application Flow & State Machines",
        "subtitle": "End-to-end candidate lifecycle, multi-platform apply sequence diagrams, 5-tier Q&A routing, and fail-closed error recovery protocols.",
        "badge": "Operational Flow Specification",
        "version": "v0.1.0-beta.1 (PROD)",
        "date": "November 2026",
    },
    {
        "id": "JOBPILOT-DOC-04-UIUX",
        "file": "04-UI-UX-Design-Brief.md",
        "out_pdf": "04-UI-UX-Design-Brief.pdf",
        "title": "04 — UI/UX Design Brief & Screen Inventory",
        "subtitle": "Design tokens, color semantics, typography hierarchy, PySide6 component specifications, and complete 15-tab widescreen UI inventory.",
        "badge": "Design System & UI Inventory",
        "version": "v0.1.0-beta.1 (PROD)",
        "date": "November 2026",
    },
    {
        "id": "JOBPILOT-DOC-05-SCHEMA",
        "file": "05-Backend-Schema.md",
        "out_pdf": "05-Backend-Schema.pdf",
        "title": "05 — Database Architecture & Schema Specification",
        "subtitle": "SQLite 3 WAL engine tuning, complete schema specifications for 16 SQLAlchemy models, SHA-256 fingerprinting, and relational ERD.",
        "badge": "Database Engineering Specification",
        "version": "v0.1.0-beta.1 (PROD)",
        "date": "November 2026",
    },
    {
        "id": "JOBPILOT-DOC-06-PLAN",
        "file": "06-Implementation-Plan.md",
        "out_pdf": "06-Implementation-Plan.pdf",
        "title": "06 — Implementation Plan & Roadmap",
        "subtitle": "Implementation reality audit, technical debt assessment, work breakdown structure (WBS), risk matrix, and 4-milestone release plan.",
        "badge": "Engineering Roadmap & Strategy",
        "version": "v0.1.0-beta.1 (PROD)",
        "date": "November 2026",
    },
]

# Load Marked and Mermaid libraries
with open(TOOLS_DIR / "marked.min.js", "r", encoding="utf-8") as f:
    marked_js = f.read()

with open(TOOLS_DIR / "mermaid.min.js", "r", encoding="utf-8") as f:
    mermaid_js = f.read()

# Load Splash Icon as high-res clean transparent brand asset
splash_path = ASSETS_DIR / "jobpilot_splash.png"
if not splash_path.exists():
    splash_path = ASSETS_DIR / "jobpilot-symbol-color.png"

with open(splash_path, "rb") as f:
    splash_b64 = "data:image/png;base64," + base64.b64encode(f.read()).decode("utf-8")

# Cache image base64 encodings for markdown replacement
image_b64_map = {}
for img in ASSETS_DIR.glob("*.png"):
    with open(img, "rb") as f:
        image_b64_map[img.name] = "data:image/png;base64," + base64.b64encode(f.read()).decode("utf-8")

def build_html_for_doc(doc: dict) -> str:
    md_file_path = SOURCE_DIR / doc["file"]
    with open(md_file_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # Replace image paths with base64 data URIs
    for img_name, b64_str in image_b64_map.items():
        md_text = md_text.replace(f"docs/assets/{img_name}", b64_str)
        md_text = md_text.replace(f"assets/{img_name}", b64_str)
        md_text = md_text.replace(f"({img_name})", f"({b64_str})")

    # Extract headings for Table of Contents
    toc_items = []
    for line in md_text.splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            heading_text = line[3:].strip()
            anchor = re.sub(r"[^a-zA-Z0-9\s-]", "", heading_text).strip().lower().replace(" ", "-")
            toc_items.append((heading_text, anchor))

    toc_html = "<div class='toc-box'><h3>Table of Contents</h3><ul class='toc-list'>"
    for h_text, anchor in toc_items:
        toc_html += f"<li><span class='toc-title'>{h_text}</span></li>"
    toc_html += "</ul></div>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{doc["title"]}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

  @page {{
    size: A4;
    margin: 20mm 14mm 20mm 14mm;
  }}

  * {{
    box-sizing: border-box;
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }}

  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 9.5pt;
    line-height: 1.55;
    color: #1e293b;
    background-color: #ffffff;
    margin: 0;
    padding: 0;
  }}

  /* Cover Page */
  .cover-page {{
    page-break-after: always;
    height: 92vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 44px 32px;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #ffffff;
    border-radius: 12px;
  }}

  .cover-header {{
    display: flex;
    align-items: center;
    gap: 22px;
  }}

  .cover-logo {{
    height: 92px;
    width: 92px;
    object-fit: contain;
    filter: drop-shadow(0 10px 24px rgba(0, 0, 0, 0.45));
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    margin: 0 !important;
    padding: 0 !important;
  }}

  .cover-brand-block {{
    display: flex;
    flex-direction: column;
  }}

  .cover-brand-title {{
    font-size: 26pt;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #ffffff;
    margin: 0;
  }}

  .cover-brand-sub {{
    font-size: 10.5pt;
    color: #0ea5e9;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin: 4px 0 0 0;
  }}

  .cover-body {{
    margin: 40px 0;
  }}

  .doc-badge {{
    display: inline-block;
    padding: 6px 14px;
    background-color: rgba(255, 95, 21, 0.2);
    border: 1px solid #ff5f15;
    color: #ff8c42;
    border-radius: 6px;
    font-size: 8.5pt;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 18px;
  }}

  .doc-main-title {{
    font-size: 27pt;
    font-weight: 800;
    line-height: 1.25;
    color: #ffffff;
    margin: 0 0 16px 0;
  }}

  .doc-subtitle {{
    font-size: 12.5pt;
    color: #94a3b8;
    max-width: 650px;
    line-height: 1.5;
    margin: 0;
  }}

  .cover-footer {{
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    padding-top: 20px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
  }}

  .meta-item {{
    font-size: 8.5pt;
  }}

  .meta-label {{
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 600;
    margin-bottom: 4px;
  }}

  .meta-value {{
    color: #f8fafc;
    font-weight: 600;
    font-size: 9.5pt;
  }}

  /* Table of Contents */
  .toc-box {{
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 4px solid #0ea5e9;
    border-radius: 8px;
    padding: 14px 20px;
    margin: 16px 0 24px 0;
    page-break-after: avoid;
  }}

  .toc-box h3 {{
    margin: 0 0 10px 0;
    color: #0f172a;
    font-size: 11pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}

  .toc-list {{
    list-style-type: none;
    padding-left: 0;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 6px 20px;
  }}

  .toc-list li {{
    font-size: 8.5pt;
    color: #334155;
    position: relative;
    padding-left: 12px;
  }}

  .toc-list li::before {{
    content: "•";
    color: #ff5f15;
    position: absolute;
    left: 0;
    font-size: 12pt;
    line-height: 8pt;
  }}

  /* Content Headings */
  h1 {{
    font-size: 18pt;
    font-weight: 800;
    color: #0f172a;
    border-bottom: 2px solid #ff5f15;
    padding-bottom: 6px;
    margin-top: 24px;
    margin-bottom: 12px;
    page-break-after: avoid;
  }}

  h2 {{
    font-size: 13pt;
    font-weight: 700;
    color: #1e293b;
    border-left: 4px solid #0ea5e9;
    padding-left: 10px;
    margin-top: 20px;
    margin-bottom: 10px;
    page-break-after: avoid;
  }}

  h3 {{
    font-size: 10.5pt;
    font-weight: 600;
    color: #334155;
    margin-top: 14px;
    margin-bottom: 8px;
    page-break-after: avoid;
  }}

  p, li {{
    font-size: 9pt;
    color: #334155;
    line-height: 1.55;
  }}

  ul, ol {{
    padding-left: 18px;
    margin-bottom: 12px;
  }}

  li {{
    margin-bottom: 4px;
  }}

  hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 22px 0;
  }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 14px 0;
    font-size: 8.5pt;
    page-break-inside: avoid;
  }}

  th {{
    background-color: #0f172a;
    color: #f8fafc;
    font-weight: 600;
    text-align: left;
    padding: 8px 10px;
    border: 1px solid #1e293b;
  }}

  td {{
    padding: 7px 10px;
    border: 1px solid #cbd5e1;
    color: #334155;
    vertical-align: top;
  }}

  tr:nth-child(even) td {{
    background-color: #f8fafc;
  }}

  /* Code blocks */
  code {{
    font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
    font-size: 8pt;
    background-color: #f1f5f9;
    color: #0f172a;
    padding: 2px 4px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
  }}

  pre {{
    background-color: #0f172a;
    color: #e2e8f0;
    padding: 10px 12px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 7.8pt;
    line-height: 1.4;
    border: 1px solid #334155;
    page-break-inside: avoid;
  }}

  pre code {{
    background: none;
    border: none;
    color: inherit;
    padding: 0;
  }}

  /* Images / Screenshots */
  img {{
    max-width: 100%;
    max-height: 480px;
    object-fit: contain;
    border-radius: 8px;
    border: 1px solid #cbd5e1;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
    margin: 12px 0 6px 0;
    page-break-inside: avoid;
  }}

  em {{
    font-size: 8pt;
    color: #64748b;
    display: block;
    margin-top: -4px;
    margin-bottom: 14px;
  }}

  /* Mermaid Diagrams */
  .mermaid {{
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 14px;
    margin: 12px 0 16px 0;
    max-height: 480px;
    overflow: hidden;
  }}

  .mermaid svg {{
    max-width: 100% !important;
    max-height: 440px !important;
    height: auto !important;
  }}
</style>
</head>
<body>

<div class="cover-page">
  <div class="cover-header">
    <img src="{splash_b64}" class="cover-logo" alt="JobPilot Logo" />
    <div class="cover-brand-block">
      <div class="cover-brand-title">JobPilot</div>
      <div class="cover-brand-sub">Autonomous Career Navigation</div>
    </div>
  </div>

  <div class="cover-body">
    <div class="doc-badge">{doc["badge"]}</div>
    <div class="doc-main-title">{doc["title"]}</div>
    <div class="doc-subtitle">{doc["subtitle"]}</div>
  </div>

  <div class="cover-footer">
    <div class="meta-item">
      <div class="meta-label">Document ID</div>
      <div class="meta-value">{doc["id"]}</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Classification</div>
      <div class="meta-value">Proprietary / Engineering</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Target Release</div>
      <div class="meta-value">{doc["version"]}</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Published</div>
      <div class="meta-value">{doc["date"]}</div>
    </div>
  </div>
</div>

{toc_html}

<div class="content-container" id="content"></div>

<script>
{marked_js}
</script>
<script>
{mermaid_js}
mermaid.initialize({{
  startOnLoad: false,
  theme: 'neutral',
  securityLevel: 'loose',
  flowchart: {{ useMaxWidth: true, htmlLabels: true }},
  sequence: {{ useMaxWidth: true, showSequenceNumbers: true }}
}});

const rawMd = {json.dumps(md_text)};
const parsedHtml = marked.parse(rawMd);
const contentEl = document.getElementById('content');
contentEl.innerHTML = parsedHtml;

// Transform code.language-mermaid into div.mermaid
const codeBlocks = contentEl.querySelectorAll('pre code.language-mermaid');
codeBlocks.forEach((code) => {{
  const pre = code.parentElement;
  const div = document.createElement('div');
  div.className = 'mermaid';
  div.textContent = code.textContent;
  pre.replaceWith(div);
}});

mermaid.run().then(() => {{
  window.MERMAID_READY = true;
}}).catch((err) => {{
  console.error("Mermaid error:", err);
  window.MERMAID_READY = true;
}});
</script>
</body>
</html>"""
    return html

def main():
    print("Starting JobPilot Enterprise Documentation PDF Generation...")
    
    generated_pdfs = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for doc in DOCUMENTS:
            print(f"--> Building {doc['out_pdf']} ({doc['id']})...")
            page = browser.new_page()
            html_content = build_html_for_doc(doc)
            page.set_content(html_content, wait_until="networkidle")
            
            try:
                page.wait_for_function("window.MERMAID_READY === true", timeout=25000)
            except Exception as e:
                print(f"    Warning on Mermaid rendering timeout for {doc['id']}: {e}")
            
            header_html = f"""
            <div style="font-family: -apple-system, sans-serif; font-size: 7.5pt; color: #94a3b8; width: 100%; display: flex; justify-content: space-between; padding: 0 14mm; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px;">
              <span>JobPilot Enterprise Documentation</span>
              <span>{doc['id']} • {doc['title']}</span>
            </div>
            """
            
            footer_html = """
            <div style="font-family: -apple-system, sans-serif; font-size: 7.5pt; color: #94a3b8; width: 100%; display: flex; justify-content: space-between; padding: 0 14mm; border-top: 1px solid #e2e8f0; padding-top: 4px;">
              <span>Confidential & Proprietary • JobPilot Architecture Group</span>
              <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
            </div>
            """
            
            out_file = OUTPUT_DIR / doc["out_pdf"]
            page.pdf(
                path=str(out_file),
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template=header_html,
                footer_template=footer_html,
                margin={"top": "20mm", "bottom": "20mm", "left": "14mm", "right": "14mm"}
            )
            page.close()
            
            reader = pypdf.PdfReader(str(out_file))
            print(f"    [DONE] {doc['out_pdf']}: {len(reader.pages)} pages, {out_file.stat().st_size:,} bytes")
            generated_pdfs.append(out_file)
            
        browser.close()

    # Compile Combined Master PDF
    master_pdf = OUTPUT_DIR / "Job-Pilot-Complete-Documentation.pdf"
    print(f"\n--> Merging {len(generated_pdfs)} documents into master PDF: {master_pdf.name}...")
    
    writer = pypdf.PdfWriter()
    for pdf_path in generated_pdfs:
        writer.append(str(pdf_path))
        
    with open(master_pdf, "wb") as f_out:
        writer.write(f_out)
        
    master_reader = pypdf.PdfReader(str(master_pdf))
    print(f"    [SUCCESS] Master PDF Generated: {len(master_reader.pages)} pages, {master_pdf.stat().st_size:,} bytes")
    print("\nAll deliverables generated in docs/output/ successfully.")

if __name__ == "__main__":
    main()

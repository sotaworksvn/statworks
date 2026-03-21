# ADR-0007: PDF Export with LLM Analysis

**Status:** proposed
**Date:** 2026-03-21
**Last updated:** 2026-03-21

**Chose:** Server-side ReportLab + OpenAI LLM analysis over client-side html2pdf
**Rationale:** The PDF must contain AI-generated analysis that synthesizes the entire work session — this requires server-side access to all history entries and the LLM API. ReportLab provides precise control over layout, fonts (Helvetica ≈ Arial), and table formatting. The server generates the PDF as a binary stream and returns it as a download attachment.

## Pipeline

1. `POST /export-pdf` collects all `HistoryEntry` objects for the user (with optional date range filter)
2. Entry summaries are sent to `gpt-5.4-mini` with a structured prompt requesting: Executive Summary, Chat Analysis, Data Changes, Dashboard Insights, Recommendations
3. ReportLab generates a professional A4 PDF with branded styles (#2D3561 header colors, Helvetica font family)
4. PDF is streamed back as `application/pdf` with `Content-Disposition: attachment`

## Alternatives Considered

- **Client-side html2pdf / jsPDF**: No server roundtrip but cannot access full history or LLM analysis. Limited layout control. Rejected because AI-analyzed report is the core value proposition.
- **Puppeteer / Playwright PDF**: Renders HTML to PDF via headless browser. Higher fidelity but heavy dependency (300MB+ browser binary). Overkill for structured data report.
- **LaTeX**: Highest quality typesetting but adds compilation complexity and large dependency. Rejected for hackathon timeline.

## Consequences

- **Short-term**: Users get a one-click professional PDF report with AI synthesis. Adds `reportlab` (~2MB) to Python dependencies.
- **Long-term**: ReportLab scales well for more complex reports (charts, multi-page, headers/footers). If richer visualizations are needed, Playwright can be reconsidered.
- **Risk**: LLM failure during export. Mitigated by fallback text: "AI analysis unavailable. Raw session data is included below."

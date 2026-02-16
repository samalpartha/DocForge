# DocForge CLI

**Generate polished Release Notes PDFs from GitHub-style release JSON — powered by Foxit APIs.**

One command. One JSON file. One production-ready PDF with watermark, highlighted breaking changes, and optional password protection.

```
docforge generate examples/release.json --out release-notes.pdf
```

---

## The Problem

Dev teams waste time manually formatting release notes into distributable documents. Copy-pasting from GitHub Releases into Word or Google Docs, adding branding, and exporting to PDF is tedious, error-prone, and inconsistent.

## The Solution

DocForge CLI automates the entire workflow:

1. You provide structured release JSON (features, fixes, breaking changes)
2. DocForge generates a templated PDF via the **Foxit Document Generation API**
3. DocForge enhances it with watermarks, security, and flattening via the **Foxit PDF Services API**
4. You get a polished, locked PDF ready for distribution

---

## Architecture

```
┌─────────────────┐         ┌─────────────────────────────────────────────┐
│   docforge CLI  │         │          DocForge Backend (FastAPI)         │
│   (Node.js)     │         │                                            │
│                 │  POST   │  ┌───────────┐   ┌──────────────────────┐  │
│  Read JSON ─────┼────────▶│  │ Validate  │──▶│ Foxit Doc Gen API    │  │
│  Validate       │ /v1/    │  │ Input     │   │ (Word template +     │  │
│  Send to API    │generate │  └───────────┘   │  JSON → base PDF)    │  │
│  Save PDF       │         │                  └──────────┬───────────┘  │
│                 │◀────────┤                             ▼              │
│  Print result   │  PDF    │  ┌──────────────────────────────────────┐  │
└─────────────────┘  bytes  │  │    Foxit PDF Services API            │  │
                            │  │                                      │  │
                            │  │  1. Upload PDF                       │  │
                            │  │  2. Add watermark ("INTERNAL")       │  │
                            │  │  3. Flatten annotations              │  │
                            │  │  4. Password-protect (optional)      │  │
                            │  │  5. Download final PDF               │  │
                            │  └──────────────────────────────────────┘  │
                            └─────────────────────────────────────────────┘
```

---

## Where We Use Each Foxit API

### Foxit Document Generation API

| What | Why |
|------|-----|
| **Generate base PDF** from a Word template + JSON data | Converts structured release data into a professionally formatted PDF with tables, headings, and branding — all driven by a `.docx` template with Foxit's token syntax (`{{ product_name }}`, `{{TableStart:features}}`, etc.) |

- **Endpoint:** `POST {HOST}/document-generation/api/GenerateDocumentBase64`
- **Input:** Base64-encoded Word template + JSON document values
- **Output:** Base64-encoded PDF (synchronous)
- **Code:** [`backend/app/foxit/docgen.py`](backend/app/foxit/docgen.py)

### Foxit PDF Services API

| What | Why |
|------|-----|
| **Upload** the generated PDF | Stage the document for server-side processing |
| **Add watermark** ("INTERNAL" / "DRAFT") | Visually mark documents for internal distribution |
| **Password-protect** the PDF | Prevent unauthorized access to sensitive release info |
| **Flatten** annotations and form fields | Lock down the final document for archival |

- **Base URL:** `{HOST}/pdf-services`
- **Endpoints used:**
  - `POST /api/documents/upload`
  - `POST /api/documents/enhance/pdf-watermark`
  - `POST /api/documents/security/pdf-protect`
  - `POST /api/documents/modify/pdf-flatten`
  - `GET /api/tasks/{taskId}` (polling)
  - `GET /api/documents/{docId}/download`
- **Code:** [`backend/app/foxit/pdfservices.py`](backend/app/foxit/pdfservices.py)

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Foxit Developer account ([sign up free](https://app.developer-api.foxit.com/pricing))

### Option A: One-command setup (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/docforge.git
cd docforge
make setup                       # installs everything, creates .env
# Edit backend/.env with your Foxit API credentials
make backend                     # start API server (leave running)
# In a second terminal:
make demo                        # generates a PDF with DRAFT watermark + password
```

### Option B: Manual setup

```bash
# 1. Backend
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit with your Foxit credentials
uvicorn app.main:app --reload

# 2. CLI (in a second terminal)
cd cli
npm install
node src/index.js generate ../examples/release.json --out output.pdf
```

The backend runs at `http://localhost:8000`. Health check: `GET /health`.

---

## CLI Usage

```
docforge generate <input.json> [options]

Options:
  -o, --out <path>        Output PDF path (default: <product>-v<version>-release-notes.pdf)
  -w, --watermark <text>  Watermark text (default: "INTERNAL")
  -p, --password <pwd>    Password-protect the PDF
  -t, --template <id>     Template ID (default: "release-notes-v1")
  -h, --help              Show help
```

### Examples

```bash
# Basic generation
docforge generate examples/release.json --out output.pdf

# With custom watermark
docforge generate examples/release.json --watermark "DRAFT" --out draft.pdf

# With password protection
docforge generate examples/release.json --password "s3cret" --out locked.pdf
```

---

## Input JSON Format

```json
{
  "product_name": "Acme Platform",
  "version": "2.4.0",
  "release_date": "2026-02-16",
  "summary": "Major release with new collaboration features.",
  "features": [
    { "title": "Real-time Collaboration", "description": "Live editing support." }
  ],
  "fixes": [
    { "id": "BUG-1042", "title": "SSO token refresh", "description": "Fixed redirect loop." }
  ],
  "breaking_changes": [
    { "title": "Removed /v1/users", "description": "Migrate to /v2/users.", "migration": "..." }
  ],
  "links": [
    { "label": "Changelog", "url": "https://example.com/changelog" }
  ]
}
```

If any optional field is missing, the PDF shows "None" in that section.

---

## Pipeline Logging

Every step is logged with its duration — useful for debugging and impressive in demos:

```
16:24:07 | INFO    | ============================================================
16:24:07 | INFO    | DocForge Pipeline — starting
16:24:07 | INFO    | ============================================================
16:24:07 | INFO    | ▶ Step 1 · Validate input — started
16:24:07 | INFO    |   Product: Acme Platform v2.4.0
16:24:07 | INFO    | ✔ Step 1 · Validate input — completed in 0 ms
16:24:07 | INFO    | ▶ Step 2 · Generate base PDF (Document Generation API) — started
16:24:07 | INFO    | ▶ Build Word template — started
16:24:07 | INFO    | ✔ Build Word template — completed in 28 ms
16:24:08 | INFO    | ✔ Foxit Document Generation API call — completed in 1127 ms
16:24:08 | INFO    |   Document Generation returned 38822 bytes PDF
16:24:08 | INFO    | ✔ Step 2 · Generate base PDF — completed in 1156 ms
16:24:09 | INFO    | ▶ PDF Services — upload document — started
16:24:09 | INFO    |   Uploaded document → 69938af9…
16:24:09 | INFO    | ✔ PDF Services — upload document — completed in 994 ms
16:24:09 | INFO    | ▶ PDF Services — add watermark — started
16:24:11 | INFO    | ✔ PDF Services — add watermark — completed in 1945 ms
16:24:11 | INFO    | ▶ PDF Services — flatten PDF — started
16:24:13 | INFO    | ✔ PDF Services — flatten PDF — completed in 1949 ms
16:24:13 | INFO    | ▶ PDF Services — protect PDF — started
16:24:15 | INFO    | ✔ PDF Services — protect PDF — completed in 2006 ms
16:24:15 | INFO    | ▶ PDF Services — download result — started
16:24:16 | INFO    |   Downloaded 39332 bytes
16:24:16 | INFO    | ✔ PDF Services — download result — completed in 1074 ms
16:24:16 | INFO    | ============================================================
16:24:16 | INFO    | DocForge Pipeline — complete  (39332 bytes)
16:24:16 | INFO    | ============================================================
16:24:16 | INFO    | Total request time: 9126 ms
```

> The output above is from a real run, not synthetic. Every Foxit API call is timed.

---

## Project Structure

```
docforge/
├── README.md
├── LICENSE
├── Makefile                          # make setup / make backend / make demo
├── examples/
│   └── release.json                  # Sample input
├── templates/
│   └── release-notes.template.json   # Template definition
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app, POST /v1/generate
│   │   ├── core/
│   │   │   └── config.py            # Environment config + credential check
│   │   ├── foxit/
│   │   │   ├── auth.py              # Foxit API auth headers
│   │   │   ├── docgen.py            # Document Generation API client
│   │   │   ├── pdfservices.py       # PDF Services API client
│   │   │   └── pipeline.py          # End-to-end pipeline orchestrator
│   │   └── utils/
│   │       ├── logging.py           # Step logger with duration tracking
│   │       └── validate.py          # Input JSON validation
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── cli/
│   ├── package.json
│   ├── src/
│   │   ├── index.js                 # CLI entry point
│   │   ├── commands/
│   │   │   └── generate.js          # `generate` command
│   │   └── lib/
│   │       ├── apiClient.js         # HTTP client + health check
│   │       └── config.js            # CLI configuration
│   └── Dockerfile
├── docs/
│   └── index.html                   # Landing page (GitHub Pages)
└── .gitignore
```

---

## Deployment

### Docker

```bash
# Backend
cd backend
docker build -t docforge-api .
docker run -p 8000:8000 --env-file .env docforge-api

# CLI (point to hosted backend)
export DOCFORGE_API_URL=https://your-backend.onrender.com
docforge generate examples/release.json --out output.pdf
```

### Render (recommended for hackathon)

1. Push to GitHub
2. Create a new Web Service on [Render](https://render.com)
3. Set root directory to `backend/`
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables from `.env.example`

---

## CI/CD Integration

```yaml
# .github/workflows/release-notes.yml
name: Generate Release Notes
on:
  release:
    types: [published]

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: cd cli && npm install
      - run: |
          echo '${{ toJson(github.event.release) }}' > release.json
          node cli/src/index.js generate release.json --out release-notes.pdf
      - uses: actions/upload-artifact@v4
        with:
          name: release-notes
          path: release-notes.pdf
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend   | Python 3.12, FastAPI, httpx, python-docx |
| CLI       | Node.js 20, Commander.js, Axios, Chalk, Ora |
| PDF Gen   | Foxit Document Generation API |
| PDF Post  | Foxit PDF Services API |
| Deploy    | Docker, Render |

---

## License

MIT — see [LICENSE](LICENSE).

# DocForge CLI — Solution Architecture & Implementation Plan

**Author:** Solution Architecture Team
**Date:** 2026-02-16
**Version:** 1.0
**Status:** Approved for implementation

---

## Executive Summary

DocForge CLI transforms structured release data into polished, watermarked, password-protected PDFs through the Foxit Document Automation platform. The current system proves the concept with a working pipeline (JSON → Foxit Doc Gen API → Foxit PDF Services API → PDF). This plan elevates DocForge from a functional demo to a **production-grade, enterprise-ready PDF automation tool** with three differentiators:

1. **Multi-engine rendering** with cloud-first generation and a safe local verification layer
2. **Image and scanned-document ingestion** that converts messy inputs into structured release JSON
3. **Enterprise security and observability** that matches file-processing compliance expectations

The Foxit Document Generation API and Foxit PDF Services API remain the core automation layer throughout.

---

## 1. Current State Assessment

### What exists today

| Layer | Component | Status | Notes |
|-------|-----------|--------|-------|
| Backend | FastAPI server, single `/v1/generate` endpoint | Working | Synchronous, in-process |
| Engine: DocGen | Foxit Document Generation API integration | Working | Programmatic `.docx` template + JSON merge |
| Engine: LaTeX | tectonic compilation with variable injection | Working | Sandboxed, 60s timeout |
| PDF Services | Upload → Watermark → Flatten → Protect → Download | Working | Retry logic, polling |
| CLI | Node.js with Commander.js | Working | `--engine`, `--watermark`, `--password` flags |
| Web UI | Landing page with form/JSON modes, presets, pipeline progress | Working | Served by backend |
| CI | GitHub Action for auto-generation on release tag | Working | Template only, not tested in live repo |
| Validation | `product_name` + `version` required checks | Basic | No nested field validation, no schema file |
| Observability | Step timer logging with request IDs | Basic | Console only, no structured export |
| Templates | 3 presets in UI, 1 `.tex` reference file | Partial | Template registry not implemented |

### Gaps identified

| Gap | Impact | Phase |
|-----|--------|-------|
| No formal JSON Schema for input validation | Bad input produces cryptic errors | 0 |
| No typed internal data model (Pydantic) | Engine-specific branching, fragile | 0 |
| No output contract (job metadata, timings, hashes) | No auditability, no verification | 0 |
| Template registry is hardcoded | Can't add templates without code changes | 0 |
| No job orchestrator — pipeline is one synchronous function | No retries, no observability, no async | 1 |
| No asset/image support | Can't embed screenshots, diagrams | 3 |
| No OCR or image ingestion | Can't process scanned docs | 4 |
| No post-processing verification | Can't prove watermark was applied | 5 |
| No structured error codes | Frontend shows raw exceptions | 6 |
| CLI lacks `--mode`, `--verify`, `--assets` flags | Limited automation surface | 7 |

---

## 2. Target Architecture

### High-level data flow

```
                                    ┌──────────────────────────────────────────────────┐
                                    │              DocForge Backend                     │
                                    │                                                  │
 ┌─────────────┐   POST /v1/jobs   │  ┌───────────┐   ┌──────────────┐               │
 │  CLI         │──────────────────▶│  │   Job      │──▶│  Validator   │               │
 │  Web UI      │                   │  │ Orchestrator│   │  + Schema    │               │
 │  GitHub Act  │◀──────────────────│  │            │   └──────┬───────┘               │
 │              │  job status + PDF  │  │  RECEIVED  │          │                       │
 └─────────────┘                   │  │  VALIDATED  │          ▼                       │
                                    │  │  RESOLVED   │   ┌──────────────┐               │
                                    │  │  GENERATED  │   │Asset Resolver│               │
                                    │  │  PROCESSED  │   │  (images,    │               │
                                    │  │  VERIFIED   │   │   zip, OCR)  │               │
                                    │  │  DELIVERED  │   └──────┬───────┘               │
                                    │  │  FAILED     │          │                       │
                                    │  └──────┬──────┘          ▼                       │
                                    │         │          ┌──────────────┐               │
                                    │         │          │Engine Selector│               │
                                    │         │          │              │               │
                                    │         │          │ ┌──────────┐ │               │
                                    │         │          │ │ DocGen   │ │  Foxit Doc    │
                                    │         │          │ │ (Foxit)  │◀┼─ Gen API      │
                                    │         │          │ └──────────┘ │               │
                                    │         │          │ ┌──────────┐ │               │
                                    │         │          │ │ LaTeX    │ │  tectonic     │
                                    │         │          │ │(tectonic)│ │  (sandboxed)  │
                                    │         │          │ └──────────┘ │               │
                                    │         │          └──────┬───────┘               │
                                    │         │                 │ base PDF              │
                                    │         │                 ▼                       │
                                    │         │          ┌──────────────┐               │
                                    │         │          │ Foxit PDF    │  Foxit PDF    │
                                    │         │          │ Services API │◀─ Services    │
                                    │         │          │              │               │
                                    │         │          │ • Upload     │               │
                                    │         │          │ • Watermark  │               │
                                    │         │          │ • Flatten    │               │
                                    │         │          │ • Protect    │               │
                                    │         │          │ • Download   │               │
                                    │         │          └──────┬───────┘               │
                                    │         │                 │ final PDF             │
                                    │         │                 ▼                       │
                                    │         │          ┌──────────────┐               │
                                    │         │          │  Verifier    │               │
                                    │         │          │              │               │
                                    │         │          │ • Page count │               │
                                    │         │          │ • Watermark  │               │
                                    │         │          │ • Encryption │               │
                                    │         │          │ • Metadata   │               │
                                    │         │          └──────────────┘               │
                                    └──────────────────────────────────────────────────┘
```

### Component registry

| Component | Responsibility | New or Existing |
|-----------|---------------|-----------------|
| Job Orchestrator | State machine, retry, audit | New |
| Schema Validator | JSON Schema + Pydantic models | New (replaces basic validate.py) |
| Asset Resolver | Images, zips, path traversal checks | New |
| OCR Pipeline | Image/scan → text → structured JSON | New |
| Engine Interface | Uniform `run(model, context) → pdf_bytes` | New (wraps existing) |
| DocGen Engine | Foxit Document Generation API | Existing, enhanced |
| LaTeX Engine | tectonic compilation | Existing, enhanced |
| PDF Services Client | Upload, watermark, flatten, protect, download | Existing |
| Verifier | Post-processing validation checks | New |
| Template Registry | Template metadata, selection, compatibility | New |
| Error Catalog | Structured error codes + human messages | New |

---

## 3. Phase 0 — Contracts, Schema, and Data Model

**Goal:** Establish the internal contracts that every subsequent phase depends on.

### 0.1 Release JSON Schema

Create `schemas/release.schema.json` using JSON Schema draft 2020-12.

```
schemas/
└── release.schema.json       # Strict input validation
```

**Schema structure:**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["product_name", "version"],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "product_name":   { "type": "string", "minLength": 1, "maxLength": 200 },
    "version":        { "type": "string", "pattern": "^[\\w\\.\\-]+$" },
    "release_date":   { "type": "string", "format": "date" },
    "summary":        { "type": "string", "maxLength": 5000 },
    "features":       { "type": "array", "items": { "$ref": "#/$defs/Feature" }, "maxItems": 50 },
    "fixes":          { "type": "array", "items": { "$ref": "#/$defs/Fix" }, "maxItems": 100 },
    "breaking_changes": { "type": "array", "items": { "$ref": "#/$defs/BreakingChange" }, "maxItems": 30 },
    "links":          { "type": "array", "items": { "$ref": "#/$defs/Link" }, "maxItems": 20 },
    "images":         { "type": "array", "items": { "$ref": "#/$defs/Image" }, "maxItems": 10 },
    "attachments":    { "type": "array", "items": { "$ref": "#/$defs/Attachment" }, "maxItems": 5 }
  },
  "$defs": {
    "Feature":        { "type": "object", "required": ["title", "description"], "properties": { ... } },
    "Fix":            { "type": "object", "required": ["id", "title"], "properties": { ... } },
    "BreakingChange": { "type": "object", "required": ["title", "description", "migration"], "properties": { ... } },
    "Link":           { "type": "object", "required": ["label", "url"], "properties": { ... } },
    "Image":          { "type": "object", "required": ["path"], "properties": { "path": {}, "caption": {}, "width_percent": {}, "placement": {} } },
    "Attachment":     { "type": "object", "required": ["label", "path"], "properties": { "label": {}, "path": {}, "type": {} } }
  }
}
```

**Implementation:** Install `jsonschema` (Python) for server-side validation. CLI validates client-side before sending.

### 0.2 Internal Data Model (Pydantic)

Create `backend/app/models/release.py`:

```python
class FeatureModel(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(max_length=2000)

class FixModel(BaseModel):
    id: str = Field(max_length=50)
    title: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)

class BreakingChangeModel(BaseModel):
    title: str = Field(max_length=200)
    description: str = Field(max_length=2000)
    migration: str = Field(max_length=2000)

class ImageModel(BaseModel):
    path: str
    caption: str = ""
    width_percent: int = Field(default=80, ge=10, le=100)
    placement: Literal["inline", "full_width"] = "inline"

class AttachmentModel(BaseModel):
    label: str
    path: str
    type: Literal["appendix", "embed"] = "appendix"

class LinkModel(BaseModel):
    label: str
    url: HttpUrl

class ReleaseModel(BaseModel):
    schema_version: str = "1.0"
    product_name: str = Field(min_length=1, max_length=200)
    version: str = Field(pattern=r"^[\w\.\-]+$")
    release_date: date = Field(default_factory=date.today)
    summary: str = Field(default="", max_length=5000)
    features: list[FeatureModel] = Field(default_factory=list, max_length=50)
    fixes: list[FixModel] = Field(default_factory=list, max_length=100)
    breaking_changes: list[BreakingChangeModel] = Field(default_factory=list, max_length=30)
    links: list[LinkModel] = Field(default_factory=list, max_length=20)
    images: list[ImageModel] = Field(default_factory=list, max_length=10)
    attachments: list[AttachmentModel] = Field(default_factory=list, max_length=5)
```

**Why this matters:** Every engine, every pipeline step, and every output formatter works against `ReleaseModel`. No raw dicts leaking across boundaries.

### 0.3 Output Contract

Every generation returns a `JobResult`:

```python
class StepTiming(BaseModel):
    step: str                     # "validate", "resolve_assets", "generate", "watermark", etc.
    duration_ms: int
    status: Literal["ok", "skipped", "failed"]
    detail: str = ""

class ArtifactMetadata(BaseModel):
    filename: str
    size_bytes: int
    pages: int
    content_hash: str             # SHA-256 of final PDF

class JobResult(BaseModel):
    job_id: str                   # UUID
    engine_used: str              # "docgen" | "latex"
    input_hash: str               # SHA-256 of input JSON (for determinism checks)
    artifact: ArtifactMetadata
    before_pdf_id: str | None     # Foxit document ID before post-processing
    after_pdf_id: str | None      # Foxit document ID after post-processing
    timings: list[StepTiming]
    warnings: list[str]
    errors: list[str]
    verification: dict | None     # Verification results (Phase 5)
```

**Returned as:** `X-DocForge-Job` response header (JSON-encoded) alongside the PDF body. CLI and web UI parse this for display.

### 0.4 Template Registry

Create `backend/app/templates/registry.py`:

```python
TEMPLATES = {
    "product-release": TemplateEntry(
        id="product-release",
        name="Product Release",
        description="Standard product release notes with features, fixes, and breaking changes.",
        engines=["docgen", "latex"],
        variables=["product_name", "version", "release_date", "summary", "features", "fixes", "breaking_changes", "links"],
        default_layout={"watermark": "INTERNAL", "include_toc": False},
    ),
    "security-advisory": TemplateEntry(
        id="security-advisory",
        name="Security Advisory",
        description="Security-focused release with CVE references and severity ratings.",
        engines=["docgen", "latex"],
        variables=["product_name", "version", "release_date", "summary", "fixes", "breaking_changes", "links"],
        default_layout={"watermark": "CONFIDENTIAL", "include_toc": False},
    ),
    "api-release": TemplateEntry(
        id="api-release",
        name="API Release",
        description="API changelog with endpoint changes, deprecations, and migration guides.",
        engines=["docgen", "latex"],
        variables=["product_name", "version", "release_date", "summary", "features", "breaking_changes", "links"],
        default_layout={"watermark": "DRAFT", "include_toc": True},
    ),
}
```

**Endpoint:** `GET /v1/templates` returns the registry for CLI and UI consumption.

**File layout:**

```
backend/app/
├── models/
│   ├── release.py        # ReleaseModel, FeatureModel, etc.
│   ├── job.py            # JobResult, StepTiming, ArtifactMetadata
│   └── template.py       # TemplateEntry
├── templates/
│   └── registry.py       # Template registry
schemas/
└── release.schema.json   # JSON Schema for external validation
```

---

## 4. Phase 1 — Pipeline Architecture Upgrades

**Goal:** Move from a synchronous function to an observable, retryable state machine.

### 1.1 Job Orchestrator

Replace the inline `run_pipeline()` with a `JobOrchestrator` class.

```
States:  RECEIVED → VALIDATED → ASSET_RESOLVED → BASE_PDF_GENERATED
         → POST_PROCESSED → VERIFIED → DELIVERED
         Any state → FAILED (with error code and retry info)
```

**Implementation:**

```python
class JobOrchestrator:
    def __init__(self, job_id: str, request: GenerateRequest):
        self.job_id = job_id
        self.state = JobState.RECEIVED
        self.context = PipelineContext()
        self.timings: list[StepTiming] = []

    async def run(self) -> JobResult:
        steps = [
            ("validate",        self._validate),
            ("resolve_assets",  self._resolve_assets),
            ("generate",        self._generate),
            ("post_process",    self._post_process),
            ("verify",          self._verify),
        ]
        for name, step_fn in steps:
            with step_timer(name) as t:
                try:
                    await step_fn()
                    self.timings.append(StepTiming(step=name, duration_ms=t.ms, status="ok"))
                except RetryableError:
                    # Retry once for idempotent steps
                    await step_fn()
                except FatalError as e:
                    self.state = JobState.FAILED
                    raise
        self.state = JobState.DELIVERED
        return self._build_result()
```

**Storage:** For the hackathon, state is in-memory (dict keyed by `job_id`). The design allows Redis/Postgres drop-in later.

**API change:** The endpoint remains synchronous for simplicity (`POST /v1/generate` blocks until complete), but the orchestrator internally tracks state. A future `POST /v1/jobs` + `GET /v1/jobs/{id}` async pattern is architecturally ready.

### 1.2 Worker Model (Design Only for Hackathon)

Heavy operations that benefit from off-thread execution:

| Operation | Current | Target |
|-----------|---------|--------|
| LaTeX compilation | In-process subprocess | Worker (future: Celery/ARQ) |
| Image conversion | N/A | Worker |
| OCR | N/A | Worker |
| PDF verification | N/A | Inline (fast enough) |

**Hackathon scope:** Keep everything in-process but behind the `StepInterface` abstraction so workers can be added without refactoring.

### 1.3 Unified Step Interface

Every pipeline step implements:

```python
class PipelineStep(ABC):
    @abstractmethod
    async def run(self, input: StepInput, context: PipelineContext) -> StepOutput:
        """Execute the step. Raise RetryableError or FatalError on failure."""
        ...

    @property
    def idempotent(self) -> bool:
        """Whether this step can be safely retried."""
        return False
```

**Steps to implement:**

| Step Class | Idempotent | Notes |
|------------|-----------|-------|
| `ValidateStep` | Yes | Schema + Pydantic validation |
| `ResolveAssetsStep` | Yes | Path resolution, hash computation |
| `GenerateStep` | Yes | Engine dispatch |
| `UploadStep` | No | Foxit PDF Services upload |
| `WatermarkStep` | No | Foxit watermark operation |
| `FlattenStep` | No | Foxit flatten operation |
| `ProtectStep` | No | Foxit protect operation (conditional) |
| `DownloadStep` | Yes | Foxit download |
| `VerifyStep` | Yes | Local PDF inspection |

### 1.4 Structured Observability

```python
# Structured log format per step
{
    "timestamp": "2026-02-16T18:27:08Z",
    "level": "info",
    "job_id": "cfdd020f518b",
    "trace_id": "a1b2c3d4",
    "step": "watermark",
    "duration_ms": 2572,
    "status": "ok",
    "engine": "latex",
    "product": "Acme Platform",
    "version": "2.4.0"
}
```

**Metrics (collected in-memory, exposed at `GET /metrics`):**

| Metric | Type | Labels |
|--------|------|--------|
| `docforge_jobs_total` | Counter | engine, status |
| `docforge_step_duration_seconds` | Histogram | step, engine |
| `docforge_pdf_pages` | Histogram | engine |
| `docforge_pdf_bytes` | Histogram | engine |
| `docforge_errors_total` | Counter | step, error_code |

---

## 5. Phase 2 — Engines and PDF Generation

### 2.1 Engine Interface

```python
class PDFEngine(ABC):
    engine_id: str

    @abstractmethod
    async def generate(self, model: ReleaseModel, context: PipelineContext) -> bytes:
        """Generate a base PDF from the release model. Returns PDF bytes."""
        ...

    @abstractmethod
    def supports_images(self) -> bool: ...

    @abstractmethod
    def supports_template(self, template_id: str) -> bool: ...
```

**Engine registry:**

```python
ENGINES = {
    "docgen": FoxitDocGenEngine(),     # Cloud, default
    "latex":  TectonicLatexEngine(),   # Local, advanced
}
```

**Selection rules:**

| Condition | Engine |
|-----------|--------|
| Default / no preference | `docgen` (Foxit Document Generation API) |
| `engine=latex` explicitly | `latex` (tectonic) |
| Foxit API unavailable + `engine=docgen` | Fail with clear error |
| Images/assets requested | `latex` preferred (native image support) |

### 2.2 DocGen Engine Enhancements

**Current:** Builds `.docx` template in code, sends to Foxit API.

**Improvements:**

| Enhancement | Description |
|-------------|-------------|
| Section suppression | If `features` array is empty, omit the "New Features" section entirely instead of printing "None" |
| Table pagination | Add page-break-before for large tables (>20 rows) |
| Consistent headers/footers | Product name + version in header, "Generated by DocForge" in footer |
| Token validation | Pre-check that all template tokens have corresponding data before API call |

**Implementation change in `docgen.py`:**

```python
# Before building table section, check if data exists
if model.features:
    _add_features_table(doc, model.features)
# No else — section is simply omitted
```

### 2.3 LaTeX Engine Enhancements

**Current:** Inline LaTeX generation with variable injection.

**Improvements:**

| Enhancement | Description |
|-------------|-------------|
| Image inclusion | `\includegraphics` for assets referenced in `images[]` |
| Figure blocks | Auto-generated `\begin{figure}` with caption and sizing |
| Section suppression | Conditional sections via Python logic |
| Custom fonts | Support for organization fonts via font configuration |
| Multi-page tables | `longtable` for tables exceeding one page |

**Implementation change in `texgen.py`:**

```python
# Image support
if data.get("images"):
    for img in data["images"]:
        latex += rf"""
\begin{{figure}}[h]
    \centering
    \includegraphics[width={img['width_percent'] / 100}\textwidth]{{{img['resolved_path']}}}
    \caption{{{e(img.get('caption', ''))}}}
\end{{figure}}
"""
```

### 2.4 Local PDF Utilities Layer

Create `backend/app/pdf/verify.py` — a local verification module (no Foxit API calls) that inspects PDFs before and after post-processing.

```python
class PDFVerifier:
    """Local PDF inspection using pymupdf (fitz). No external API calls."""

    def verify(self, pdf_bytes: bytes, expectations: VerifyExpectations) -> VerifyResult:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        return VerifyResult(
            page_count=len(doc),
            has_text=any(page.get_text().strip() for page in doc),
            watermark_detected=self._check_watermark(doc, expectations.watermark_text),
            is_encrypted=doc.is_encrypted,
            metadata=dict(doc.metadata),
            file_size=len(pdf_bytes),
            content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
        )

    def _check_watermark(self, doc, expected_text: str) -> bool:
        """Check if watermark text appears on every page."""
        for page in doc:
            if expected_text.upper() not in page.get_text().upper():
                return False
        return True
```

**Usage:** Called as the `VerifyStep` in the pipeline. Results included in `JobResult.verification`.

---

## 6. Phase 3 — Assets, Images, and Placeholders

### 3.1 Asset Pack Concept

Users can provide assets in two ways:

```
# Option A: Separate assets directory
docforge generate release.json --assets ./assets/

# Option B: Zip archive
docforge generate release.zip
# Contains: release.json + assets/screenshot1.png + assets/diagram.pdf
```

**Security controls:**

| Control | Rule |
|---------|------|
| Path traversal | Block `..` in all paths; only relative paths allowed |
| File type allowlist | `.jpg`, `.jpeg`, `.png`, `.gif`, `.pdf`, `.txt` only |
| Max single file size | 10 MB |
| Max total asset size | 50 MB |
| Max asset count | 20 files |
| Filename sanitization | Strip non-alphanumeric chars except `-_.` |

### 3.2 Schema Extensions

Already included in Phase 0 schema:

```json
"images": [{
    "path": "assets/dashboard-screenshot.png",
    "caption": "New dashboard with real-time metrics",
    "width_percent": 80,
    "placement": "inline"
}],
"attachments": [{
    "label": "Migration Script",
    "path": "assets/migrate-v2.sql",
    "type": "appendix"
}]
```

### 3.3 Asset Resolution Step

Create `backend/app/pipeline/resolve_assets.py`:

```python
class ResolveAssetsStep(PipelineStep):
    idempotent = True

    async def run(self, input: StepInput, context: PipelineContext) -> StepOutput:
        for image in input.model.images:
            resolved = self._resolve_path(image.path, context.asset_dir)
            self._validate_file(resolved)
            image.resolved_path = resolved
            image.sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
            context.resolved_assets.append(image)
        return StepOutput(status="ok")

    def _resolve_path(self, path: str, base: Path) -> Path:
        resolved = (base / path).resolve()
        if not str(resolved).startswith(str(base.resolve())):
            raise FatalError("ASSET_PATH_TRAVERSAL", f"Path traversal blocked: {path}")
        return resolved

    def _validate_file(self, path: Path):
        if not path.exists():
            raise FatalError("ASSET_NOT_FOUND", f"Asset not found: {path.name}")
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise FatalError("ASSET_TYPE_BLOCKED", f"File type not allowed: {path.suffix}")
        if path.stat().st_size > MAX_FILE_SIZE:
            raise FatalError("ASSET_TOO_LARGE", f"File exceeds 10MB limit: {path.name}")
```

### 3.4 LaTeX Image Placeholders

The LaTeX engine's `_build_latex_source()` generates `\includegraphics` blocks from resolved images:

```latex
\section*{Screenshots}
\begin{figure}[h]
    \centering
    \includegraphics[width=0.8\textwidth]{/tmp/docforge-job-abc123/assets/dashboard.png}
    \caption{New dashboard with real-time metrics}
\end{figure}
```

**Note:** The DocGen engine (Foxit API) does not natively support image embedding in the same way. For `docgen` engine + images, we embed images in the `.docx` template using `python-docx` before sending to the API.

### 3.5 Appendix Builder

Create `backend/app/pipeline/appendix.py`:

```python
class AppendixBuilder:
    """Build an appendix section from attachments."""

    def build_latex_appendix(self, attachments: list[AttachmentModel], context: PipelineContext) -> str:
        latex = r"\newpage\appendix\section*{Appendices}" + "\n"
        for att in attachments:
            if att.type == "embed" and att.path.endswith(".pdf"):
                latex += rf"\includepdf[pages=-]{{{att.resolved_path}}}" + "\n"
            else:
                latex += rf"\subsection*{{{att.label}}}" + "\n"
                latex += rf"See attached file: \texttt{{{att.path}}}" + "\n"
        return latex
```

---

## 7. Phase 4 — Image Ingestion and OCR to JSON

### 4.1 Image to PDF Mode

**Flow:** Image(s) → normalize → single PDF → Foxit PDF Services post-processing

```
Input:  POST /v1/image-to-pdf
        Content-Type: multipart/form-data
        files: [image1.png, image2.jpg, ...]
        watermark: "DRAFT"

Output: PDF (one page per image, normalized to A4/Letter)
```

**Implementation:** `backend/app/pipeline/image_to_pdf.py`

```python
class ImageToPDFStep:
    """Convert images to a single PDF using pymupdf."""

    async def run(self, images: list[bytes], page_size: str = "A4") -> bytes:
        doc = fitz.open()
        for img_bytes in images:
            img = fitz.open(stream=img_bytes, filetype="png")
            # Auto-rotate if landscape
            page = doc.new_page(width=595, height=842)  # A4
            rect = page.rect
            page.insert_image(rect, stream=img_bytes)
        return doc.tobytes()
```

**Then:** Pass through Foxit PDF Services for watermark + flatten + protect.

### 4.2 OCR Pipeline: Image/Scan → Text

**Flow:** Image or scanned PDF → OCR → structured text with confidence scores

**Technology choice:** `pytesseract` (Tesseract OCR wrapper) — free, well-supported, runs locally.

```
Input:  Image (png/jpg) or scanned PDF
Output: {
          "blocks": [
            { "text": "Release Notes v2.4", "confidence": 0.95, "bbox": [...] },
            { "text": "New Features", "confidence": 0.92, "bbox": [...] },
            ...
          ],
          "overall_confidence": 0.89,
          "page_count": 1
        }
```

**Implementation:** `backend/app/ocr/extract.py`

```python
class OCRExtractor:
    """Extract text from images using Tesseract OCR."""

    def extract(self, image_bytes: bytes) -> OCRResult:
        image = Image.open(io.BytesIO(image_bytes))
        # Preprocessing: grayscale, threshold, deskew
        processed = self._preprocess(image)
        data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
        blocks = self._group_blocks(data)
        return OCRResult(
            blocks=blocks,
            overall_confidence=sum(b.confidence for b in blocks) / len(blocks),
        )

    def _preprocess(self, image: Image) -> Image:
        """Grayscale + threshold for better OCR accuracy."""
        gray = image.convert("L")
        return gray.point(lambda x: 0 if x < 128 else 255, "1")
```

### 4.3 Text → Release JSON Extraction

**Flow:** OCR text → pattern-based structured extraction → schema validation → user review

**Implementation:** `backend/app/ocr/structurize.py`

```python
class ReleaseExtractor:
    """Extract structured release data from raw OCR text."""

    SECTION_PATTERNS = {
        "features": r"(?:new\s+features?|what'?s\s+new|additions?)",
        "fixes":    r"(?:bug\s+fix(?:es)?|resolved|fixed)",
        "breaking": r"(?:breaking\s+changes?|deprecat|removed|migration)",
    }

    def extract(self, ocr_result: OCRResult) -> ExtractionResult:
        text = " ".join(b.text for b in ocr_result.blocks)
        sections = self._split_sections(text)

        draft = {
            "product_name": self._extract_product_name(text),
            "version":      self._extract_version(text),
            "summary":      self._extract_summary(text),
            "features":     self._extract_list(sections.get("features", "")),
            "fixes":        self._extract_list(sections.get("fixes", "")),
            "breaking_changes": self._extract_list(sections.get("breaking", "")),
        }

        # Validate against schema
        missing = [k for k in ["product_name", "version"] if not draft.get(k)]

        return ExtractionResult(
            draft_json=draft,
            confidence=ocr_result.overall_confidence,
            missing_required=missing,
            needs_review=ocr_result.overall_confidence < 0.85 or len(missing) > 0,
        )
```

**Quality gates:**

| Confidence | Behavior |
|-----------|----------|
| > 0.90 | Auto-populate form, allow one-click generation |
| 0.70–0.90 | Populate form with warnings, require user confirmation |
| < 0.70 | Show extracted text, force manual review, block auto-generation |

### 4.4 Table Extraction

For tabular data (common in release notes), use pattern-based extraction:

```python
class TableExtractor:
    """Recognize tables in OCR output using spatial analysis."""

    def extract_tables(self, blocks: list[OCRBlock]) -> list[dict]:
        # Group blocks by Y-coordinate (same row)
        rows = self._group_by_rows(blocks)
        # Detect column boundaries by X-coordinate clustering
        cols = self._detect_columns(rows)
        # Build table structure
        return self._build_table(rows, cols)
```

### 4.5 API Endpoints

```
POST /v1/ocr/extract
  Input:  multipart/form-data (image or PDF)
  Output: { "text": "...", "blocks": [...], "confidence": 0.89 }

POST /v1/ocr/structurize
  Input:  { "text": "..." }  (or raw OCR result)
  Output: { "draft_json": {...}, "confidence": 0.85, "missing": [...], "needs_review": true }
```

**Web UI flow:**
1. User uploads image/scan
2. OCR extracts text → shows raw text with confidence
3. Structurizer produces draft JSON → populates form with yellow warnings
4. User reviews and edits
5. Click Generate → normal pipeline

---

## 8. Phase 5 — Post-Processing and Verification

### 5.1 Consistent Post-Processing

All engines produce a base PDF. Post-processing is always:

```
Base PDF → Upload → Watermark → Flatten → [Protect] → Download → Verify
```

**Foxit PDF Services API** handles steps 2–5. This never changes regardless of engine.

**Optional future additions (Foxit API permitting):**
- Document properties (title, author, subject)
- Digital signature placeholder

### 5.2 Verification Module

Create `backend/app/pdf/verify.py`:

```python
class VerificationResult(BaseModel):
    page_count: int
    has_text: bool
    watermark_detected: bool
    watermark_on_all_pages: bool
    is_encrypted: bool
    flattening_signals: bool      # No interactive annotations remain
    file_size: int
    content_hash: str             # SHA-256
    metadata: dict
    checks_passed: int
    checks_total: int
    passed: bool

class PDFVerifier:
    def verify(self, pdf_bytes: bytes, expectations: VerifyExpectations) -> VerificationResult:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        checks = {
            "opens_and_parses":    len(doc) > 0,
            "page_count_stable":   len(doc) == expectations.expected_pages or expectations.expected_pages is None,
            "has_text_content":    any(page.get_text().strip() for page in doc),
            "watermark_detected":  self._check_watermark(doc, expectations.watermark_text),
            "watermark_all_pages": self._check_watermark_all_pages(doc, expectations.watermark_text),
            "encryption_matches":  doc.is_encrypted == expectations.should_be_encrypted,
            "no_annotations":      self._check_flattened(doc),  # Flattening check
        }

        passed = sum(checks.values())
        return VerificationResult(
            page_count=len(doc),
            has_text=checks["has_text_content"],
            watermark_detected=checks["watermark_detected"],
            watermark_on_all_pages=checks["watermark_all_pages"],
            is_encrypted=doc.is_encrypted,
            flattening_signals=checks["no_annotations"],
            file_size=len(pdf_bytes),
            content_hash=hashlib.sha256(pdf_bytes).hexdigest(),
            metadata=dict(doc.metadata),
            checks_passed=passed,
            checks_total=len(checks),
            passed=passed == len(checks),
        )
```

### 5.3 Before/After Diff

Store both the base PDF (before post-processing) and the final PDF (after) in the job context.

**API addition:**

```json
{
  "verification": {
    "checks_passed": 7,
    "checks_total": 7,
    "passed": true,
    "details": {
      "opens_and_parses": true,
      "page_count": 1,
      "watermark_detected": true,
      "watermark_all_pages": true,
      "is_encrypted": false,
      "no_annotations": true,
      "has_text_content": true
    },
    "diff_summary": {
      "watermark_applied": true,
      "flattened": true,
      "password_protected": false,
      "size_change_bytes": 1279
    }
  }
}
```

**Web UI:** Side-by-side "Before" and "After" panels showing verification results.

---

## 9. Phase 6 — Web Demo UX Upgrades

### 6.1 Mode Selector

Replace the single-mode demo with a tabbed interface:

```
┌─────────────────┬───────────────┬──────────────┬─────────────────────┐
│ Release JSON    │ LaTeX + Assets│ Image → PDF  │ Scan → JSON → PDF   │
│ → PDF           │ → PDF         │              │                     │
└─────────────────┴───────────────┴──────────────┴─────────────────────┘
```

| Mode | Input | Engine | Output |
|------|-------|--------|--------|
| Release JSON → PDF | JSON (form or textarea) | docgen or latex | PDF |
| LaTeX + Assets → PDF | JSON + asset upload | latex | PDF with images |
| Image → PDF | Image upload(s) | N/A (direct conversion) | PDF via Foxit Services |
| Scan → JSON → PDF | Image/scan upload | OCR → user review → engine | PDF |

### 6.2 Pipeline Progress Panel

Upgrade from the current 4-step indicator to a detailed side-by-side panel:

```
┌─────────────────────────────────────────────────────┐
│  Pipeline Progress                                  │
├──────────────────────┬──────────────────────────────┤
│  Step                │  Status                      │
├──────────────────────┼──────────────────────────────┤
│  1. Validate         │  ✓  0ms                      │
│  2. Resolve Assets   │  ✓  12ms  (2 images)         │
│  3. Generate PDF     │  ✓  4,908ms  (LaTeX)         │
│  4. Upload           │  ✓  2,217ms                  │
│  5. Watermark        │  ✓  2,572ms  (DRAFT)         │
│  6. Flatten          │  ✓  2,099ms                  │
│  7. Verify           │  ✓  45ms   (7/7 checks)     │
├──────────────────────┼──────────────────────────────┤
│  Total               │  11,853ms                    │
│  Output              │  22,147 bytes · 1 page       │
│  Content Hash        │  a3f2...b8c1                 │
├──────────────────────┴──────────────────────────────┤
│  [Download PDF]  [View Before/After]  [Copy Link]   │
└─────────────────────────────────────────────────────┘
```

### 6.3 Error Experience

Replace raw exception display with structured errors:

```json
{
  "error_code": "LATEX_COMPILE_FAILED",
  "message": "LaTeX compilation failed on line 42: Undefined control sequence \\badcommand",
  "suggestion": "Check your template for typos. The token \\badcommand is not a valid LaTeX command.",
  "docs_link": "#troubleshooting-latex",
  "job_id": "abc123",
  "step": "generate"
}
```

**Error catalog (`backend/app/errors.py`):**

| Code | Message | Suggestion |
|------|---------|------------|
| `VALIDATION_FAILED` | Required field missing: {field} | Add the field to your JSON |
| `ASSET_NOT_FOUND` | Asset file not found: {path} | Check the path in images[] or attachments[] |
| `ASSET_PATH_TRAVERSAL` | Path traversal blocked | Use relative paths only |
| `ASSET_TOO_LARGE` | File exceeds 10MB limit | Compress or resize the file |
| `DOCGEN_API_ERROR` | Foxit Doc Gen API returned {status} | Check API credentials and input format |
| `LATEX_COMPILE_FAILED` | LaTeX compilation failed | Check template syntax |
| `LATEX_TIMEOUT` | Compilation timed out after 60s | Simplify the template |
| `PDF_SERVICES_ERROR` | Foxit PDF Services returned {status} | Check API credentials |
| `VERIFICATION_FAILED` | PDF verification: {n} checks failed | Retry or contact support |
| `OCR_LOW_CONFIDENCE` | OCR confidence below threshold | Upload a clearer image |
| `OCR_EXTRACTION_FAILED` | Could not extract structured data | Review and edit the draft JSON manually |

### 6.4 Last-Mile Open Flow

After PDF generation, offer:

- **Download** — Direct browser download (existing)
- **Copy sharable link** — Temporary URL valid for 5 minutes
- **Open in PDF reader** — `window.open(blob_url)` with browser-native PDF viewer
- **Copy job metadata** — JSON with timings, verification, hashes

---

## 10. Phase 7 — CLI and CI Integration

### 7.1 Expanded CLI Flags

```
docforge generate <input> [options]

Options:
  -o, --out <path>         Output PDF path (auto-generated if omitted)
  -w, --watermark <text>   Watermark text (default: INTERNAL)
  -p, --password <pwd>     Password-protect the PDF
  -e, --engine <type>      Engine: docgen | latex (default: docgen)
  -a, --assets <dir>       Assets directory for images/attachments
  -z, --zip <file>         Zip archive containing release.json + assets/
  -m, --mode <mode>        Mode: release | image2pdf | ocr2json (default: release)
  -v, --verify             Run post-processing verification checks
  --output-dir <dir>       Output directory (for batch operations)
  --open                   Open PDF in system reader after generation
  --json                   Output job metadata as JSON to stdout
  --template <id>          Template: product-release | security-advisory | api-release
```

**New commands:**

```
docforge templates          # List available templates
docforge verify <pdf>       # Run verification checks on an existing PDF
docforge ocr <image>        # Extract text from image, output draft JSON
```

### 7.2 GitHub Actions Templates

**Template 1: Generate on tag**

```yaml
# .github/workflows/release-notes.yml
name: Generate Release Notes PDF
on:
  release:
    types: [published]
jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate PDF
        run: |
          curl -X POST ${{ secrets.DOCFORGE_API_URL }}/v1/generate \
            -H "Content-Type: application/json" \
            -d @release.json \
            -o release-notes.pdf
      - name: Upload to release
        uses: softprops/action-gh-release@v2
        with:
          files: release-notes.pdf
```

**Template 2: Generate on merge to main**

```yaml
# .github/workflows/release-notes-on-merge.yml
name: Generate Release Notes on Merge
on:
  push:
    branches: [main]
    paths: ['release.json']
jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate and verify
        run: |
          curl -s -X POST ${{ secrets.DOCFORGE_API_URL }}/v1/generate \
            -H "Content-Type: application/json" \
            -d @release.json -o release-notes.pdf
      - uses: actions/upload-artifact@v4
        with:
          name: release-notes
          path: release-notes.pdf
```

**Template 3: PR comment with draft link**

```yaml
# .github/workflows/release-notes-pr.yml
name: Release Notes Preview
on:
  pull_request:
    paths: ['release.json']
jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate draft
        run: |
          curl -s -X POST ${{ secrets.DOCFORGE_API_URL }}/v1/generate \
            -H "Content-Type: application/json" \
            -d '{"data":'$(cat release.json)', "watermark":"DRAFT PR #${{ github.event.pull_request.number }}"}' \
            -o draft.pdf
      - uses: actions/upload-artifact@v4
        with:
          name: draft-release-notes
          path: draft.pdf
```

### 7.3 Pre-commit Hook

```bash
#!/bin/sh
# .githooks/pre-push
# Auto-generate draft PDF when release.json changes
if git diff --cached --name-only | grep -q "release.json"; then
  echo "📄 Generating draft release notes..."
  docforge generate release.json --watermark "DRAFT" --out draft-release-notes.pdf
  echo "✓ Draft PDF saved to draft-release-notes.pdf"
fi
```

---

## 11. Phase 8 — Security, Robustness, and Testing

### 8.1 Threat Model

| Threat | Vector | Control |
|--------|--------|---------|
| Malicious file upload | Oversized images, zip bombs | Size limits, type allowlist, decompression limits |
| Path traversal | `../../etc/passwd` in asset paths | Resolve + compare to base dir |
| LaTeX injection | Shell escape in TeX | tectonic disables shell-escape by default |
| LaTeX infinite loop | `\loop` or recursive macros | 60-second subprocess timeout |
| Resource exhaustion | Many concurrent jobs | Rate limiting, max concurrent jobs |
| Data exfiltration | TeX `\input{/etc/passwd}` | Sandbox to temp dir, no access outside |
| Denial of service | Large JSON payloads | Request body size limit (10MB) |
| Credential leakage | Foxit keys in logs | Never log payloads, only request IDs and sizes |

**Controls matrix:**

```
┌───────────────────┬──────────┬──────────┬──────────┬──────────┐
│ Control           │ Upload   │ LaTeX    │ OCR      │ API      │
├───────────────────┼──────────┼──────────┼──────────┼──────────┤
│ Size limit        │    ✓     │    ✓     │    ✓     │    ✓     │
│ Type allowlist    │    ✓     │   N/A    │    ✓     │   N/A    │
│ Path sanitization │    ✓     │    ✓     │   N/A    │   N/A    │
│ Timeout           │   N/A    │  60s     │  30s     │  120s    │
│ Sandbox           │   temp   │  temp    │  temp    │  N/A     │
│ Rate limit        │  10/min  │  5/min   │  5/min   │  20/min  │
│ Logging           │  ID+size │ ID+size  │ ID+size  │ ID+size  │
└───────────────────┴──────────┴──────────┴──────────┴──────────┘
```

### 8.2 Test Harnesses

**Unit tests (`tests/unit/`):**

| Test file | Coverage |
|-----------|----------|
| `test_schema.py` | JSON Schema validation edge cases |
| `test_models.py` | Pydantic model serialization/deserialization |
| `test_docgen.py` | Template building, token mapping |
| `test_texgen.py` | LaTeX source generation, escaping |
| `test_verify.py` | PDF verification checks |
| `test_resolve.py` | Asset resolution, path traversal blocking |
| `test_ocr.py` | OCR extraction accuracy |
| `test_errors.py` | Error catalog completeness |

**Integration tests (`tests/integration/`):**

| Test file | Coverage |
|-----------|----------|
| `test_pipeline.py` | Full pipeline with mock Foxit APIs |
| `test_api.py` | FastAPI endpoint contract tests |
| `test_cli.py` | CLI flag combinations and output |

**Robustness harnesses (`tests/fuzz/`):**

| Harness | Input |
|---------|-------|
| `fuzz_json.py` | Random/malformed JSON payloads |
| `fuzz_latex.py` | Adversarial LaTeX input strings |
| `fuzz_image.py` | Corrupted/edge-case images |
| `fuzz_pdf.py` | Malformed PDFs for verification |

### 8.3 Regression Corpus

Maintain `tests/corpus/` with real-world samples:

```
tests/corpus/
├── json/
│   ├── minimal.json              # Just product_name + version
│   ├── maximal.json              # All fields populated
│   ├── unicode_heavy.json        # Chinese, Arabic, emoji
│   ├── large_release.json        # 50 features, 100 fixes
│   ├── deeply_nested.json        # Long descriptions, many links
│   └── empty_sections.json       # features: [], fixes: []
├── images/
│   ├── screenshot_4k.png         # Large resolution
│   ├── scan_skewed.jpg           # Rotated scanned document
│   ├── handwritten.png           # Low OCR confidence
│   └── table_screenshot.png      # Tabular data
└── pdfs/
    ├── pre_watermark.pdf         # Before post-processing
    ├── post_watermark.pdf        # After watermark
    ├── encrypted.pdf             # Password-protected
    └── malformed.pdf             # Corrupt PDF for verification
```

### 8.4 Golden Tests

For each template + engine combination, maintain expected properties:

```python
# tests/golden/test_golden.py
@pytest.mark.parametrize("template,engine,expected", [
    ("product-release", "docgen", {"pages": 1, "watermark": True, "sections": ["Features", "Bug Fixes"]}),
    ("product-release", "latex",  {"pages": 1, "watermark": True, "sections": ["New Features", "Bug Fixes"]}),
    ("security-advisory", "docgen", {"pages": 1, "watermark": True, "sections": ["Bug Fixes", "Breaking Changes"]}),
])
def test_golden(template, engine, expected):
    result = run_pipeline_sync(GOLDEN_INPUT, template=template, engine=engine)
    assert result.verification.page_count == expected["pages"]
    assert result.verification.watermark_detected == expected["watermark"]
```

---

## 12. Phase 9 — Hackathon Demo Script

### Demo Flow (3–4 minutes)

| Time | Action | What judges see |
|------|--------|-----------------|
| 0:00–0:15 | **Problem statement** | "Dev teams waste hours formatting release notes. DocForge automates it." |
| 0:15–0:40 | **Mode 1: JSON → PDF (DocGen)** | Paste JSON in web demo, click Generate. Show 7-step pipeline with timings. Download PDF. Point to watermark, tables, headers. |
| 0:40–1:10 | **Mode 2: Same JSON → PDF (LaTeX)** | Switch engine to LaTeX. Same input. Show improved typography — typeset tables, professional headers/footers, page numbers. Side-by-side comparison. |
| 1:10–1:40 | **Mode 3: Image → PDF** | Upload a screenshot. Auto-converted to PDF. Watermark and flatten applied via Foxit PDF Services. Show one-click flow. |
| 1:40–2:20 | **Mode 4: Scan → JSON → PDF** | Upload a photo of printed release notes. OCR extracts text. Structurizer produces draft JSON with confidence scores. Review in form. Generate PDF. Full circle. |
| 2:20–2:40 | **Verification** | Show verification panel: 7/7 checks passed, content hash, before/after diff summary. |
| 2:40–3:00 | **CLI demo** | Run `docforge generate release.json --engine latex --verify --open`. PDF opens in system reader. Show CI template. |
| 3:00–3:20 | **Architecture** | Show pipeline diagram. Point to both Foxit APIs. Show structured logging with job IDs and durations. |
| 3:20–3:40 | **Security** | Show threat model. Sandboxed LaTeX. Asset validation. No data stored. Rate limits. |
| 3:40–4:00 | **What's next** | Template marketplace, GitHub/Jira ingestion, AI-assisted summarization, SaaS dashboard. |

### What judges should notice

| Judging criteria | DocForge evidence |
|-----------------|-------------------|
| **Meaningful use of Document Generation API** | Core engine for JSON → template → PDF. Token syntax, table merging, section generation. |
| **Meaningful use of PDF Services API** | Every PDF passes through upload → watermark → flatten → protect. Visible before/after. |
| **Creative/innovative application** | OCR ingestion (scan → structured JSON → PDF), multi-engine architecture, verification layer. |
| **Technical execution** | State machine pipeline, structured observability, security controls, deterministic output. |
| **User experience** | 4 modes, real-time progress, verification results, last-mile open, structured errors. |
| **Safe and respectful data handling** | No storage, no payload logging, sandboxed execution, path traversal protection. |

---

## 13. Implementation Timeline (7–10 Day Hackathon)

```
Day 1–2:  Phase 0  — Schema, models, output contract, template registry
Day 2–3:  Phase 1  — Job orchestrator, step interface, structured logging
Day 3–4:  Phase 2  — Engine interface, DocGen improvements, LaTeX images, verifier
Day 4–5:  Phase 3  — Asset resolver, image support in templates, appendix builder
Day 5–6:  Phase 4  — Image-to-PDF, OCR pipeline, text-to-JSON extractor
Day 6–7:  Phase 5  — Verification module, before/after diff
Day 7–8:  Phase 6  — Web UI modes, pipeline panel, error experience
Day 8–9:  Phase 7  — CLI expansion, CI templates, pre-commit hook
Day 9–10: Phase 8  — Security hardening, golden tests, regression corpus
Day 10:   Phase 9  — Demo polish, video script, README final pass
```

### Critical path

```
Schema (0.1) → Models (0.2) → Job Orchestrator (1.1) → Step Interface (1.3)
    → Engine Interface (2.1) → Asset Resolver (3.3) → OCR Pipeline (4.2)
    → Verification (5.2) → Web UI (6.1) → Demo (9.1)
```

### Risk mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Foxit API downtime during demo | Low | Critical | LaTeX engine as fallback for base PDF; pre-generate backup PDFs |
| OCR accuracy too low | Medium | Medium | Quality gates force manual review; position as "assisted" not "automatic" |
| tectonic package download slow on first run | Medium | Low | Pre-warm tectonic cache in Docker build |
| Tesseract installation issues | Medium | Medium | Defer OCR to Phase 4; demo with pre-extracted text if needed |
| Scope creep | High | High | Lock Phase 0–5 as MVP. Phase 6–8 are polish. |

---

## 14. File Structure (Target State)

```
docforge/
├── README.md
├── LICENSE
├── Makefile
├── render.yaml
├── schemas/
│   └── release.schema.json
├── templates/
│   ├── release-notes.tex
│   ├── release-notes.template.json
│   └── presets/
│       ├── product-release.json
│       ├── security-advisory.json
│       └── api-release.json
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                    # FastAPI routes
│       ├── errors.py                  # Error catalog
│       ├── core/
│       │   └── config.py
│       ├── models/
│       │   ├── release.py             # ReleaseModel + sub-models
│       │   ├── job.py                 # JobResult, StepTiming
│       │   └── template.py            # TemplateEntry
│       ├── foxit/
│       │   ├── auth.py
│       │   ├── docgen.py              # DocGen engine
│       │   ├── texgen.py              # LaTeX engine
│       │   ├── pdfservices.py         # PDF Services client
│       │   └── pipeline.py            # Job orchestrator
│       ├── pipeline/
│       │   ├── steps.py               # Step interface + implementations
│       │   ├── resolve_assets.py      # Asset resolution
│       │   └── appendix.py            # Appendix builder
│       ├── pdf/
│       │   ├── verify.py              # PDF verification
│       │   └── image_to_pdf.py        # Image conversion
│       ├── ocr/
│       │   ├── extract.py             # Tesseract OCR
│       │   └── structurize.py         # Text → JSON extraction
│       ├── templates/
│       │   └── registry.py            # Template registry
│       └── utils/
│           ├── logging.py
│           └── validate.py            # Schema-based validation
├── cli/
│   ├── package.json
│   └── src/
│       ├── index.js
│       ├── commands/
│       │   ├── generate.js
│       │   ├── templates.js           # List templates
│       │   ├── verify.js              # Verify existing PDF
│       │   └── ocr.js                 # OCR command
│       └── lib/
│           ├── apiClient.js
│           └── config.js
├── docs/
│   ├── index.html                     # Landing page
│   └── IMPLEMENTATION_PLAN.md         # This document
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fuzz/
│   ├── golden/
│   └── corpus/
├── .github/
│   ├── workflows/
│   │   ├── release-notes.yml
│   │   ├── release-notes-on-merge.yml
│   │   └── release-notes-pr.yml
│   └── hooks/
│       └── pre-push
└── examples/
    ├── release.json
    ├── release-with-images.json
    └── assets/
        └── screenshot.png
```

---

## 15. Dependencies (New)

### Backend (`requirements.txt` additions)

| Package | Purpose | Phase |
|---------|---------|-------|
| `jsonschema` | JSON Schema validation | 0 |
| `pymupdf` (fitz) | PDF verification, image-to-PDF | 2, 4, 5 |
| `pytesseract` | OCR extraction | 4 |
| `Pillow` | Image preprocessing for OCR | 4 |

### System dependencies

| Package | Purpose | Phase |
|---------|---------|-------|
| `tectonic` | LaTeX compilation | Existing |
| `tesseract-ocr` | OCR engine | 4 |

### Docker additions

```dockerfile
# Phase 4: OCR support
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*
```

---

*This document is the single source of truth for DocForge CLI's evolution from hackathon demo to production-grade PDF automation platform. Each phase is self-contained and shippable. The Foxit Document Generation API and PDF Services API remain the core automation layer throughout every phase.*

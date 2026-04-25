# System Architecture & Data Flow

> **Teacher Paperwork Assistant** — processes, validates, and compares Romanian academic documents.

## High-Level Architecture

```mermaid
graph TB
    User([👤 User])

    subgraph Frontend["Frontend — Angular 19 (port 4200)"]
        Home[Home Page\nDocument Upload + Guard Editor]
        DiffPage[Diff Page\nPDF Comparison Viewer]
    end

    subgraph Backend["Backend — FastAPI"]
        Parse[POST /api/documents/parse]
        Validate[POST /api/documents/validate]
        Suggest[POST /api/documents/suggest]
        Draft[POST /api/documents/draft]
    end

    subgraph DiffSvc["Diff-Service — Flask (port 5000)"]
        DiffCompare[POST /api/diff/]
        DiffVisual[POST /api/diff/visual]
        DiffHealth[GET /api/diff/health]
    end

    Claude[(Anthropic Claude\nSonnet 3.5)]

    User --> Home
    User --> DiffPage

    Home -->|PDF / image upload| Parse
    Home -->|template + schema + guards| Validate
    Home -->|violations + user message| Suggest
    Home -->|extracted document| Draft

    DiffPage -->|file_old + file_new| DiffCompare
    DiffPage -->|file_old + file_new| DiffVisual

    Parse --> Claude
    Suggest --> Claude
    Draft --> Claude
```

---

## Document Extraction Flow (`/api/documents/parse`)

```mermaid
flowchart TD
    A([Upload File\nPDF or Image]) --> B{File Type?}

    B -->|Image file\n.png .jpg .jpeg| C[scan_extractor\nConvert to base64 PNG]
    B -->|PDF| D{pdf_router\nText density check\navg chars/page > 100?}

    D -->|Yes → text PDF| E[text_extractor\nExtract plain text\nmax 20 pages]
    D -->|No → scanned PDF| F[scan_extractor\nRender at 150 DPI\nmax 20 pages / batch]

    C --> G[claude_service\nextract_from_images / extract_from_images_paged]
    E --> H[claude_service\nextract_from_text]
    F --> G

    G --> I[ExtractedDocument]
    H --> I

    I -->|optional| J[claude_service\ngenerate_markdown_from_*]
    J --> K[ExtractedDocument\nwith markdown_content]
    I --> K

    K --> L([JSON Response\nfields · tables · summary\nsource_route · markdown])
```

---

## Template Validation & Suggestion Flow

```mermaid
flowchart TD
    A([Extracted Document]) --> B[template_drafts\nbuild_template_schema_and_baseline_drafts]
    B --> C([TemplateDraftResponse\ntemplate + schema + guard_drafts])

    C --> D{User edits\nguard options}

    D --> E[POST /api/documents/validate\ntemplate + schema + guards]
    E --> F[template_validator\nvalidate_template]

    F --> G{Guards OK?}

    G -->|✅ valid| H([ValidationResult\nstatus: valid])

    G -->|❌ violations| I([ValidationResult\nstatus: invalid\nviolations list])

    I --> J{User requests\nfix suggestions}

    J --> K[POST /api/documents/suggest\nviolations + user message]
    K --> L[template_suggester\nsuggest_template_fixes → Claude]
    L --> M([SemanticSuggestionResult\nexplanation + patches\nconfidence per suggestion])

    M --> N[User applies patch]
    N --> E
```

### Guard Types

```mermaid
graph LR
    G[Guard] --> R[range\nmin / max numeric bounds]
    G --> S[sum_equals\nmultiple fields sum to target]
    G --> T[type check\nstring · date · number\nboolean · list]
```

---

## Diff-Service Processing Pipeline (`/api/diff/`)

```mermaid
flowchart TD
    A([Upload\nfile_old + file_new\nparser_type]) --> B[Extractor\npdfplumber_extractor\nPageText per page]

    B --> C[Parser\nfd_parser — Fișe de Disciplină\npi_parser — Planuri de Învățământ]

    C --> D[Differ\ndifflib_differ\nline-level diffs per section]

    D --> E[Analyzer\nregex_analyzer\ndetect semantic changes]

    E --> F([DiffResponse])

    F --> G[sections: SectionDiff list\nequal · modified · added · removed]
    F --> H[logic_changes: LogicChange list\nHOURS_CHANGED · ECTS_CHANGED · …]
    F --> I[summary: DiffSummary\ntotals + counts]
```

### Visual Diff Flow (`/api/diff/visual`)

```mermaid
flowchart LR
    A([file_old + file_new]) --> B[visual_differ\nbounding boxes on pages]
    B --> C{Change type}
    C -->|deleted text| D[🔴 Red box]
    C -->|added text| E[🟢 Green box]
    D & E --> F([base64-encoded\nannotated PDFs])
```

---

## Frontend Component Structure

```mermaid
graph TD
    Router[Angular Router] --> Home[HomeComponent\n/]
    Router --> DiffPage[DiffPageComponent\n/diff]

    DiffPage --> DiffUpload[DiffUploadComponent\nfile picker]
    DiffPage --> DiffViewer[DiffViewerComponent\nside-by-side diff]
    DiffPage --> DiffSummary[DiffSummaryComponent\nstats table]
    DiffPage --> LogicChanges[LogicChangesComponent\nsemantic alerts]

    DiffUpload -->|compare / visualCompare| DiffService[DiffService\nHTTP client]
    DiffService -->|POST /api/diff/| DiffSvcBackend[(Diff-Service)]
    DiffService -->|POST /api/diff/visual| DiffSvcBackend

    SharedNav[NavComponent] --> Router
```

---

## Parser Target Documents

```mermaid
graph LR
    FD["📄 Fișă de Disciplină\n(Course Description Sheet)"] --> FDP[fd_parser]
    PI["📋 Plan de Învățământ\n(Teaching Plan)"] --> PIP[pi_parser]

    FDP --> S1[Identificare]
    FDP --> S2[Obiective]
    FDP --> S3[Competențe]
    FDP --> S4[Conținuturi]
    FDP --> S5[Structura]
    FDP --> S6[Evaluare]
    FDP --> S7[Bibliografie]

    PIP --> S8[ALL-CAPS headers\nas section delimiters]
```

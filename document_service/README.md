# Document Service - Background Task

Independent background worker for document processing. Runs separately from the main backend API.

## Structure

```
document_service/
├── main.py                 # Entry point - worker loop
├── config.py               # Configuration (env-based)
├── database.py             # Database engine & sessions
├── pyproject.toml          # Dependencies
├── .env.example            # Environment template
├── models/
│   ├── __init__.py
│   ├── base.py             # Base model + AuditMixin
│   └── document.py         # Document & DocumentVersion models
├── security/
│   ├── __init__.py         # Exports: SecurityCheckerFactory, run_security_check
│   ├── base.py             # Base FileSecurityCheck class
│   ├── pdf.py              # PDF security checks (PyMuPDF)
│   ├── office.py           # Office docs (DOCX/XLSX/PPTX) checks
│   ├── text.py             # Plain text/CSV/MD checks
│   └── factory.py          # Factory for checker by MIME type
└── utils/
    ├── __init__.py
    └── object_storage.py   # R2 download utilities
```

## Setup

```bash
# 1. Copy env template
cp .env.example .env
# Edit .env with your database URL, R2 credentials, etc.

# 2. Install dependencies
pip install -r requirements.txt  # or use pyproject.toml

# 3. Run
python main.py
```

## Configuration (via `.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/dociq` | PostgreSQL connection |
| `WORKER_POLL_INTERVAL` | `30` | Seconds between polling for pending docs |
| `WORKER_BATCH_SIZE` | `10` | Max documents to process per loop |
| `MAX_PROCESSING_SIZE` | `52428800` | Max file size for processing (50MB) |
| `R2_*` | - | Cloudflare R2 credentials for file downloads |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Worker Loop

The `main.py` runs a continuous loop:

1. **Fetch** - Queries `document_versions` with `status = 'pending'` (oldest first, batch size)
2. **Download** - Downloads file from R2 to temp file using `storage_path`
3. **Security Check** - Runs `run_security_check(file_path, mime_type, file_size)`
4. **Update Status**:
   - `PASS` → `UPLOADED` (ready for next processing stage)
   - `QUARANTINE` → `QUARANTINED` with `quarantine_reason`
   - `FAIL` → `UPLOADED` (retry later)
4. **Loop** - Sleeps `WORKER_POLL_INTERVAL` seconds if no pending docs

## Security Checks

| Type | Checks |
|------|--------|
| **All** | Size limit, MIME type, dangerous extensions, magic bytes, integrity |
| **PDF** | Page count, encryption, embedded files, JavaScript, form fields, parseable |
| **Office** | Zip integrity, VBA macros, external refs, suspicious files, content validation |
| **Text/CSV** | Line count, line length, suspicious patterns, high entropy, CSV format |

## Factory Usage

```python
from security import SecurityCheckerFactory, run_security_check

# Direct usage
report = run_security_check("/path/file.pdf", "application/pdf", 1024000)

# Or via factory
checker = SecurityCheckerFactory.get_checker("application/pdf")
report = checker.check("/path/file.pdf", "application/pdf", 1024000)

# Check result
if report.result == SecurityCheckResult.PASS:
    # proceed
elif report.result == SecurityCheckResult.QUARANTINE:
    # quarantine
elif report.result == SecurityCheckResult.FAIL:
    # reject/retry
```

## Database Schema

Uses the same `documents` and `document_versions` tables as the backend. The worker only reads/writes:
- `document_versions.status` (PENDING → PROCESSING → UPLOADED/QUARANTINED)
- `document_versions.quarantine_reason`
- `document_versions.modifiedAt`

## Running as a Service

```bash
# Development
python main.py

# Production (with process manager)
# systemd, supervisor, or Docker
```

## Dependencies

Core (required):
- `sqlalchemy>=2.0`, `psycopg2-binary`, `python-dotenv`, `pydantic`, `pydantic-settings`
- `boto3` (for R2)

Optional (for deep checks):
- `PyMuPDF` (`pip install pymupdf`) - PDF deep analysis
- `python-docx`, `openpyxl` - Not required (uses stdlib `zipfile` + `xml.etree`)

The service gracefully degrades if optional deps are missing.
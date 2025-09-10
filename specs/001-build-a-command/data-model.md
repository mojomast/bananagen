# Data Model

## Entities

### Image Asset
Represents a generated or placeholder image.

**Fields**:
- id: UUID (primary key)
- path: string (file path)
- width: integer
- height: integer
- format: string (e.g., png, jpg)
- sha256: string (hash for integrity)
- created_at: datetime
- type: string (placeholder or generated)

**Relationships**:
- Belongs to Generation Job (if generated)

**Validation Rules**:
- Path must exist
- Width/height > 0
- Format in allowed list

### Generation Job
Represents a task to generate an image.

**Fields**:
- id: UUID (primary key)
- prompt: string
- placeholder_path: string (optional)
- output_path: string
- status: string (queued, running, done, error)
- params: JSON (model, seed, etc.)
- batch_id: UUID (optional, for batch jobs)
- created_at: datetime
- finished_at: datetime (optional)

**Relationships**:
- Has many Metadata Records
- Belongs to Batch (optional)

**Validation Rules**:
- Prompt not empty
- Output path valid
- Status in allowed values

### Metadata Record
Represents provenance data for a generation.

**Fields**:
- id: UUID (primary key)
- generation_id: UUID (foreign key)
- prompt: string
- model: string
- seed: integer (optional)
- params: JSON
- timestamp: datetime
- gemini_response_id: string
- sha256: string
- source_placeholder: string (optional)

**Relationships**:
- Belongs to Generation Job

**Validation Rules**:
- Generation ID exists
- Model not empty
- Timestamp not future

### Batch
Represents a batch of jobs.

**Fields**:
- id: UUID (primary key)
- name: string
- jobs_json: JSON (list of job specs)
- status: string (pending, running, done, error)
- started_at: datetime (optional)
- finished_at: datetime (optional)

**Relationships**:
- Has many Generation Jobs

**Validation Rules**:
- Name not empty
- Jobs JSON valid structure

## State Transitions

### Generation Job Status
- queued → running (when started)
- running → done (on success)
- running → error (on failure)

### Batch Status
- pending → running (when started)
- running → done (all jobs done)
- running → error (any job error)

## Schema (SQLite)

```sql
CREATE TABLE generations (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    placeholder_path TEXT,
    output_path TEXT NOT NULL,
    status TEXT NOT NULL,
    params TEXT, -- JSON
    batch_id TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE metadata (
    id TEXT PRIMARY KEY,
    generation_id TEXT NOT NULL,
    prompt TEXT NOT NULL,
    model TEXT NOT NULL,
    seed INTEGER,
    params TEXT, -- JSON
    timestamp TEXT NOT NULL,
    gemini_response_id TEXT,
    sha256 TEXT,
    source_placeholder TEXT,
    FOREIGN KEY (generation_id) REFERENCES generations(id)
);

CREATE TABLE batches (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    jobs_json TEXT NOT NULL, -- JSON
    status TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
```

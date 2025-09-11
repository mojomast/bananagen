import sqlite3
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
import json
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class GenerationRecord:
    id: str
    prompt: str
    width: int
    height: int
    output_path: str
    model: str
    status: str  # queued, processing, done, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None
    sha256: Optional[str] = None


@dataclass
class BatchRecord:
    id: str
    job_count: int
    status: str  # queued, processing, done, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: Optional[List[dict]] = None
    error: Optional[str] = None


@dataclass
class ScanRecord:
    id: str
    root: str
    pattern: str
    replace: bool
    extract_from: List[str]
    status: str  # queued, processing, done, failed
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class APIProviderRecord:
    id: str
    name: str
    display_name: str
    endpoint_url: str
    auth_type: str
    created_at: datetime
    updated_at: datetime
    model_name: Optional[str] = None
    base_url: Optional[str] = None
    settings: Optional[dict] = None
    is_active: bool = True


@dataclass
class APIKeyRecord:
    id: str
    provider_id: str
    key_value: str  # encrypted
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    environment: str = "default"
    is_active: bool = True
    last_used_at: Optional[datetime] = None


class Database:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        try:
            self._init_db()
            logger.info("Database initialized", extra={"db_path": db_path})
        except Exception as e:
            logger.error("Failed to initialize database", extra={
                "db_path": db_path,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise Exception(f"Database initialization failed: {e}")
    
    def _init_db(self):
        """Initialize database tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS generations (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    width INTEGER NOT NULL,
                    height INTEGER NOT NULL,
                    output_path TEXT NOT NULL,
                    model TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata TEXT,
                    error TEXT,
                    sha256 TEXT
                )
            ''')
            # Add sha256 column if not exists for existing databases
            try:
                conn.execute('ALTER TABLE generations ADD COLUMN sha256 TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
            conn.execute('''
                CREATE TABLE IF NOT EXISTS batches (
                    id TEXT PRIMARY KEY,
                    job_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    results TEXT,
                    error TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scans (
                    id TEXT PRIMARY KEY,
                    root TEXT NOT NULL,
                    pattern TEXT NOT NULL,
                    replace BOOLEAN NOT NULL,
                    extract_from TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    metadata TEXT,
                    error TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_providers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    endpoint_url TEXT NOT NULL,
                    auth_type TEXT NOT NULL,
                    model_name TEXT,
                    base_url TEXT,
                    settings TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Add new columns if not exists
            try:
                conn.execute('ALTER TABLE api_providers ADD COLUMN base_url TEXT')
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute('ALTER TABLE api_providers ADD COLUMN settings TEXT')
            except sqlite3.OperationalError:
                pass
            conn.execute('''
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    key_value TEXT NOT NULL,
                    description TEXT,
                    environment TEXT DEFAULT 'default',
                    is_active BOOLEAN DEFAULT 1,
                    last_used_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (provider_id) REFERENCES api_providers(id)
                )
            ''')
            # Add description column if not exists for existing databases
            try:
                conn.execute('ALTER TABLE api_keys ADD COLUMN description TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists
            # Create indexes for performance
            try:
                conn.execute('CREATE INDEX IF NOT EXISTS idx_api_providers_name ON api_providers(name)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_provider_id ON api_keys(provider_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_api_keys_environment ON api_keys(environment)')
            except sqlite3.OperationalError:
                # Indexes may already exist, ignore
                pass
    
    def save_generation(self, record: GenerationRecord):
        """Save a generation record."""
        try:
            logger.debug("Saving generation record", extra={"generation_id": record.id, "status": record.status})
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO generations
                    (id, prompt, width, height, output_path, model, status, created_at, completed_at, metadata, error, sha256)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.id,
                    record.prompt,
                    record.width,
                    record.height,
                    record.output_path,
                    record.model,
                    record.status,
                    record.created_at.isoformat(),
                    record.completed_at.isoformat() if record.completed_at else None,
                    json.dumps(record.metadata) if record.metadata else None,
                    record.error,
                    record.sha256
                ))
                conn.commit()
                logger.info("Generation record saved", extra={"generation_id": record.id})
        except sqlite3.Error as e:
            logger.error("Database error saving generation", extra={
                "generation_id": record.id,
                "error": str(e),
                "db_path": self.db_path
            })
            raise Exception(f"Failed to save generation record: {e}")
        except (json.JSONEncodeError, TypeError) as e:
            logger.error("Serialization error saving generation", extra={
                "generation_id": record.id,
                "error": str(e)
            })
            raise Exception(f"Failed to serialize generation record data: {e}")
        except Exception as e:
            logger.error("Unexpected error saving generation", extra={
                "generation_id": record.id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise Exception(f"Unexpected error saving generation: {e}")
    
    def get_generation(self, generation_id: str) -> Optional[GenerationRecord]:
        """Get a generation record by ID."""
        try:
            logger.debug("Retrieving generation record", extra={"generation_id": generation_id})
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute('SELECT * FROM generations WHERE id = ?', (generation_id,)).fetchone()
                if row:
                    try:
                        metadata = json.loads(row[9]) if row[9] else None
                        created_at = datetime.fromisoformat(row[7])
                        completed_at = datetime.fromisoformat(row[8]) if row[8] else None

                        record = GenerationRecord(
                            id=row[0],
                            prompt=row[1],
                            width=row[2],
                            height=row[3],
                            output_path=row[4],
                            model=row[5],
                            status=row[6],
                            created_at=created_at,
                            completed_at=completed_at,
                            metadata=metadata,
                            error=row[10],
                            sha256=row[11] if len(row) > 11 else None
                        )
                        logger.debug("Generation record retrieved", extra={"generation_id": generation_id, "status": record.status})
                        return record
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error("Failed to parse generation record data", extra={
                            "generation_id": generation_id,
                            "error": str(e),
                            "raw_metadata": row[9] if len(row) > 9 else None
                        })
                        return None
                else:
                    logger.debug("Generation record not found", extra={"generation_id": generation_id})
                    return None
        except sqlite3.Error as e:
            logger.error("Database error retrieving generation", extra={
                "generation_id": generation_id,
                "error": str(e),
                "db_path": self.db_path
            })
            raise Exception(f"Failed to retrieve generation record: {e}")
        except Exception as e:
            logger.error("Unexpected error retrieving generation", extra={
                "generation_id": generation_id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise Exception(f"Unexpected error retrieving generation: {e}")

    def get_generation_by_sha(self, sha256: str) -> Optional[GenerationRecord]:
        """Get a generation record by SHA256 hash."""
        try:
            logger.debug("Retrieving generation record by SHA", extra={"sha256": sha256})
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute('SELECT * FROM generations WHERE sha256 = ?', (sha256,)).fetchone()
                if row:
                    try:
                        metadata = json.loads(row[9]) if row[9] else None
                        created_at = datetime.fromisoformat(row[7])
                        completed_at = datetime.fromisoformat(row[8]) if row[8] else None

                        record = GenerationRecord(
                            id=row[0],
                            prompt=row[1],
                            width=row[2],
                            height=row[3],
                            output_path=row[4],
                            model=row[5],
                            status=row[6],
                            created_at=created_at,
                            completed_at=completed_at,
                            metadata=metadata,
                            error=row[10],
                            sha256=row[11] if len(row) > 11 else None
                        )
                        logger.debug("Generation record retrieved by SHA", extra={"generation_id": record.id, "sha256": sha256})
                        return record
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error("Failed to parse generation record data by SHA", extra={
                            "sha256": sha256,
                            "error": str(e),
                            "raw_metadata": row[9] if len(row) > 9 else None
                        })
                        return None
                else:
                    logger.debug("Generation record not found by SHA", extra={"sha256": sha256})
                    return None
        except sqlite3.Error as e:
            logger.error("Database error retrieving generation by SHA", extra={
                "sha256": sha256,
                "error": str(e),
                "db_path": self.db_path
            })
            raise Exception(f"Failed to retrieve generation record by SHA: {e}")
        except Exception as e:
            logger.error("Unexpected error retrieving generation by SHA", extra={
                "sha256": sha256,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise Exception(f"Unexpected error retrieving generation by SHA: {e}")

    def save_batch(self, record: BatchRecord):
        """Save a batch record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO batches
                (id, job_count, status, created_at, completed_at, results, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.id,
                record.job_count,
                record.status,
                record.created_at.isoformat(),
                record.completed_at.isoformat() if record.completed_at else None,
                json.dumps(record.results) if record.results else None,
                record.error
            ))
    
    def get_batch(self, batch_id: str) -> Optional[BatchRecord]:
        """Get a batch record by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT * FROM batches WHERE id = ?', (batch_id,)).fetchone()
            if row:
                return BatchRecord(
                    id=row[0],
                    job_count=row[1],
                    status=row[2],
                    created_at=datetime.fromisoformat(row[3]),
                    completed_at=datetime.fromisoformat(row[4]) if row[4] else None,
                    results=json.loads(row[5]) if row[5] else None,
                    error=row[6]
                )
        return None

    def save_scan(self, record: ScanRecord):
        """Save a scan record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO scans
                (id, root, pattern, replace, extract_from, status, created_at, completed_at, metadata, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.id,
                record.root,
                record.pattern,
                record.replace,
                json.dumps(record.extract_from),
                record.status,
                record.created_at.isoformat(),
                record.completed_at.isoformat() if record.completed_at else None,
                json.dumps(record.metadata) if record.metadata else None,
                record.error
            ))

    def get_scan(self, scan_id: str) -> Optional[ScanRecord]:
        """Get a scan record by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT * FROM scans WHERE id = ?', (scan_id,)).fetchone()
            if row:
                return ScanRecord(
                    id=row[0],
                    root=row[1],
                    pattern=row[2],
                    replace=bool(row[3]),
                    extract_from=json.loads(row[4]) if row[4] else [],
                    status=row[5],
                    created_at=datetime.fromisoformat(row[6]),
                    completed_at=datetime.fromisoformat(row[7]) if row[7] else None,
                    metadata=json.loads(row[8]) if row[8] else None,
                    error=row[9]
                )
        return None
    
    def update_generation_status(self, generation_id: str, status: str, metadata: dict = None, error: str = None):
        """Update generation status."""
        with sqlite3.connect(self.db_path) as conn:
            update_fields = ["status = ?"]
            values = [status]
            
            if metadata:
                update_fields.append("metadata = ?")
                values.append(json.dumps(metadata))
            
            if error:
                update_fields.append("error = ?")
                values.append(error)
            
            if status in ['done', 'failed']:
                update_fields.append("completed_at = ?")
                values.append(datetime.now().isoformat())
            
            query = f"UPDATE generations SET {', '.join(update_fields)} WHERE id = ?"
            values.append(generation_id)
            
            conn.execute(query, values)
    
    def update_batch_status(self, batch_id: str, status: str, results: List[dict] = None, error: str = None):
        """Update batch status."""
        with sqlite3.connect(self.db_path) as conn:
            update_fields = ["status = ?"]
            values = [status]

            if results:
                update_fields.append("results = ?")
                values.append(json.dumps(results))

            if error:
                update_fields.append("error = ?")
                values.append(error)

            if status in ['done', 'failed']:
                update_fields.append("completed_at = ?")
                values.append(datetime.now().isoformat())

            query = f"UPDATE batches SET {', '.join(update_fields)} WHERE id = ?"
            values.append(batch_id)

            conn.execute(query, values)

    def update_scan_status(self, scan_id: str, status: str, metadata: dict = None, error: str = None):
        """Update scan status."""
        with sqlite3.connect(self.db_path) as conn:
            update_fields = ["status = ?"]
            values = [status]

            if metadata:
                update_fields.append("metadata = ?")
                values.append(json.dumps(metadata))

            if error:
                update_fields.append("error = ?")
                values.append(error)

            if status in ['done', 'failed']:
                update_fields.append("completed_at = ?")
                values.append(datetime.now().isoformat())

            query = f"UPDATE scans SET {', '.join(update_fields)} WHERE id = ?"
            values.append(scan_id)

            conn.execute(query, values)

    def save_api_provider(self, record: APIProviderRecord):
        """Save an API provider record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO api_providers
                (id, name, display_name, endpoint_url, auth_type, model_name, base_url, settings, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.id,
                record.name,
                record.display_name,
                record.endpoint_url,
                record.auth_type,
                record.model_name,
                record.base_url,
                json.dumps(record.settings) if record.settings else None,
                record.is_active,
                record.created_at.isoformat(),
                record.updated_at.isoformat()
            ))

    def get_api_provider(self, provider_name_or_id: str) -> Optional[APIProviderRecord]:
        """Get an API provider record by name or ID."""
        with sqlite3.connect(self.db_path) as conn:
            # Try looking up by name first
            row = conn.execute('SELECT * FROM api_providers WHERE name = ?', (provider_name_or_id,)).fetchone()
            if row:
                created_at = datetime.fromisoformat(row[9]) if row[9] else None
                updated_at = datetime.fromisoformat(row[10]) if row[10] else None
                settings = json.loads(row[7]) if row[7] else None
                return APIProviderRecord(
                    id=row[0],
                    name=row[1],
                    display_name=row[2],
                    endpoint_url=row[3],
                    auth_type=row[4],
                    model_name=row[5],
                    base_url=row[6],
                    settings=settings,
                    is_active=bool(row[8]),
                    created_at=created_at,
                    updated_at=updated_at
                )

            # If not found, try looking up by ID
            row = conn.execute('SELECT * FROM api_providers WHERE id = ?', (provider_name_or_id,)).fetchone()
            if row:
                created_at = datetime.fromisoformat(row[9]) if row[9] else None
                updated_at = datetime.fromisoformat(row[10]) if row[10] else None
                settings = json.loads(row[7]) if row[7] else None
                return APIProviderRecord(
                    id=row[0],
                    name=row[1],
                    display_name=row[2],
                    endpoint_url=row[3],
                    auth_type=row[4],
                    model_name=row[5],
                    base_url=row[6],
                    settings=settings,
                    is_active=bool(row[8]),
                    created_at=created_at,
                    updated_at=updated_at
                )
            return None
            if row:
                created_at = datetime.fromisoformat(row[9]) if row[9] else None
                updated_at = datetime.fromisoformat(row[10]) if row[10] else None
                settings = json.loads(row[7]) if row[7] else None
                return APIProviderRecord(
                    id=row[0],
                    name=row[1],
                    display_name=row[2],
                    endpoint_url=row[3],
                    auth_type=row[4],
                    model_name=row[5],
                    base_url=row[6],
                    settings=settings,
                    is_active=bool(row[8]),
                    created_at=created_at,
                    updated_at=updated_at
                )
        return None

    def list_active_api_providers(self) -> List[APIProviderRecord]:
        """Get all active API provider records."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('SELECT * FROM api_providers WHERE is_active = 1').fetchall()
            providers = []
            for row in rows:
                created_at = datetime.fromisoformat(row[9]) if row[9] else None
                updated_at = datetime.fromisoformat(row[10]) if row[10] else None
                settings = json.loads(row[7]) if row[7] else None
                providers.append(APIProviderRecord(
                    id=row[0],
                    name=row[1],
                    display_name=row[2],
                    endpoint_url=row[3],
                    auth_type=row[4],
                    model_name=row[5],
                    base_url=row[6],
                    settings=settings,
                    is_active=bool(row[8]),
                    created_at=created_at,
                    updated_at=updated_at
                ))
            return providers

    def save_api_key(self, record: APIKeyRecord):
        """Save an API key record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO api_keys
                (id, provider_id, key_value, description, environment, is_active, last_used_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.id,
                record.provider_id,
                record.key_value,  # should be encrypted
                record.description,
                record.environment,
                record.is_active,
                record.last_used_at.isoformat() if record.last_used_at else None,
                record.created_at.isoformat(),
                record.updated_at.isoformat()
            ))

    def get_api_key(self, key_id: str) -> Optional[APIKeyRecord]:
        """Get an API key record by ID."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT * FROM api_keys WHERE id = ?', (key_id,)).fetchone()
            if row:
                created_at = datetime.fromisoformat(row[7]) if row[7] else None
                updated_at = datetime.fromisoformat(row[8]) if row[8] else None
                last_used_at = datetime.fromisoformat(row[6]) if row[6] else None
                return APIKeyRecord(
                    id=row[0],
                    provider_id=row[1],
                    key_value=row[2],
                    description=row[3],
                    environment=row[4],
                    is_active=bool(row[5]),
                    last_used_at=last_used_at,
                    created_at=created_at,
                    updated_at=updated_at
                )
        return None

    def get_api_keys_for_provider(self, provider_id: str, environment: str = "default") -> List[APIKeyRecord]:
        """Get active API key records for a provider and environment."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                'SELECT * FROM api_keys WHERE provider_id = ? AND environment = ? AND is_active = 1',
                (provider_id, environment)
            ).fetchall()
            keys = []
            for row in rows:
                created_at = datetime.fromisoformat(row[7]) if row[7] else None
                updated_at = datetime.fromisoformat(row[8]) if row[8] else None
                last_used_at = datetime.fromisoformat(row[6]) if row[6] else None
                keys.append(APIKeyRecord(
                    id=row[0],
                    provider_id=row[1],
                    key_value=row[2],
                    description=row[3],
                    environment=row[4],
                    is_active=bool(row[5]),
                    last_used_at=last_used_at,
                    created_at=created_at,
                    updated_at=updated_at
                ))
            return keys

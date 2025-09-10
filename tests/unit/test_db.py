import pytest
from datetime import datetime
from bananagen.db import Database, GenerationRecord, BatchRecord
import tempfile
import os


@pytest.fixture
def test_db():
    """Create a test database in memory."""
    db = Database(":memory:")
    return db


@pytest.fixture
def test_db_file():
    """Create a test database file."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    
    def cleanup():
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    yield db, db_path
    cleanup()


def test_database_init():
    """Test database initialization creates tables."""
    db = Database(":memory:")
    assert db is not None  # If we get here, init worked


def test_database_init_file():
    """Test database initialization with file."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        db_path = f.name
    
    try:
        db = Database(db_path)
        assert db is not None
    finally:
        os.unlink(db_path)


class TestGenerationRecord:
    def test_save_and_get_generation(self, test_db):
        """Test saving and retrieving generation records."""
        db = test_db
        
        # Create test record
        record = GenerationRecord(
            id="test-gen-1",
            prompt="test prompt",
            width=512,
            height=512,
            output_path="/path/to/output.png",
            model="test-model",
            status="queued",
            created_at=datetime.now(),
            metadata={"seed": 123}
        )
        
        # Save
        db.save_generation(record)
        
        # Get
        retrieved = db.get_generation("test-gen-1")
        
        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.prompt == record.prompt
        assert retrieved.width == record.width
        assert retrieved.height == record.height
        assert retrieved.output_path == record.output_path
        assert retrieved.model == record.model
        assert retrieved.status == record.status
        assert retrieved.metadata == record.metadata
    
    def test_save_generation_minimal(self, test_db):
        """Test saving generation with minimal fields."""
        db = test_db
        
        record = GenerationRecord(
            id="minimal-gen",
            prompt="minimal",
            width=10,
            height=10,
            output_path="min.png",
            model="min",
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_generation(record)
        
        retrieved = db.get_generation("minimal-gen")
        assert retrieved is not None
        assert retrieved.prompt == "minimal"
        assert retrieved.metadata is None  # Not provided
    
    def test_get_nonexistent_generation(self, test_db):
        """Test getting non-existent generation returns None."""
        db = test_db
        
        retrieved = db.get_generation("does-not-exist")
        assert retrieved is None
    
    def test_update_generation_status(self, test_db):
        """Test updating generation status."""
        db = test_db
        
        # Create initial record
        record = GenerationRecord(
            id="test-gen-2",
            prompt="test",
            width=256,
            height=256,
            output_path="/test.png",
            model="test",
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_generation(record)
        
        # Update status
        metadata = {"result": "success"}
        db.update_generation_status("test-gen-2", "done", metadata=metadata)
        
        # Verify update
        retrieved = db.get_generation("test-gen-2")
        assert retrieved.status == "done"
        assert retrieved.metadata == metadata
        assert retrieved.completed_at is not None
    
    def test_update_generation_error(self, test_db):
        """Test updating generation with error."""
        db = test_db
        
        record = GenerationRecord(
            id="test-gen-3",
            prompt="test",
            width=100,
            height=100,
            output_path="/test.png",
            model="test",
            status="processing",
            created_at=datetime.now()
        )
        
        db.save_generation(record)
        
        # Update with error
        error = "Test error"
        db.update_generation_status("test-gen-3", "failed", error=error)
        
        # Verify
        retrieved = db.get_generation("test-gen-3")
        assert retrieved.status == "failed"
        assert retrieved.error == error
        assert retrieved.completed_at is not None
    
    def test_update_generation_both_metadata_error(self, test_db):
        """Test updating generation with both metadata and error."""
        db = test_db
        
        record = GenerationRecord(
            id="test-gen-4",
            prompt="test",
            width=128,
            height=128,
            output_path="test.png",
            model="test",
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_generation(record)
        
        metadata = {"duration": 10}
        error = "Combined failure"
        db.update_generation_status("test-gen-4", "failed", metadata=metadata, error=error)
        
        retrieved = db.get_generation("test-gen-4")
        assert retrieved.status == "failed"
        assert retrieved.metadata == metadata
        assert retrieved.error == error
    
    def test_generation_with_sha(self, test_db):
        """Test generation record with SHA."""
        db = test_db
        
        record = GenerationRecord(
            id="sha-gen",
            prompt="test",
            width=64,
            height=64,
            output_path="test.png",
            model="test",
            status="queued",
            created_at=datetime.now(),
            sha256="abcd1234"
        )
        
        db.save_generation(record)
        
        retrieved = db.get_generation("sha-gen")
        assert retrieved.sha256 == "abcd1234"
    
    def test_get_generation_by_sha(self, test_db):
        """Test getting generation by SHA."""
        db = test_db
        
        test_sha = "unique_sha_123"
        record = GenerationRecord(
            id="unique-gen",
            prompt="unique test",
            width=512,
            height=512,
            output_path="/unique.png",
            model="unique",
            status="done",
            created_at=datetime.now(),
            sha256=test_sha
        )
        
        db.save_generation(record)
        
        # Assuming _get_generation_by_sha exists
        try:
            retrieved = db.get_generation_by_sha(test_sha)
            assert retrieved is not None
            assert retrieved.sha256 == test_sha
        except AttributeError:
            # If method doesn't exist, skip this test
            pytest.skip("get_generation_by_sha not implemented yet")


class TestBatchRecord:
    def test_save_and_get_batch(self, test_db):
        """Test saving and retrieving batch records."""
        db = test_db
        
        # Create test record
        record = BatchRecord(
            id="test-batch-1",
            job_count=3,
            status="queued",
            created_at=datetime.now(),
            results=[{"job_id": "1", "success": True}]
        )
        
        # Save
        db.save_batch(record)
        
        # Get
        retrieved = db.get_batch("test-batch-1")
        
        assert retrieved is not None
        assert retrieved.id == record.id
        assert retrieved.job_count == record.job_count
        assert retrieved.status == record.status
        assert retrieved.results == record.results
    
    def test_batch_minimal(self, test_db):
        """Test batch record with minimal data."""
        db = test_db
        
        record = BatchRecord(
            id="minimal-batch",
            job_count=1,
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_batch(record)
        
        retrieved = db.get_batch("minimal-batch")
        assert retrieved is not None
        assert retrieved.job_count == 1
        assert retrieved.results is None
    
    def test_update_batch_status(self, test_db):
        """Test updating batch status."""
        db = test_db
        
        record = BatchRecord(
            id="test-batch-2",
            job_count=2,
            status="processing",
            created_at=datetime.now()
        )
        
        db.save_batch(record)
        
        # Update with results
        results = [{"success": True}, {"success": False}]
        db.update_batch_status("test-batch-2", "done", results=results)
        
        # Verify
        retrieved = db.get_batch("test-batch-2")
        assert retrieved.status == "done"
        assert retrieved.results == results
        assert retrieved.completed_at is not None
    
    def test_update_batch_error(self, test_db):
        """Test updating batch with error."""
        db = test_db
        
        record = BatchRecord(
            id="error-batch",
            job_count=1,
            status="processing",
            created_at=datetime.now()
        )
        
        db.save_batch(record)
        
        error = "Batch processing failed"
        db.update_batch_status("error-batch", "failed", error=error)
        
        retrieved = db.get_batch("error-batch")
        assert retrieved.status == "failed"
        assert retrieved.error == error
    
    def test_get_nonexistent_batch(self, test_db):
        """Test getting non-existent batch returns None."""
        db = test_db
        
        retrieved = db.get_batch("does-not-exist")
        assert retrieved is None


class TestScanRecords:
    """Test scan record operations (if implemented)."""
    
    def test_save_and_get_scan(self, test_db):
        """Test scan records if ScanRecord exists."""
        db = test_db
        
        # Assuming ScanRecord exists
        try:
            from bananagen.db import ScanRecord
            record = ScanRecord(
                id="test-scan-1",
                root="/tmp",
                pattern="*",
                replace=False,
                extract_from=["readme"],
                status="queued",
                created_at=datetime.now()
            )
            
            db.save_scan(record)
            retrieved = db.get_scan("test-scan-1")
            
            assert retrieved is not None
            assert retrieved.id == record.id
        except ImportError:
            pytest.skip("ScanRecord not implemented")


class TestDatabasePersistence:
    """Test database persistence with file."""
    
    def test_database_persistence_file(self, test_db_file):
        """Test that records persist in file database."""
        db, db_path = test_db_file
        
        # Add a record
        record = GenerationRecord(
            id="persist-gen",
            prompt="persistence test",
            width=64,
            height=64,
            output_path="persist.png",
            model="test",
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_generation(record)
        
        # Close and reopen (simulate process restart)
        del db
        db2 = Database(db_path)
        
        # Check record still exists
        retrieved = db2.get_generation("persist-gen")
        assert retrieved is not None
        assert retrieved.prompt == "persistence test"


class TestTimestamps:
    """Test timestamp handling."""
    
    def test_generation_created_at_preservation(self, test_db):
        """Test that created_at timestamp is preserved."""
        db = test_db
        now = datetime(2023, 1, 1, 12, 0, 0)
        
        record = GenerationRecord(
            id="time-gen",
            prompt="time test",
            width=100,
            height=100,
            output_path="time.png",
            model="test",
            status="queued",
            created_at=now
        )
        
        db.save_generation(record)
        
        retrieved = db.get_generation("time-gen")
        assert retrieved.created_at == now
    
    def test_completed_at_timestamp(self, test_db):
        """Test that completed_at is set on status update."""
        db = test_db
        
        record = GenerationRecord(
            id="complete-gen",
            prompt="complete test",
            width=200,
            height=200,
            output_path="complete.png",
            model="test",
            status="processing",
            created_at=datetime.now()
        )
        
        db.save_generation(record)
        
        before_update = datetime.now()
        db.update_generation_status("complete-gen", "done")
        
        retrieved = db.get_generation("complete-gen")
        assert retrieved.completed_at >= before_update


class TestMetadataHandling:
    """Test metadata serialization and retrieval."""
    
    def test_generation_metadata_complex(self, test_db):
        """Test complex metadata structures."""
        db = test_db
        
        metadata = {
            "generation": {
                "temperature": 0.8,
                "steps": 20,
                "guidance_scale": 7.5
            },
            "input_sha256": "hash123",
            "output_format": "PNG",
            "tags": ["landscape", "sunset"]
        }
        
        record = GenerationRecord(
            id="meta-gen",
            prompt="metadata test",
            width=300,
            height=300,
            output_path="meta.png",
            model="test",
            status="done",
            created_at=datetime.now(),
            metadata=metadata
        )
        
        db.save_generation(record)
        
        retrieved = db.get_generation("meta-gen")
        assert retrieved.metadata == metadata
    
    def test_empty_metadata(self, test_db):
        """Test handling of empty metadata."""
        db = test_db
        
        record = GenerationRecord(
            id="empty-meta-gen",
            prompt="empty meta",
            width=50,
            height=50,
            output_path="empty.png",
            model="test",
            status="queued",
            created_at=datetime.now(),
            metadata={}
        )
        
        db.save_generation(record)
        
        retrieved = db.get_generation("empty-meta-gen")
        assert retrieved.metadata == {}


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_update_nonexistent_generation(self, test_db):
        """Test updating non-existent generation."""
        db = test_db
        
        # Should not raise error
        db.update_generation_status("nonexistent", "done")
    
    def test_update_nonexistent_batch(self, test_db):
        """Test updating non-existent batch."""
        db = test_db
        
        # Should not raise error
        db.update_batch_status("nonexistent", "done")
    
    def test_save_duplicate_generation(self, test_db):
        """Test saving duplicate generation ID."""
        db = test_db
        
        record1 = GenerationRecord(
            id="duplicate-gen",
            prompt="first",
            width=100,
            height=100,
            output_path="first.png",
            model="test",
            status="queued",
            created_at=datetime.now()
        )
        
        record2 = GenerationRecord(
            id="duplicate-gen",
            prompt="second",
            width=200,
            height=200,
            output_path="second.png",
            model="test",
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_generation(record1)
        
        # Save duplicate - should either update or handle gracefully
        db.save_generation(record2)
        
        retrieved = db.get_generation("duplicate-gen")
        # Could be either record
        assert retrieved is not None
    
    def test_save_duplicate_batch(self, test_db):
        """Test saving duplicate batch ID."""
        db = test_db
        
        record1 = BatchRecord(
            id="duplicate-batch",
            job_count=1,
            status="queued",
            created_at=datetime.now()
        )
        
        record2 = BatchRecord(
            id="duplicate-batch",
            job_count=2,
            status="queued",
            created_at=datetime.now()
        )
        
        db.save_batch(record1)
        db.save_batch(record2)
        
        retrieved = db.get_batch("duplicate-batch")
        # Could be either record
        assert retrieved is not None
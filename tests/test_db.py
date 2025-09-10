"""
Unit tests for bananagen database and metadata functionality.

These tests MUST FAIL initially (TDD approach).
Tests SQLite storage and metadata operations.
"""
import pytest
import tempfile
from pathlib import Path
import sqlite3
from datetime import datetime
import json

from bananagen.db import Database, GenerationRecord, BatchRecord


class TestDatabase:
    """Test database operations and metadata storage."""
    
    @pytest.fixture
    def db(self):
        """Create temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        database = Database(db_path)
        yield database
        
        # Cleanup
        Path(db_path).unlink(missing_ok=True)
    
    def test_database_initialization(self, db):
        """Test database initialization creates required tables."""
        # Check that tables exist
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()
        
        # Check generations table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='generations'")
        assert cursor.fetchone() is not None
        
        # Check batches table  
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='batches'")
        assert cursor.fetchone() is not None
        
        conn.close()
    
    def test_create_generation_record(self, db):
        """Test creating and storing a generation record."""
        record = GenerationRecord(
            id="gen_123",
            prompt="A beautiful landscape",
            width=1024,
            height=768,
            model="gemini-2.5-flash",
            output_path="/path/to/output.png",
            template_path="/path/to/template.png",
            metadata={
                "seed": 42,
                "temperature": 0.7,
                "response_id": "gemini_response_456"
            }
        )
        
        # Store record
        db.create_generation(record)
        
        # Retrieve and verify
        retrieved = db.get_generation("gen_123")
        assert retrieved is not None
        assert retrieved.id == "gen_123"
        assert retrieved.prompt == "A beautiful landscape"
        assert retrieved.width == 1024
        assert retrieved.height == 768
        assert retrieved.model == "gemini-2.5-flash"
        assert retrieved.metadata["seed"] == 42
    
    def test_get_generation_not_found(self, db):
        """Test retrieving non-existent generation returns None."""
        result = db.get_generation("nonexistent_id")
        assert result is None
    
    def test_list_generations(self, db):
        """Test listing generations with filtering."""
        # Create multiple records
        record1 = GenerationRecord(
            id="gen_1",
            prompt="First image", 
            width=512,
            height=512,
            model="gemini-2.5-flash",
            output_path="/path/1.png"
        )
        
        record2 = GenerationRecord(
            id="gen_2",
            prompt="Second image",
            width=1024,
            height=1024, 
            model="gemini-2.5-flash",
            output_path="/path/2.png"
        )
        
        db.create_generation(record1)
        db.create_generation(record2)
        
        # List all
        all_generations = db.list_generations()
        assert len(all_generations) == 2
        
        # List with limit
        limited = db.list_generations(limit=1)
        assert len(limited) == 1
        
        # List by model
        by_model = db.list_generations(model="gemini-2.5-flash")
        assert len(by_model) == 2
    
    def test_create_batch_record(self, db):
        """Test creating and storing a batch record."""
        batch_record = BatchRecord(
            id="batch_456",
            total_jobs=5,
            completed_jobs=3,
            failed_jobs=1,
            status="running",
            metadata={
                "concurrency": 2,
                "input_file": "jobs.json"
            }
        )
        
        # Store record
        db.create_batch(batch_record)
        
        # Retrieve and verify
        retrieved = db.get_batch("batch_456") 
        assert retrieved is not None
        assert retrieved.id == "batch_456"
        assert retrieved.total_jobs == 5
        assert retrieved.completed_jobs == 3
        assert retrieved.failed_jobs == 1
        assert retrieved.status == "running"
        assert retrieved.metadata["concurrency"] == 2
    
    def test_update_batch_status(self, db):
        """Test updating batch status and job counts."""
        # Create initial batch
        batch = BatchRecord(
            id="batch_update",
            total_jobs=10,
            completed_jobs=0,
            failed_jobs=0,
            status="pending"
        )
        db.create_batch(batch)
        
        # Update status
        db.update_batch_status(
            batch_id="batch_update",
            status="running",
            completed_jobs=5,
            failed_jobs=1
        )
        
        # Verify updates
        updated = db.get_batch("batch_update")
        assert updated.status == "running"
        assert updated.completed_jobs == 5
        assert updated.failed_jobs == 1
        assert updated.total_jobs == 10  # Should remain unchanged
    
    def test_generation_record_dataclass(self):
        """Test GenerationRecord dataclass functionality."""
        record = GenerationRecord(
            id="test_123",
            prompt="Test prompt",
            width=800,
            height=600,
            model="test-model",
            output_path="/test.png"
        )
        
        # Test required fields
        assert record.id == "test_123"
        assert record.prompt == "Test prompt"
        assert record.width == 800
        assert record.height == 600
        
        # Test optional fields with defaults
        assert record.template_path is None
        assert record.metadata == {}
        assert isinstance(record.created_at, datetime)
        
        # Test to_dict method
        record_dict = record.to_dict()
        assert "id" in record_dict
        assert "prompt" in record_dict
        assert "created_at" in record_dict
        
        # Test from_dict method
        reconstructed = GenerationRecord.from_dict(record_dict)
        assert reconstructed.id == record.id
        assert reconstructed.prompt == record.prompt
    
    def test_batch_record_dataclass(self):
        """Test BatchRecord dataclass functionality."""
        record = BatchRecord(
            id="batch_test",
            total_jobs=100,
            completed_jobs=75,
            failed_jobs=5,
            status="running"
        )
        
        assert record.id == "batch_test"
        assert record.total_jobs == 100
        assert record.completed_jobs == 75
        assert record.failed_jobs == 5
        assert record.status == "running"
        assert record.pending_jobs == 20  # total - completed - failed
        
        # Test to_dict
        batch_dict = record.to_dict()
        assert "pending_jobs" in batch_dict
        assert batch_dict["pending_jobs"] == 20
    
    def test_database_connection_error_handling(self):
        """Test database error handling for invalid paths."""
        # Test with invalid path
        with pytest.raises(Exception):  # Should raise connection error
            db = Database("/invalid/path/to/database.db")
            db.create_generation(GenerationRecord(
                id="test", 
                prompt="test", 
                width=100, 
                height=100, 
                model="test",
                output_path="test.png"
            ))
    
    def test_concurrent_access(self, db):
        """Test database handles concurrent operations safely."""
        import threading
        import time
        
        results = []
        
        def create_generation(gen_id):
            try:
                record = GenerationRecord(
                    id=f"gen_{gen_id}",
                    prompt=f"Prompt {gen_id}",
                    width=100,
                    height=100,
                    model="test",
                    output_path=f"test_{gen_id}.png"
                )
                db.create_generation(record)
                results.append(True)
            except Exception as e:
                results.append(False)
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_generation, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All operations should succeed
        assert all(results)
        assert len(results) == 5

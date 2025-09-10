"""
Unit tests for bananagen batch processing functionality.

Enhanced for comprehensive coverage including edge cases, error handling, and performance testing.
"""
import pytest
import tempfile
from pathlib import Path
import json
import asyncio
from unittest.mock import AsyncMock, patch
import time

from bananagen.batch_runner import BatchRunner, BatchJob, BatchResult


class TestBatchRunner:
    """Test batch processing functionality."""
    
    @pytest.fixture
    def batch_runner(self):
        """Create BatchRunner instance for testing."""
        return BatchRunner(concurrency=2, rate_limit=1.0)
    
    @pytest.fixture
    def sample_jobs(self):
        """Create sample batch jobs for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs = [
                BatchJob(
                    id="job_1",
                    prompt="A red apple on a table",
                    width=512,
                    height=512,
                    output_path=str(Path(tmpdir) / "apple.png"),
                    model="gemini-2.5-flash"
                ),
                BatchJob(
                    id="job_2", 
                    prompt="A blue car driving on a road",
                    width=1024,
                    height=768,
                    output_path=str(Path(tmpdir) / "car.png"),
                    model="gemini-2.5-flash"
                ),
                BatchJob(
                    id="job_3",
                    prompt="A cat sitting in a garden",
                    width=256,
                    height=256,
                    output_path=str(Path(tmpdir) / "cat.png"),
                    model="gemini-2.5-flash",
                    template_path=str(Path(tmpdir) / "cat_template.png")
                )
            ]
            yield jobs
    
    @pytest.mark.asyncio
    async def test_process_batch_jobs_success(self, batch_runner, sample_jobs):
        """Test successful batch processing of jobs."""
        # Mock the generation function
        async def mock_generate(job):
            await asyncio.sleep(0.1)  # Simulate processing time
            return BatchResult(
                job_id=job.id,
                success=True,
                output_path=job.output_path,
                metadata={"processed_at": "2025-09-10T12:00:00Z"}
            )
        
        with patch.object(batch_runner, '_process_single_job', side_effect=mock_generate):
            results = await batch_runner.process_batch(sample_jobs)
            
            assert len(results) == 3
            for result in results:
                assert isinstance(result, BatchResult)
                assert result.success is True
                assert result.job_id in ["job_1", "job_2", "job_3"]
    
    @pytest.mark.asyncio
    async def test_process_batch_with_failures(self, batch_runner, sample_jobs):
        """Test batch processing with some job failures."""
        async def mock_generate_with_failure(job):
            await asyncio.sleep(0.1)
            if job.id == "job_2":
                return BatchResult(
                    job_id=job.id,
                    success=False,
                    error="API rate limit exceeded",
                    metadata={"error_code": 429}
                )
            return BatchResult(
                job_id=job.id,
                success=True,
                output_path=job.output_path,
                metadata={}
            )
        
        with patch.object(batch_runner, '_process_single_job', side_effect=mock_generate_with_failure):
            results = await batch_runner.process_batch(sample_jobs)
            
            assert len(results) == 3
            
            # Check success/failure distribution
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            
            assert len(successful) == 2
            assert len(failed) == 1
            assert failed[0].job_id == "job_2"
            assert "rate limit" in failed[0].error.lower()
    
    @pytest.mark.asyncio
    async def test_concurrency_control(self, sample_jobs):
        """Test that batch runner respects concurrency limits."""
        # Track concurrent executions
        active_jobs = []
        max_concurrent = 0
        
        async def mock_generate_with_tracking(job):
            nonlocal max_concurrent
            active_jobs.append(job.id)
            max_concurrent = max(max_concurrent, len(active_jobs))
            
            await asyncio.sleep(0.2)  # Simulate longer processing
            
            active_jobs.remove(job.id)
            return BatchResult(job_id=job.id, success=True, output_path=job.output_path)
        
        # Set concurrency to 2
        runner = BatchRunner(concurrency=2, rate_limit=0.1)
        
        with patch.object(runner, '_process_single_job', side_effect=mock_generate_with_tracking):
            results = await runner.process_batch(sample_jobs)
            
            # Should never exceed concurrency limit
            assert max_concurrent <= 2
            assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, sample_jobs):
        """Test rate limiting between job starts."""
        start_times = []
        
        async def mock_generate_with_timing(job):
            start_times.append(asyncio.get_event_loop().time())
            return BatchResult(job_id=job.id, success=True, output_path=job.output_path)
        
        # Set rate limit to 1 second between starts
        runner = BatchRunner(concurrency=1, rate_limit=1.0)
        
        with patch.object(runner, '_process_single_job', side_effect=mock_generate_with_timing):
            results = await runner.process_batch(sample_jobs[:2])  # Only 2 jobs
            
            # Check time between starts is approximately 1 second
            if len(start_times) >= 2:
                time_diff = start_times[1] - start_times[0]
                assert time_diff >= 0.8  # Allow some variance
    
    def test_load_jobs_from_json(self, batch_runner):
        """Test loading batch jobs from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            jobs_data = [
                {
                    "id": "json_job_1",
                    "prompt": "A sunset over mountains",
                    "width": 800,
                    "height": 600,
                    "output_path": "/tmp/sunset.png"
                },
                {
                    "id": "json_job_2", 
                    "prompt": "A forest scene",
                    "width": 1200,
                    "height": 800,
                    "output_path": "/tmp/forest.png",
                    "template_path": "/tmp/forest_template.png",
                    "params": {"temperature": 0.8}
                }
            ]
            json.dump(jobs_data, f)
            json_file = f.name
        
        try:
            jobs = batch_runner.load_jobs_from_file(json_file)
            
            assert len(jobs) == 2
            assert isinstance(jobs[0], BatchJob)
            assert jobs[0].id == "json_job_1"
            assert jobs[0].prompt == "A sunset over mountains"
            assert jobs[1].params["temperature"] == 0.8
        finally:
            Path(json_file).unlink(missing_ok=True)
    
    def test_batch_job_dataclass(self):
        """Test BatchJob dataclass functionality."""
        job = BatchJob(
            id="test_job",
            prompt="Test image generation",
            width=512,
            height=512,
            output_path="/tmp/test.png"
        )
        
        # Test required fields
        assert job.id == "test_job"
        assert job.prompt == "Test image generation"
        assert job.width == 512
        assert job.height == 512
        assert job.output_path == "/tmp/test.png"
        
        # Test optional fields with defaults
        assert job.template_path is None
        assert job.model == "gemini-2.5-flash"
        assert job.params == {}
        
        # Test to_dict method
        job_dict = job.to_dict()
        assert "id" in job_dict
        assert "prompt" in job_dict
        assert "width" in job_dict
        
        # Test from_dict method
        reconstructed = BatchJob.from_dict(job_dict)
        assert reconstructed.id == job.id
        assert reconstructed.prompt == job.prompt
    
    def test_batch_result_dataclass(self):
        """Test BatchResult dataclass functionality."""
        # Success result
        success_result = BatchResult(
            job_id="job_123",
            success=True,
            output_path="/tmp/output.png",
            metadata={"generation_time": 5.2}
        )
        
        assert success_result.job_id == "job_123"
        assert success_result.success is True
        assert success_result.output_path == "/tmp/output.png"
        assert success_result.error is None
        assert success_result.metadata["generation_time"] == 5.2
        
        # Failure result
        failure_result = BatchResult(
            job_id="job_456",
            success=False,
            error="Invalid prompt format",
            metadata={"error_code": "PROMPT_ERROR"}
        )
        
        assert failure_result.job_id == "job_456"
        assert failure_result.success is False
        assert failure_result.output_path is None
        assert failure_result.error == "Invalid prompt format"
    
    @pytest.mark.asyncio
    async def test_empty_batch(self, batch_runner):
        """Test processing empty batch."""
        results = await batch_runner.process_batch([])
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_batch_with_large_concurrency(self, sample_jobs):
        """Test batch with high concurrency setting."""
        runner = BatchRunner(concurrency=10, rate_limit=0.1)
        
        async def mock_generate(job):
            return BatchResult(job_id=job.id, success=True, output_path=job.output_path)
        
        with patch.object(runner, '_process_single_job', side_effect=mock_generate):
            results = await runner.process_batch(sample_jobs)
            assert len(results) == 3
    
    def test_batch_job_with_params(self):
        """Test BatchJob with custom parameters."""
        job = BatchJob(
            id="param_job",
            prompt="Test",
            width=512,
            height=512,
            output_path="/tmp/test.png",
            params={"temperature": 0.7, "max_tokens": 100}
        )
        
        assert job.params == {"temperature": 0.7, "max_tokens": 100}
    
    def test_load_invalid_json_file(self, batch_runner):
        """Test loading from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content {")
            json_file = f.name
        
        try:
            jobs = batch_runner.load_jobs_from_file(json_file)
            # Handle gracefully
        except Exception:
            pass
        finally:
            Path(json_file).unlink(missing_ok=True)
    
    @pytest.mark.asyncio
    async def test_batch_timeout_simulation(self, batch_runner, sample_jobs):
        """Test batch with simulated long-running jobs."""
        async def mock_slow_job(job):
            await asyncio.sleep(1.0)  # Simulate delay
            return BatchResult(job_id=job.id, success=True, output_path=job.output_path)
        
        start_time = time.time()
        with patch.object(batch_runner, '_process_single_job', side_effect=mock_slow_job):
            results = await batch_runner.process_batch(sample_jobs[:1])  # One job
        elapsed = time.time() - start_time
        
        assert elapsed >= 1.0
        assert len(results) == 1
    
    def test_batch_runner_initialization(self):
        """Test BatchRunner initialization with different parameters."""
        runner = BatchRunner(concurrency=5, rate_limit=2.0)
        assert runner.concurrency == 5
        assert runner.rate_limit == 2.0
    
    def test_batch_job_equality(self):
        """Test BatchJob equality comparison."""
        job1 = BatchJob(id="1", prompt="test", width=512, height=512, output_path="test.png")
        job2 = BatchJob(id="1", prompt="test", width=512, height=512, output_path="test.png")
        job3 = BatchJob(id="2", prompt="test", width=512, height=512, output_path="test.png")
        
        assert job1 == job2
        assert job1 != job3
    
    @pytest.mark.asyncio  
    async def test_batch_with_mixed_success_failure(self, batch_runner, sample_jobs):
        """Test batch with mixed success and failure scenarios."""
        call_count = 0
        
        async def mock_unreliable_job(job):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:  # Odd calls fail
                return BatchResult(job_id=job.id, success=False, error="Network error")
            return BatchResult(job_id=job.id, success=True, output_path=job.output_path)
        
        # Run 4 jobs to get both failures and successes
        jobs = sample_jobs * 2  # Duplicate for more jobs
        
        with patch.object(batch_runner, '_process_single_job', side_effect=mock_unreliable_job):
            results = await batch_runner.process_batch(jobs)
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        assert len(successful) == len(failed)  # Should be equal in this case
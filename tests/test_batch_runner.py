"""
Unit tests for bananagen batch processing functionality.

These tests MUST FAIL initially (TDD approach).
Tests batch job processing with concurrency and rate limiting.
"""
import pytest
import tempfile
from pathlib import Path
import json
import asyncio
from unittest.mock import AsyncMock, patch

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
            import time
            start_times.append(time.time())
            return BatchResult(job_id=job.id, success=True, output_path=job.output_path)
        
        # Set rate limit to 2 seconds between starts
        runner = BatchRunner(concurrency=1, rate_limit=2.0)
        
        with patch.object(runner, '_process_single_job', side_effect=mock_generate_with_timing):
            start_time = asyncio.get_event_loop().time()
            results = await runner.process_batch(sample_jobs[:2])  # Only 2 jobs
            
            # Check time between starts is approximately 2 seconds
            if len(start_times) >= 2:
                time_diff = start_times[1] - start_times[0]
                assert time_diff >= 1.8  # Allow some variance
    
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
    
    def test_load_jobs_from_csv(self, batch_runner):
        """Test loading batch jobs from CSV file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_content = '''id,prompt,width,height,output_path
csv_job_1,"A mountain landscape",640,480,/tmp/mountain.png
csv_job_2,"A beach scene",1920,1080,/tmp/beach.png'''
            f.write(csv_content)
            csv_file = f.name
        
        try:
            jobs = batch_runner.load_jobs_from_file(csv_file)
            
            assert len(jobs) == 2
            assert jobs[0].id == "csv_job_1"
            assert jobs[0].width == 640
            assert jobs[1].height == 1080
        finally:
            Path(csv_file).unlink(missing_ok=True)
    
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
    async def test_retry_logic(self, batch_runner, sample_jobs):
        """Test retry logic for failed jobs."""
        attempt_count = {}
        
        async def mock_generate_with_retries(job):
            if job.id not in attempt_count:
                attempt_count[job.id] = 0
            attempt_count[job.id] += 1
            
            # Fail first two attempts, succeed on third
            if attempt_count[job.id] < 3:
                return BatchResult(
                    job_id=job.id,
                    success=False,
                    error="Temporary failure",
                    metadata={"attempt": attempt_count[job.id]}
                )
            
            return BatchResult(
                job_id=job.id,
                success=True,
                output_path=job.output_path,
                metadata={"attempt": attempt_count[job.id]}
            )
        
        # Configure batch runner with retries
        runner = BatchRunner(concurrency=1, rate_limit=0.1, max_retries=3)
        
        with patch.object(runner, '_process_single_job', side_effect=mock_generate_with_retries):
            results = await runner.process_batch([sample_jobs[0]])  # Test with one job
            
            assert len(results) == 1
            result = results[0]
            assert result.success is True
            assert attempt_count[sample_jobs[0].id] == 3
    
    def test_batch_progress_tracking(self, batch_runner, sample_jobs):
        """Test batch progress tracking and callbacks."""
        progress_updates = []
        
        def progress_callback(completed, total, current_job):
            progress_updates.append({
                "completed": completed,
                "total": total,
                "current_job": current_job.id if current_job else None,
                "percentage": (completed / total) * 100
            })
        
        batch_runner.set_progress_callback(progress_callback)
        
        # This would be tested with actual batch processing
        # For now, test the callback mechanism exists
        assert hasattr(batch_runner, 'set_progress_callback')
        assert batch_runner.progress_callback == progress_callback

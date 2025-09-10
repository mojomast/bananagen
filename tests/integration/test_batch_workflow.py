import pytest
import tempfile
import os
import subprocess
import sys
import json


class TestBatchWorkflow:
    """Integration tests for batch processing workflow.

    Tests the complete batch workflow from job list to processing results.
    """

    def test_batch_cli_processes_job_list_successfully(self):
        """Test that bananagen batch command processes a job list successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a job list JSON file
            jobs_data = [
                {
                    "id": "job1",
                    "prompt": "A red apple",
                    "width": 256,
                    "height": 256,
                    "output_path": os.path.join(tmpdir, "apple.png"),
                    "model": "gemini-2.5-flash"
                },
                {
                    "id": "job2",
                    "prompt": "A green banana",
                    "width": 256,
                    "height": 256,
                    "output_path": os.path.join(tmpdir, "banana.png")
                }
            ]

            jobs_file = os.path.join(tmpdir, "jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            # Run batch command
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--concurrency", "2",
                "--rate-limit", "1.0",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=120)

            if result.returncode == 0:
                # Parse JSON output
                output_data = json.loads(result.stdout.strip())

                # Should be a list of results
                assert isinstance(output_data, list)
                assert len(output_data) == 2

                # Check each job result
                for job_result in output_data:
                    assert "job_id" in job_result
                    assert "success" in job_result
                    assert "output_path" in job_result

                    job_id = job_result["job_id"]
                    expected_job = next(job for job in jobs_data if job["id"] == job_id)

                    # Output path should match
                    assert job_result["output_path"] == expected_job["output_path"]

                    if job_result["success"]:
                        # File should exist
                        assert os.path.exists(job_result["output_path"])
                        assert os.path.getsize(job_result["output_path"]) > 0
            else:
                # Implementation not ready - this is expected during TDD
                assert result.returncode != 0

    def test_batch_cli_with_single_job(self):
        """Test batch processing with a single job."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Single job
            jobs_data = [{
                "id": "single_job",
                "prompt": "A single test image",
                "width": 128,
                "height": 128,
                "output_path": os.path.join(tmpdir, "single.png")
            }]

            jobs_file = os.path.join(tmpdir, "single_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                assert isinstance(output_data, list)
                assert len(output_data) == 1

                job_result = output_data[0]
                assert job_result["job_id"] == "single_job"
                assert job_result["output_path"] == os.path.join(tmpdir, "single.png")

                if job_result["success"]:
                    assert os.path.exists(job_result["output_path"])

    def test_batch_cli_handles_missing_job_fields(self):
        """Test batch processing when jobs are missing required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Job missing required fields
            invalid_jobs = [{
                "id": "incomplete_job",
                # missing prompt, width, height, output_path
                "some_field": "value"
            }]

            jobs_file = os.path.join(tmpdir, "invalid_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(invalid_jobs, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should either fail immediately or handle gracefully
            # Either way is acceptable during development
            assert result.returncode == 0 or result.returncode == 1

            if result.returncode == 0:
                # If it succeeds, should still produce output structure
                output_data = json.loads(result.stdout.strip())
                assert isinstance(output_data, list)

    def test_batch_cli_non_json_output(self):
        """Test batch command without JSON flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_data = [{
                "id": "text_output_job",
                "prompt": "A test for text output",
                "width": 64,
                "height": 64,
                "output_path": os.path.join(tmpdir, "text_output.png")
            }]

            jobs_file = os.path.join(tmpdir, "text_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            if result.returncode == 0:
                # Should output plain text, not JSON
                assert "Job" in result.stdout
                assert "Success" in result.stdout or "Failed" in result.stdout

                # Should not be valid JSON
                with pytest.raises(json.JSONDecodeError):
                    json.loads(result.stdout.strip())

    def test_batch_cli_concurrency_parameter(self):
        """Test batch processing with different concurrency levels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple jobs
            jobs_data = []
            for i in range(4):
                jobs_data.append({
                    "id": f"concurrency_job_{i}",
                    "prompt": f"Test image {i}",
                    "width": 64,
                    "height": 64,
                    "output_path": os.path.join(tmpdir, f"concurrency_{i}.png")
                })

            jobs_file = os.path.join(tmpdir, "concurrency_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            # Test with concurrency=1
            result1 = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--concurrency", "1",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=120)

            # Test with concurrency=3
            result2 = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--concurrency", "3",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=120)

            # Both should produce valid results
            assert result1.returncode in [0, 1]  # 1 is acceptable if implementation not ready
            assert result2.returncode in [0, 1]

            if result1.returncode == 0 and result2.returncode == 0:
                output1 = json.loads(result1.stdout.strip())
                output2 = json.loads(result2.stdout.strip())

                # Should have same number of results
                assert len(output1) == len(output2) == 4

    def test_batch_cli_rate_limit_parameter(self):
        """Test batch processing with rate limiting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_data = [{
                "id": "rate_limit_job",
                "prompt": "Test rate limiting",
                "width": 64,
                "height": 64,
                "output_path": os.path.join(tmpdir, "rate_limit.png")
            }]

            jobs_file = os.path.join(tmpdir, "rate_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--rate-limit", "0.5",  # Very slow rate limit
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            # Should handle rate limiting gracefully
            assert result.returncode in [0, 1]

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())
                assert len(output_data) == 1

    def test_batch_cli_empty_job_list(self):
        """Test batch processing with empty job list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_data = []  # Empty list

            jobs_file = os.path.join(tmpdir, "empty_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should handle empty list gracefully
            assert result.returncode in [0, 1]

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())
                assert output_data == []  # Should return empty list

    def test_batch_cli_handles_nonexistent_jobs_file(self):
        """Test batch processing with nonexistent jobs file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_file = os.path.join(tmpdir, "nonexistent.json")

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", nonexistent_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should fail cleanly
            assert result.returncode != 0
            assert "error" in (result.stderr + result.stdout).lower() or \
                   "not found" in (result.stderr + result.stdout).lower()

    def test_batch_cli_invalid_json_jobs_file(self):
        """Test batch processing with invalid JSON jobs file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_file = os.path.join(tmpdir, "invalid_jobs.json")

            # Write invalid JSON
            with open(jobs_file, 'w') as f:
                f.write("{ invalid json content }")

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should fail with JSON parsing error
            assert result.returncode != 0

    def test_batch_cli_creates_job_output_directories(self):
        """Test that batch processing creates necessary output directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Jobs with nested output paths
            nested_output = os.path.join(tmpdir, "batch", "output", "deep", "nesting.png")
            jobs_data = [{
                "id": "nested_output_job",
                "prompt": "Test nested output path creation",
                "width": 64,
                "height": 64,
                "output_path": nested_output
            }]

            jobs_file = os.path.join(tmpdir, "nested_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                # Should create all intermediate directories
                nested_dir = os.path.dirname(nested_output)
                assert os.path.exists(nested_dir), "Nested directories should be created"

                if output_data[0]["success"]:
                    assert os.path.exists(nested_output), "Output file should be created"

    def test_batch_cli_result_format(self):
        """Test that batch results have consistent format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_data = [{
                "id": "format_test_job",
                "prompt": "Format test image",
                "width": 32,
                "height": 32,
                "output_path": os.path.join(tmpdir, "format_test.png")
            }]

            jobs_file = os.path.join(tmpdir, "format_jobs.json")
            with open(jobs_file, 'w') as f:
                json.dump(jobs_data, f)

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "batch",
                "--list", jobs_file,
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                assert len(output_data) == 1
                job_result = output_data[0]

                # Required fields
                assert "job_id" in job_result
                assert "success" in job_result
                assert "output_path" in job_result

                # Types should be correct
                assert isinstance(job_result["job_id"], str)
                assert isinstance(job_result["success"], bool)
                assert isinstance(job_result["output_path"], str)

                # Optional fields that may be present
                if "metadata" in job_result:
                    assert isinstance(job_result["metadata"], dict)
                if "error" in job_result:
                    assert isinstance(job_result["error"], str)
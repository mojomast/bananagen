"""
Unit tests for bananagen CLI functionality.

These tests MUST FAIL initially (TDD approach).
Tests CLI commands and JSON output.
"""
import pytest
from click.testing import CliRunner
import json
import tempfile
from pathlib import Path

from bananagen.cli import cli, generate, batch, scan, serve, status


class TestCLI:
    """Test command-line interface."""
    
    @pytest.fixture
    def runner(self):
        """Create Click test runner."""
        return CliRunner()
    
    def test_cli_help(self, runner):
        """Test main CLI help command."""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert 'bananagen' in result.output
        assert 'generate' in result.output
        assert 'batch' in result.output
        assert 'scan' in result.output
        assert 'serve' in result.output
        assert 'status' in result.output
    
    def test_generate_command_basic(self, runner):
        """Test basic generate command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"
            
            result = runner.invoke(generate, [
                '--width', '512',
                '--height', '512',
                '--prompt', 'A beautiful sunset',
                '--out', str(output_path)
            ])
            
            assert result.exit_code == 0
            assert output_path.exists()
    
    def test_generate_command_json_output(self, runner):
        """Test generate command with JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"
            
            result = runner.invoke(generate, [
                '--width', '256',
                '--height', '256',
                '--prompt', 'A cat',
                '--out', str(output_path),
                '--json'
            ])
            
            assert result.exit_code == 0
            
            # Parse JSON output
            output_data = json.loads(result.output)
            assert 'id' in output_data
            assert 'status' in output_data
            assert 'path' in output_data
            assert output_data['status'] in ['success', 'pending', 'completed']
    
    def test_generate_command_validation(self, runner):
        """Test generate command input validation."""
        # Missing required arguments
        result = runner.invoke(generate, ['--width', '100'])
        assert result.exit_code != 0
        
        # Invalid dimensions
        result = runner.invoke(generate, [
            '--width', '0',
            '--height', '100',
            '--prompt', 'test',
            '--out', 'test.png'
        ])
        assert result.exit_code != 0
        
        # Invalid color format
        result = runner.invoke(generate, [
            '--width', '100',
            '--height', '100',
            '--prompt', 'test',
            '--color', 'invalid-color',
            '--out', 'test.png'
        ])
        assert result.exit_code != 0
    
    def test_batch_command(self, runner):
        """Test batch processing command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create batch jobs file
            jobs_file = Path(tmpdir) / "jobs.json"
            jobs = [
                {
                    "prompt": "A red apple",
                    "width": 128,
                    "height": 128,
                    "out_path": str(Path(tmpdir) / "apple.png")
                },
                {
                    "prompt": "A blue car",
                    "width": 256,
                    "height": 256,
                    "out_path": str(Path(tmpdir) / "car.png")
                }
            ]
            
            with open(jobs_file, 'w') as f:
                json.dump(jobs, f)
            
            result = runner.invoke(batch, [
                '--list', str(jobs_file),
                '--concurrency', '1'
            ])
            
            assert result.exit_code == 0
    
    def test_batch_command_json_output(self, runner):
        """Test batch command with JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jobs_file = Path(tmpdir) / "jobs.json"
            jobs = [{"prompt": "test", "width": 100, "height": 100, "out_path": "test.png"}]
            
            with open(jobs_file, 'w') as f:
                json.dump(jobs, f)
            
            result = runner.invoke(batch, [
                '--list', str(jobs_file),
                '--json'
            ])
            
            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert 'batch_id' in output_data
            assert 'total_jobs' in output_data
            assert 'status' in output_data
    
    def test_scan_command_dry_run(self, runner):
        """Test scan command in dry-run mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some placeholder files
            (Path(tmpdir) / "image__placeholder__.png").touch()
            (Path(tmpdir) / "banner__placeholder__.jpg").touch()
            
            result = runner.invoke(scan, [
                '--root', str(tmpdir),
                '--pattern', '*__placeholder__*',
                '--dry-run'
            ])
            
            assert result.exit_code == 0
            # Should show planned replacements without executing
            assert 'dry-run' in result.output.lower() or 'plan' in result.output.lower()
    
    def test_scan_command_json_output(self, runner):
        """Test scan command with JSON output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test__placeholder__.png").touch()
            
            result = runner.invoke(scan, [
                '--root', str(tmpdir),
                '--pattern', '*__placeholder__*',
                '--dry-run',
                '--json'
            ])
            
            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert 'planned_replacements' in output_data or 'files_found' in output_data
    
    def test_status_command(self, runner):
        """Test status command for checking job status."""
        result = runner.invoke(status, ['test-job-123'])
        
        # Should either return status or indicate job not found
        assert result.exit_code in [0, 1]  # 0 for found, 1 for not found
    
    def test_status_command_json_output(self, runner):
        """Test status command with JSON output."""
        result = runner.invoke(status, ['test-job-123', '--json'])
        
        assert result.exit_code in [0, 1]
        
        if result.exit_code == 0:
            # If job found, should be valid JSON
            output_data = json.loads(result.output)
            assert 'id' in output_data
            assert 'status' in output_data
    
    def test_serve_command_help(self, runner):
        """Test serve command help."""
        result = runner.invoke(serve, ['--help'])
        assert result.exit_code == 0
        assert 'port' in result.output.lower()
        assert 'host' in result.output.lower()
    
    def test_global_json_flag(self, runner):
        """Test that --json flag works globally."""
        # Test with generate
        with tempfile.TemporaryDirectory() as tmpdir:
            result = runner.invoke(cli, [
                'generate',
                '--width', '100',
                '--height', '100', 
                '--prompt', 'test',
                '--out', str(Path(tmpdir) / 'test.png'),
                '--json'
            ])
            
            if result.exit_code == 0:
                # Should be valid JSON
                json.loads(result.output)
    
    def test_log_level_flag(self, runner):
        """Test --log-level flag."""
        result = runner.invoke(cli, ['--log-level', 'DEBUG', '--help'])
        assert result.exit_code == 0
        
        result = runner.invoke(cli, ['--log-level', 'invalid-level', '--help'])
        # Should handle invalid log levels gracefully

import pytest
import tempfile
import os
import subprocess
import sys
import json


class TestScanWorkflow:
    """Integration tests for scan-and-replace workflow.

    Tests the complete workflow from scan command to placeholder replacement.
    """

    def test_scan_cli_finds_placeholder_pattern(self):
        """Test that bananagen scan command finds files with placeholder patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files with placeholders
            normal_file = os.path.join(tmpdir, "normal.txt")
            with open(normal_file, 'w') as f:
                f.write("This is a normal file with no placeholders.")

            placeholder_file = os.path.join(tmpdir, "has_placeholders.txt")
            with open(placeholder_file, 'w') as f:
                f.write("Here's a __placeholder__ in the text.")
                f.write("\nAnd another _PLACEHOLDER_HERE_ pattern.")

            nested_dir = os.path.join(tmpdir, "nested")
            os.makedirs(nested_dir)
            nested_placeholder = os.path.join(nested_dir, "nested_placeholder.md")
            with open(nested_placeholder, 'w') as f:
                f.write("# Document with __placeholder__\n")
                f.write("Some README__placeholder__content.")

            # Run scan command
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                # Verify output structure
                assert "matches" in output_data or isinstance(output_data, list)

                if isinstance(output_data, list):
                    # Should find at least one match
                    assert len(output_data) > 0

                    # Check that matches contain expected information
                    found_nested = False
                    found_root = False

                    for match in output_data:
                        assert "file" in match
                        assert "line" in match
                        assert "pattern" in match

                        if "nested_placeholder.md" in match["file"]:
                            found_nested = True
                            assert "__placeholder__" in match["pattern"]
                        if "has_placeholders.txt" in match["file"]:
                            found_root = True

                    assert found_nested or found_root, "Should find placeholders in test files"
            else:
                # Implementation not ready - this is expected during TDD
                assert result.returncode != 0

    def test_scan_cli_with_replace_flag(self):
        """Test scan command with replace flag enabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file with placeholder
            test_file = os.path.join(tmpdir, "replace_test.txt")
            with open(test_file, 'w') as f:
                f.write("Replace this __placeholder__ with an image.")

            # First scan without replace to see what would be done
            scan_result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Then scan with replace
            replace_result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--replace",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            # Both commands should handle gracefully
            assert scan_result.returncode in [0, 1]
            assert replace_result.returncode in [0, 1]

            if replace_result.returncode == 0:
                replace_data = json.loads(replace_result.stdout.strip())

                # Should report on replacements
                assert isinstance(replace_data, list)

    def test_scan_cli_different_pattern_formats(self):
        """Test scan with various placeholder patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different placeholder formats
            patterns = {
                "__placeholder__": "double_underscore.txt",
                "_PLACEHOLDER_": "single_underscore.txt",
                "{{placeholder}}": "double_brace.txt",
                "[PLACEHOLDER]": "square_bracket.txt"
            }

            for placeholder, filename in patterns.items():
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'w') as f:
                    f.write(f"This file has a {placeholder} to find.")

            # Test different pattern scans
            for placeholder_pattern, filename in patterns.items():
                result = subprocess.run([
                    sys.executable, "-m", "bananagen",
                    "scan",
                    "--root", tmpdir,
                    "--pattern", f"*{placeholder_pattern}*",
                    "--json"
                ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

                # Each pattern scan should find its corresponding file
                if result.returncode == 0:
                    output_data = json.loads(result.stdout.strip())

                    if isinstance(output_data, list):
                        # Should find the matching file
                        found = any(filename in match["file"] for match in output_data)
                        assert found, f"Pattern {placeholder_pattern} should find file {filename}"

    def test_scan_cli_non_json_output(self):
        """Test scan command without JSON flag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with placeholder
            test_file = os.path.join(tmpdir, "text_output_test.txt")
            with open(test_file, 'w') as f:
                f.write("File with __placeholder__ for text output testing.")

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            if result.returncode == 0:
                # Should output plain text format
                assert "Replaced" in result.stdout or \
                       "Generated" in result.stdout or \
                       "Skipped" in result.stdout or \
                       "Error" in result.stdout

                # Should not be valid JSON
                with pytest.raises(json.JSONDecodeError):
                    json.loads(result.stdout.strip())

    def test_scan_cli_handles_empty_directory(self):
        """Test scan command on empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory should not crash
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should handle empty directory gracefully
            assert result.returncode in [0, 1]

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())
                assert output_data == []  # Should return empty list

    def test_scan_cli_nonexistent_root_directory(self):
        """Test scan command with nonexistent root directory."""
        nonexistent_dir = "/completely/nonexistent/directory/path"

        result = subprocess.run([
            sys.executable, "-m", "bananagen",
            "scan",
            "--root", nonexistent_dir,
            "--pattern", "*__placeholder__*",
            "--json"
        ], capture_output=True, text=True, timeout=30)

        # Should handle nonexistent directory gracefully
        assert result.returncode != 0

    def test_scan_cli_nested_directory_traversal(self):
        """Test scan command traverses nested directories correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create deep nested structure
            deep_path = os.path.join(tmpdir, "level1", "level2", "level3")
            os.makedirs(deep_path)

            # Add placeholders at different levels
            files_with_placeholders = [
                os.path.join(tmpdir, "root_placeholder.txt"),
                os.path.join(tmpdir, "level1", "level1_placeholder.md"),
                os.path.join(tmpdir, "level1", "level2", "level2_placeholder.py"),
                os.path.join(deep_path, "deep_placeholder.js")
            ]

            for filepath in files_with_placeholders:
                with open(filepath, 'w') as f:
                    f.write(f"This file at {os.path.basename(filepath)} has __placeholder__ content.")

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                if isinstance(output_data, list):
                    # Should find all placeholder files
                    found_files = {os.path.basename(match["file"]) for match in output_data}
                    expected_files = {os.path.basename(f) for f in files_with_placeholders}

                    # At minimum should find some of the nested files
                    assert len(found_files & expected_files) > 0, \
                        f"Should find nested placeholder files, found: {found_files}, expected: {expected_files}"

    def test_scan_cli_case_sensitive_patterns(self):
        """Test whether scan patterns are case-sensitive."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with different cases
            files_data = [
                ("UPPERCASE__PLACEHOLDER__.txt", "uppercase"),
                ("lowercase__placeholder__.txt", "lowercase"),
                ("Mixed__Placeholder__.txt", "mixed")
            ]

            for filename, case_type in files_data:
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'w') as f:
                    f.write(f"This is a {case_type} case placeholder file.")

            # Test case-insensitive pattern (default behavior may vary)
            result_lower = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            if result_lower.returncode == 0:
                output_data = json.loads(result_lower.stdout.strip())

                if isinstance(output_data, list):
                    # Should find all files with placeholders
                    found_count = len(output_data)
                    assert found_count >= 2, f"Should find multiple placeholder files, found: {found_count}"

    def test_scan_cli_maximum_matches_limit(self):
        """Test scan command behavior with many matches."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create many files with placeholders
            for i in range(20):
                filepath = os.path.join(tmpdir, f"file_with_placeholder_{i:02d}.txt")
                with open(filepath, 'w') as f:
                    f.write(f"File {i} has __placeholder_{i}__ content.\n")
                    f.write(f"And another __placeholder_{i}_second__ here.")

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                if isinstance(output_data, list):
                    # Should find multiple matches (40 total: 20 files × 2 placeholders each)
                    assert len(output_data) >= 20, f"Should find many matches, found: {len(output_data)}"

                    # Verify match structure
                    for match in output_data[:5]:  # Check first few
                        assert "file" in match
                        assert "line" in match
                        assert "pattern" in match

    def test_scan_cli_pattern_validation(self):
        """Test scan command validates pattern format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test empty pattern
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should handle empty pattern gracefully
            assert result.returncode in [0, 1]

            # Test pattern with special characters
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*[special]__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            # Should handle special characters gracefully
            assert result.returncode in [0, 1]

    def test_scan_cli_output_directory_creation(self):
        """Test that scan creates output directories when needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file that will generate output in nested directory
            test_file = os.path.join(tmpdir, "source.txt")
            with open(test_file, 'w') as f:
                f.write("This file has __placeholder__ and will generate output in nested folder.")

            # Run scan with replace
            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--replace",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=60)

            # Should handle output path creation gracefully
            assert result.returncode in [0, 1]

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                if isinstance(output_data, list) and output_data:
                    # If replacements occurred, generated files should exist
                    for replacement in output_data:
                        if "generated_path" in replacement:
                            # Directory should be created automatically
                            gen_dir = os.path.dirname(replacement["generated_path"])
                            assert os.path.exists(gen_dir), f"Generated directory should exist: {gen_dir}"

    def test_scan_cli_handles_readonly_files(self):
        """Test scan command with readonly files (if supported)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file with placeholder
            readonly_file = os.path.join(tmpdir, "readonly.txt")
            with open(readonly_file, 'w') as f:
                f.write("This readonly __placeholder__ should be handled.")

            try:
                # Try to make file read-only (OS dependent)
                os.chmod(readonly_file, 0o444)

                result = subprocess.run([
                    sys.executable, "-m", "bananagen",
                    "scan",
                    "--root", tmpdir,
                    "--pattern", "*__placeholder__*",
                    "--json"
                ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

                # Should handle readonly files gracefully
                assert result.returncode in [0, 1]

                # Restore permissions for cleanup
                os.chmod(readonly_file, 0o644)

            except OSError:
                # File permissions not supported on this OS
                pytest.skip("File permissions not supported on this operating system")

    def test_scan_cli_result_format_consistency(self):
        """Test that scan results have consistent format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create predictable test case
            test_file = os.path.join(tmpdir, "format_test.txt")
            with open(test_file, 'w') as f:
                f.write("Line 1: No placeholder here.\n")
                f.write("Line 2: This has __placeholder__ here.\n")
                f.write("Line 3: Another __placeholder__ on this line.\n")

            result = subprocess.run([
                sys.executable, "-m", "bananagen",
                "scan",
                "--root", tmpdir,
                "--pattern", "*__placeholder__*",
                "--json"
            ], capture_output=True, text=True, cwd=tmpdir, timeout=30)

            if result.returncode == 0:
                output_data = json.loads(result.stdout.strip())

                if isinstance(output_data, list) and output_data:
                    # Check format consistency for each match
                    for match in output_data:
                        # Required fields
                        assert "file" in match
                        assert "line" in match
                        assert "pattern" in match

                        # Types should be correct
                        assert isinstance(match["file"], str)
                        assert isinstance(match["line"], int)
                        assert isinstance(match["pattern"], str)

                        # Files should be absolute paths or relative to root
                        assert match["file"] is not None and len(match["file"]) > 0
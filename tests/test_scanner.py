"""
Unit tests for bananagen scanner functionality.

These tests MUST FAIL initially (TDD approach).
Tests placeholder scanning and context extraction.
"""
import pytest
from pathlib import Path
import tempfile
import json

from bananagen.scanner import Scanner, PlaceholderMatch, ContextExtractor


class TestScanner:
    """Test placeholder scanning functionality."""
    
    @pytest.fixture
    def scanner(self):
        """Create Scanner instance for testing."""
        return Scanner()
    
    @pytest.fixture
    def temp_project(self):
        """Create temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)
            
            # Create project structure
            (project_root / "assets").mkdir()
            (project_root / "src").mkdir()
            (project_root / "docs").mkdir()
            
            # Create placeholder files
            (project_root / "assets" / "hero__placeholder__.png").touch()
            (project_root / "assets" / "banner__placeholder__.jpg").touch()
            (project_root / "src" / "icon__placeholder__.svg").touch()
            
            # Create context files
            with open(project_root / "README.md", 'w') as f:
                f.write("# My Project\nThis project has a hero image and banner.\n")
            
            with open(project_root / "assets" / "manifest.json", 'w') as f:
                json.dump({
                    "hero__placeholder__.png": {
                        "description": "Main hero image for landing page",
                        "alt_text": "Hero image showing product features"
                    },
                    "banner__placeholder__.jpg": {
                        "description": "Banner image for header",
                        "alt_text": "Company banner with logo"
                    }
                }, f)
            
            # Create HTML file with alt text
            with open(project_root / "src" / "index.html", 'w') as f:
                f.write('''
                <html>
                    <img src="../assets/hero__placeholder__.png" alt="Beautiful hero image" />
                    <img src="../assets/banner__placeholder__.jpg" alt="Header banner" />
                </html>
                ''')
            
            yield project_root
    
    def test_find_placeholders_by_pattern(self, scanner, temp_project):
        """Test finding placeholders by filename pattern."""
        matches = scanner.find_placeholders(
            root=str(temp_project),
            pattern="*__placeholder__*"
        )
        
        assert len(matches) == 3
        
        # Verify match structure
        for match in matches:
            assert isinstance(match, PlaceholderMatch)
            assert match.file_path.exists()
            assert "__placeholder__" in match.file_path.name
            assert match.pattern_matched == "*__placeholder__*"
    
    def test_find_placeholders_specific_pattern(self, scanner, temp_project):
        """Test finding placeholders with specific patterns."""
        # Find only PNG files
        png_matches = scanner.find_placeholders(
            root=str(temp_project),
            pattern="*__placeholder__.png"
        )
        
        assert len(png_matches) == 1
        assert png_matches[0].file_path.suffix == ".png"
        
        # Find only in assets directory
        asset_matches = scanner.find_placeholders(
            root=str(temp_project / "assets"),
            pattern="*__placeholder__*"
        )
        
        assert len(asset_matches) == 2
        for match in asset_matches:
            assert "assets" in str(match.file_path)
    
    def test_find_placeholders_no_matches(self, scanner, temp_project):
        """Test finding placeholders when no matches exist."""
        matches = scanner.find_placeholders(
            root=str(temp_project),
            pattern="*nonexistent*"
        )
        
        assert len(matches) == 0
    
    def test_extract_context_from_manifest(self, scanner, temp_project):
        """Test context extraction from manifest files."""
        placeholder_path = temp_project / "assets" / "hero__placeholder__.png"
        
        context = scanner.extract_context(
            placeholder_path=str(placeholder_path),
            context_sources=["manifest"]
        )
        
        assert context is not None
        assert "description" in context
        assert "alt_text" in context
        assert context["description"] == "Main hero image for landing page"
        assert context["alt_text"] == "Hero image showing product features"
    
    def test_extract_context_from_html_alt_text(self, scanner, temp_project):
        """Test context extraction from HTML alt attributes."""
        placeholder_path = temp_project / "assets" / "hero__placeholder__.png"
        
        context = scanner.extract_context(
            placeholder_path=str(placeholder_path),
            context_sources=["html_alt"]
        )
        
        assert context is not None
        assert "alt_text" in context
        assert "Beautiful hero image" in context["alt_text"]
    
    def test_extract_context_from_readme(self, scanner, temp_project):
        """Test context extraction from README files."""
        placeholder_path = temp_project / "assets" / "hero__placeholder__.png"
        
        context = scanner.extract_context(
            placeholder_path=str(placeholder_path),
            context_sources=["readme"]
        )
        
        assert context is not None
        assert "readme_content" in context
        assert "hero image" in context["readme_content"].lower()
    
    def test_extract_context_combined_sources(self, scanner, temp_project):
        """Test context extraction from multiple sources."""
        placeholder_path = temp_project / "assets" / "hero__placeholder__.png"
        
        context = scanner.extract_context(
            placeholder_path=str(placeholder_path),
            context_sources=["manifest", "html_alt", "readme"]
        )
        
        assert context is not None
        # Should have data from multiple sources
        assert "description" in context  # from manifest
        assert "alt_text" in context     # from manifest and HTML
        assert "readme_content" in context  # from README
    
    def test_placeholder_match_dataclass(self):
        """Test PlaceholderMatch dataclass functionality."""
        match = PlaceholderMatch(
            file_path=Path("/test/image__placeholder__.png"),
            pattern_matched="*__placeholder__*",
            context={"description": "Test image"},
            confidence=0.95
        )
        
        assert match.file_path == Path("/test/image__placeholder__.png")
        assert match.pattern_matched == "*__placeholder__*"
        assert match.context["description"] == "Test image"
        assert match.confidence == 0.95
        
        # Test to_dict method
        match_dict = match.to_dict()
        assert "file_path" in match_dict
        assert "pattern_matched" in match_dict
        assert "context" in match_dict
        assert "confidence" in match_dict
    
    def test_scan_and_generate_replacement_plan(self, scanner, temp_project):
        """Test generating a replacement plan from scan results."""
        plan = scanner.scan_and_plan_replacements(
            root=str(temp_project),
            pattern="*__placeholder__*",
            extract_context=True
        )
        
        assert "replacements" in plan
        assert len(plan["replacements"]) == 3
        
        for replacement in plan["replacements"]:
            assert "source_path" in replacement
            assert "target_path" in replacement
            assert "prompt" in replacement or "context" in replacement
            assert "estimated_dimensions" in replacement or replacement.get("use_source_dimensions", False)
    
    def test_context_extractor_initialization(self):
        """Test ContextExtractor initialization and configuration."""
        extractor = ContextExtractor()
        
        # Should have default extractors registered
        assert len(extractor.extractors) > 0
        assert "manifest" in extractor.extractors
        assert "html_alt" in extractor.extractors
        assert "readme" in extractor.extractors
    
    def test_context_extractor_custom_extractors(self):
        """Test adding custom context extractors."""
        extractor = ContextExtractor()
        
        def custom_extractor(file_path, project_root):
            return {"custom": "data"}
        
        extractor.register_extractor("custom", custom_extractor)
        
        assert "custom" in extractor.extractors
        
        # Test extraction with custom extractor
        context = extractor.extract_context(
            placeholder_path="/test/file.png",
            sources=["custom"]
        )
        
        assert context["custom"] == "data"
    
    def test_scanner_error_handling(self, scanner):
        """Test scanner error handling for invalid inputs."""
        # Invalid root directory
        matches = scanner.find_placeholders(
            root="/nonexistent/directory",
            pattern="*"
        )
        assert len(matches) == 0
        
        # Invalid placeholder path for context
        context = scanner.extract_context(
            placeholder_path="/nonexistent/file.png",
            context_sources=["manifest"]
        )
        assert context == {} or context is None
    
    def test_scanner_with_gitignore_respect(self, scanner, temp_project):
        """Test scanner respects .gitignore patterns."""
        # Create .gitignore
        with open(temp_project / ".gitignore", 'w') as f:
            f.write("*.tmp\n/ignored/\n")
        
        # Create ignored files
        (temp_project / "ignored").mkdir()
        (temp_project / "ignored" / "test__placeholder__.png").touch()
        (temp_project / "temp__placeholder__.tmp").touch()
        
        matches = scanner.find_placeholders(
            root=str(temp_project),
            pattern="*__placeholder__*",
            respect_gitignore=True
        )
        
        # Should not include ignored files
        ignored_paths = [str(m.file_path) for m in matches if "ignored" in str(m.file_path) or m.file_path.suffix == ".tmp"]
        assert len(ignored_paths) == 0

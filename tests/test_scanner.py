import pytest
import tempfile
import os
from pathlib import Path
from bananagen.scanner import ContextExtractor, Scanner, PlaceholderMatch


@pytest.fixture
def extractor():
    """Create a ContextExtractor instance."""
    return ContextExtractor()


@pytest.fixture
def test_file():
    """Create a temporary file for testing."""
    temp_dir = tempfile.mkdtemp()
    test_file_path = os.path.join(temp_dir, "test.txt")
    with open(test_file_path, 'w') as f:
        content = """# prompt: A sunny landscape with mountains
line 2
This is line 3 with __placeholder__ in it
line 4
# prompt: A beautiful forest
line 6
/* prompt: A breathtaking ocean view */
placeholder__found_here__"""
        f.write(content)
    
    yield test_file_path
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)


class TestContextExtractor:
    def test_parse_placeholder_with_dimensions(self, extractor):
        """Test parsing placeholder with dimensions."""
        text = "__placeholder_1024x768__"
        width, height = extractor.parse_placeholder(text)
        assert width == 1024
        assert height == 768
    
    def test_parse_placeholder_without_dimensions(self, extractor):
        """Test parsing placeholder without dimensions."""
        text = "__placeholder__"
        width, height = extractor.parse_placeholder(text)
        assert width == 512
        assert height == 512
    
    def test_parse_placeholder_mixed(self, extractor):
        """Test parsing various placeholder formats."""
        # With prefix/suffix around
        text = "some__placeholder_256x256__text"
        width, height = extractor.parse_placeholder(text)
        assert width == 256
        assert height == 256
    
    def test_extract_from_context_same_line(self, extractor):
        """Test extracting prompt from the same line."""
        lines = [
            "line 1",
            'placeholder = "__placeholder__"  # prompt: A serene lake',
            "line 3"
        ]
        prompt = extractor.extract_from_context(lines, 1)
        assert prompt == "A serene lake"
    
    def test_extract_from_context_previous_lines(self, extractor):
        """Test extracting prompt from previous lines."""
        lines = [
            "# prompt: A majestic mountain",
            "line 2",
            "__placeholder__"
        ]
        prompt = extractor.extract_from_context(lines, 2)
        assert prompt == "A majestic mountain"
    
    def test_extract_from_context_next_lines(self, extractor):
        """Test extracting prompt from next lines."""
        lines = [
            "__placeholder__",
            "line 2",
            "/* prompt: A peaceful sunset */"
        ]
        prompt = extractor.extract_from_context(lines, 0)
        assert prompt == "A peaceful sunset "  # Note trailing space from regex
    
    def test_extract_from_context_no_prompt(self, extractor):
        """Test when no prompt is found."""
        lines = [
            "__placeholder__",
            "line 2"
        ]
        prompt = extractor.extract_from_context(lines, 0)
        assert prompt is None
    
    def test_extract_from_context_multiline_comment(self, extractor):
        """Test extracting from multiline comment."""
        lines = [
            "/* prompt: A vast desert */",
            "line 2",
            "__placeholder__"
        ]
        prompt = extractor.extract_from_context(lines, 2)
        assert prompt == "A vast desert "


class TestScanner:
    def test_scan_file_with_placeholders(self, test_file):
        """Test scanning a file with placeholders."""
        scanner = Scanner(root_path=Path(os.path.dirname(test_file)), pattern="")
        matches = scanner.scan_files()
    
        # Should find matches in our test file
        file_matches = [m for m in matches if os.path.normpath(m.file_path) == os.path.normpath(test_file)]
        assert len(file_matches) >= 1  # Should find at least one
    
        # Check the first match
        match = file_matches[0]
        assert "placeholder" in match.placeholder_text
        assert match.line_number > 0
        assert match.context is not None
        assert len(match.context) > 0
    
    def test_scan_nonexistent_directory(self):
        """Test scanning non-existent directory."""
        scanner = Scanner(root_path="nonexistent", pattern="*")
        matches = scanner.scan_files()
        assert len(matches) == 0
    
    def test_matches_pattern(self):
        """Test pattern matching."""
        scanner = Scanner(pattern="__placeholder__")
        
        # Test paths that should match
        assert scanner._matches_pattern(Path("test__placeholder__.txt"))
        assert scanner._matches_pattern(Path("some__placeholder__file.md"))
        
        # Test paths that shouldn't match
        assert not scanner._matches_pattern(Path("regular_tile.txt"))
        assert not scanner._matches_pattern(Path("placeholder.txt"))
    
    @pytest.mark.asyncio
    async def test_replace_placeholders_no_replace(self):
        """Test replace_placeholders without actual file replacement."""
        # Create minimal test case
        matches = [PlaceholderMatch(
            file_path="dummy",
            line_number=1,
            placeholder_text="__placeholder__",
            context="context",
            prompt=None  # This will be skipped
        )]
        
        scanner = Scanner()
        results = await scanner.replace_placeholders(matches, replace=False)
        
        assert len(results) == 1
        assert results[0]["status"] == "skipped"
        assert "no prompt found" in results[0]["reason"]
    
    def test_scanner_initialization(self):
        """Test scanner initialization with custom parameters."""
        scanner = Scanner(root_path="/tmp", pattern="*custom*")
        assert scanner.root_path == Path("/tmp")
        assert scanner.pattern == "*custom*"
        assert scanner.extractor is not None
        assert isinstance(scanner.extractor, ContextExtractor)


class TestPlaceholderMatch:
    def test_placeholder_match_creation(self):
        """Test creating a PlaceholderMatch instance."""
        match = PlaceholderMatch(
            file_path="test.txt",
            line_number=5,
            placeholder_text="__placeholder_512x256__",
            context="some context",
            prompt="test prompt",
            width=512,
            height=256
        )
        
        assert match.file_path == "test.txt"
        assert match.line_number == 5
        assert match.placeholder_text == "__placeholder_512x256__"
        assert match.context == "some context"
        assert match.prompt == "test prompt"
        assert match.width == 512
        assert match.height == 256
    
    def test_placeholder_match_defaults(self):
        """Test PlaceholderMatch with default values."""
        match = PlaceholderMatch(
            file_path="test.txt",
            line_number=1,
            placeholder_text="__placeholder__",
            context="context"
        )
        
        assert match.prompt is None
        assert match.width == 512
        assert match.height == 512

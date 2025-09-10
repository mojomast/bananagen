import re
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import asyncio

from .gemini_adapter import call_gemini
from .core import generate_placeholder


@dataclass
class PlaceholderMatch:
    file_path: str
    line_number: int
    placeholder_text: str
    context: str
    prompt: Optional[str] = None
    width: int = 512
    height: int = 512


class ContextExtractor:
    def __init__(self):
        # Regex to find placeholders like __placeholder__ or __placeholder_512x512__
        self.placeholder_pattern = re.compile(r'__placeholder(?:_(\d+)x(\d+))?__')
        # Regex to find prompt in comments or nearby
        self.prompt_pattern = re.compile(r'#\s*prompt:\s*(.+)|/\*\s*prompt:\s*(.+)\s*\*/|<!--\s*prompt:\s*(.+)-->')
    
    def extract_from_context(self, lines: List[str], match_line: int) -> Optional[str]:
        """Extract prompt from context around the match."""
        # Look in the match line
        line = lines[match_line]
        match = self.prompt_pattern.search(line)
        if match:
            return match.group(1) or match.group(2) or match.group(3)
        
        # Look in previous lines
        for i in range(max(0, match_line - 5), match_line):
            match = self.prompt_pattern.search(lines[i])
            if match:
                return match.group(1) or match.group(2) or match.group(3)
        
        # Look in next lines
        for i in range(match_line + 1, min(len(lines), match_line + 6)):
            match = self.prompt_pattern.search(lines[i])
            if match:
                return match.group(1) or match.group(2) or match.group(3)
        
        return None
    
    def parse_placeholder(self, text: str) -> tuple[int, int]:
        """Parse width and height from placeholder text."""
        match = self.placeholder_pattern.search(text)
        if match and match.group(1) and match.group(2):
            return int(match.group(1)), int(match.group(2))
        return 512, 512


class Scanner:
    def __init__(self, root_path: str = ".", pattern: str = "*__placeholder__*"):
        self.root_path = Path(root_path)
        self.pattern = pattern
        self.extractor = ContextExtractor()
    
    def scan_files(self) -> List[PlaceholderMatch]:
        """Scan files for placeholders."""
        matches = []
        for file_path in self.root_path.rglob("*"):
            if file_path.is_file() and self._matches_pattern(file_path):
                file_matches = self._scan_file(file_path)
                matches.extend(file_matches)
        return matches
    
    def _matches_pattern(self, file_path: Path) -> bool:
        """Check if file matches the pattern."""
        return self.pattern in str(file_path)
    
    def _scan_file(self, file_path: Path) -> List[PlaceholderMatch]:
        """Scan a single file for placeholders."""
        matches = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines):
                if '__placeholder__' in line:
                    # Find all placeholders in the line
                    for match in self.extractor.placeholder_pattern.finditer(line):
                        placeholder_text = match.group(0)
                        width, height = self.extractor.parse_placeholder(placeholder_text)
                        
                        # Extract context (5 lines before and after)
                        start = max(0, i - 5)
                        end = min(len(lines), i + 6)
                        context = ''.join(lines[start:end])
                        
                        prompt = self.extractor.extract_from_context(lines, i)
                        
                        matches.append(PlaceholderMatch(
                            file_path=str(file_path),
                            line_number=i + 1,
                            placeholder_text=placeholder_text,
                            context=context,
                            prompt=prompt,
                            width=width,
                            height=height
                        ))
        except UnicodeDecodeError:
            # Skip binary files
            pass
        return matches
    
    async def replace_placeholders(self, matches: List[PlaceholderMatch], replace: bool = False) -> List[dict]:
        """Replace placeholders with generated images."""
        results = []
        for match in matches:
            if not match.prompt:
                results.append({
                    "file": match.file_path,
                    "line": match.line_number,
                    "status": "skipped",
                    "reason": "no prompt found"
                })
                continue
            
            try:
                # Generate placeholder
                placeholder_path = f"{match.file_path}_{match.line_number}_placeholder.png"
                generate_placeholder(match.width, match.height, out_path=placeholder_path)
                
                # Generate image
                generated_path, metadata = await call_gemini(placeholder_path, match.prompt)
                
                if replace:
                    # Replace in file
                    with open(match.file_path, 'r') as f:
                        content = f.read()
                    
                    # Assume placeholder is replaced with image path or something
                    # For simplicity, replace with generated path
                    new_content = content.replace(match.placeholder_text, generated_path)
                    
                    with open(match.file_path, 'w') as f:
                        f.write(new_content)
                    
                    results.append({
                        "file": match.file_path,
                        "line": match.line_number,
                        "status": "replaced",
                        "generated_path": generated_path
                    })
                else:
                    results.append({
                        "file": match.file_path,
                        "line": match.line_number,
                        "status": "generated",
                        "generated_path": generated_path
                    })
            except Exception as e:
                results.append({
                    "file": match.file_path,
                    "line": match.line_number,
                    "status": "error",
                    "error": str(e)
                })
        
        return results

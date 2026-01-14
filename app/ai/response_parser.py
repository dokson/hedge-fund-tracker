from toon import decode
import re


class ResponseParser:
    """
    Utility class for parsing TOON from LLM responses
    """
    @staticmethod
    def extract_and_decode_toon(response_text: str) -> dict:
        """
        Extract and decode TOON from LLM response text.
        Always returns the LAST toon block found, as previous ones
        might be intermediate reasoning steps.
        """
        try:
            text = response_text.strip()
            
            # Find all markdown blocks (toon or generic)
            # Allow for potential whitespace/newline before 'toon' (e.g. ```\n toon)
            markdown_blocks = re.findall(r'```(?:\s*toon)?\s*(.*?)```', text, re.DOTALL)
            
            if markdown_blocks:
                # Use the last block content
                toon_content = markdown_blocks[-1].strip()
            else:
                # Fallback: Use the whole text if no blocks found
                toon_content = text

            if toon_content:
                # Sanitize the content to help toon library (strip comments, collapse lists)
                clean_content = ResponseParser._sanitize_toon(toon_content)
                return decode(clean_content)

        except Exception as e:
            print(f"❌ ERROR: Invalid TOON structure: {e}")
            return {}

        print(f"🚨 Warning: Could not find TOON in response: {response_text[:200]}...")
        return {}


    @staticmethod
    def _sanitize_toon(text: str) -> str:
        """
        Refactored to be simple (no over-engineering).
        Sanitizes TOON content to help the library handle common LLM quirks:
        1. Strips comments (while respecting quotes).
        2. Collapses multiline JSON lists (which toon doesn't support).
        3. Removes YAML-style bullets/checklists (which break toon).
        """
        # 1. Strip comments (respecting quotes) using regex
        # Pattern captures: Group 1 (Quoted String), Group 2 (Comment)
        pattern_comment = r'("[^"\\]*(?:\\.[^"\\]*)*")|(#.*)'
        # Replace comments with empty string, keep strings as is
        text = re.sub(pattern_comment, lambda m: m.group(1) if m.group(1) else "", text)
        
        # 2. Collapse JSON lists to single line (handling newlines inside [ ... ])
        # Uses DOTALL to match across lines.
        text = re.sub(r'\[\s*(.*?)\s*\]', lambda m: '[' + ' '.join(m.group(1).split()) + ']', text, flags=re.DOTALL)

        # 3. Filter invalid lines (markdown bullets)
        lines = text.split('\n')
        valid_lines = []
        for line in lines:
            cleaned = line.rstrip()
            # Filter lines starting with "- " which are YAML lists or markdown bullets
            if cleaned.lstrip().startswith('- '):
                continue
            if cleaned.strip():
                valid_lines.append(cleaned)
        
        return '\n'.join(valid_lines)

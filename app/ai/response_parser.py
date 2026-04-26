from toon import decode
import re


class ResponseParser:
    """
    Utility class for parsing TOON from LLM responses
    """
    # Field keys we expect inside a per-stock or weights toon block. Used to repair
    # responses where an LLM drops the newline between consecutive key-value pairs.
    _KNOWN_FIELD_KEYS = (
        "industry", "momentum_score", "low_volatility_score", "risk_score", "growth_score",
        "High_Conviction_Count", "Max_Portfolio_Pct", "Ownership_Delta_Avg", "Net_Buyers",
        "New_Holder_Count", "Portfolio_Concentration_Avg", "Total_Delta_Value",
        "Holder_Count", "Buyer_Count", "Seller_Count", "Buyer_Seller_Ratio",
    )

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

        # 3a. Repair missing newlines between known keys on the same line
        # (e.g. "momentum_score: 65  low_volatility_score: 70"), preserving indent.
        keys_alt = "|".join(re.escape(k) for k in ResponseParser._KNOWN_FIELD_KEYS)
        split_field_re = re.compile(rf"\s+(?=(?:{keys_alt})\s*:)")
        repaired_lines: list[str] = []
        for raw_line in text.split('\n'):
            indent = re.match(r'^(\s*)', raw_line).group(1)
            parts = split_field_re.split(raw_line)
            if len(parts) > 1:
                repaired_lines.append(parts[0])
                for p in parts[1:]:
                    repaired_lines.append(indent + p)
            else:
                repaired_lines.append(raw_line)
        text = '\n'.join(repaired_lines)

        # 3b. Repair tickers glued to the previous numeric value
        # (e.g. "risk_score: 90KRRO:" → ticker on its own line).
        text = re.sub(r'(\d)(?=[A-Z][A-Z0-9]{1,9}:)', r'\1\n', text)

        # 4. Filter invalid lines (markdown bullets)
        valid_lines = []
        for line in text.split('\n'):
            cleaned = line.rstrip()
            # Filter lines starting with "- " which are YAML lists or markdown bullets
            if cleaned.lstrip().startswith('- '):
                continue
            if cleaned.strip():
                valid_lines.append(cleaned)
        
        return '\n'.join(valid_lines)

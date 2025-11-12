from toon import decode
import re


class ResponseParser:
    """
    Utility class for parsing TOON from LLM responses
    """
    @staticmethod
    def extract_and_decode_toon(response_text: str) -> dict:
        """
        Extract and decode TOON from LLM response text
        """
        try:
            text = response_text.strip()
            
            # 1. Prioritize finding a markdown block, as it's the most reliable indicator.
            markdown_match = re.search(r'```(?:toon)?\s*\n(.*?)```', text, re.DOTALL)
            if markdown_match:
                toon_content = markdown_match.group(1).strip()
                return decode(toon_content)

            # 2. Fallback for responses without markdown: find the last contiguous block of key-value pairs.
            lines = text.split('\n')
            last_block_lines = []
            for line in reversed(lines):
                # If the line looks like a key-value pair, add it to our block
                is_toon_line = re.match(r'^\s*[a-zA-Z0-9_]+\s*:', line)
                is_empty_line = not line.strip()

                if is_toon_line or (is_empty_line and last_block_lines):
                    last_block_lines.insert(0, line)
                elif last_block_lines:
                    break

            if last_block_lines:
                toon_content = '\n'.join(last_block_lines)
                return decode(toon_content)

        except Exception as e:
            print(f"❌ ERROR: Invalid TOON structure: {e}")
            return {}

        print(f"🚨 Warning: Could not find TOON in response: {response_text[:200]}...")
        return {}

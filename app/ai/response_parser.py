import json
import re


class ResponseParser:
    """
    Utility class for parsing JSON from LLM responses
    """
    @staticmethod
    def extract_and_parse(response_text: str) -> dict:
        """
        Extract and parse JSON from LLM response text
        """
        try:
            text = response_text.strip()
            if text.startswith('```'):
                text = re.sub(r'^```(?:json)?\s*\n', '', text)
                text = re.sub(r'\n```$', '', text)
            
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            
            if not json_match:
                print(f"🚨 Warning: Could not find JSON in response: {response_text[:200]}...")
                return {}

            json_string = json_match.group(0)
            return json.loads(json_string)
            
        except Exception as e:
            print(f"❌ ERROR: Invalid JSON structure: {e}")
            return {}

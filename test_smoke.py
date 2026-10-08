"""
Smoke tests for LinkedIn AI Chatbot core logic.
Run with: python3 -m unittest test_smoke.py
"""

import unittest
from pathlib import Path
from api.main import (
    structure_text_as_markdown,
    parse_profile_stats,
    select_relevant_context,
    extract_text_from_html,
    PROFILE_FILE
)

class TestChatbotLogic(unittest.TestCase):

    def test_profile_file_exists(self):
        """Ensure initial starter profile exists."""
        self.assertTrue(PROFILE_FILE.exists(), "Starter linkedin_profile.md should exist")
        content = PROFILE_FILE.read_text(encoding="utf-8")
        self.assertIn("Experience", content)
        self.assertIn("Education", content)

    def test_parse_profile_stats(self):
        """Ensure profile stats calculates words, chars, and section headers."""
        sample_md = "# Profile Overview\nJohn Doe\n\n## Experience\nEngineer\n\n## Education\nBS CS"
        stats = parse_profile_stats(sample_md)
        self.assertGreater(stats["words"], 5)
        self.assertGreater(stats["characters"], 30)
        self.assertIn("Profile Overview", stats["sections"])
        self.assertIn("Experience", stats["sections"])
        self.assertIn("Education", stats["sections"])

    def test_extract_text_from_html(self):
        """Ensure HTML extractor pulls headings and text cleanly."""
        html = """
        <html>
            <body>
                <h1>Jane Smith</h1>
                <p>Senior Data Scientist</p>
                <ul><li>Python</li><li>PyTorch</li></ul>
            </body>
        </html>
        """
        extracted = extract_text_from_html(html)
        self.assertIn("Jane Smith", extracted)
        self.assertIn("Senior Data Scientist", extracted)
        self.assertIn("Python", extracted)

    def test_structure_text_as_markdown(self):
        """Ensure unformatted text gets categorized by recognized section keywords."""
        raw_text = (
            "About\nTech enthusiast and architect\n"
            "Experience\nStaff Developer at Acme Corp\n"
            "Education\nMIT Class of 2018\n"
            "Skills\nPython, Docker, FastAPI"
        )
        md = structure_text_as_markdown(raw_text)
        self.assertIn("# Profile Overview", md)
        self.assertIn("## Experience", md)
        self.assertIn("## Education", md)
        self.assertIn("## Skills", md)

    def test_context_selection_within_limit(self):
        """Normal profiles should return complete content."""
        sample_md = "# Profile Overview\nSummary info\n## Experience\nWork history"
        selected = select_relevant_context(sample_md, "Tell me about your experience", max_chars=5000)
        self.assertEqual(selected, sample_md)

if __name__ == "__main__":
    unittest.main()

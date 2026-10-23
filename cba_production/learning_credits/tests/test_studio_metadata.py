import unittest
from cba_production.learning_credits.management.commands.import_cba_studio_metadata import metadata_values

class StudioMetadataTests(unittest.TestCase):
    def record(self):
        return dict(short_description='Summary', full_description='Description', pacing='self_paced', language='en')

    def test_escapes_untrusted_markup(self):
        row = self.record()
        row['full_description'] = '<script>alert(1)</script>'
        self.assertNotIn('<script>', metadata_values(row)['overview'])

    def test_includes_outcomes_syllabus_and_requirements(self):
        row = self.record()
        row.update(learning_outcomes=['Explain risk'], syllabus='Practice', completion_requirements='80 percent')
        html = metadata_values(row)['overview']
        for text in ('Explain risk', 'Practice', '80 percent'):
            self.assertIn(text, html)

    def test_private_authoring_content_is_not_exposed(self):
        row = self.record()
        row.update(authoring_metadata={'secret': 'PRIVATE'}, ai_brief='PRIVATE', access_policy_key='PRIVATE')
        self.assertNotIn('PRIVATE', metadata_values(row)['overview'])

    def test_explicit_zero_price_is_preserved(self):
        row = self.record()
        row['price'] = 0
        self.assertIn('<p>0</p>', metadata_values(row)['overview'])

    def test_incomplete_metadata_is_rejected(self):
        for name in ('full_description', 'short_description', 'pacing', 'language'):
            row = self.record()
            row.pop(name)
            with self.assertRaises(ValueError):
                metadata_values(row)

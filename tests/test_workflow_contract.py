import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

class WorkflowContract(unittest.TestCase):
    def test_workflow_has_manual_input(self):
        txt=(ROOT/'.github/workflows/hunter.yml').read_text()
        self.assertIn('workflow_dispatch:',txt)
        self.assertIn('listing_urls:',txt)
        self.assertIn('upload-artifact@v4',txt)
    def test_model_is_in_package(self):
        self.assertTrue((ROOT/'models/lvc_model_v06.joblib').is_file())
    def test_report_generator_present(self):
        self.assertTrue((ROOT/'report_html.py').is_file())

if __name__=='__main__':unittest.main()

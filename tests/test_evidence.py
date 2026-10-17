import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from validate_evidence import audit
class EvidenceTests(unittest.TestCase):
 def test_audit(self):
  d=audit(Path(__file__).resolve().parents[1]/'data/sold_evidence.csv')
  self.assertEqual(d['records'],20)
  self.assertEqual(d['verified_SEK_tier_comparables'],0)
  self.assertEqual(d['issues'],[])
if __name__=='__main__':unittest.main()

import unittest
from evidence_checklist import checklist
class EvidenceTests(unittest.TestCase):
 def test_valencia(self):
  result=' '.join(checklist('Valencia 555 NOS',tier='lvc_valencia_555',condition='nos'))
  self.assertIn('knappens',result)
  self.assertIn('otvättat',result)
 def test_verified(self):
  result=' '.join(checklist('jeans',tier='lvc_non_usa',tier_confidence='verified',condition_evidence='verified'))
  self.assertNotIn('knappens',result)
if __name__=='__main__':unittest.main()

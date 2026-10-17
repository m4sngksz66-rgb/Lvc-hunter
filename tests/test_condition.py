import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from condition_signals import analyze_condition,valencia_unwashed_priority
class ConditionTests(unittest.TestCase):
 def test_terms(self):
  for key,term in [('nwt','NWT'),('nwot','NWOT'),('nos','NOS'),('unwashed','otvättade')]:
   self.assertEqual(analyze_condition(term)['condition'],key)
 def test_claim_not_verified(self):
  x=analyze_condition('NOS LVC Valencia 555')
  self.assertEqual(x['condition_evidence'],'seller_claim')
  self.assertEqual(valencia_unwashed_priority('lvc_valencia_555','text_clue',x),'verify_photos')
 def test_verified_priority(self):
  x=analyze_condition('LVC Valencia 555',verified_condition='unwashed')
  self.assertEqual(valencia_unwashed_priority('lvc_valencia_555','verified',x),'verified_priority')
 def test_no_misleading_raw(self):
  self.assertEqual(analyze_condition('raw denim')['condition'],'unknown')
if __name__=='__main__':unittest.main()

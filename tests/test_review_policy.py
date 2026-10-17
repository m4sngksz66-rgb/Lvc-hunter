import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from review_policy import decide
class PolicyTests(unittest.TestCase):
 def setUp(self):
  self.cond={'condition':'unwashed','condition_evidence':'verified'}
  self.deal={'deal_status':'potential_bargain'}
 def test_complete_evidence_alerts(self):
  self.assertEqual(decide(.8,.25,'verified',self.cond,self.deal,'50155',True)[0],'bargain_alert')
 def test_seller_claim_not_proof(self):
  self.assertEqual(decide(.8,.25,'text_clue',self.cond,self.deal,'50155',True)[0],'manual_review')
 def test_unknown_shipping_not_alert(self):
  self.assertEqual(decide(.8,.25,'verified',self.cond,self.deal,'50155',False)[0],'manual_review')
 def test_no_model_key_not_alert(self):
  self.assertEqual(decide(.8,.25,'verified',self.cond,self.deal,'',True)[0],'manual_review')
 def test_unverified_condition_not_alert(self):
  self.assertEqual(decide(.8,.25,'verified',{'condition':'nos','condition_evidence':'seller_claim'},self.deal,'50155',True)[0],'manual_review')
 def test_visual_low(self):
  self.assertEqual(decide(.1,.25,'verified',self.cond,self.deal,'50155',True)[0],'ignore')
if __name__=='__main__':unittest.main()

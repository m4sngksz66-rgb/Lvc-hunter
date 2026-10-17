import unittest,sys,tempfile,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from price_control import assess_deal
from validate_evidence import audit
class PriceSafetyTests(unittest.TestCase):
 def test_no_real_comparables_from_uncertain_offers(self):
  base=Path(__file__).resolve().parents[1]
  self.assertEqual(audit(base/'data/sold_evidence.csv')['verified_SEK_tier_comparables'],0)
 def test_insufficient_comparables_never_alerts(self):
  result=assess_deal('500 kr','japanese_selvedge_repro',[],minimum=3)
  self.assertEqual(result['deal_status'],'insufficient_comparables')
if __name__=='__main__':unittest.main()

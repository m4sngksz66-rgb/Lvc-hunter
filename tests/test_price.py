import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from price_control import *
class PriceTests(unittest.TestCase):
 def test_parse(self):
  self.assertEqual(parse_sek_price('1 499 kr'),1499)
  self.assertEqual(parse_sek_price('1.499 SEK'),1499)
  self.assertEqual(parse_sek_price('1 499,50 kr'),1499.5)
  self.assertIsNone(parse_sek_price('$99'))
 def test_tier(self):
  self.assertEqual(classify_listing('LVC Valencia Street 555')[0],'lvc_valencia_555')
  self.assertEqual(classify_listing('Levis 501XX vintage')[0],'unclassified')
  self.assertEqual(classify_listing('LVC Made in Turkey')[0],'lvc_non_usa')
 def test_no_fake_market_value(self):
  self.assertEqual(assess_deal('400 kr','true_vintage',[])['deal_status'],'insufficient_comparables')
 def test_sold_only(self):
  rows=[{'tier':'lvc_valencia_555','status':'sold','sold_price_sek':str(p)} for p in [2000,2200,2400]]
  rows.append({'tier':'lvc_valencia_555','status':'listed','sold_price_sek':'9000'})
  result=assess_deal('1200 kr','lvc_valencia_555',rows)
  self.assertEqual(result['deal_status'],'potential_bargain')
  self.assertEqual(result['reference_sek'],2200)
  self.assertEqual(assess_deal('2100 kr','lvc_valencia_555',rows)['deal_status'],'not_a_bargain')
 def test_model_match(self):
  rows=[{'tier':'true_vintage','model_key':'501xx','status':'sold','sold_price_sek':'5000'}]*3
  self.assertEqual(assess_deal('1000 kr','true_vintage',rows,model_key='505')['deal_status'],'insufficient_comparables')
if __name__=='__main__':unittest.main()

import unittest
from evaluation import accept
class TotalSelectionTests(unittest.TestCase):
    def rows(self,a,b):return [{'task':t,'reward':int(i<n)} for t,n in [('a',a),('b',b)] for i in range(3)]
    def test_tradeoff_and_tie(self):
        self.assertTrue(accept(self.rows(2,0),self.rows(1,2),['a','b'],'total_non_decreasing')['accepted'])
        self.assertTrue(accept(self.rows(2,0),self.rows(1,1),['a','b'],'total_non_decreasing')['accepted'])
        self.assertFalse(accept(self.rows(2,0),self.rows(1,0),['a','b'],'total_non_decreasing')['accepted'])
    def test_errors_still_block(self):
        rows=self.rows(2,0);rows[0]['exception']={'type':'error'}
        with self.assertRaises(ValueError):accept(self.rows(2,0),rows,['a','b'],'total_non_decreasing')

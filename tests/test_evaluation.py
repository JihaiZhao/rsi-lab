import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from evaluation import accept

def rows(a,b):
    return [{'task':'a','reward':a},{'task':'b','reward':b}]

class SelectionTests(unittest.TestCase):
    def test_accepts_strict_gain(self):
        self.assertTrue(accept(rows(0,0),rows(1,0),['a','b'])['accepted'])
    def test_ties_retain_parent(self):
        self.assertFalse(accept(rows(1,0),rows(1,0),['a','b'])['accepted'])
    def test_task_regression_rejected(self):
        self.assertFalse(accept(rows(1,0),rows(0,1),['a','b'])['accepted'])
    def test_missing_score_cannot_be_silently_dropped(self):
        with self.assertRaises(ValueError):accept(rows(0,0),rows(1,None),['a','b'])

if __name__=='__main__':unittest.main()

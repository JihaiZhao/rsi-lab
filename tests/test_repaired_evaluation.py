import unittest
from pathlib import Path
from repaired_evaluation import collect_refs

class RepairTests(unittest.TestCase):
    def test_preserves_normal_failures_and_source_paths(self):
        data={'old':[{'trial':'failed-task','reward':0,'path':'original'}, {'trial':'setup','reward':None}], 'new':[{'trial':'replacement','reward':1,'path':'new'}]}
        rows=collect_refs(Path('.'), [{'job':'old','trial':'failed-task'},{'job':'new','trial':'replacement'}],lambda p:data[p.name])
        self.assertEqual([r['reward'] for r in rows],[0,1])
        self.assertEqual(rows[0]['path'],'original')
    def test_missing_and_duplicate_rejected(self):
        ref={'job':'job','trial':'trial'}
        for refs in ([ref], [ref,ref]):
            with self.assertRaises(ValueError):
                collect_refs(Path('.'),refs,lambda p:[] if len(refs)==1 else [{'trial':'trial'}])

import unittest,tempfile
from pathlib import Path
from structured_search import directives,validate_plan,changed_files
class StructuredSearchTests(unittest.TestCase):
 def test_prompt_only_triggers_exploration(self):
  self.assertTrue(directives([{'reason':'total_gain'}]*2)['require_structural_exploration'])
 def test_no_fake_tool_change(self):
  plan={k:'evidence' for k in ['problem','evidence','hypothesis','why_this_component','expected_effect']}
  plan.update(component='tool',exploration_waiver='')
  self.assertTrue(validate_plan(plan,['instructions.md'],directives([])))
  self.assertEqual(validate_plan(plan,['tools/check.py','instructions.md'],directives([])),[])
 def test_changed_files(self):
  with tempfile.TemporaryDirectory() as d:
   a=Path(d)/'a';b=Path(d)/'b';a.mkdir();b.mkdir()
   (a/'instructions.md').write_text('same');(b/'instructions.md').write_text('same')
   (b/'tools').mkdir();(b/'tools/check.py').write_text('pass')
   self.assertEqual(changed_files(a,b),['tools/check.py'])

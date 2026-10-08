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
 def test_schema_uses_same_component_vocabulary(self):
  from structured_search import PLAN_SCHEMA,COMPONENTS,validate_plan_fields
  self.assertEqual(PLAN_SCHEMA['properties']['component']['enum'],list(COMPONENTS))
  for component in COMPONENTS:
   plan={k:'evidence' for k in PLAN_SCHEMA['required']};plan['component']=component
   self.assertEqual(validate_plan_fields(plan),[])
 def test_archived_labels_are_supported_without_mutation(self):
  from structured_search import PLAN_SCHEMA,LEGACY_COMPONENTS,canonical_component
  for label,canonical in LEGACY_COMPONENTS.items():
   plan={k:'evidence' for k in PLAN_SCHEMA['required']};plan.update(component=label,exploration_waiver='')
   self.assertEqual(validate_plan(plan,['tools/check.py'],directives([])),[])
   self.assertEqual(plan['component'],label)
   self.assertEqual(canonical_component(label),canonical)
 def test_unknown_label_still_rejected(self):
  from structured_search import PLAN_SCHEMA,validate_plan_fields
  plan={k:'evidence' for k in PLAN_SCHEMA['required']};plan['component']='Memory: arbitrary new label'
  self.assertIn('Unsupported component',validate_plan_fields(plan))
 def test_legacy_instruction_history_is_canonicalized(self):
  d=directives([{'mechanism':{'component':'Memory: task-local append-only pass-risk state machine.'}}])
  self.assertEqual(d['explored_components'],['memory'])

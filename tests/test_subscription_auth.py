import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from subscription_auth import subscription_environment

class SubscriptionTests(unittest.TestCase):
    def invoke(self,usage):
        with patch('pathlib.Path.read_text',return_value=json.dumps({'claudeAiOauth':{'accessToken':'fake-test-token'}})):
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(usage).encode())):
                return subscription_environment()
    def test_strips_api_keys_and_routing(self):
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'fake-api-key','ANTHROPIC_BASE_URL':'https://example.invalid','CLAUDE_CODE_USE_BEDROCK':'1'}):
            env,_=self.invoke({'extra_usage':{'is_enabled':False},'five_hour':{'utilization':1}})
        self.assertNotIn('ANTHROPIC_API_KEY',env)
        self.assertNotIn('ANTHROPIC_BASE_URL',env)
        self.assertNotIn('CLAUDE_CODE_USE_BEDROCK',env)
        self.assertEqual(env['CLAUDE_FORCE_OAUTH'],'1')
        self.assertEqual(env['CLAUDE_CODE_SUBAGENT_MODEL'],'claude-sonnet-5-5')
    def test_paid_overage_or_unknown_status_blocks_calls(self):
        for usage in [{'extra_usage':{'is_enabled':True}},{}]:
            with self.assertRaises(RuntimeError):self.invoke(usage)
    def test_exhausted_quota_blocks_calls(self):
        with self.assertRaises(RuntimeError):self.invoke({'extra_usage':{'is_enabled':False},'five_hour':{'utilization':100}})

if __name__=='__main__':unittest.main()

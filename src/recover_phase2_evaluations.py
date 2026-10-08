"""User-authorized evaluation of two archived phase-2 candidates; no reproposals."""
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from job_spec import ROOT
from native_bundle import bundle_hash, validate_bundle
from structured_search import validate_plan, changed_files, telemetry
from codex_evaluation import collect
from evaluation import accept
from codex_role import role
from cached_codex_runtime import validate_cache


def dump(path, value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    config_path=ROOT/'config/chem-luna-phase2.json'
    config=json.loads(config_path.read_text())
    if config['search_rounds']!=2 or config['budget_status']!='subscription_only_authorized':
        raise RuntimeError('Expected authorized two-round budget')
    validate_cache()
    run=ROOT/'runs/experiments'/config['experiment_id']
    old=run/'evolution/chemistry'
    root=run/'authorized-recovery';root.mkdir(exist_ok=False)
    state={'status':'running','authorization':'User explicitly requested rerun after schema fix; evaluate two unchanged candidates', 'started_at':datetime.now(timezone.utc).isoformat()}
    dump(root/'status.json',state)
    try:
        seed=ROOT/'runs/experiments'/config['seed_experiment']
        selected=json.loads((seed/'evolution/chemistry/selected.json').read_text())
        parent=Path(selected['bundle'])
        if bundle_hash(parent)!=selected['sha256']:raise RuntimeError('Seed changed')
        collector=lambda path:collect(path,expected_model='gpt-5.6-luna')
        incumbent=collector(seed/'jobs'/config['seed_job'])
        names=[Path(t).name for t in config['domains']['chemistry']]
        if len(incumbent)!=6:raise RuntimeError('Incomplete seed results')
        accept(incumbent,incumbent,names)
        history=[]
        for number in (1,2):
            source=old/f'chemistry-round-{number:02d}'
            folder=root/f'chemistry-recovery-{number:02d}';folder.mkdir()
            hashes=json.loads((source/'source.json').read_text())
            if bundle_hash(source/'candidate')!=hashes['candidate_sha256']:raise RuntimeError('Archived candidate changed')
            for name in ('parent','candidate','evidence'):shutil.copytree(source/name,folder/name)
            mechanism=json.loads((source/'mechanism.json').read_text())
            directive=json.loads((source/'evidence/search-directive.json').read_text())
            errors=validate_bundle(folder/'candidate')+validate_plan(mechanism,changed_files(folder/'parent',folder/'candidate'),directive)
            if errors:raise RuntimeError(str(errors))
            review=role('critic',folder,
                'Review this existing candidate and its evidence/mechanism.json. Do not edit files. '
                'The legacy component label is now supported; judge the actual implementation. '
                'Check private-data access, benchmark answer hardcoding, model/billing overrides and leakage. '
                'Verify it implements one mechanism hypothesis, with usable helper interfaces and synthetic smoke-test fixtures. '
                'Only approve if it respects the boundaries. Do not execute model calls or benchmark experiments. '
                'Return approved and reasons.',
                {'type':'object','properties':{'approved':{'type':'boolean'},'reasons':{'type':'array','items':{'type':'string'}}},'required':['approved','reasons'],'additionalProperties':False},
                boundary=config['role_boundary'],model=config['model_roles']['critic']).get('structured_output')
            if not isinstance(review,dict) or not isinstance(review.get('approved'),bool):raise RuntimeError('Invalid critic verdict')
            if bundle_hash(folder/'candidate')!=hashes['candidate_sha256']:raise RuntimeError('Candidate changed during review')
            verdict={'round':number,'phase':2,'recovery':True,'mechanism':mechanism,'candidate_sha256':hashes['candidate_sha256'],
                     'original_parent_sha256':hashes['parent_sha256'],'comparison_incumbent_sha256':bundle_hash(parent),'critic':review}
            if not review['approved']:
                verdict.update(accepted=False,reason='critic_rejected',trials=0)
            else:
                job=f'chemistry-r{number:02d}-authorized-recovery-01'
                subprocess.run([sys.executable,str(ROOT/'src/run_job.py'),'--name',job,'--domain','chemistry','--config',str(config_path),'--bundle',str(folder/'candidate'),'--attempts','3'],check=True)
                rows=collector(run/'jobs'/job)
                if len(rows)!=6 or any(sum(r['task']==n for r in rows)!=3 for n in names):raise RuntimeError('Incomplete evaluation')
                verdict.update(accept(incumbent,rows,names,rule='total_non_decreasing'),job=job,passes=sum(r['reward'] for r in rows),trials=6)
                dump(folder/'component-telemetry.json',telemetry(rows,folder/'candidate'))
                if verdict['accepted']:parent=folder/'candidate';incumbent=rows
            dump(folder/'decision.json',verdict);history.append(verdict);dump(root/'history.json',history)
            print('Round completed',number,'accepted',verdict['accepted'],'trials',verdict.get('trials'),'passes',verdict.get('passes'),flush=True)
        dump(root/'selected.json',{'bundle':str(parent),'sha256':bundle_hash(parent),'passes':sum(r['reward'] for r in incumbent),'trials':len(incumbent),'frozen_at':datetime.now(timezone.utc).isoformat()})
        state.update(status='complete',finished_at=datetime.now(timezone.utc).isoformat());dump(root/'status.json',state)
    except BaseException as error:
        state.update(status='stopped',error_type=type(error).__name__,message=str(error));dump(root/'status.json',state);raise

if __name__=='__main__':main()

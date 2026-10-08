"""Explicit user-authorized selection change; reuse running R4, never rerun trials."""
import json, time, subprocess, sys
from pathlib import Path
from datetime import datetime, timezone
from job_spec import ROOT
from codex_evaluation import collect
from repaired_evaluation import collect_refs
from evaluation import accept
from native_bundle import bundle_hash

def main():
    run=ROOT/'runs/experiments/chem-luna-rsi-fresh-20261008'
    root=run/'evolution/chemistry'
    record=root/'selection-rule-change.json'
    state={'authorization':'User accepts total improvements and ties, permitting per-task regression', 'rule':'total_non_decreasing','status':'running','at':datetime.now(timezone.utc).isoformat(),'running_round4_parent_unchanged':True}
    with record.open('x') as f:json.dump(state,f,indent=2)
    try:
        config=json.loads((ROOT/'config/chem-luna.json').read_text())
        names=[Path(t).name for t in config['domains']['chemistry']]
        collector=lambda p:collect(p,expected_model='gpt-5.6-luna')
        original=json.loads((root/'history.json').read_text())
        with (root/'history-before-rule-change.json').open('x') as f:json.dump(original,f,indent=2)
        incumbent=collect_refs(run/'jobs',original[0]['effective_trial_refs'],collector)
        refs=original[0]['effective_trial_refs']; best=1; history=[original[0]]
        for number in range(2,5):
            folder=root/f'chemistry-round-{number:02d}'
            job=f'chemistry-r{number:02d}-search'
            if number==4:
                marker=run/'launches'/job/'job-result.json'
                while not marker.exists():
                    if (run/'launches'/job/'failure.json').exists():raise RuntimeError('Round 4 job failed')
                    try:
                        status=Path('/proc/4036731/stat').read_text().split(') ')[1].split()[0]
                        if status=='Z':raise RuntimeError('Round 4 worker exited without completion')
                    except FileNotFoundError:raise RuntimeError('Round 4 worker missing without completion')
                    time.sleep(10)
            rows=collector(run/'jobs'/job)
            if len(rows)!=6 or any(sum(r['task']==n for r in rows)!=3 for n in names):raise RuntimeError('Incomplete trial set')
            selection=accept(incumbent,rows,names,rule='total_non_decreasing')
            if number<4: verdict=dict(original[number-1])
            else:
                source=json.loads((folder/'source.json').read_text())
                verdict={'round':number,'job':job,**source,'proposal':json.loads((folder/'proposer-stdout.json').read_text()).get('result',''),'diff':(folder/'candidate.diff').read_text()}
            verdict.update(selection,selection_amended=True)
            if number==4:
                with (folder/'decision.json').open('x') as f:json.dump(verdict,f,indent=2)
            else:
                with (folder/'decision-amended.json').open('x') as f:json.dump(verdict,f,indent=2)
            history.append(verdict)
            if selection['accepted']:
                best=number;incumbent=rows;refs=[{'job':job,'trial':r['trial']} for r in rows]
            (root/'history.json').write_text(json.dumps(history,indent=2))
            print('Selection',number,selection,flush=True)
        parent=root/f'chemistry-round-{best:02d}/candidate'
        resume={'start_round':5,'parent':str(parent),'sha256':bundle_hash(parent),'refs':refs,'feedback_job':'chemistry-r04-search'}
        resume_path=root/'selection-resume.json';resume_path.write_text(json.dumps(resume,indent=2))
        state.update(status='selection_complete',selected_round=best);record.write_text(json.dumps(state,indent=2))
        subprocess.run([sys.executable,str(ROOT/'src/evolve.py'),'--domain','chemistry','--config',str(ROOT/'config/chem-luna.json'),'--resume-state',str(resume_path)],check=True)
    except BaseException as error:
        state.update(status='stopped',message=str(error));record.write_text(json.dumps(state,indent=2));raise
if __name__=='__main__':main()

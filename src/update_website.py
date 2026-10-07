"""Render only observed local outcomes; never substitute leaderboard scores."""
import html
import json
from pathlib import Path
import re
from datetime import datetime, timezone
from evaluation import collect
from job_spec import ROOT

def main():
    config=json.loads((ROOT/'config/experiment.json').read_text())
    all_records=[]
    for job in sorted((ROOT/'runs/jobs').glob('*')):
        if not job.is_dir():continue
        for record in collect(job):
            record.pop('path',None);record['job']=job.name;all_records.append(record)
    export={'updated_at':datetime.now(timezone.utc).isoformat(),'protocol':config,
            'trials':all_records,'decisions':[],'billing':'subscription_only; CLI dollar estimates are not charges'}
    export['domain_stops']=[json.loads(p.read_text()) for p in (ROOT/'runs/domain-stops').glob('*.json')]
    export['role_calls']=[]
    for path in (ROOT/'runs/evolution').glob('*/*/*-stdout.json'):
        try:call=json.loads(path.read_text())
        except ValueError:continue
        export['role_calls'].append({'domain':path.parent.parent.name,'round':path.parent.name,
            'role':path.name.removesuffix('-stdout.json'),'is_error':call.get('is_error'),
            'model_usage':call.get('modelUsage'),'usage':call.get('usage'),
            'list_price_estimate_usd':call.get('total_cost_usd')})
    parts=[]
    for domain in ['biology','chemistry']:
        for directory in sorted((ROOT/'runs/evolution'/domain).glob('*round-*')):
            decision_path=directory/'decision.json'
            if not decision_path.exists():continue
            decision=json.loads(decision_path.read_text());export['decisions'].append({'domain':domain,**decision})
            source=json.loads((directory/'source.json').read_text()) if (directory/'source.json').exists() else {}
            diff=(directory/'candidate.diff').read_text() if (directory/'candidate.diff').exists() else ''
            parts.append('<details><summary>'+html.escape(domain+' · 第 '+str(decision['round'])+' 轮 · '+('接受' if decision['accepted'] else '拒绝'))+'</summary><p>'+html.escape(json.dumps(decision,ensure_ascii=False))+'</p><p class="note">'+html.escape(json.dumps(source))+'</p><pre style="overflow:auto;white-space:pre-wrap;font-size:13px">'+html.escape(diff)+'</pre></details>')
    def text_score(records):
        if not records:return '未评估'
        errors=[r for r in records if r.get('exception') or r.get('model_audit_error') or r.get('api_error') or r['reward'] is None]
        graded=[r for r in records if r['reward'] is not None]
        text=(f"{sum(r['reward'] for r in graded):g} / {len(records)}" if graded else '尚无评分')
        if len(graded)<len(records):text+=f'；{len(records)-len(graded)} 次缺少评分'
        if errors:text+=f'；{len(errors)} 次执行异常（未剔除）'
        return text
    rows=[]
    for domain,tasks in config['domains'].items():
        selected_path=ROOT/'runs/evolution'/domain/'selected.json'
        selected=json.loads(selected_path.read_text()) if selected_path.exists() else None
        accepted=[d for d in export['decisions'] if d['domain']==domain and d['accepted']]
        current_job=accepted[-1]['job'] if accepted else None
        for task in tasks:
            name=Path(task).name
            baseline=[r for r in all_records if r['task']==name and r['job'].startswith('h0-search')]
            candidate=[r for r in all_records if r['task']==name and r['job']==current_job]
            candidate_label=text_score(candidate) if current_job else ('保留 H₀' if selected else '未评估')
            rows.append(f'<tr data-domain="{domain}"><td>{html.escape(name)}</td><td>{"Bio" if domain=="biology" else "Chem"}</td><td>{text_score(baseline)}</td><td>{candidate_label}</td><td>Evolve 搜索</td></tr>')
    final_records=[r for r in all_records if '-final-' in r['job']]
    if final_records:
        for domain,tasks in config['domains'].items():
            for task in tasks:
                name=Path(task).name
                baseline=[r for r in final_records if r['task']==name and '-h0-final-' in r['job']]
                selected=[r for r in final_records if r['task']==name and '-selected-final-' in r['job']]
                rows.append(f'<tr data-domain="{domain}"><td>{html.escape(name)}</td><td>{domain}</td><td>{text_score(baseline)}</td><td>{text_score(selected)}</td><td>同任务最终复测</td></tr>')
    target=ROOT/'website/dist/index.html';page=target.read_text()
    def replace(identifier,content,tag='p'):
        nonlocal page
        pattern=rf'(<{tag}\b[^>]*id="{identifier}"[^>]*>).*?(</{tag}>)'
        page,count=re.subn(pattern,lambda m:m[1]+content+m[2],page,flags=re.S)
        if count!=1:raise ValueError('Missing unique website section: '+identifier)
    replace('scores',''.join(rows),'tbody')
    status=config['status']
    replace('status-title',{'running':'H₀ / RSI 实验进行中','complete':'实验已完成','failed':'实验停止，保留已有结果'}.get(status,'已授权，准备运行'),'strong')
    replace('status-detail',f'仅使用现有 Claude Max 订阅。Bio、Chem 各最多 5 轮。已归档 {len(all_records)} 次任务结果；拒绝、失败和中断均保留。')
    replace('protocol-detail','每领域最多 5 轮，每轮 1 个候选；搜索阶段每任务运行 1 次。仅当官方通过率严格提高且无逐任务通过回退时接受，同分保留父版本。最终 H₀ 与选定版本各每任务复测 3 次。仅使用现有 Max 订阅，禁止付费 API 与额外计费；遇到订阅限制停止，不自动重试。搜索是小样本探索，不声明统计显著性。')
    input_tokens=sum((r['agent_result'].get('n_input_tokens') or 0) for r in all_records)
    output_tokens=sum((r['agent_result'].get('n_output_tokens') or 0) for r in all_records)
    policy_cost=sum((r['agent_result'].get('cost_usd') or 0) for r in all_records)
    role_cost=sum((r.get('list_price_estimate_usd') or 0) for r in export['role_calls'])
    replace('history-detail',f'已归档 {len(export["decisions"])} 个候选决定、{len(export["role_calls"])} 次演化角色调用。任务执行已报告 input tokens：{input_tokens:,}；output tokens：{output_tokens:,}。任务调用标价估算 ${policy_cost:.3f}，分析／提案／检查标价估算 ${role_cost:.3f}。尚在执行或缺失的用量不包含在内；这些估算不是订阅外扣费。<br><a href="experiment.json">下载实验摘要、角色用量与协议</a>')
    page=re.sub(r'<!-- decision-log-start -->.*?<!-- decision-log-end -->','',page,flags=re.S)
    if parts:page=page.replace('<footer>','<!-- decision-log-start --><section><h2>逐轮真实改动</h2>'+''.join(parts)+'</section><!-- decision-log-end --><footer>')
    page=re.sub(r'<!-- stop-log-start -->.*?<!-- stop-log-end -->','',page,flags=re.S)
    if export['domain_stops']:
        notices=[]
        for stop in export['domain_stops']:
            notices.append('<p><b>'+html.escape(stop['domain'])+'</b>：'+html.escape(stop['reason'])+'。保留已有官方评分及执行状态，不自动重试或绕过模型拒绝。</p>')
        page=page.replace('<footer>','<!-- stop-log-start --><section><h2>停止与异常记录</h2>'+''.join(notices)+'</section><!-- stop-log-end --><footer>')
    page=page.replace('Sonnet RSI / 当前实验尚无 performance 结果','Sonnet RSI / 仅展示本次实验的实际记录')
    target.write_text(page)
    (ROOT/'website/dist/experiment.json').write_text(json.dumps(export,ensure_ascii=False,indent=2)+'\n')
    print('Website updated from',len(all_records),'archived trials;',len(export['decisions']),'decisions')

if __name__=='__main__':main()

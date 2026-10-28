"""Run the existing playbook with real Ansible and an isolated kubectl recorder."""
import argparse,hashlib,json,os,re,shutil,subprocess,sys,tempfile,time
import ansible
from datetime import datetime,timezone
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,help='Keep native logs in a new directory; otherwise use temporary reports.')
args=parser.parse_args()
if os.name!='posix':raise SystemExit('These Ansible integration tests require a POSIX control node.')
root=Path(__file__).resolve().parents[2]
packages=Path(ansible.__file__).resolve().parent
temporary_report=args.output is None
out=Path(tempfile.mkdtemp(prefix='cicd-ansible-report-')) if temporary_report else args.output.resolve()
if not temporary_report:out.mkdir(exist_ok=False)
inputs=[root/'ansible/playbooks/configure-app.yml',root/'ansible/inventory/local.ini',
        root/'ansible/templates/app.env.j2',root/'scripts/test-ansible.sh',Path(__file__).resolve()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
before={str(path):sha(path) for path in inputs}
temporary_root=Path(tempfile.gettempdir()).resolve()
scratch=Path(tempfile.mkdtemp(prefix='cicd-ansible-cases-',dir=temporary_root))
marker=scratch/'.codex-owned';marker.write_text('owned isolated regression scratch\n')
rows=[];started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
fixture=r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:];remaining=list(args)
if remaining[:1]==['--context']:
    remaining=remaining[2:]
if remaining[:1]==['-n']:
    remaining=remaining[2:];namespaced=True
else:
    namespaced=False
if remaining[:2]==['create','namespace']:
    stage='namespace_build';kind='Namespace'
elif remaining[:2]==['create','configmap']:
    stage='configmap_build';kind='ConfigMap'
elif remaining==['apply','-f','-']:
    stage='configmap_apply' if namespaced else 'namespace_apply';kind=None
else:
    raise SystemExit('Unexpected fixture invocation: '+repr(args))
stdin=sys.stdin.read() if kind is None else ''
row={'stage':stage,'argv':args,'kubeconfig':os.environ.get('KUBECONFIG'),'stdin':stdin}
with Path(os.environ['RECORDER']).open('a') as stream:stream.write(json.dumps(row)+'\n')
if stage==os.environ.get('FAIL_STAGE'):
    print('controlled backend failure: '+stage,file=sys.stderr);raise SystemExit(32)
if kind:
    print('apiVersion: v1\nkind: '+kind+'\nmetadata: {name: fixture}')
else:
    print('resource unchanged')
'''
try:
    bins=scratch/'bin';bins.mkdir()
    recorder=scratch/'record-kubectl.py';recorder.write_text(fixture)
    stub=bins/'kubectl'
    stub.write_text('#!/bin/sh\nexec "$CICD_TEST_PYTHON" "$CICD_TEST_RECORDER" "$@"\n')
    stub.chmod(0o700)
    config=scratch/'ansible.cfg';config.write_text('[defaults]\nretry_files_enabled = False\n')
    home=scratch/'home';home.mkdir()
    clean={key:value for key,value in os.environ.items() if not key.startswith('ANSIBLE_')}
    for key in ('TF_ENV','KUBECONFIG','KUBECONTEXT','CLUSTER_NAME','FAIL_STAGE','RECORDER'):
        clean.pop(key,None)
    clean.update(PATH=str(bins)+':/usr/bin:/bin',HOME=str(home),PYTHONDONTWRITEBYTECODE='1',
                 CICD_TEST_PYTHON=sys.executable,CICD_TEST_RECORDER=str(recorder),ANSIBLE_CONFIG=str(config),ANSIBLE_HOME=str(scratch/'ansible-home'),
                 ANSIBLE_LOCAL_TEMP=str(scratch/'local'),ANSIBLE_REMOTE_TEMP=str(scratch/'remote'),
                 ANSIBLE_PYTHON_INTERPRETER=sys.executable,ANSIBLE_NOCOLOR='1')
    defaults={'ENVIRONMENT':'dev','RELEASE_COLOR':'blue','BUILD_ID':'local','GIT_SHA':'dev','DEPLOY_MODE':'blue-green'}
    def run(name,*,overrides=None,environment=None,deploy=None,context='kind-cicd-demo',kubeconfig=None,
            fail=None,expected_changed=None):
        directory=deploy or scratch/name/'render with spaces'
        extra={'deploy_dir':str(directory),**(overrides or {})}
        extra_file=scratch/(name+'-vars.json');extra_file.write_text(json.dumps(extra))
        record=scratch/(name+'-calls.jsonl')
        env=dict(clean,RECORDER=str(record),**(environment or {}))
        if fail:env['FAIL_STAGE']=fail
        command=[sys.executable,'-m','ansible.cli.playbook','-i',
                 str(root/'ansible/inventory/local.ini'),str(root/'ansible/playbooks/configure-app.yml'),
                 '-e','@'+str(extra_file)]
        case_clock=time.monotonic()
        process=subprocess.run(command,cwd=scratch,env=env,capture_output=True,timeout=60)
        raw=process.stdout+process.stderr;(out/(name+'.log')).write_bytes(raw)
        calls=[json.loads(line) for line in record.read_text().splitlines()] if record.exists() else []
        text=raw.decode('utf-8',errors='replace')
        recap=re.search(r'localhost\s+:\s+ok=(\d+)\s+changed=(\d+)\s+unreachable=(\d+)\s+failed=(\d+)\s+skipped=(\d+)\s+rescued=(\d+)\s+ignored=(\d+)',text)
        assert recap,name+': missing native recap'
        counts=dict(zip(('ok','changed','unreachable','failed','skipped','rescued','ignored'),map(int,recap.groups())))
        assert all(counts[key]==0 for key in ('unreachable','skipped','rescued','ignored')),counts
        stages=['namespace_build','namespace_apply','configmap_build','configmap_apply']
        if fail:
            stages=stages[:stages.index(fail)+1]
            assert process.returncode!=0 and counts['failed']==1,(name,process.returncode,counts)
            assert 'controlled backend failure: '+fail in text
        else:
            assert process.returncode==0 and counts['failed']==0 and counts['ok']==6,(name,process.returncode,counts)
        if expected_changed is not None:assert counts['changed']==expected_changed,(name,counts)
        assert [call['stage'] for call in calls]==stages,(name,calls)
        namespace=extra.get('namespace','cicd-demo');configmap=extra.get('configmap_name','cicd-demo-env')
        prefix=['--context',context] if context else []
        expected={
            'namespace_build':prefix+['create','namespace',namespace,'--dry-run=client','-o','yaml'],
            'namespace_apply':prefix+['apply','-f','-'],
            'configmap_build':prefix+['-n',namespace,'create','configmap',configmap,
                                      '--from-env-file='+str(directory/'app.env'),'--dry-run=client','-o','yaml'],
            'configmap_apply':prefix+['-n',namespace,'apply','-f','-']}
        expected_kubeconfig=kubeconfig or str(root/'ansible/playbooks/../../.kube/config')
        for call in calls:
            assert call['argv']==expected[call['stage']],(name,call['argv'],expected[call['stage']])
            assert call['kubeconfig']==expected_kubeconfig,(name,call['kubeconfig'],expected_kubeconfig)
            if call['stage'].endswith('_apply'):
                kind='Namespace' if call['stage']=='namespace_apply' else 'ConfigMap'
                assert call['stdin']=='apiVersion: v1\nkind: '+kind+'\nmetadata: {name: fixture}\n'
        expected_env=dict(defaults)
        for key,var in [('ENVIRONMENT','app_environment'),('RELEASE_COLOR','release_color'),
                        ('BUILD_ID','build_id'),('GIT_SHA','git_sha'),('DEPLOY_MODE','deploy_mode')]:
            if var in extra:expected_env[key]=extra[var]
        rendered=(directory/'app.env').read_text().splitlines()
        assert len(rendered)==5 and dict(line.split('=',1) for line in rendered)==expected_env,(name,rendered)
        row={'name':name,'status':'PASS','seconds':time.monotonic()-case_clock,'native_exit':process.returncode,
             'expected_backend_failure':fail,'recap':counts,'calls':calls,'rendered':expected_env,
             'log_sha256':sha(out/(name+'.log'))}
        rows.append(row);print(json.dumps({key:row[key] for key in ('name','status','seconds','native_exit')}),flush=True)
        return directory
    default_dir=run('local_defaults',expected_changed=2)
    run('idempotent_repeat',deploy=default_dir,expected_changed=0)
    run('metadata_overrides',overrides={'app_environment':'staging','release_color':'green','build_id':'build 42',
                                      'git_sha':'abc123','deploy_mode':'rolling'})
    custom_config=str(scratch/'config with spaces')
    run('context_and_paths',overrides={'namespace':'team-a','configmap_name':'team.settings'},
        environment={'CLUSTER_NAME':'irrelevant','KUBECONTEXT':"fixture context 'quoted'",'KUBECONFIG':custom_config},
        context="fixture context 'quoted'",kubeconfig=custom_config)
    run('external_defaults',environment={'TF_ENV':'aws-eks'},context='',kubeconfig=str(home/'.kube/config'))
    merged=str(scratch/'cloud one')+':'+str(scratch/'cloud two')
    run('external_merged',environment={'TF_ENV':'aws-eks','KUBECONFIG':merged,'KUBECONTEXT':''},context='',kubeconfig=merged)
    for stage in ('namespace_build','namespace_apply','configmap_apply'):
        run('failure_'+stage,fail=stage)
    after={str(path):sha(path) for path in inputs}
    assert after==before,'Application sources changed'
    result={'status':'PASS_SCOPED','utc':started,'seconds':time.monotonic()-clock,'cases':rows,
            'source_hashes':before,'sources_unchanged':True,'python':sys.version.split()[0],
            'python_executable':str(Path(sys.executable).resolve()),'python_sha256':sha(Path(sys.executable).resolve()),
            'ansible_cli_sha256':sha(packages/'cli/playbook.py'),
            'ansible_version_file_sha256':sha(packages/'release.py'),
            'verifier_sha256':sha(Path(__file__)),
            'limits':['Real Ansible and local file/template modules; kubectl is an isolated recording fixture.',
                      'No live Kubernetes, provider credentials, Jenkins or cloud validation.',
                      'Existing reserved-name namespace warning remains visible; no failure or suppression.',
                      'Idempotence is demonstrated for local rendering and unchanged fixture responses.']}
except BaseException as exc:
    result={'status':'FAILED','utc':started,'seconds':time.monotonic()-clock,'cases':rows,'error':repr(exc),
            'source_hashes':before,'verifier_sha256':sha(Path(__file__))}
finally:
    if scratch.parent==temporary_root and scratch.name.startswith('cicd-ansible-cases-') and marker.is_file() and not scratch.is_symlink():
        shutil.rmtree(scratch)
    result['cleanup_verified']=not scratch.exists()
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({key:result[key] for key in ('status','seconds','cleanup_verified')}),flush=True)
success=result['status']=='PASS_SCOPED' and result['cleanup_verified']
if not success:
    print(result.get('error','Cleanup failed'),file=sys.stderr)
    for log in sorted(out.glob('*.log')):
        print(log.name+':\n'+log.read_text(errors='replace')[-6000:],file=sys.stderr)
if temporary_report:
    shutil.rmtree(out)
    success=success and not out.exists()
raise SystemExit(0 if success else 1)

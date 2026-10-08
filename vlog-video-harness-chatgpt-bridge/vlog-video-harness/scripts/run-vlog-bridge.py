#!/usr/bin/env python3
import argparse, json, os, subprocess, sys, time

ap=argparse.ArgumentParser()
ap.add_argument('url'); ap.add_argument('images',type=int); ap.add_argument('mode',choices=['auto','native','script'])
ap.add_argument('--issue',required=True)
a=ap.parse_args()
root=os.path.abspath(os.path.join(os.path.dirname(__file__),'..'))
out=os.path.join(root,'output',f'github-job-{a.issue}')
os.makedirs(out,exist_ok=True)
status={'status':'running','job':a.issue,'url':a.url,'output_dir':out}
json.dump(status,open(os.path.join(out,'job-result.json'),'w'),indent=2)
try:
    cmd=[os.path.join(root,'scripts','run-vlog'),a.url,str(a.images),a.mode]
    env=os.environ.copy(); env['HARNESS_JOB_DIR']=out
    p=subprocess.run(cmd,cwd=root,env=env,text=True,capture_output=True)
    status['status']='success' if p.returncode==0 else 'failed'
    status['stdout_tail']=p.stdout[-4000:]
    status['stderr_tail']=p.stderr[-4000:]
    status['returncode']=p.returncode
    # run-vlog normally creates its own timestamped job. Copy the latest result into bridge output.
    import glob, shutil
    jobs=sorted(glob.glob(os.path.join(root,'output','job-*')),key=os.path.getmtime)
    if jobs:
        status['pipeline_job']=jobs[-1]
        dst=os.path.join(out,'pipeline')
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(jobs[-1],dst)
except Exception as e:
    status['status']='failed'; status['error']=repr(e)
json.dump(status,open(os.path.join(out,'job-result.json'),'w'),indent=2)
if status['status']!='success': sys.exit(1)

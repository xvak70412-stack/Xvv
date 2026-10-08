#!/usr/bin/env python3
import argparse, json, os, re, subprocess, sys

def parse_body(body):
    if not body:
        raise SystemExit('empty issue body')
    m = re.search(r'(?im)^\s*url\s*:\s*(\S+)\s*$', body)
    if not m:
        raise SystemExit('issue body must contain: URL: <youtube-url>')
    url = m.group(1)
    if not re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be)/', url):
        raise SystemExit('only YouTube URLs are accepted')
    mode = 'auto'
    mm = re.search(r'(?im)^\s*mode\s*:\s*(auto|native|script)\s*$', body)
    if mm: mode = mm.group(1)
    images = 5
    im = re.search(r'(?im)^\s*images\s*:\s*(\d+)\s*$', body)
    if im: images = max(1, min(10, int(im.group(1))))
    return {'url': url, 'mode': mode, 'images': images}

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('parse'); p.add_argument('body')
    c=sub.add_parser('comment'); c.add_argument('--repo',required=True); c.add_argument('--issue',required=True); c.add_argument('--status-file',required=True); c.add_argument('--run-url',required=True)
    a=ap.parse_args()
    if a.cmd=='parse': print(json.dumps(parse_body(a.body))); return
    data=json.load(open(a.status_file)) if os.path.exists(a.status_file) else {'status':'failed','error':'status file missing'}
    msg=f"## Video job result\n\n**Status:** `{data.get('status','unknown')}`\n\n**Job:** `{data.get('job','unknown')}`\n\n**Run:** {a.run_url}\n"
    if data.get('output_dir'): msg += f"\nOutput directory: `{data['output_dir']}`\n"
    if data.get('error'): msg += f"\n**Error:** {data['error']}\n"
    subprocess.run(['gh','issue','comment',a.issue,'--repo',a.repo,'--body',msg],check=False)
if __name__=='__main__': main()

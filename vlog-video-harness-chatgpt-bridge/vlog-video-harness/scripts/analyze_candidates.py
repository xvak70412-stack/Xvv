import argparse,json,re,subprocess
from pathlib import Path
def cues(p):
 s=p.read_text(errors="ignore"); out=[]
 for b in re.split(r"\\n\\s*\\n",s):
  m=re.search(r"(\\d\\d:\\d\\d:\\d\\d[.,]\\d+)\\s+-->\\s+(\\d\\d:\\d\\d:\\d\\d[.,]\\d+)",b)
  if not m: continue
  def sec(x):
   h,mi,se=x.replace(",",".").split(":"); return int(h)*3600+int(mi)*60+float(se)
  tx=" ".join(re.sub(r"<[^>]+>","",x).strip() for x in b.splitlines()[2:] if x.strip())
  if tx: out.append({"start":sec(m.group(1)),"end":sec(m.group(2)),"text":tx})
 return out
p=argparse.ArgumentParser();p.add_argument("video");p.add_argument("subs");p.add_argument("--images",type=int);p.add_argument("--mode");p.add_argument("--out");a=p.parse_args()
all=[]
for f in Path(a.subs).glob("*.vtt"): all+=cues(f)
all.sort(key=lambda x:x["start"])
if all:
 step=max(1,len(all)//a.images); groups=[all[i:i+4] for i in range(0,len(all),step)][:a.images]
else:
 d=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",a.video],text=True))
 groups=[[{"start":d*(i+1)/(a.images+1),"text":""}] for i in range(a.images)]
m={"mode":a.mode,"needs_native_pixel_confirmation":a.mode=="auto","images":[{"title":f"candidate-{i+1:02d}","times":[round(x["start"],3) for x in g],"lines":[x["text"] for x in g if x["text"]]} for i,g in enumerate(groups)]}
Path(a.out).parent.mkdir(parents=True,exist_ok=True);Path(a.out).write_text(json.dumps(m,ensure_ascii=False,indent=2))
print(json.dumps(m,ensure_ascii=False,indent=2))

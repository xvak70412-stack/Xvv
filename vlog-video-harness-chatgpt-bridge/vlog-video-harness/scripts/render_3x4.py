import argparse,json,subprocess,tempfile
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
p=argparse.ArgumentParser();p.add_argument("video");p.add_argument("manifest");p.add_argument("--out");p.add_argument("--width",type=int,default=1440);a=p.parse_args()
o=Path(a.out);o.mkdir(parents=True,exist_ok=True);m=json.loads(Path(a.manifest).read_text(encoding="utf-8"));W=a.width;H=round(W*4/3)
def grab(t,d):
 subprocess.run(["ffmpeg","-y","-ss",str(t),"-i",a.video,"-frames:v","1","-q:v","2",str(d)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
for n,it in enumerate(m["images"],1):
 ts=it["times"]
 if not ts: continue
 with tempfile.TemporaryDirectory() as td:
  hero=Path(td)/"hero.jpg";grab(ts[0],hero)
  c=Image.new("RGB",(W,H)); c.paste(ImageOps.fit(Image.open(hero).convert("RGB"),(W,round(H*.7))), (0,0)); y=round(H*.7); sh=max(1,(H-y)//len(ts))
  for j,t in enumerate(ts):
   q=Path(td)/f"{j}.jpg";grab(t,q);c.paste(ImageOps.fit(Image.open(q).convert("RGB"),(W,sh)),(0,y+j*sh))
  c.save(o/f"{n:02d}-{it['title']}.jpg",quality=94)
imgs=[x for x in o.glob("*.jpg")]
if imgs:
 ims=[]
 for p in imgs:
  im=Image.open(p);im.thumbnail((360,480));ims.append((p.name,im.copy()))
 s=Image.new("RGB",(360*len(ims),520),"white");d=ImageDraw.Draw(s)
 for i,(n,im) in enumerate(ims):s.paste(im,(i*360,0));d.text((i*360+5,490),n,fill="black")
 s.save(o/"contact_sheet.jpg")
print("render complete")

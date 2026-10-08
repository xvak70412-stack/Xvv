import argparse,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("video");p.add_argument("out");p.add_argument("--count",type=int,default=48);a=p.parse_args()
o=Path(a.out);o.mkdir(parents=True,exist_ok=True)
d=float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",a.video],text=True))
for i in range(a.count):
 t=d*(i+.5)/a.count
 subprocess.run(["ffmpeg","-y","-ss",str(t),"-i",a.video,"-frames:v","1","-q:v","3",str(o/f"{i:03d}.jpg")],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print("sample frames complete")

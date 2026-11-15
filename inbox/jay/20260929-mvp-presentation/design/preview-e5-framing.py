from pathlib import Path
from PIL import Image,ImageDraw
r=Path(__file__).resolve().parents[1]
a=Image.open(r/'output/e5-transition-source-2.png')
b=Image.open(r/'output/e5-transition-source-3.png')
s=1.18;x=-60;y=-64
c=b.transform(b.size,Image.Transform.AFFINE,(1/s,0,-x/s,0,1/s,-y/s),resample=Image.Resampling.BICUBIC)
out=Image.new('RGB',(854*3,510));d=ImageDraw.Draw(out)
for i,(im,title) in enumerate([(a,'POV END'),(b,'PREVIOUS E5 START'),(c,'MATCHED E5 START')]):out.paste(im,(854*i,30));d.text((854*i+10,8),title,fill='white')
out.resize((1536,306)).save(r/'output/e5-framing-match-preview.jpg')


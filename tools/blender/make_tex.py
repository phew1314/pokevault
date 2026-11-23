# Card back (matches site's createCardBackTexture, at 4x res) + envelope print
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import random, math
S=4
W,H=360*S,500*S
im=Image.new('RGB',(W,H),'#172554'); d=ImageDraw.Draw(im)
d.rectangle([14*S-9*S,14*S-9*S,346*S+9*S,486*S+9*S],outline='#60a5fa',width=18*S)
cx,cy,r=180*S,250*S,72*S
d.pieslice([cx-r,cy-r,cx+r,cy+r],180,360,fill='#ef4444')
d.pieslice([cx-r,cy-r,cx+r,cy+r],0,180,fill='#f8fafc')
d.ellipse([cx-r,cy-r,cx+r,cy+r],outline='#0f172a',width=8*S)
d.line([cx-r,cy,cx+r,cy],fill='#0f172a',width=8*S)
r2=20*S; d.ellipse([cx-r2,cy-r2,cx+r2,cy+r2],fill='#ffffff',outline='#0f172a',width=8*S)
im.save('/home/claude/blend/tex/cardback.png')

# Envelope print: matte black kraft with gold foil mask (separate mask for metallic)
EW,EH=1600,2300
env=Image.new('RGB',(EW,EH),'#0b0f1a'); m=Image.new('L',(EW,EH),0)
de=ImageDraw.Draw(env); dm=ImageDraw.Draw(m)
random.seed(3)
# subtle diagonal guilloche pattern
for i in range(-EH,EW,26):
    de.line([i,0,i+EH,EH],fill='#111827',width=3)
for k in range(2):
    pad=70+k*34
    dm.rectangle([pad,pad,EW-pad,EH-pad],outline=255,width=10 if k==0 else 4)
def font(sz):
    for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']:
        try: return ImageFont.truetype(p,sz)
        except: pass
    return ImageFont.load_default()
def ctext(y,t,sz):
    f=font(sz); w=dm.textlength(t,font=f); dm.text(((EW-w)/2,y),t,font=f,fill=255)
ctext(430,'POKÉVAULT',190)
ctext(690,'ORIPA',130)
ctext(880,'— SPECIAL LOT —',60)
# star emblem
cx,cy=EW//2,1450
pts=[]
for i in range(10):
    a=-math.pi/2+i*math.pi/5; rr=260 if i%2==0 else 110
    pts.append((cx+rr*math.cos(a),cy+rr*math.sin(a)))
dm.polygon(pts,fill=255)
dm.ellipse([cx-340,cy-340,cx+340,cy+340],outline=255,width=8)
ctext(1880,'1 CARD  •  NO RETURN',70)
ctext(2010,'No. 0030',60)
# tear notch guide line near top
for x in range(90,EW-90,40): dm.line([x,250,x+20,250],fill=255,width=5)
env.save('/home/claude/blend/tex/env_base.png'); m.save('/home/claude/blend/tex/env_foil.png')
print('ok')

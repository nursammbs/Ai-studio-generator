#!/usr/bin/env python3
"""AI-assisted sprite animation: animate poses from a transparent character sheet."""
from __future__ import annotations
import argparse, math, os, subprocess, wave
from pathlib import Path
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from imageio_ffmpeg import get_ffmpeg_exe

# Coordinates for the accompanying 1774x887 AI-generated cat/mouse sheet.
BOXES = {
    "cat_idle": (25,0,585,495), "cat_run": (570,65,1320,490),
    "cat_shock": (1260,0,1770,500), "mouse_idle": (45,490,530,875),
    "mouse_run": (580,490,1170,875), "mouse_shock": (1170,490,1770,885),
}
def font(size, bold=False):
    paths = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p,size)
            except OSError: pass
    return ImageFont.load_default()

def load_sprites(path):
    sheet=Image.open(path).convert("RGBA"); result={}
    for name,box in BOXES.items():
        im=sheet.crop(box); bb=im.getchannel("A").getbbox()
        result[name]=im.crop(bb) if bb else im
    return result

def background(t,w,h):
    im=Image.new("RGB",(w,h),(150,205,244)); d=ImageDraw.Draw(im)
    for y in range(h):
        if y<h*.64:
            f=y/(h*.64); c=(int(157-28*f),int(216-18*f),int(250-3*f))
        else:
            f=(y-h*.64)/(h*.36); c=(int(112-8*f),int(185-12*f),int(91-9*f))
        d.line((0,y,w,y),fill=c)
    off=int(t*12%250)
    d.ellipse((-200-off,315,480-off,580),fill=(116,190,128))
    d.ellipse((360-off//2,300,990-off//2,570),fill=(102,181,115))
    d.ellipse((800-off,330,1450-off,585),fill=(124,196,130))
    for cx0,cy in [(150+t*10%1500,115),(670+t*7%1500,155),(1060+t*8%1500,78)]:
        cx=int(cx0%(w+280))-140
        for ox,oy,rx,ry in [(-45,8,44,24),(0,-8,57,34),(43,7,42,23)]:
            d.ellipse((cx+ox-rx,cy+oy-ry,cx+ox+rx,cy+oy+ry),fill=(249,252,255))
    for x in range(-40,w+80,100):
        xx=x-int(t*20%100); y=435+int(7*math.sin(x*.02))
        d.ellipse((xx-65,y-42,xx+65,y+50),fill=(53,145,76))
        d.ellipse((xx-35,y-60,xx+33,y+27),fill=(66,160,80))
    d.rectangle((0,480,w,h),fill=(111,177,83)); d.rectangle((0,566,w,h),fill=(155,196,101))
    d.line((0,481,w,481),fill=(69,139,73),width=5)
    for i in range(22):
        x=int((i*73-int(t*44))%(w+40)); y=522+int(20*math.sin(i*2.1))
        d.line((x,y+5,x-2,y+28),fill=(44,121,57),width=3)
        col=[(255,232,95),(255,182,202),(255,255,240),(185,170,255)][i%4]
        for a in range(5):
            ang=a*math.tau/5; px=x+int(math.cos(ang)*7); py=y+int(math.sin(ang)*7)
            d.ellipse((px-5,py-5,px+5,py+5),fill=col)
        d.ellipse((x-4,y-4,x+4,y+4),fill=(247,173,48))
    for i in range(25):
        x=(i*59+int(t*37))%w; y=630+i%5*10
        d.line((x,y,x-9,y-18-i%3*4),fill=(64,142,62),width=3)
        d.line((x,y,x+7,y-13),fill=(74,151,66),width=3)
    return im

def paste(base,sprite,cx,bottom,target_h,tilt=0):
    sp=sprite.resize((max(1,int(sprite.width*target_h/sprite.height)),target_h),Image.Resampling.LANCZOS)
    if tilt: sp=sp.rotate(tilt,resample=Image.Resampling.BICUBIC,expand=True)
    x,y=int(cx-sp.width/2),int(bottom-sp.height)
    sh=Image.new("RGBA",(sp.width+50,30),(0,0,0,0)); ImageDraw.Draw(sh).ellipse((10,7,sp.width+40,25),fill=(35,68,35,75))
    base.paste(sh.convert("RGB"),(int(cx-sh.width/2),int(bottom-6)),sh.getchannel("A"))
    base.paste(sp,(x,y),sp)

def music(path,duration,sr=44100):
    n=int(sr*duration); a=np.zeros(n,dtype=np.float32); notes=[659.25,783.99,880,783.99,659.25,523.25,587.33,659.25]; beat=.3
    for k,start in enumerate(np.arange(0,duration,beat)):
        i=int(start*sr); end=min(n,i+int(beat*.78*sr)); t=np.arange(end-i)/sr
        env=np.exp(-t*5.5); a[i:end]+=(.12*np.sin(2*np.pi*notes[k%8]*t)+.035*np.sin(4*np.pi*notes[k%8]*t))*env
        if k%2==0: a[i:end]+=.09*np.sin(2*np.pi*110*t)*np.exp(-t*7)
    for start,f in [(10.8,180),(11.1,135),(11.35,100)]:
        i=int(start*sr); end=min(n,i+int(.22*sr)); t=np.arange(end-i)/sr; sweep=f+400*np.exp(-t*18)
        a[i:end]+=.16*np.sin(2*np.pi*np.cumsum(sweep)/sr)*np.exp(-t*8)
    a=np.clip(a,-.8,.8); pcm=(np.stack([a,a],axis=1)*32767).astype("<i2")
    with wave.open(str(path),"wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())

def render(sheet,output,seconds=15,fps=24,w=1280,h=720):
    s=load_sprites(sheet); output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    silent=output.with_name(output.stem+"_silent.mp4"); wav=output.with_suffix(".wav")
    wr=imageio.get_writer(str(silent),fps=fps,codec="libx264",quality=8,macro_block_size=16)
    captions=["A sleepy cat spots a tiny mouse...","The chase is on! Keep running!","Uh-oh... that bush wasn't on the map!"]
    for i in range(seconds*fps):
        t=i/fps; scene=0 if t<3.5 else 1 if t<9.5 else 2; local=t if scene==0 else t-3.5 if scene==1 else t-9.5
        im=background(t,w,h); d=ImageDraw.Draw(im)
        if scene==2:
            d.ellipse((825,435,1070,535),fill=(43,112,55)); d.ellipse((850,408,1035,510),fill=(49,127,60)); d.ellipse((880,426,1018,495),fill=(59,142,66))
        if scene==0:
            cx=250+10*math.sin(t*2); mx=1000+6*math.sin(t*3)
            paste(im,s["cat_idle"],cx,500+3*math.sin(t*4),270,1.2*math.sin(t*2))
            paste(im,s["mouse_idle"],mx,515+2*math.sin(t*5),150,2*math.sin(t*3))
            if 1.5<t<3.2:
                d.ellipse((cx+80,235,cx+108,263),fill=(255,247,184),outline=(45,50,65),width=3); d.text((cx+88,235),"!",font=font(22,True),fill=(40,45,60))
        elif scene==1:
            p=local/6; cx=160+520*p; mx=700+430*p; by=490+14*math.sin(local*12); my=520+9*math.sin(local*13+.5)
            paste(im,s["cat_run"] if int(local*5)%2==0 else s["cat_idle"],cx,by,245,2*math.sin(local*10))
            paste(im,s["mouse_run"] if int(local*6)%2==0 else s["mouse_idle"],mx,my,142,3*math.sin(local*11))
            for k in range(3):
                x,y=int(cx-135-k*28),int(by-55-k*12); d.line((x,y,x-18,y-3),fill=(255,255,255),width=4)
        else:
            cx=410+250*min(1,local/5.5*1.2)
            if local<1.8: paste(im,s["cat_run"],cx,490-55*math.sin(local*math.pi/1.8),250,-5*math.sin(local*3))
            elif local<2.5: paste(im,s["cat_shock"],cx+100,470,275,8*math.sin(local*9))
            else: paste(im,s["cat_shock"],cx+90,486,275)
            paste(im,s["mouse_shock"] if local<3.1 else s["mouse_idle"],935+45*math.sin(local*2),520,145,5*math.sin(local*4))
            if 2.4<local<4.5:
                d.rounded_rectangle((720,195,970,265),radius=16,fill=(255,248,198),outline=(55,50,48),width=3)
                d.text((755,207),"BONK!",font=font(43,True),fill=(234,70,47),stroke_width=2,stroke_fill=(255,255,255))
        if t>13.25:
            d.rounded_rectangle((205,170,1075,315),radius=24,fill=(255,255,255),outline=(45,59,70),width=4)
            d.text((278,192),"KEJAR-KEJARAN BELUM SELESAI!",font=font(37,True),fill=(37,58,78),stroke_width=1)
            d.text((380,254),"An AI-assisted cartoon short",font=font(23),fill=(70,91,98))
        d.rounded_rectangle((28,20,480,70),radius=14,fill=(255,255,255),outline=(39,58,70),width=2)
        d.text((45,29),"AI ANIME STUDIO • PILOT",font=font(23,True),fill=(36,55,75))
        d.rounded_rectangle((w//2-430,h-68,w//2+430,h-18),radius=16,fill=(255,255,255),outline=(37,58,66),width=2)
        b=d.textbbox((0,0),captions[scene],font=font(23,True)); d.text((w//2-(b[2]-b[0])/2,h-60),captions[scene],font=font(23,True),fill=(35,52,62))
        wr.append_data(np.asarray(im))
    wr.close(); music(wav,seconds); ffmpeg=get_ffmpeg_exe()
    proc=subprocess.run([ffmpeg,"-y","-i",str(silent),"-i",str(wav),"-c:v","copy","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(output)],capture_output=True,text=True)
    if proc.returncode: raise RuntimeError(proc.stderr[-2000:])
    silent.unlink(missing_ok=True)
    print(f"Rendered {output} ({seconds}s, {fps} fps, {w}x{h}, {output.stat().st_size:,} bytes)")

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sheet",type=Path,default=Path(__file__).parent/"assets"/"character_sheet.png")
    ap.add_argument("--output",type=Path,default=Path(__file__).parent/"ai_cartoon_short.mp4")
    ap.add_argument("--seconds",type=int,default=15); ap.add_argument("--fps",type=int,default=24)
    args=ap.parse_args(); render(args.sheet,args.output,args.seconds,args.fps)

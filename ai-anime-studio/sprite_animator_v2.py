#!/usr/bin/env python3
"""V2 cutout-cartoon renderer with cyclic AI-generated poses and timed action beats.

This is AI-art-assisted sprite animation, not neural text-to-video. Put the cat and
mouse 2x2 transparent sprite sheets in assets/ (provided in the V2 production kit).
"""
from __future__ import annotations
import argparse, math, os, subprocess
from pathlib import Path
import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw
from imageio_ffmpeg import get_ffmpeg_exe
from sprite_animator import background, font, music, paste

def load_cycle(sheet_path: str | Path) -> list[Image.Image]:
    sheet = Image.open(sheet_path).convert("RGBA")
    cw, ch = sheet.width // 2, sheet.height // 2
    if cw < 64 or ch < 64:
        raise ValueError("Sprite sheet harus berupa grid transparan 2x2 dengan resolusi memadai.")
    frames=[]
    for row in range(2):
        for col in range(2):
            im=sheet.crop((col*cw,row*ch,(col+1)*cw,(row+1)*ch))
            a=np.asarray(im.getchannel("A")).copy()
            a[a<12]=0
            im.putalpha(Image.fromarray(a))
            bbox=im.getchannel("A").getbbox()
            if bbox: im=im.crop(bbox)
            frames.append(im)
    return frames

def add_label(im, caption, scene, t, w=1280, h=720):
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((26,18,410,64),radius=13,fill=(255,255,255),outline=(42,58,73),width=2)
    d.text((42,27),"AI CARTOON STUDIO • V2",font=font(22,True),fill=(35,53,70))
    d.rounded_rectangle((w//2-420,h-63,w//2+420,h-17),radius=14,fill=(255,255,255),outline=(42,58,73),width=2)
    f=font(21,True); b=d.textbbox((0,0),caption,font=f)
    d.text((w//2-(b[2]-b[0])/2,h-55),caption,font=f,fill=(35,52,63))
    for j in range(4):
        c=(255,190,60) if j==scene else (217,230,235)
        d.ellipse((w-145+j*30,29,w-127+j*30,47),fill=c,outline=(48,63,72),width=1)

def render(cat_sheet, mouse_sheet, output, seconds=20, fps=24, width=1280, height=720):
    cats, mice = load_cycle(cat_sheet), load_cycle(mouse_sheet)
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    silent=output.with_name(output.stem+"_silent.mp4")
    wav=output.with_suffix(".wav")
    writer=imageio.get_writer(str(silent),fps=fps,codec="libx264",quality=8,macro_block_size=16)
    captions=[
        "A quiet garden. One cat spots a quick little mouse.",
        "The chase accelerates — paws fly and scenery rushes by!",
        "The mouse jukes left! The cat tries to brake...",
        "A leap, a slide, and a very undignified landing.",
    ]
    try:
        for i in range(seconds*fps):
            t=i/fps
            scene=0 if t<3.3 else 1 if t<9 else 2 if t<14.2 else 3
            local=t if scene==0 else t-3.3 if scene==1 else t-9 if scene==2 else t-14.2
            im=background(t,width,height); d=ImageDraw.Draw(im)
            if scene in (2,3):
                d.ellipse((850,430,1130,560),fill=(42,117,55))
                d.ellipse((885,400,1080,525),fill=(51,136,62))
                d.ellipse((920,420,1050,510),fill=(65,151,69))
            if scene==0:
                cx=245+6*math.sin(t*1.7); mx=1010 if t<2.1 else 1010+min(75,(t-2.1)*70)
                paste(im,cats[0] if t<2.1 else cats[3],cx,510+2*math.sin(t*2.6),246,1.1*math.sin(t*2))
                paste(im,mice[0] if t<2.1 else mice[int((t-2.1)*8)%4],mx,521+4*math.sin(t*5),143,1.4*math.sin(t*7))
                if 1.35<t<3.25:
                    d.ellipse((cx+60,205,cx+110,255),fill=(255,247,188),outline=(42,54,67),width=3)
                    d.text((cx+77,207),"!",font=font(32,True),fill=(42,54,67))
            elif scene==1:
                cx=255+35*math.sin(local*1.4); mx=730+100*math.sin(local+0.4); freq=9.0
                ci=int(local*freq)%4; mi=int(local*(freq+1.1)+.7)%4
                phase=math.sin(local*math.tau*freq/4)
                paste(im,cats[ci],cx,496-28*max(0,phase),256,2.2*math.sin(local*freq))
                paste(im,mice[mi],mx,523-21*max(0,math.sin(local*math.tau*(freq+1)/4)),146,2.8*math.sin(local*(freq+1)))
                for j in range(5):
                    xx=int(cx-150-j*30); yy=int(430-j*12)
                    d.line((xx,yy,xx-23,yy-4),fill=(255,255,255),width=4)
                if int(local*10)%2==0:
                    for j in range(3):
                        x=int(cx-110-j*17); y=490+j*8
                        d.ellipse((x-10,y-7,x+10,y+7),fill=(226,220,188))
            elif scene==2:
                cx=360+280*min(1,local/3.4)
                mx=965-300*math.sin(min(1,local/2)*math.pi/2)+110*max(0,(local-2)/3)
                if local<1.7:
                    paste(im,cats[int(local*9)%4],cx+80,500-30*math.sin(local*math.pi/1.7),250,-4*math.sin(local*3))
                elif local<2.5:
                    paste(im,cats[3],cx+150,510,252,-11)
                    for j in range(6):
                        yy=410+j*17; d.line((cx+12,yy,cx-48-j*10,yy+4),fill=(255,255,255),width=5)
                    d.rounded_rectangle((740,180,1010,248),radius=16,fill=(255,248,195),outline=(45,50,55),width=3)
                    d.text((790,191),"SKRRT!",font=font(40,True),fill=(220,71,46),stroke_width=2,stroke_fill=(255,255,255))
                else: paste(im,cats[0],cx+140,510+2*math.sin(local*7),245,3*math.sin(local*5))
                paste(im,mice[int(local*10)%4],mx,520+8*math.sin(local*8),145,5*math.sin(local*5))
            else:
                cx=610+35*math.sin(local*1.1); mx=940+min(370,local*115)
                if local<1.65:
                    paste(im,cats[int(local*8)%4],cx,500-75*math.sin(local*math.pi/1.65),265,-7*math.sin(local*2))
                else:
                    paste(im,cats[3],cx+80,512,260,7)
                    if 1.65<local<2.5:
                        for j in range(10):
                            a=j*math.tau/10
                            d.line((cx+80+math.cos(a)*80,420+math.sin(a)*45,
                                    cx+80+math.cos(a)*110,420+math.sin(a)*65),fill=(255,216,83),width=5)
                        d.rounded_rectangle((760,180,1010,250),radius=16,fill=(255,248,195),outline=(45,50,55),width=3)
                        d.text((814,193),"BONK!",font=font(43,True),fill=(228,70,47),stroke_width=2,stroke_fill=(255,255,255))
                if local<3.2: paste(im,mice[int(local*9)%4],mx,520+3*math.sin(local*9),145,1.5*math.sin(local*8))
                if t>18.1:
                    d.rounded_rectangle((190,145,1090,300),radius=24,fill=(255,255,255),outline=(41,57,70),width=4)
                    d.text((315,171),"NANTI KUTANGKAP!",font=font(43,True),fill=(43,64,80))
                    d.text((408,237),"Episode 01 • The Garden Chase",font=font(24),fill=(65,83,95))
            add_label(im,captions[scene],scene,t,width,height)
            writer.append_data(np.asarray(im))
    finally: writer.close()
    music(wav,seconds)
    ffmpeg=get_ffmpeg_exe()
    proc=subprocess.run([ffmpeg,"-y","-i",str(silent),"-i",str(wav),"-c:v","copy","-c:a","aac","-b:a","160k","-shortest","-movflags","+faststart",str(output)],capture_output=True,text=True)
    if proc.returncode: raise RuntimeError(proc.stderr[-3000:])
    silent.unlink(missing_ok=True)
    rd=imageio.get_reader(str(output))
    try:
        for idx in (0,seconds*fps//3,2*seconds*fps//3,seconds*fps-1):
            if rd.get_data(idx).shape[:2]!=(height,width): raise RuntimeError("Output frame dimensions mismatch")
    finally: rd.close()
    check=subprocess.run([ffmpeg,"-hide_banner","-i",str(output),"-f","null","-"],capture_output=True,text=True)
    if check.returncode or "Audio:" not in check.stderr: raise RuntimeError("Output video/audio validation failed")
    print(f"PASS: {output} | {seconds}s | {fps} FPS | {width}x{height} | {output.stat().st_size:,} bytes")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cat-sheet",type=Path,default=Path(__file__).parent/"assets"/"cat_running_sheet_clean.png")
    p.add_argument("--mouse-sheet",type=Path,default=Path(__file__).parent/"assets"/"mouse_running_sheet_clean.png")
    p.add_argument("--output",type=Path,default=Path(__file__).parent/"outputs"/"ai_cartoon_short_v2.mp4")
    p.add_argument("--seconds",type=int,default=20); p.add_argument("--fps",type=int,default=24)
    a=p.parse_args(); render(a.cat_sheet,a.mouse_sheet,a.output,a.seconds,a.fps)

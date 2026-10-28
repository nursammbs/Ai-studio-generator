from PIL import Image, ImageDraw
from pathlib import Path
from sprite_animator_v2 import load_cycle, render

def make_sheet(path):
    sheet=Image.new("RGBA",(256,256),(0,0,0,0))
    d=ImageDraw.Draw(sheet)
    for r in range(2):
        for c in range(2):
            x=c*128; y=r*128
            d.ellipse((x+24,y+25,x+104,y+104),fill=(120+20*c,130+10*r,145,255))
            d.ellipse((x+65,y+45,x+75,y+55),fill=(255,230,90,255))
    sheet.save(path)

def test_load_cycle_returns_four_transparent_poses(tmp_path):
    sheet=tmp_path/"sheet.png"; make_sheet(sheet)
    poses=load_cycle(sheet)
    assert len(poses)==4
    assert all(p.mode=="RGBA" and p.width>0 and p.height>0 for p in poses)

def test_v2_renderer_produces_decodeable_mp4(tmp_path):
    cat=tmp_path/"cat.png"; mouse=tmp_path/"mouse.png"
    make_sheet(cat); make_sheet(mouse)
    out=tmp_path/"v2.mp4"
    render(cat,mouse,out,seconds=1,fps=6,width=1280,height=720)
    assert out.exists() and out.stat().st_size>10_000

#!/usr/bin/env python3
"""Pull a figure out of the lecture deck, so a chapter can show it.

A chapter that says "slide 43 shows why this is useful" asks the reader to
look at something they do not have. The fix is to put the slide's own figure
in the book, and this renders one:

    python scripts/slide_figure.py Part-4.pptx chapters/figures/lec08 43 44 47

It draws each slide's pictures at their true positions, its preset shapes
(ellipse, rectangle, arc), freeform paths, straight connectors with
arrowheads, and its text boxes in DejaVu, then trims the white margin. There
is no LibreOffice on this machine; this is what replaces it, and it is not a
PowerPoint renderer.

Two limits are worth knowing before you trust the output, and both are
visible if you look at the PNG:

* **Equations stored as EMF/WMF do not render.** Pillow cannot read them, the
  script says so on stderr and leaves a hole. Slides whose content is one
  equation picture (46, 52, 53 of the diffusion deck) come out empty and
  belong in the prose instead.
* **An animated slide has no single static state.** Every build step is a
  shape in the file, so a slide that replaces one row of results with another
  renders as all of them at once, with labels that no longer line up. Slide
  41 of the diffusion deck is the example. Look at the PNG before using it.

Always look at the rendered PNG beside the slide before putting it in a
chapter. The script is a convenience, not an authority on what the lecture
showed.
"""
import sys, zipfile, io, os, math
from xml.etree import ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

A="{http://schemas.openxmlformats.org/drawingml/2006/main}"
P="{http://schemas.openxmlformats.org/presentationml/2006/main}"
R="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
FONT="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONTB="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SCHEME={"tx1":(0,0,0),"dk1":(0,0,0),"dk2":(0,0,0),"bg1":(255,255,255),"lt1":(255,255,255),
        "tx2":(0,0,0),"bg2":(240,240,240),"lt2":(240,240,240),
        "accent1":(68,114,196),"accent2":(237,125,49),"accent3":(165,165,165),
        "accent4":(255,192,0),"accent5":(91,155,213),"accent6":(112,173,71)}

def color(node):
    if node is None: return None
    c=node.find(f"{A}srgbClr")
    if c is not None:
        v=c.get("val"); return tuple(int(v[i:i+2],16) for i in (0,2,4))
    c=node.find(f"{A}schemeClr")
    if c is not None: return SCHEME.get(c.get("val"),(0,0,0))
    return None

class Render:
    def __init__(self, path, dpi=150):
        self.z=zipfile.ZipFile(path); self.dpi=dpi
        pres=ET.fromstring(self.z.read("ppt/presentation.xml"))
        sz=pres.find(f"{P}sldSz"); self.W=int(sz.get("cx")); self.H=int(sz.get("cy"))
    def px(self,emu): return emu/914400*self.dpi
    def font(self,pts,bold=False):
        return ImageFont.truetype(FONTB if bold else FONT, max(7,int(pts*self.dpi/72)))

    def render(self, idx, out, crop=True):
        rels={r.get("Id"):r.get("Target") for r in
              ET.fromstring(self.z.read(f"ppt/slides/_rels/slide{idx}.xml.rels"))}
        root=ET.fromstring(self.z.read(f"ppt/slides/slide{idx}.xml"))
        S=4  # supersample for the vector work
        self.S=S
        img=Image.new("RGBA",(int(self.px(self.W)*S),int(self.px(self.H)*S)),(255,255,255,255))
        d=ImageDraw.Draw(img)
        self.walk(root.find(f"{P}cSld").find(f"{P}spTree"), img, d, rels, (0,0,1.0,1.0))
        img=img.convert("RGB").resize((int(self.px(self.W)),int(self.px(self.H))), Image.LANCZOS)
        img.save(out); print(out, img.size)

    def xfrm(self, sp, grp=False):
        x=sp.find(f"{P}spPr/{A}xfrm") or sp.find(f"{P}grpSpPr/{A}xfrm") or sp.find(f".//{A}xfrm")
        if x is None: return None
        off=x.find(f"{A}off"); ext=x.find(f"{A}ext")
        if off is None or ext is None: return None
        return (int(off.get("x")),int(off.get("y")),int(ext.get("cx")),int(ext.get("cy")),
                int(x.get("rot") or 0), x.get("flipH")=="1", x.get("flipV")=="1")

    def box(self, b, tf):
        ox,oy,sx,sy=tf
        x,y,cx,cy,rot,fh,fv=b
        X=(x*sx+ox); Y=(y*sy+oy); CX=cx*sx; CY=cy*sy
        S=self.S
        return self.px(X)*S, self.px(Y)*S, self.px(CX)*S, self.px(CY)*S, rot, fh, fv

    def walk(self, node, img, d, rels, tf):
        for ch in node:
            t=ch.tag
            if t==f"{P}grpSp":
                gx=ch.find(f"{P}grpSpPr/{A}xfrm")
                if gx is None: continue
                off=gx.find(f"{A}off"); ext=gx.find(f"{A}ext")
                cho=gx.find(f"{A}chOff"); che=gx.find(f"{A}chExt")
                sx=int(ext.get("cx"))/max(1,int(che.get("cx")))
                sy=int(ext.get("cy"))/max(1,int(che.get("cy")))
                pox,poy,psx,psy=tf
                nox=int(off.get("x"))*psx+pox-int(cho.get("x"))*sx*psx
                noy=int(off.get("y"))*psy+poy-int(cho.get("y"))*sy*psy
                self.walk(ch, img, d, rels, (nox,noy,sx*psx,sy*psy))
            elif t in (f"{P}pic", f"{P}sp", f"{P}cxnSp"):
                self.shape(ch, img, d, rels, tf)

    def shape(self, sp, img, d, rels, tf):
        b=self.xfrm(sp)
        if b is None: return
        X,Y,CX,CY,rot,fh,fv=self.box(b,tf)
        spPr=sp.find(f"{P}spPr")
        blip=sp.find(f".//{A}blip")
        if blip is not None:
            self.picture(sp, blip, img, rels, X,Y,CX,CY,rot)
        elif spPr is not None:
            self.vector(sp, spPr, d, X,Y,CX,CY,rot,fh,fv)
        self.text(sp, d, X,Y,CX,CY, tf)

    def picture(self, sp, blip, img, rels, X,Y,CX,CY,rot):
        tgt=rels.get(blip.get(f"{R}embed"))
        if not tgt: return
        name="ppt/"+tgt.replace("../","")
        try:
            im=Image.open(io.BytesIO(self.z.read(name)))
            if getattr(im,"n_frames",1)>1: im.seek(0)
            im=im.convert("RGBA")
        except Exception as e:
            print("  skip",name,e); return
        sr=sp.find(f".//{A}srcRect")
        if sr is not None:
            l=int(sr.get("l") or 0)/100000; r_=int(sr.get("r") or 0)/100000
            t=int(sr.get("t") or 0)/100000; bo=int(sr.get("b") or 0)/100000
            w,h=im.size
            im=im.crop((int(w*l),int(h*t),max(1,int(w*(1-r_))),max(1,int(h*(1-bo)))))
        im=im.resize((max(1,int(CX)),max(1,int(CY))), Image.LANCZOS)
        if rot: im=im.rotate(-rot/60000, expand=True, fillcolor=(0,0,0,0))
        img.alpha_composite(im,(int(X),int(Y)))

    def vector(self, sp, spPr, d, X,Y,CX,CY,rot,fh,fv):
        fill=color(spPr.find(f"{A}solidFill"))
        if spPr.find(f"{A}noFill") is not None: fill=None
        ln=spPr.find(f"{A}ln")
        lc=color(ln.find(f"{A}solidFill")) if ln is not None else None
        if ln is not None and ln.find(f"{A}noFill") is not None: lc=None
        lw=max(1,int(self.px(int(ln.get("w")))*self.S)) if (ln is not None and ln.get("w")) else max(1,self.S)
        # No explicit line colour means no outline. Defaulting to black here
        # draws a border around every title and text placeholder on the slide.
        if ln is not None and ln.find(f"{A}solidFill") is None and ln.get("w") and \
           ln.find(f"{A}noFill") is None and fill is not None:
            lc=(0,0,0)
        prst=spPr.find(f"{A}prstGeom"); cust=spPr.find(f"{A}custGeom")
        bb=[X,Y,X+CX,Y+CY]
        if prst is not None:
            p=prst.get("prst")
            if p in ("ellipse",):
                d.ellipse(bb, fill=fill, outline=lc, width=lw)
            elif p in ("rect","roundRect","snip1Rect","flowChartProcess"):
                if fill or lc: d.rectangle(bb, fill=fill, outline=lc, width=lw)
            elif p=="arc":
                adj={g.get("name"):g.get("fmla") for g in prst.iter(f"{A}gd")}
                a1=float(adj.get("adj1","val 16200000").split()[-1])/60000
                a2=float(adj.get("adj2","val 0").split()[-1])/60000
                if lc: d.arc(bb, a1, a2, fill=lc, width=lw)
            elif p in ("line","straightConnector1"):
                x0,y0,x1,y1=(X,Y,X+CX,Y+CY)
                if fh: x0,x1=x1,x0
                if fv: y0,y1=y1,y0
                if lc:
                    d.line([x0,y0,x1,y1], fill=lc, width=lw)
                    self.arrow(d,(x0,y0),(x1,y1),lc,lw, ln)
            elif p in ("triangle","rightArrow"):
                if fill: d.polygon([(X,Y+CY),(X+CX,Y+CY),(X+CX/2,Y)], fill=fill, outline=lc)
        elif cust is not None:
            self.custom(cust, d, X,Y,CX,CY, fill, lc, lw)

    def arrow(self, d, p0, p1, col, lw, ln):
        if ln is None: return
        if ln.find(f"{A}tailEnd") is None and ln.find(f"{A}headEnd") is None: return
        for end,(a,b) in (("tailEnd",(p0,p1)),("headEnd",(p1,p0))):
            if ln.find(f"{A}{end}") is None: continue
            dx,dy=b[0]-a[0],b[1]-a[1]
            L=math.hypot(dx,dy) or 1
            ux,uy=dx/L,dy/L
            s=lw*4
            tip=b; back=(b[0]-ux*s, b[1]-uy*s)
            d.polygon([tip,(back[0]-uy*s*0.5,back[1]+ux*s*0.5),(back[0]+uy*s*0.5,back[1]-ux*s*0.5)], fill=col)

    def custom(self, cust, d, X,Y,CX,CY, fill, lc, lw):
        path=cust.find(f"{A}pathLst/{A}path")
        if path is None: return
        pw=int(path.get("w") or 0) or 1; ph=int(path.get("h") or 0) or 1
        def pt(e): return (X+int(e.get("x"))/pw*CX, Y+int(e.get("y"))/ph*CY)
        pts=[]; cur=None
        for e in path:
            tag=e.tag.split("}")[1]
            if tag=="moveTo": cur=pt(e.find(f"{A}pt")); pts=[cur]
            elif tag=="lnTo":
                cur=pt(e.find(f"{A}pt")); pts.append(cur)
            elif tag=="cubicBezTo":
                ps=[pt(x) for x in e.findall(f"{A}pt")]
                if cur and len(ps)==3:
                    for i in range(1,13):
                        t=i/12; mt=1-t
                        x=mt**3*cur[0]+3*mt*mt*t*ps[0][0]+3*mt*t*t*ps[1][0]+t**3*ps[2][0]
                        y=mt**3*cur[1]+3*mt*mt*t*ps[0][1]+3*mt*t*t*ps[1][1]+t**3*ps[2][1]
                        pts.append((x,y))
                    cur=ps[2]
            elif tag=="close" and len(pts)>2:
                if fill: d.polygon(pts, fill=fill)
                if lc: d.line(pts+[pts[0]], fill=lc, width=lw)
                pts=[]
        if len(pts)>1 and lc: d.line(pts, fill=lc, width=lw)

    def text(self, sp, d, X,Y,CX,CY, tf):
        tx=sp.find(f"{P}txBody")
        if tx is None: return
        cy=Y+2*self.S
        for p_ in tx.findall(f"{A}p"):
            runs=[(r.find(f"{A}t").text or "", r.find(f"{A}rPr"))
                  for r in p_.findall(f"{A}r") if r.find(f"{A}t") is not None]
            if not runs:
                cy+=10*self.S; continue
            txt="".join(t for t,_ in runs)
            rPr=runs[0][1]; sz=1800; bold=False; col=(0,0,0)
            if rPr is not None:
                sz=int(rPr.get("sz") or 1800); bold=(rPr.get("b")=="1")
                col=color(rPr.find(f"{A}solidFill")) or (0,0,0)
            f=self.font(sz/100*tf[2]*self.S, bold)
            pPr=p_.find(f"{A}pPr")
            algn=pPr.get("algn") if pPr is not None else None
            # Wrap inside the shape's own width. Without this a long caption
            # runs off the slide and over whatever sits to its right.
            avail=max(40*self.S, CX-4*self.S)
            words=txt.split(" "); lines=[]; cur=""
            for w_ in words:
                trial=(cur+" "+w_).strip()
                if d.textlength(trial,font=f)<=avail or not cur: cur=trial
                else: lines.append(cur); cur=w_
            if cur: lines.append(cur)
            for line in lines:
                w=d.textlength(line,font=f)
                ax=X+2*self.S
                if algn=="ctr": ax=X+(CX-w)/2
                elif algn=="r": ax=X+CX-w
                d.text((ax,cy),line,font=f,fill=col)
                cy+=f.size*1.25

def trim(path, pad=12):
    """Crop the white margin a 16:9 slide leaves around its content."""
    from PIL import ImageChops
    im=Image.open(path).convert("RGB")
    bb=ImageChops.difference(im, Image.new("RGB", im.size, (255,255,255))).getbbox()
    if not bb: return
    x0,y0,x1,y1=bb
    im.crop((max(0,x0-pad),max(0,y0-pad),min(im.width,x1+pad),min(im.height,y1+pad))).save(path, optimize=True)

if __name__=="__main__":
    if len(sys.argv)<4:
        sys.exit(__doc__)
    r=Render(sys.argv[1], dpi=200); os.makedirs(sys.argv[2],exist_ok=True)
    for n in sys.argv[3:]:
        out=os.path.join(sys.argv[2], f"slide{int(n):02d}.png")
        r.render(int(n), out)
        trim(out)

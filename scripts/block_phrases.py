"""Smooth extruded Nunito glyphs; text timing is independent of scene clocks."""
from dataclasses import dataclass
from pathlib import Path
import math
import sys
import numpy as np
from PIL import ImageFont
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.render-deps'))
import mapbox_earcut
import pathops

FONT_ROOT=ROOT/'assets/fonts'
CREAM=(.95,.96,.91)
MINT=(.73,.91,.78)
INK=(.035,.10,.105)

@dataclass(frozen=True)
class Phrase:
    start: float
    assembly: float
    hold: float
    exit: float
    lines: tuple
    center_y: float = 116
    @property
    def text(self):return ' '.join(line[0] for line in self.lines)
    @property
    def end(self):return self.start+self.assembly+self.hold+self.exit

PHRASES=(
    Phrase(.25,.40,4.4,.30,(
        ('Um jogo educativo independente para estudar',49,'SemiBold',CREAM),
        ('Análise e Desenvolvimento de Sistemas',65,'ExtraBold',MINT),
    )),
    Phrase(5.50,.35,2.8,.28,(
        ('Acerte os desafios por fases',74,'ExtraBold',CREAM),
    ), center_y=87),
    Phrase(9.10,.40,3.0,.30,(
        ('Reconstrua uma cidade digital',55,'ExtraBold',CREAM),
        ('enquanto constrói aprendizado real',55,'ExtraBold',CREAM),
    ), center_y=78),
)

# Same sentences and clocks, reflowed only for the single portrait scene.
PORTRAIT_PHRASES=(
    Phrase(.25,.40,4.4,.30,(
        ('Um jogo educativo',42,'SemiBold',CREAM),
        ('independente para estudar',39,'SemiBold',CREAM),
        ('Análise e',50,'ExtraBold',MINT),
        ('Desenvolvimento',50,'ExtraBold',MINT),
        ('de Sistemas',50,'ExtraBold',MINT),
    ), center_y=190),
    Phrase(5.50,.35,2.8,.28,(
        ('Acerte os desafios',53,'ExtraBold',CREAM),
        ('por fases',53,'ExtraBold',CREAM),
    ), center_y=153),
    Phrase(9.10,.40,3.0,.30,(
        ('Reconstrua uma',45,'ExtraBold',CREAM),
        ('cidade digital',45,'ExtraBold',CREAM),
        ('enquanto constrói',42,'ExtraBold',CREAM),
        ('aprendizado real',45,'ExtraBold',CREAM),
    ), center_y=157),
)

def ease(value):
    u=float(np.clip(value,0,1))
    return 1-(1-u)**4

class OutlinePen(BasePen):
    def __init__(self,glyphs):
        super().__init__(glyphs);self.contours=[];self.current=[]
    def _moveTo(self,p):self.current=[np.array(p,float)]
    def _lineTo(self,p):self.current.append(np.array(p,float))
    def _qCurveToOne(self,p1,p2):
        p0=self.current[-1];p1=np.array(p1);p2=np.array(p2)
        for u in np.linspace(0,1,13)[1:]:self.current.append((1-u)**2*p0+2*u*(1-u)*p1+u*u*p2)
    def _curveToOne(self,p1,p2,p3):
        p0=self.current[-1];p1,p2,p3=map(np.array,(p1,p2,p3))
        for u in np.linspace(0,1,17)[1:]:self.current.append((1-u)**3*p0+3*(1-u)**2*u*p1+3*(1-u)*u*u*p2+u**3*p3)
    def _closePath(self):
        points=np.array(self.current)
        if len(points)>1 and np.linalg.norm(points[0]-points[-1])<1e-5:points=points[:-1]
        if len(points)>=3:self.contours.append(points)
        self.current=[]
    def _endPath(self):self._closePath()

def area(ring):
    return .5*np.sum(ring[:,0]*np.roll(ring[:,1],-1)-np.roll(ring[:,0],-1)*ring[:,1])

def contains(ring,p):
    x,y=p;inside=False
    for a,b in zip(ring,np.roll(ring,-1,axis=0)):
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside

def extrude(contours):
    rings=[r for r in contours if abs(area(r))>.1]
    if not rings:return []
    sign=np.sign(area(max(rings,key=lambda r:abs(area(r)))))
    outers=[r for r in rings if np.sign(area(r))==sign]
    holes=[r for r in rings if np.sign(area(r))!=sign]
    groups=[[] for _ in outers]
    for hole in holes:
        candidates=[i for i,r in enumerate(outers) if contains(r,hole[0])]
        if candidates:groups[min(candidates,key=lambda i:abs(area(outers[i])))].append(hole)
    vertices=[]
    def triangle(a,b,c,normal):
        if np.dot(np.cross(np.subtract(b,a),np.subtract(c,a)),normal)<0:b,c=c,b
        for p in (a,b,c):vertices.append((*p,*normal,0,0,0))
    for outer,inner in zip(outers,groups):
        shape=[outer,*inner];points=np.concatenate(shape).astype(np.float64)
        ends=np.cumsum([len(r) for r in shape]).astype(np.uint32)
        triangles=mapbox_earcut.triangulate_float64(points,ends).reshape(-1,3)
        for indices in triangles:
            p=points[indices]
            triangle((*p[0],25),(*p[1],25),(*p[2],25),(0,0,1))
            triangle((*p[0],-25),(*p[1],-25),(*p[2],-25),(0,0,-1))
        for ring in shape:
            for a,b in zip(ring,np.roll(ring,-1,axis=0)):
                edge=b-a;length=np.linalg.norm(edge)
                if length<1e-7:continue
                n=np.array((sign*edge[1],-sign*edge[0],0))/length
                triangle((*a,-25),(*b,-25),(*b,25),n)
                triangle((*a,-25),(*b,25),(*a,25),n)
    return vertices

class BlockPhrases:
    def __init__(self,width=1920,height=1080):
        self.width,self.height=width,height
        self.portrait=height>width
        self.phrases=PORTRAIT_PHRASES if self.portrait else PHRASES
        self.fonts={weight:TTFont(FONT_ROOT/f'Nunito-{weight}.ttf') for weight in ('SemiBold','ExtraBold')}
        self.meshes={};self.layouts=[]
        for phrase in self.phrases:
            rows=[];heights=[]
            for text,size,weight,color in phrase.lines:
                font=ImageFont.truetype(str(FONT_ROOT/f'Nunito-{weight}.ttf'),size)
                bbox=font.getbbox(text,anchor='ls')
                heights.append(bbox[3]-bbox[1]);rows.append((text,size,weight,color,font,bbox))
            total=sum(heights)+18*(len(rows)-1)
            center=phrase.center_y
            top=center-total/2
            glyphs=[]
            for (text,size,weight,color,font,bbox),height in zip(rows,heights):
                left=(width-font.getlength(text,features=['-liga']))/2
                baseline=top-bbox[1]
                tt=self.fonts[weight];glyphset=tt.getGlyphSet();cmap=tt.getBestCmap()
                for i,char in enumerate(text):
                    if char.isspace():continue
                    key=f'glyph_{weight}_{ord(char)}'
                    if key not in self.meshes:
                        # Resolve self-intersections with the font winding rule
                        # before triangulating; otherwise A/z develop missing faces.
                        outline=pathops.Path()
                        glyphset[cmap[ord(char)]].draw(outline.getPen(glyphSet=glyphset))
                        outline=pathops.simplify(outline,clockwise=outline.clockwise)
                        pen=OutlinePen(glyphset)
                        outline.draw(pen)
                        self.meshes[key]=extrude(pen.contours)
                    x=left+font.getlength(text[:i+1],features=['-liga'])-font.getlength(char,features=['-liga'])
                    glyphs.append((key,x,baseline,size/tt['head'].unitsPerEm,color))
                top+=height+18
            self.layouts.append(glyphs)

    def append(self,renderer,t,eye,basis):
        for phrase,glyphs in zip(self.phrases,self.layouts):
            if not phrase.start<=t<=phrase.end:continue
            elapsed=t-phrase.start
            unit=2*6*math.tan(math.radians(44 if self.portrait else 38)/2)/self.height
            center_x=self.width*(.5 if self.portrait else .62)
            for i,(kind,x,y,font_scale,color) in enumerate(glyphs):
                stagger=.065*i/max(1,len(glyphs)-1)
                incoming=1-ease((elapsed-stagger)/(phrase.assembly-.065))
                outgoing=ease((elapsed-phrase.assembly-phrase.hold)/phrase.exit)
                visibility=(1-incoming)*(1-outgoing)
                if visibility<.003:continue
                turn=(incoming-outgoing)*.13
                c,s=math.cos(turn),math.sin(turn)
                orient=basis@np.array(((c,0,s),(0,1,0),(-s,0,c)))
                camera_point=np.array(((x-center_x)*unit,(self.height/2-y-10*incoming+8*outgoing)*unit,-6+.05*(incoming+outgoing)))
                position=eye+basis@camera_point
                scale=unit*font_scale*(.97+.03*visibility)
                for shadow in (True,False):
                    m=np.eye(4)
                    m[:3,:3]=orient*scale
                    offset=basis@np.array((1.4*unit,-1.8*unit,-.025)) if shadow else 0
                    m[:3,3]=position+offset
                    ink=(.018,.032,.032) if shadow else color
                    renderer.items[kind].append([*m.T.reshape(-1),*ink,visibility*(.72 if shadow else 1),0,0,0,0,0,.8])
            # A few small blocks mark the transition, never the letter outlines.
            activity=max(1-ease(elapsed/phrase.assembly),ease((elapsed-phrase.assembly-phrase.hold)/phrase.exit))
            if activity>.02:
                for j in range(32):
                    phase=j*2.39996
                    px=self.width/2+math.sin(phase)*(self.width*.35 if self.portrait else 470)
                    py=87+math.cos(phase)*55+activity*25
                    point=eye+basis@np.array(((px-center_x)*unit,(self.height/2-py)*unit,-5.9))
                    size=(2.5+2*(j%3))*unit*activity
                    renderer.box(point,(size,size,size),MINT,rot=basis,emission=.6)

def captions_vtt():
    def stamp(t):return f'00:{int(t)//60:02d}:{t%60:06.3f}'
    return 'WEBVTT\n\n'+'\n\n'.join(f'{stamp(p.start)} --> {stamp(p.end)}\n{p.text}' for p in PHRASES)+'\n'

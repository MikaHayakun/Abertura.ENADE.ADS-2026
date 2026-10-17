"""Three spatial arrangements. Screenshots are references, never display planes."""
import math
from dataclasses import dataclass, replace
import numpy as np


@dataclass
class Part:
    pos: np.ndarray
    size: np.ndarray
    color: np.ndarray
    rot: np.ndarray
    kind: str = 'cube'
    surface: str | None = None
    uv: tuple = (0, 0, 1, 1)
    finish: float = 0.0


class Assembly:
    def __init__(self): self.parts = []

    def add(self, pos, size, color, rot=(0,0,0), kind='cube', surface=None, uv=(0,0,1,1), finish=0):
        self.parts.append(Part(np.array(pos,float),np.array(size,float),np.array(color,float),np.array(rot,float),kind,surface,uv,finish))


TEAL=(.27,.51,.44)
IVORY=(.78,.80,.65)
STONE=(.17,.32,.33)
MINT=(.54,.82,.72)


def portal():
    a=Assembly()
    # The gate, five crystals, player and polygonal island in reference 34.
    a.add((0,-2.65,0),(8.7,.38,6.8),TEAL,kind='hex')
    a.add((0,-2.93,0),(8.1,.28,6.3),(.12,.30,.28),kind='hex')
    for x in (-2.45,2.45):a.add((x,-.15,-1.7),(.43,4.65,.48),IVORY)
    a.add((0,2.2,-1.7),(5.5,.48,.67),IVORY)
    for j in range(5):
        a.add((-1.7+j*.85,2.2,-1.30),(.27,.27,.10),MINT if j==0 else STONE,rot=(math.pi/2,0,0),kind='cylinder')
    for x in (-1.10,1.10):
        a.add((x,-.15,-1.75),(2.11,4.12,.16),(.075,.20,.20))
        a.add((x,-.15,-1.60),(.55,.55,.08),MINT,rot=(0,0,math.pi/4))
    for x in (-.15,.15):a.add((x,-.15,-1.59),(.04,3.6,.03),MINT)
    for j in range(5):
        x=-3+j*1.5
        a.add((x,-2.30,1.05),(1.12,.32,1.05),STONE,kind='hex')
        a.add((x,-1.65,1.05),(.72,.95,.72),MINT,rot=(.10,j*.24,.12),kind='octa')
        a.add((x,-.92,1.05),(.27,.29,.025),TEAL,surface='ABCDE'[j],finish=1)
    for x in (-3.8,3.8):
        a.add((x,-1.47,-.85),(.12,2.1,.12),(.42,.62,.50))
        a.add((x,-.37,-.85),(.28,.28,.28),MINT,kind='octa')
    # Cubic avatar, reconstructed as separate head, torso, arms and legs.
    px,pz=-1.6,2.65
    a.add((px,-1.00,pz),(.44,.42,.43),IVORY)
    a.add((px,-1.56,pz),(.66,.72,.36),IVORY)
    a.add((px,-1.43,pz+.20),(.69,.12,.04),MINT)
    for side in (-1,1):
        a.add((px+side*.43,-1.60,pz),(.18,.62,.22),IVORY)
        a.add((px+side*.19,-2.14,pz),(.24,.42,.25),(.09,.20,.21))
    return a.parts


def districts():
    a=Assembly()
    centers=[(-2.7,1.3),(-.05,1.6),(2.55,1.2),(-1.45,-1.85),(1.45,-1.85)]
    for k,(x,z) in enumerate(centers):
        y=-2.10
        a.add((x,y,z),(2.35,.30,2.12),TEAL,kind='hex')
        a.add((x,y-.36,z),(2.06,.48,1.90),(.10,.25,.25),kind='hex')
        h=1.9+(k%2)*.34+(k//3)*.35
        color=IVORY if k==0 else (.25,.38,.38)
        a.add((x,y+.20+h/2,z),(1.0,h,.96),color)
        a.add((x,y+.20+h+.48,z),(1.22,.95,1.18),MINT if k==0 else (.39,.52,.50),kind='pyramid')
        for floor in range(3):
            a.add((x,y+.52+floor*.48,z+.495),(.62,.12,.035),(.59,.74,.65) if k==0 else (.46,.60,.57))
            a.add((x+.515,y+.52+floor*.48,z),(.035,.12,.59),(.40,.57,.53))
        a.add((x-.64,y+.73,z),(.28,.84,.34),MINT)
        a.add((x,y+.22,z+.86),(1.80,.12,.22),(.64,.73,.62))
        a.add((x,y+h+1.55,z),(.32,.39,.025),TEAL,surface=str(k+1),finish=1)
    return a.parts


def building():
    a=Assembly()
    w,d,h=6.6,3.2,8.4
    bottom=-3.80
    dark=(.14,.18,.18); frame=(.43,.46,.43)
    # Photographic finish is rectified separately for each architectural facade.
    # There is no screenshot rectangle or final image grid anywhere in the scene.
    for side in range(4):
        cols=10 if side<2 else 5
        width=w if side<2 else d
        for row in range(8):
            for col in range(cols):
                u=-width/2+(col+.5)*width/cols
                y=bottom+(row+.5)*h/8
                if side==0:p=(u,y,d/2);r=(0,0,0)
                elif side==1:p=(-u,y,-d/2);r=(0,math.pi,0)
                elif side==2:p=(w/2,y,-u);r=(0,math.pi/2,0)
                else:p=(-w/2,y,u);r=(0,-math.pi/2,0)
                green=(col+row*3+side)%5 in (0,1)
                color=(.36,.50,.27) if green else (.24,.34,.36)
                a.add(p,(width/cols-.015,h/8-.018,.12),color,rot=r,surface='facade' if side<2 else 'side',uv=(col/cols,row/8,1/cols,1/8),finish=1)
        for col in range(cols+1):
            u=-width/2+col*width/cols
            for row in range(8):
                y=bottom+(row+.5)*h/8
                if side==0:p=(u,y,d/2+.08);r=(0,0,0)
                elif side==1:p=(-u,y,-d/2-.08);r=(0,math.pi,0)
                elif side==2:p=(w/2+.08,y,-u);r=(0,math.pi/2,0)
                else:p=(-w/2-.08,y,u);r=(0,-math.pi/2,0)
                a.add(p,(.048,h/8,.055),frame,rot=r)
        for row in range(9):
            y=bottom+row*h/8
            if side==0:p=(0,y,d/2+.06);r=(0,0,0)
            elif side==1:p=(0,y,-d/2-.06);r=(0,math.pi,0)
            elif side==2:p=(w/2+.06,y,0);r=(0,math.pi/2,0)
            else:p=(-w/2-.06,y,0);r=(0,-math.pi/2,0)
            a.add(p,(width+.08,.055,.08),dark,rot=r)
    # Ground-floor glazing, columns, planted canopy, roof and parapet.
    for col in range(10):
        x=-3.3+(col+.5)*.66
        a.add((x,-4.50,1.59),(.64,1.30,.10),(.16,.24,.21),surface='lobby',uv=(col/10,0,.1,1),finish=1)
        a.add((x,-3.95,2.02),(.66,.11,.95),dark)
        a.add((x,4.68,0),(.66,.17,3.38),dark)
        a.add((x,4.82,1.55),(.66,.16,.17),frame)
        a.add((x,-4.47,1.71),(.055,1.30,.09),frame)
    for side in (-1,1):
        for z in (-1.3,-.2,.9):
            a.add((side*3.20,-4.5,z),(.12,1.3,.12),frame)
    rng=np.random.default_rng(58)
    for k in range(56):
        x=float(rng.uniform(-3.3,3.3));z=1.46 if k<28 else -1.46
        a.add((x,4.97+float(rng.uniform(0,.12)),z),(.26,.27,.25),(.14+float(rng.uniform(0,.09)),.32+float(rng.uniform(0,.15)),.12),rot=(0,k*.67,0),kind='octa')
    for k in range(22):
        a.add((-3.2+k*.30,-3.82,2.10),(.35,.23,.40),(.20,.39,.16),rot=(0,k*.7,0),kind='octa')
    return a.parts


def equalize(parts, count):
    """Subdivide real solids so all three arrangements share the same pieces."""
    parts=list(parts)
    while len(parts)<count:
        eligible=[(float(np.prod(p.size)),i) for i,p in enumerate(parts) if p.kind=='cube' and p.surface is None]
        _,i=max(eligible)
        p=parts.pop(i)
        axis=int(np.argmax(p.size))
        size=p.size.copy();size[axis]/=2
        x,y,z=p.rot
        cx,sx,cy,sy,cz,sz=math.cos(x),math.sin(x),math.cos(y),math.sin(y),math.cos(z),math.sin(z)
        R=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]])@np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]])@np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
        offset=np.zeros(3);offset[axis]=p.size[axis]/4
        for sign in (-1,1):parts.append(replace(p,pos=p.pos+R@offset*sign,size=size.copy()))
    return parts

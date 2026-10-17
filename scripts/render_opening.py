#!/usr/bin/env python3
"""Render reproducible 3D geometry with headless OpenGL/EGL, then encode MP4.

Screenshots define spatial arrangements. Only architectural surface details are
sampled from reference 58; no screenshot is ever rendered as a picture or panel.
"""
from __future__ import annotations

import argparse
import ctypes
import math
import json
import os
from pathlib import Path
import subprocess

os.environ['PYOPENGL_PLATFORM'] = 'egl'
os.environ['EGL_PLATFORM'] = 'surfaceless'
# Leave CPU and memory available for the desktop on this notebook.
for variable in ('LP_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable] = '1'
if hasattr(os,'sched_getaffinity'):
    os.sched_setaffinity(0,{max(os.sched_getaffinity(0))})
if hasattr(os,'nice'):
    os.nice(12)

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from OpenGL import EGL
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
from scene_geometry import portal, districts, building, equalize
from block_phrases import BlockPhrases, PHRASES, captions_vtt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
DURATION = 13.0
FPS = 25
W, H = 720, 1280
LANDSCAPE = False
FOREGROUND_COPIES = 1
ANIMATED_PHRASES = False
F32 = np.float32


def smooth(a, b, t):
    u = np.clip((t-a)/(b-a), 0.0, 1.0)
    return float(u*u*(3-2*u))


def lerp(a, b, u):
    return np.asarray(a)*(1-u)+np.asarray(b)*u


def rotation(x=0, y=0, z=0):
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])


def model(pos, size, rot=(0,0,0)):
    m = np.eye(4, dtype=F32)
    orient = np.asarray(rot) if np.shape(rot) == (3,3) else rotation(*rot)
    m[:3,:3] = orient @ np.diag(size)
    m[:3,3] = pos
    return m


def look_at(eye, target):
    eye, target = np.array(eye, float), np.array(target, float)
    f = target-eye
    f /= np.linalg.norm(f)
    s = np.cross(f, [0,1,0]); s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4, dtype=F32)
    m[:3,:3] = [s,u,-f]
    m[:3,3] = -m[:3,:3] @ eye
    return m


def projection():
    f = 1/math.tan(math.radians(38 if LANDSCAPE else 44)/2)
    near, far = .1, 100
    # An off-axis lens places the existing animation beside its titles without
    # moving, scaling or retiming any part of the approved 3D choreography.
    shift = -.24 if LANDSCAPE else 0
    return np.array([[f/(W/H),0,shift,0],[0,f,0,0],[0,0,(far+near)/(near-far),2*far*near/(near-far)],[0,0,-1,0]], dtype=F32)


def init_egl():
    display = EGL.eglGetDisplay(EGL.EGL_DEFAULT_DISPLAY)
    major, minor = EGL.EGLint(), EGL.EGLint()
    EGL.eglInitialize(display, major, minor)
    attrs = (EGL.EGLint*15)(EGL.EGL_SURFACE_TYPE,EGL.EGL_PBUFFER_BIT,EGL.EGL_RENDERABLE_TYPE,EGL.EGL_OPENGL_BIT,EGL.EGL_RED_SIZE,8,EGL.EGL_GREEN_SIZE,8,EGL.EGL_BLUE_SIZE,8,EGL.EGL_DEPTH_SIZE,24,EGL.EGL_NONE)
    config, count = EGL.EGLConfig(), EGL.EGLint()
    EGL.eglChooseConfig(display, attrs, ctypes.byref(config), 1, count)
    EGL.eglBindAPI(EGL.EGL_OPENGL_API)
    surface = EGL.eglCreatePbufferSurface(display, config, (EGL.EGLint*5)(EGL.EGL_WIDTH,W,EGL.EGL_HEIGHT,H,EGL.EGL_NONE))
    context = EGL.eglCreateContext(display, config, EGL.EGL_NO_CONTEXT, None)
    EGL.eglMakeCurrent(display, surface, surface, context)
    print('3D renderer:', glGetString(GL_RENDERER).decode(), flush=True)
    return display, surface, context


def upload_texture(image):
    image = image.convert('RGBA').transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    texture = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture)
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,image.width,image.height,0,GL_RGBA,GL_UNSIGNED_BYTE,image.tobytes())
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE)
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE)
    return texture


def make_atlas():
    atlas = Image.new('RGBA', (2048,2048), (10,25,27,255))
    regions = {}
    def put(name, im, x, y):
        atlas.paste(im,(x,y))
        regions[name] = (x/2048, (2048-y-im.height)/2048, im.width/2048, im.height/2048)
    reference = Image.open(ROOT/'Captura de tela de 2026-10-16 16-52-58.png').convert('RGBA')
    def facade(size, corners):
        width,height=size
        destinations=((0,0),(0,height-1),(width-1,height-1),(width-1,0))
        sources=list(zip(corners[::2],corners[1::2]))
        matrix=[];values=[]
        for (x,y),(u,v) in zip(destinations,sources):
            matrix.extend(((x,y,1,0,0,0,-u*x,-u*y),(0,0,0,x,y,1,-v*x,-v*y)))
            values.extend((u,v))
        coefficients=np.linalg.solve(np.array(matrix,float),np.array(values,float))
        return reference.transform(size,Image.Transform.PERSPECTIVE,coefficients,Image.Resampling.BICUBIC)
    # Rectify only the wall polygons. Sky, road, border and photograph layout
    # are deliberately absent from the texture atlas.
    put('facade',facade((1000,1200),(44,163,44,281,230,277,227,73)),0,0)
    put('side',facade((500,1200),(227,73,230,277,261,285,260,145)),1020,0)
    put('lobby',facade((1000,240),(44,282,44,320,238,325,230,278)),0,1210)
    heavy = str(ROOT/'assets/FiraSans-Heavy.otf')
    for j,label in enumerate('ABCDE12345'):
        im=Image.new('RGBA',(64,80),(36,73,67,255))
        d=ImageDraw.Draw(im)
        d.text((11,7),label,font=ImageFont.truetype(heavy,49),fill='#d3e4ce')
        put(label,im,1300+(j%5)*75,1480+(j//5)*90)
    return upload_texture(atlas), regions


VERT = '''#version 330 core
layout(location=0) in vec3 position;
layout(location=1) in vec3 normal;
layout(location=2) in vec2 uv;
layout(location=3) in float face;
layout(location=4) in mat4 model;
layout(location=8) in vec4 color;
layout(location=9) in vec4 rect;
layout(location=10) in vec2 params;
uniform mat4 vp;
out vec3 vNormal;
out vec3 vWorld;
out vec2 vUv;
out vec4 vColor;
out float vTexture;
out float vEmission;
void main(){
 vec4 p=model*vec4(position,1.0);
 gl_Position=vp*p;
 vNormal=normalize(mat3(model)*normal);
 vWorld=p.xyz;
 vUv=rect.xy+uv*rect.zw;
 vColor=color;
 vTexture=params.x*face;
 vEmission=params.y;
}
'''
FRAG = '''#version 330 core
in vec3 vNormal;
in vec3 vWorld;
in vec2 vUv;
in vec4 vColor;
in float vTexture;
in float vEmission;
uniform sampler2D atlas;
uniform vec3 eye;
uniform float daylight;
out vec4 frag;
void main(){
 vec3 n=normalize(vNormal);
 vec3 light=normalize(vec3(-4.0,8.0,10.0));
 float diffuse=max(dot(n,light),0.0);
 vec3 v=normalize(eye-vWorld);
 float spec=pow(max(dot(n,normalize(light+v)),0.0),48.0);
 float rim=pow(1.0-max(dot(n,v),0.0),3.0);
 vec3 c=vColor.rgb*(0.40+0.65*diffuse)+vec3(0.36,0.48,0.41)*spec*0.35+vec3(0.04,0.12,0.09)*rim;
 if(vTexture>0.01){c=mix(c,texture(atlas,vUv).rgb*(0.92+0.08*diffuse),vTexture);}
 c+=vColor.rgb*daylight*.12;
 c=mix(c,vColor.rgb,vEmission);
 float fog=smoothstep(15.0,40.0,length(eye-vWorld));
 c=mix(c,mix(vec3(0.026,0.066,0.072),vec3(.45,.63,.67),daylight),fog*.40*(1.0-daylight));
 frag=vec4(c,vColor.a);
}
'''
BG_VERT = '''#version 330 core
layout(location=0) in vec2 position;
out vec2 uv;
void main(){gl_Position=vec4(position,0.999,1);uv=position*0.5+0.5;}
'''
BG_FRAG = '''#version 330 core
in vec2 uv;
uniform sampler2D video;
uniform float fade;
uniform float videoAspectScale;
uniform float backgroundTime;
out vec4 frag;
void main(){
 vec3 sky=mix(vec3(.63,.76,.79),vec3(.24,.51,.72),smoothstep(.1,1.,uv.y));
 float cloud=sin(uv.x*17.+backgroundTime*.08+sin(uv.y*21.)*2.)*sin(uv.y*31.+uv.x*4.+backgroundTime*.03);
 sky=mix(sky,vec3(.85,.88,.86),smoothstep(.42,.85,cloud)*.32);
 vec3 base=sky;
 // Extend the repeating circuit pattern with its original proportions.
 vec2 sourceUv=vec2(fract((uv.x-.5)*videoAspectScale+.5),1.0-uv.y);
 vec3 c=texture(video,sourceUv).rgb;
 float vignette=1.0-0.46*length((uv-.5)*vec2(1.,.9));
 frag=vec4(mix(base,c*0.48,fade)*vignette,1);
}
'''


class Renderer:
    def __init__(self):
        self.egl = init_egl()
        self.atlas, self.regions = make_atlas()
        self.phrases=BlockPhrases(W,H) if ANIMATED_PHRASES else None
        self.program = compileProgram(compileShader(VERT,GL_VERTEX_SHADER),compileShader(FRAG,GL_FRAGMENT_SHADER))
        self.bg = compileProgram(compileShader(BG_VERT,GL_VERTEX_SHADER),compileShader(BG_FRAG,GL_FRAGMENT_SHADER))
        self.vao = glGenVertexArrays(1); glBindVertexArray(self.vao)
        vertices=[]
        # Counterclockwise faces, with the image on the positive-Z face.
        faces=[([(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)],(0,0,1),1),
               ([(.5,-.5,-.5),(-.5,-.5,-.5),(-.5,.5,-.5),(.5,.5,-.5)],(0,0,-1),0),
               ([(.5,-.5,.5),(.5,-.5,-.5),(.5,.5,-.5),(.5,.5,.5)],(1,0,0),0),
               ([(-.5,-.5,-.5),(-.5,-.5,.5),(-.5,.5,.5),(-.5,.5,-.5)],(-1,0,0),0),
               ([(-.5,.5,.5),(.5,.5,.5),(.5,.5,-.5),(-.5,.5,-.5)],(0,1,0),0),
               ([(-.5,-.5,-.5),(.5,-.5,-.5),(.5,-.5,.5),(-.5,-.5,.5)],(0,-1,0),0)]
        uv=[(0,0),(1,0),(1,1),(0,1)]
        for points, normal, face in faces:
            for j in (0,1,2,0,2,3):
                vertices.append((*points[j],*normal,*uv[j],face))
        self.ranges={'cube':(0,len(vertices))}
        def triangle(a,b,c):
            a,b,c=np.array(a,float),np.array(b,float),np.array(c,float)
            n=np.cross(b-a,c-a)
            if np.dot(n,(a+b+c)/3)<0:b,c=c,b;n=-n
            n/=np.linalg.norm(n)
            for p,uv in zip((a,b,c),((0,0),(1,0),(.5,1))):vertices.append((*p,*n,*uv,0))
        for kind,sides in [('hex',6),('cylinder',20),('octa',4),('pyramid',4)]:
            start=len(vertices)
            if kind=='octa':
                ring=[(.5,0,0),(0,0,.5),(-.5,0,0),(0,0,-.5)]
                for j in range(4):
                    triangle((0,.5,0),ring[j],ring[(j+1)%4])
                    triangle((0,-.5,0),ring[j],ring[(j+1)%4])
            elif kind=='pyramid':
                ring=[(-.5,-.5,-.5),(.5,-.5,-.5),(.5,-.5,.5),(-.5,-.5,.5)]
                for j in range(4):
                    triangle((0,.5,0),ring[j],ring[(j+1)%4])
                    triangle((0,-.5,0),ring[j],ring[(j+1)%4])
            else:
                for j in range(sides):
                    angle=j*2*math.pi/sides;next_angle=(j+1)*2*math.pi/sides
                    x,z=.5*math.cos(angle),.5*math.sin(angle)
                    nx,nz=.5*math.cos(next_angle),.5*math.sin(next_angle)
                    triangle((0,.5,0),(x,.5,z),(nx,.5,nz))
                    triangle((0,-.5,0),(x,-.5,z),(nx,-.5,nz))
                    triangle((x,-.5,z),(nx,-.5,nz),(nx,.5,nz))
                    triangle((x,-.5,z),(nx,.5,nz),(x,.5,z))
            self.ranges[kind]=(start,len(vertices)-start)
        if self.phrases is not None:
            for name,mesh in self.phrases.meshes.items():
                self.ranges[name]=(len(vertices),len(mesh))
                vertices.extend(mesh)
        self.mesh = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,self.mesh)
        a=np.array(vertices,dtype=F32)
        glBufferData(GL_ARRAY_BUFFER,a.nbytes,a,GL_STATIC_DRAW)
        for loc,n,offset in [(0,3,0),(1,3,3),(2,2,6),(3,1,8)]:
            glEnableVertexAttribArray(loc); glVertexAttribPointer(loc,n,GL_FLOAT,False,36,ctypes.c_void_p(offset*4))
        self.instances=glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,self.instances)
        stride=26*4
        for loc,n,offset in [(4,4,0),(5,4,4),(6,4,8),(7,4,12),(8,4,16),(9,4,20),(10,2,24)]:
            glEnableVertexAttribArray(loc); glVertexAttribPointer(loc,n,GL_FLOAT,False,stride,ctypes.c_void_p(offset*4)); glVertexAttribDivisor(loc,1)
        self.bgvao=glGenVertexArrays(1); glBindVertexArray(self.bgvao)
        b=glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER,b)
        quad=np.array([-1,-1,1,-1,1,1,-1,-1,1,1,-1,1],dtype=F32)
        glBufferData(GL_ARRAY_BUFFER,quad.nbytes,quad,GL_STATIC_DRAW)
        glEnableVertexAttribArray(0); glVertexAttribPointer(0,2,GL_FLOAT,False,8,None)
        self.video=upload_texture(Image.new('RGB',(720,1280)))
        self.items={kind:[] for kind in self.ranges}
        self.rng=np.random.default_rng(2026)
        final=building()
        count=len(final)
        first=equalize(portal(),count)
        second=equalize(districts(),count)
        # Independent assignments make pieces travel between real spatial forms.
        first=[first[i] for i in self.rng.permutation(count)]
        second=[second[i] for i in self.rng.permutation(count)]
        self.arrangements=list(zip(first,second,final))
        self.delays=self.rng.uniform(0,.35,count)
        self.phases=self.rng.uniform(0,2*math.pi,count)
        self.wall=[]
        for side in (-1,1):
            for iy in range(22):
                for ix in range(4):
                    self.wall.append(((side*(4.8+ix*.85),-10+iy*.95,-6-float(self.rng.uniform(0,1.5))),(.76,.85,float(self.rng.uniform(.3,1.4)))))
        self.last_video=None
        # Explicit multisample framebuffer avoids platform-specific pbuffer reads.
        self.render_fbo=glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER,self.render_fbo)
        self.render_buffers=glGenRenderbuffers(2)
        for attachment,format_,buffer in zip(
            (GL_COLOR_ATTACHMENT0,GL_DEPTH_ATTACHMENT),
            (GL_RGBA8,GL_DEPTH_COMPONENT24),self.render_buffers):
            glBindRenderbuffer(GL_RENDERBUFFER,int(buffer))
            glRenderbufferStorageMultisample(GL_RENDERBUFFER,4,format_,W,H)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER,attachment,GL_RENDERBUFFER,int(buffer))
        if glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError('Unable to create multisample render buffer')
        # Resolve the four-sample render into a readable single-sample buffer.
        self.resolve_fbo=glGenFramebuffers(1)
        self.resolve_texture=glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D,self.resolve_texture)
        glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,W,H,0,GL_RGBA,GL_UNSIGNED_BYTE,None)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
        glBindFramebuffer(GL_FRAMEBUFFER,self.resolve_fbo)
        glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,self.resolve_texture,0)
        if glCheckFramebufferStatus(GL_FRAMEBUFFER)!=GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError('Unable to create antialiasing resolve buffer')
        glBindFramebuffer(GL_FRAMEBUFFER,0)

    def box(self,pos,size,color=(.10,.18,.18),rot=(0,0,0),region=None,texture=0,emission=0,kind='cube'):
        if min(size)<.00001:return
        m=model(pos,size,rot)
        rect=self.regions.get(region,(0,0,0,0)) if isinstance(region,str) else (region or (0,0,0,0))
        self.items[kind].append([*m.T.reshape(-1),*color,1,*rect,texture,emission])

    def subregion(self,name,col,row,cols,rows):
        x,y,w,h=self.regions[name]
        return x+w*col/cols,y+h*(rows-row-1)/rows,w/cols,h/rows

    def material_region(self,part):
        if part.surface is None:return None
        x,y,w,h=self.regions[part.surface]
        u,v,du,dv=part.uv
        return x+u*w,y+v*h,du*w,dv*h

    def camera(self,t):
        u=smooth(5.5,10.1,t)
        eye=lerp((6.2,7.0,17.5),(11.7,-.7,18.2),u)
        eye[0]+=.6*math.sin(t*.55)*(1-smooth(9.5,11.0,t))
        return eye

    def landscaping(self,t):
        grow=smooth(7.4,12.7,t) if ANIMATED_PHRASES else smooth(7.4,10.2,t)
        if grow<.001:return
        # A modelled driveway, curbs and planted entrance replace any photo background.
        def part(pos,size,color,kind='cube',rot=(0,0,0)):
            self.box(pos,np.array(size)*grow,color,rot=rot,kind=kind)
        part((0,-5.32,0),(17,.12,13),(.37,.39,.36),kind='cylinder')
        part((0,-5.20,0),(9.0,.15,6.8),(.67,.68,.60),kind='cylinder')
        part((0,-5.08,0),(8.7,.14,6.5),(.28,.40,.21),kind='cylinder')
        part((0,-5.02,.15),(7.15,.14,4.7),(.50,.52,.45))
        # A planted roundabout in front of the entrance.
        part((.6,-5.17,4.25),(3.2,.14,1.85),(.70,.72,.65),kind='cylinder')
        part((.6,-5.08,4.25),(2.95,.15,1.62),(.27,.43,.16),kind='cylinder')
        for j in range(15):
            a=j*2*math.pi/15
            part((.6+1.15*math.cos(a),-4.86,4.25+.55*math.sin(a)),(.35,.35,.35),(.20,.41,.16),kind='octa')
        for side in (-1,1):
            for k in range(4):
                x=side*(4.5+.20*(k%2));z=-2+k*1.35
                part((x,-4.25,z),(.16,1.6,.16),(.31,.29,.20))
                for j in range(3):
                    part((x+(j-1)*.26,-3.35+(j%2)*.28,z),(.95,1.1,.95),(.21+.025*j,.39+.025*j,.18),kind='octa')
        for j in range(5):part((-1.4,-5.23,3.8+j*.64),(1.25,.025,.20),(.70,.71,.65))
        for k in (-1,1):
            x=k*4.9;z=.7 if k==1 else 2.6
            part((x,-4.90,z),(1.05,.35,.55),(.12,.15,.15))
            part((x,-4.67,z-.03),(.62,.23,.48),(.20,.27,.27))
            for dx in (-.34,.34):
                for dz in (-.29,.29):part((x+dx,-5.08,z+dz),(.23,.23,.13),(.09,.10,.10),kind='cylinder',rot=(math.pi/2,0,0))

    def scene(self,t):
        self.items={kind:[] for kind in self.ranges}
        daylight=smooth(7.0,10.2,t)
        for j,(pos,size) in enumerate(self.wall):
            p=np.array(pos,float);p[2]+=.22*math.sin(t*1.4+j*.3)-12*daylight
            self.box(p,np.array(size)*(1-daylight),(.055,.075,.075))
            if j%6==0:
                self.box(p+np.array([size[0]*.5+.025,0,size[2]*.52]),np.array((.035,size[1]*.85,.035))*(1-daylight),(.14,.65,.32),emission=.65)
        self.background_end={kind:len(items) for kind,items in self.items.items()}
        eye=self.camera(t)
        view=look_at(eye,(0,0,0));basis=view[:3,:3].T
        foreground_start={kind:len(items) for kind,items in self.items.items()}
        self.foreground(t)
        if FOREGROUND_COPIES==2:
            self.arrange_foregrounds(t,basis,foreground_start)
        if self.phrases is not None:
            self.phrases.append(self,self.presentation_time,eye,basis)

    def foreground(self,t,alternate=False):
        """Two complementary opening formations share the final building clock."""
        for i,(first,city,final) in enumerate(self.arrangements):
            delay=self.delays[i];phase=self.phases[i]
            if alternate:
                # Begin with the towers while the left group builds its portal.
                # Reverse the piece order and orbital direction, then swap forms.
                first,city=city,first
                phase=-phase
                entry_delay=.35-delay
                enter=smooth(.10+entry_delay,1.50+entry_delay,t)
                district=smooth(2.45+entry_delay,4.55+entry_delay,t)
            else:
                enter=smooth(.10+delay,1.25+delay,t)
                district=smooth(2.7+delay,4.25+delay,t)
            floor_delay=(final.pos[1]+5.0)/10.0*.90
            construction_start,construction_end=(6.0,11.55) if ANIMATED_PHRASES else (5.45,8.80)
            construction=smooth(construction_start+floor_delay+delay,construction_end+floor_delay+delay,t)
            # Two changes of spatial arrangement. The final building never disassembles.
            if construction>0:
                origin,target,u=city,final,construction
                arc=math.sin(math.pi*u)
                radius=1.8
            else:
                origin,target,u=first,city,district
                arc=math.sin(math.pi*u)
                radius=1.1
            p=lerp(origin.pos,target.pos,u)
            p+=np.array((radius*math.cos(phase+u*2),.9*math.sin(phase+u*2),1.8+math.sin(phase)))*arc
            entry=(3.2*math.cos(phase),5+1.8*math.sin(phase),-2) if alternate else (1.2*math.cos(phase),.7*math.sin(phase),-6)
            p+=np.array(entry)*(1-enter)
            rot=lerp(origin.rot,target.rot,u)
            spin=-2*math.pi if alternate else 2*math.pi
            rot+=np.array((.8*math.sin(phase),spin,.5*math.cos(phase)))*arc
            if alternate:
                rot+=np.array((.3*math.sin(phase),.7*math.cos(phase),.5*math.sin(phase)))*(1-enter)
            size=lerp(origin.size,target.size,u)*max(.0001,enter)
            color=lerp(origin.color,target.color,u)
            active=origin if u<.48 else target
            # Surface finish becomes solid as the corresponding 3D piece docks.
            finish=active.finish
            if construction>0:
                finish*=smooth(.68,.99,construction)
            uv=self.material_region(active)
            self.box(p,size,color,rot,uv,finish,kind=active.kind)
        self.landscaping(t)

    def arrange_foregrounds(self,t,basis,start):
        """Place independently choreographed foregrounds over the same backdrop."""
        left={kind:items[start[kind]:] for kind,items in self.items.items()}
        self.items={kind:items[:start[kind]] for kind,items in self.items.items()}
        self.foreground(t,alternate=True)
        right={kind:items[start[kind]:] for kind,items in self.items.items()}
        camera_distance=float(np.linalg.norm(self.camera(t)))
        half_width=camera_distance*math.tan(math.radians(38)/2)*(W/H)
        center=-.24*half_width
        spacing=float(lerp(6.4,5.05,smooth(7.4,10.1,t)))
        groups=[]
        for direction in (-1,1):
            group=np.eye(4)
            group[:3,:3]*=.90
            group[:3,3]=basis[:,0]*(center+direction*spacing)
            groups.append(group)
        for kind,items in self.items.items():
            duplicated=[]
            for group,formation in zip(groups,(left,right)):
                for instance in formation[kind]:
                    matrix=np.asarray(instance[:16]).reshape(4,4).T
                    transformed=group@matrix
                    duplicated.append([*transformed.T.reshape(-1),*instance[16:]])
            self.items[kind]=items[:start[kind]]+duplicated

    def render(self,t,video_bytes=None):
        self.presentation_time=t
        t=scene_time(t)
        if video_bytes is not None:
            glBindTexture(GL_TEXTURE_2D,self.video)
            glTexSubImage2D(GL_TEXTURE_2D,0,0,0,720,1280,GL_RGB,GL_UNSIGNED_BYTE,video_bytes)
        glBindFramebuffer(GL_FRAMEBUFFER,self.render_fbo)
        glEnable(GL_MULTISAMPLE)
        glViewport(0,0,W,H)
        glClearColor(.028,.075,.079,1);glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glDisable(GL_DEPTH_TEST);glUseProgram(self.bg);glBindVertexArray(self.bgvao)
        glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,self.video)
        glUniform1i(glGetUniformLocation(self.bg,'video'),0)
        glUniform1f(glGetUniformLocation(self.bg,'fade'),1-smooth(7.0,10.2,t))
        glUniform1f(glGetUniformLocation(self.bg,'videoAspectScale'),(W/H)/(720/1280))
        glUniform1f(glGetUniformLocation(self.bg,'backgroundTime'),self.presentation_time)
        glDrawArrays(GL_TRIANGLES,0,6)
        self.scene(t)
        eye=self.camera(t)
        vp=projection()@look_at(eye,(0,0,0))
        glEnable(GL_DEPTH_TEST);glEnable(GL_CULL_FACE);glCullFace(GL_BACK)
        glUseProgram(self.program);glBindVertexArray(self.vao)
        glUniformMatrix4fv(glGetUniformLocation(self.program,'vp'),1,GL_TRUE,vp)
        glUniform3f(glGetUniformLocation(self.program,'eye'),*eye)
        glUniform1f(glGetUniformLocation(self.program,'daylight'),smooth(7.0,10.2,t))
        glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,self.atlas)
        glUniform1i(glGetUniformLocation(self.program,'atlas'),0)
        for kind,items in self.items.items():
            if not items:continue
            instances=np.array(items,dtype=F32)
            glBindBuffer(GL_ARRAY_BUFFER,self.instances)
            glBufferData(GL_ARRAY_BUFFER,instances.nbytes,instances,GL_STREAM_DRAW)
            start,count=self.ranges[kind]
            translucent=kind.startswith('glyph_')
            if translucent:
                glEnable(GL_BLEND);glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);glDepthMask(GL_FALSE)
            glDrawArraysInstanced(GL_TRIANGLES,start,count,len(instances))
            if translucent:
                glDepthMask(GL_TRUE);glDisable(GL_BLEND)
        glFinish()
        glBindFramebuffer(GL_READ_FRAMEBUFFER,self.render_fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER,self.resolve_fbo)
        glBlitFramebuffer(0,0,W,H,0,0,W,H,GL_COLOR_BUFFER_BIT,GL_NEAREST)
        glBindFramebuffer(GL_READ_FRAMEBUFFER,self.resolve_fbo)
        pixels=glReadPixels(0,0,W,H,GL_RGB,GL_UNSIGNED_BYTE)
        glBindFramebuffer(GL_FRAMEBUFFER,0)
        return Image.frombytes('RGB',(W,H),pixels).transpose(Image.Transpose.FLIP_TOP_BOTTOM)


def scene_time(t):
    """The approved foreground choreography always advances at its native speed."""
    return min(t,13.0)


def background_frame(t):
    """Native-speed forward/reverse reference loop, independent of text timing."""
    frame=round(t*FPS)%382
    return frame if frame<191 else 381-frame


def extract_frame(t):
    source_time=background_frame(t)/FPS
    r=subprocess.run(['ffmpeg','-v','error','-threads','1','-ss',str(source_time),'-i',str(ROOT/'pinterest-savepin-onl.blocomp4'),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','pipe:1'],capture_output=True,check=True)
    return r.stdout


def main():
    global W, H, LANDSCAPE, FOREGROUND_COPIES, ANIMATED_PHRASES, DURATION
    parser=argparse.ArgumentParser()
    parser.add_argument('--stills',action='store_true')
    parser.add_argument('--format',choices=('landscape','portrait'),default='landscape')
    parser.add_argument('--copies',type=int,choices=(1,2),default=None)
    parser.add_argument('--no-phrases',action='store_true')
    args=parser.parse_args()
    LANDSCAPE = args.format == 'landscape'
    FOREGROUND_COPIES = args.copies if args.copies is not None else (2 if LANDSCAPE else 1)
    if not LANDSCAPE and FOREGROUND_COPIES==2:
        parser.error('Duas formações requerem --format landscape.')
    W,H = (1920,1080) if LANDSCAPE else (720,1280)
    ANIMATED_PHRASES=(not LANDSCAPE or FOREGROUND_COPIES==2) and not args.no_phrases
    DURATION=15.2 if ANIMATED_PHRASES else 13.0
    label='horizontal-dupla' if FOREGROUND_COPIES==2 else ('horizontal' if LANDSCAPE else 'v2')
    if ANIMATED_PHRASES:label='dupla-dinamica' if LANDSCAPE else 'mobile-vertical'
    video_name = f'ENADE.ADS-2026-abertura-3D-{label}.mp4'
    poster_name = f'poster-{label}.jpg'
    OUT.mkdir(exist_ok=True)
    r=Renderer()
    if ANIMATED_PHRASES:
        (OUT/f'{label}.vtt').write_text(captions_vtt())
        (OUT/f'{label}.json').write_text(json.dumps({
            'duration':DURATION,'cta_start':13.0,
            'phrases':[{'text':p.text,'start':p.start,'hold':p.hold,'end':p.end} for p in PHRASES],
            'city_complete':max(11.55+(part.pos[1]+5)/10*.90+delay for (_,_,part),delay in zip(r.arrangements,r.delays)),
            'formations':({'left':['portal','districts','building'],'right':['districts','portal','building']} if FOREGROUND_COPIES==2 else {'center':['portal','districts','building']}),
        },ensure_ascii=False,indent=2))
    if args.stills:
        times=[.8,2.0,3.6,5.2,8.8,11.0,12.9,14.0] if ANIMATED_PHRASES else [1.8,2.6,4.8,6.4,7.8,9.0,10.5,12.8]
        thumb_w,thumb_h=(480,270) if LANDSCAPE else (288,512)
        row_h=thumb_h+30
        board=Image.new('RGB',(4*thumb_w,2*row_h),(7,18,20))
        d=ImageDraw.Draw(board)
        for i,t in enumerate(times):
            prefix=f'frame-{label}' if LANDSCAPE or ANIMATED_PHRASES else 'frame'
            im=r.render(t,extract_frame(t));im.save(OUT/f'{prefix}-{t:04.1f}.jpg',quality=93)
            board.paste(im.resize((thumb_w,thumb_h)),((i%4)*thumb_w,(i//4)*row_h))
            d.text(((i%4)*thumb_w+12,(i//4)*row_h+thumb_h+6),f'{t:.1f} s',fill='#b7d6ca')
        board.save(OUT/(f'storyboard-{label}.jpg' if LANDSCAPE or ANIMATED_PHRASES else 'storyboard-3D.jpg'),quality=94)
        print('Storyboard saved',flush=True)
        return
    # Spool lossless reference frames to disk; reverse playback must not keep
    # hundreds of decoded frames in RAM alongside the renderer and encoder.
    reference_cache=ROOT/'.render-cache'/'background'
    reference_cache.mkdir(parents=True,exist_ok=True)
    if not all((reference_cache/f'{i:03d}.png').is_file() for i in range(191)):
        subprocess.run(['ffmpeg','-y','-v','error','-threads','1','-i',str(ROOT/'pinterest-savepin-onl.blocomp4'),
            '-threads','1','-filter_threads','1','-frames:v','191','-pix_fmt','rgb24','-start_number','0',
            str(reference_cache/'%03d.png')],check=True)
    print('Resource limit: one CPU, low priority, reference frames cached on disk.',flush=True)
    encoder=subprocess.Popen(['ffmpeg','-y','-v','warning','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-threads','1','-preset','fast','-rc-lookahead','8','-refs','2','-crf','20' if ANIMATED_PHRASES else '18',*(['-maxrate','6M','-bufsize','12M'] if ANIMATED_PHRASES else []),'-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/video_name)],stdin=subprocess.PIPE)
    last=None
    for frame in range(round(DURATION*FPS)):
        with Image.open(reference_cache/f'{background_frame(frame/FPS):03d}.png') as reference:
            last=reference.convert('RGB').tobytes()
        image=r.render(frame/FPS,last)
        encoder.stdin.write(image.tobytes())
        if frame%25==0:print(f'Rendering {frame/FPS:04.1f}/{DURATION:.0f}s',flush=True)
        poster_time=2.0 if ANIMATED_PHRASES and not LANDSCAPE else (3.6 if ANIMATED_PHRASES else 1.8)
        if frame==round(poster_time*FPS):image.save(OUT/poster_name,quality=95)
    encoder.stdin.close()
    if encoder.wait()!=0:raise RuntimeError('FFmpeg encode failed')
    print('MP4 complete:',OUT/video_name,flush=True)


if __name__=='__main__':main()

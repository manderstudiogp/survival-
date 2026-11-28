#!/usr/bin/env python3
"""Hi3D (or any single-mesh textured GLB) -> Paperland game model.

  python3 hi3d_import.py config.json

Writes models/<name>.json (glTF, geometry embedded), <name>_color.jpg and, if the config asks for glow, <name>_glow*.png.
Steps: load -> detect the texture's v orientation -> simplify keeping UV seams (simplify_uv, C++) -> scale/centre to game
size -> bake a gentle pull toward the 12-colour palette into the texture -> paint glow masks -> write.
Config keys (see README "Adding Hi3D models"):
  src, name, out_dir, tris (default 150000), tex (4096), palette (0..1, default 0.3)
  size: {"axis":"y"|"z"|"x", "length": metres}   which extent to match, e.g. height 1.3 for a character, z 4.2 for the van
  align: "feet" (y=0 at the bottom, centred in x/z)          default
  glow: [ {"group":"lamps","kind":"disc","c":[x,y,z_side],"r":0.03,"face":"+z","rgb":[255,236,196]},
          {"group":"windows","kind":"rect","side":"-x","u":[z0,z1],"v":[y0,y1],"rgb":[255,186,110],"tex":1} ,
          {"group":"lights","kind":"color","rule":"cyan"} ]       coordinates are in the source GLB's own units
"""
import sys,os,json,struct,io,base64,subprocess
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
PAL=[0xAB451C,0xDB9F44,0xD08118,0x30543B,0x668349,0xA2A673,0xB7D7D0,0x5B8093,0x84715C,0xBF9E70,0x69452A,0xF4F6F6]
PRGB=np.array([[(h>>16)&255,(h>>8)&255,h&255] for h in PAL],np.float32)/255
HERE=os.path.dirname(os.path.abspath(__file__))

def load_glb(path):
  f=open(path,'rb').read();cl,_=struct.unpack('<II',f[12:20]);j=json.loads(f[20:20+cl]);o=20+cl;bl,_=struct.unpack('<II',f[o:o+8]);B=f[o+8:o+8+bl]
  def acc(i):
    a=j['accessors'][i];bv=j['bufferViews'][a['bufferView']];dt={5126:np.float32,5125:np.uint32,5123:np.uint16}[a['componentType']];nc={'SCALAR':1,'VEC2':2,'VEC3':3}[a['type']]
    x=np.frombuffer(B,dtype=dt,count=a['count']*nc,offset=bv.get('byteOffset',0)+a.get('byteOffset',0));return x.reshape(-1,nc) if nc>1 else x
  p=j['meshes'][0]['primitives'][0];V=acc(p['attributes']['POSITION']).astype(np.float64);UV=acc(p['attributes']['TEXCOORD_0']).astype(np.float64);I=acc(p['indices']).reshape(-1,3).astype(np.int64)
  mat=j['materials'][p.get('material',0)];ti=mat['pbrMetallicRoughness']['baseColorTexture']['index'];im=j['images'][j['textures'][ti]['source']];bv=j['bufferViews'][im['bufferView']]
  img=Image.open(io.BytesIO(B[bv.get('byteOffset',0):bv.get('byteOffset',0)+bv['byteLength']])).convert('RGB')
  ok=(I[:,0]!=I[:,1])&(I[:,1]!=I[:,2])&(I[:,0]!=I[:,2]);return V,UV,I[ok],img

def detect_flip(V,UV,I,img):
  """At a UV seam the two sides of the same 3D edge come from different places in the texture; with the right v orientation their
  colours match. Compare edge-midpoint colours across seams for both orientations and keep the better match."""
  t=np.asarray(img.resize((1024,1024))).astype(np.float32);h,w,_=t.shape
  k=np.round(V*1e5).astype(np.int64);_,wid=np.unique(k,axis=0,return_inverse=True);wid=wid.ravel()
  E=np.concatenate([I[:,[0,1]],I[:,[1,2]],I[:,[2,0]]]);We=np.sort(wid[E],1);sw=wid[E[:,0]]>wid[E[:,1]]
  E=np.where(sw[:,None],E[:,::-1],E);key=We[:,0]*(len(wid)+1)+We[:,1];o=np.argsort(key,kind='stable');ks=key[o];j=np.where(ks[1:]==ks[:-1])[0]
  e1,e2=E[o[j]],E[o[j+1]];seam=(np.abs(UV[e1]-UV[e2]).sum((1,2))>1e-4)
  e1,e2=e1[seam],e2[seam];print('  seam edges',len(e1))
  if len(e1)>200000:r=np.random.default_rng(1).choice(len(e1),200000,replace=False);e1,e2=e1[r],e2[r]
  score=[]
  for flip in (False,True):
    def col(e):
      uv=UV[e].mean(1).copy()
      if flip:uv[:,1]=1-uv[:,1]
      return t[np.clip((uv[:,1]%1*h).astype(int),0,h-1),np.clip((uv[:,0]%1*w).astype(int),0,w-1)]
    score.append(np.abs(col(e1)-col(e2)).mean())
  return score[1]<score[0],score

def palette_grade(img,strength):
  if strength<=0:return img
  a=np.asarray(img).astype(np.float32)/255;out=np.empty_like(a);H=a.shape[0];step=256
  wt=np.array([0.8,1.0,0.6],np.float32);lw=np.array([0.299,0.587,0.114],np.float32)
  for r in range(0,H,step):
    c=a[r:r+step];d=(((c[...,None,:]-PRGB)*wt)**2).sum(-1);n=PRGB[d.argmin(-1)]
    l0=(c*lw).sum(-1,keepdims=True);l1=(n*lw).sum(-1,keepdims=True);n=n*(1+0.6*(np.clip(l0/np.maximum(l1,1e-3),0.75,1.25)-1))
    out[r:r+step]=c+(n-c)*strength
  return Image.fromarray((np.clip(out,0,1)*255).astype(np.uint8))

def main(cfg):
  name=cfg['name'];out=cfg.get('out_dir','models');os.makedirs(out,exist_ok=True)
  V,UV,I,img=load_glb(cfg['src']);flip,sc=detect_flip(V,UV,I,img);print(name,': uv v-flip',flip,'scores',[round(x,2) for x in sc])
  UVs=UV.copy()
  if flip:UVs[:,1]=1-UVs[:,1]            # from here on: v measured from the image top (glTF's own convention)
  # simplify, keeping seams
  exe=os.path.join(HERE,'simplify_uv');src=os.path.join(HERE,'simplify_uv.cpp')
  if not os.path.exists(exe):subprocess.check_call(['g++','-O2','-o',exe,src])
  tin=f'/tmp/{name}_in.bin';tout=f'/tmp/{name}_out.bin'
  with open(tin,'wb') as f:f.write(struct.pack('<II',len(V),len(I)));f.write(np.c_[V,UVs].astype('<f8').tobytes());f.write(I.astype('<u4').tobytes())
  subprocess.check_call([exe,tin,tout,str(cfg.get('tris',150000))],stderr=subprocess.DEVNULL)
  f=open(tout,'rb');n,m=struct.unpack('<II',f.read(8));A=np.frombuffer(f.read(n*40),'<f8').reshape(-1,5);F=np.frombuffer(f.read(m*12),'<u4').reshape(-1,3).astype(np.int64)
  P,PUV=A[:,:3],A[:,3:]
  # scale and place
  ax='xyz'.index(cfg['size'].get('axis','y'));sf=cfg['size']['length']/(V[:,ax].max()-V[:,ax].min())
  cx=(V[:,0].max()+V[:,0].min())/2;cz=(V[:,2].max()+V[:,2].min())/2;y0=V[:,1].min()
  T=lambda p:np.c_[(p[...,0]-cx)*sf,(p[...,1]-y0)*sf,(p[...,2]-cz)*sf]
  N=T(P).astype('<f4')
  # glow masks: painted by source triangles, so the shapes follow the real texture
  groups={};c3=V[I].mean(1);ES=2048
  for g in cfg.get('glow',[]):
    G=groups.setdefault(g['group'],{'img':Image.new('RGB',(ES,ES)),'pts':[],'lowsel':None});dr=ImageDraw.Draw(G['img'])
    if g['kind']=='disc':
      fa='xyz'.index(g['face'][1]);sg=1 if g['face'][0]=='+' else -1;o=[a for a in range(3) if a!=fa]
      near=np.hypot(c3[:,o[0]]-g['c'][o[0]],c3[:,o[1]]-g['c'][o[1]])<g['r'];top=(c3[near][:,fa]*sg).max();sel=near&(c3[:,fa]*sg>top-0.03*(V[:,fa].max()-V[:,fa].min()))
    elif g['kind']=='rect':
      fa='xyz'.index(g['side'][1]);sg=1 if g['side'][0]=='+' else -1;o=[a for a in range(3) if a!=fa]
      ua,va=('xyz'.index(g.get('u_axis','z')),'xyz'.index(g.get('v_axis','y')))
      sel=(c3[:,fa]*sg>g.get('depth',0.7)*(V[:,fa]*sg).max())&(c3[:,ua]>g['u'][0])&(c3[:,ua]<g['u'][1])&(c3[:,va]>g['v'][0])&(c3[:,va]<g['v'][1])
    else:   # 'color': every texel matching a colour rule glows in its own colour (e.g. cyan circuit lines)
      t=np.asarray(img.resize((ES,ES))).astype(np.int32);r,gg,b=t[...,0],t[...,1],t[...,2]
      m=((b>r+40)&(gg>r+30)&(gg+b>260)) if g.get('rule','cyan')=='cyan' else ((r>gg+60)&(r>b+60)&(r>150))
      mk=Image.fromarray(m.astype(np.uint8)*255).filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.0))
      G['img']=Image.fromarray(np.clip(t*(np.asarray(mk)[...,None]/255.0)*g.get('gain',1.0),0,255).astype(np.uint8));sel=None;print(f"  glow {g['group']}: colour rule, {int(m.sum())} texels")
    if sel is not None:
      base=np.asarray(img.resize((ES,ES))).astype(np.float32)
      for tri in I[sel]:
        pts=[(UVs[k,0]*ES,UVs[k,1]*ES) for k in tri]
        if g.get('tex'):
          u=int(np.clip(np.mean([p[0] for p in pts]),0,ES-1));v=int(np.clip(np.mean([p[1] for p in pts]),0,ES-1));L=base[v,u].mean()/255;col=tuple(int(x*(0.35+0.65*L)) for x in g['rgb'])
        else:col=tuple(g['rgb'])
        dr.polygon(pts,fill=col)
      ctr=c3[sel].mean(0) if sel.any() else np.zeros(3);G['pts'].append(T(ctr[None])[0].round(3).tolist())
      print(f"  glow {g['group']}: {sel.sum()} source faces at {G['pts'][-1]}")
  # colour texture with the palette grade baked in (no shader needed in game)
  TS=cfg.get('tex',4096);col=palette_grade(img.resize((TS,TS),Image.LANCZOS),cfg.get('palette',0.3))
  col.save(os.path.join(out,name+'_color.jpg'),quality=92)
  imgs=[{'uri':name+'_color.jpg'}];texs=[{'source':0,'sampler':0}];extras={'glow':{},'anchors':{k:T(np.array(v,float)[None])[0].round(3).tolist() for k,v in cfg.get('anchors',{}).items()}}
  for gname,G in groups.items():
    fn=f'{name}_glow_{gname}.png';G['img'].filter(ImageFilter.GaussianBlur(1.0)).save(os.path.join(out,fn),optimize=True)
    imgs.append({'uri':fn});texs.append({'source':len(imgs)-1,'sampler':0});extras['glow'][gname]={'texture':len(texs)-1,'points':G['pts']}
  geo=N.tobytes()+PUV.astype('<f4').tobytes()+F.astype('<u4').tobytes();nb=len(N)*12;ub=len(N)*8
  J={'asset':{'version':'2.0','generator':'Paperland hi3d_import'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'name':name,'mesh':0,'extras':extras}],
   'meshes':[{'primitives':[{'attributes':{'POSITION':0,'TEXCOORD_0':1},'indices':2,'material':0}]}],
   'accessors':[{'bufferView':0,'componentType':5126,'count':len(N),'type':'VEC3','min':N.min(0).tolist(),'max':N.max(0).tolist()},{'bufferView':1,'componentType':5126,'count':len(N),'type':'VEC2'},{'bufferView':2,'componentType':5125,'count':F.size,'type':'SCALAR'}],
   'bufferViews':[{'buffer':0,'byteOffset':0,'byteLength':nb,'target':34962},{'buffer':0,'byteOffset':nb,'byteLength':ub,'target':34962},{'buffer':0,'byteOffset':nb+ub,'byteLength':F.size*4,'target':34963}],
   'buffers':[{'byteLength':len(geo),'uri':'data:application/octet-stream;base64,'+base64.b64encode(geo).decode()}],
   'images':imgs,'samplers':[{'magFilter':9729,'minFilter':9987}],'textures':texs,
   'materials':[{'name':name,'pbrMetallicRoughness':{'baseColorTexture':{'index':0},'metallicFactor':0,'roughnessFactor':1}}]}
  json.dump(J,open(os.path.join(out,name+'.json'),'w'),separators=(',',':'))
  print(f'  wrote {name}.json: {len(N)} verts, {len(F)} tris, scale {sf:.4f}')
  return dict(T=T,sf=sf)
if __name__=='__main__':main(json.load(open(sys.argv[1])))

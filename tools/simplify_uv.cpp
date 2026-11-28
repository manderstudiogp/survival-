// Quadric edge-collapse simplification (Garland-Heckbert, iterative-threshold variant).
// in: n(uint32) m(uint32) n*3 double positions, m*3 uint32 indices ; out: same format
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <cmath>
#include <cstdint>
#include <algorithm>
using namespace std;
struct V3{double x,y,z;V3 operator+(const V3&b)const{return{x+b.x,y+b.y,z+b.z};}V3 operator-(const V3&b)const{return{x-b.x,y-b.y,z-b.z};}V3 operator*(double s)const{return{x*s,y*s,z*s};}};
static V3 cross(V3 a,V3 b){return{a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
static double dot(V3 a,V3 b){return a.x*b.x+a.y*b.y+a.z*b.z;}
static V3 norm(V3 a){double l=sqrt(dot(a,a));return l>0?a*(1/l):a;}
struct Q{double m[10];Q(){for(int i=0;i<10;i++)m[i]=0;}Q(double a,double b,double c,double d){m[0]=a*a;m[1]=a*b;m[2]=a*c;m[3]=a*d;m[4]=b*b;m[5]=b*c;m[6]=b*d;m[7]=c*c;m[8]=c*d;m[9]=d*d;}
 Q operator+(const Q&o)const{Q r;for(int i=0;i<10;i++)r.m[i]=m[i]+o.m[i];return r;}
 double det(int a11,int a12,int a13,int a21,int a22,int a23,int a31,int a32,int a33)const{return m[a11]*m[a22]*m[a33]+m[a13]*m[a21]*m[a32]+m[a12]*m[a23]*m[a31]-m[a13]*m[a22]*m[a31]-m[a11]*m[a23]*m[a32]-m[a12]*m[a21]*m[a33];}};
struct Tri{int v[3];double err[4];bool del,dirty;V3 n;};
struct Vert{V3 p;int ts,tc;Q q;bool border;double uv[2];};
struct Ref{int t,tv;};
vector<Tri> T;vector<Vert> Vs;vector<Ref> R;
static double vErr(const Q&q,double x,double y,double z){const double*m=q.m;return m[0]*x*x+2*m[1]*x*y+2*m[2]*x*z+2*m[3]*x+m[4]*y*y+2*m[5]*y*z+2*m[6]*y+m[7]*z*z+2*m[8]*z+m[9];}
static double cErr(int a,int b,V3&r){Q q=Vs[a].q+Vs[b].q;bool bd=Vs[a].border&&Vs[b].border;double d=q.det(0,1,2,1,4,5,2,5,7);
 if(d!=0&&!bd){r.x=-1/d*q.det(1,2,3,4,5,6,5,7,8);r.y=1/d*q.det(0,2,3,1,5,6,2,7,8);r.z=-1/d*q.det(0,1,3,1,4,6,2,5,8);return vErr(q,r.x,r.y,r.z);}
 V3 p1=Vs[a].p,p2=Vs[b].p,p3=(p1+p2)*0.5;double e1=vErr(q,p1.x,p1.y,p1.z),e2=vErr(q,p2.x,p2.y,p2.z),e3=vErr(q,p3.x,p3.y,p3.z);double e=min(e1,e2);(void)e3;
 if(e2<e1)r=p2;else r=p1;return e;}
static bool flipped(V3 p,int i0,int i1,Vert&v0,vector<int>&del){
 for(int k=0;k<v0.tc;k++){Tri&t=T[R[v0.ts+k].t];if(t.del)continue;int s=R[v0.ts+k].tv,id1=t.v[(s+1)%3],id2=t.v[(s+2)%3];
  if(id1==i1||id2==i1){del[k]=1;continue;}V3 d1=norm(Vs[id1].p-p),d2=norm(Vs[id2].p-p);if(fabs(dot(d1,d2))>0.999)return true;
  V3 n=norm(cross(d1,d2));del[k]=0;if(dot(n,t.n)<0.2)return true;}return false;}
static void updTris(int i0,Vert&v,vector<int>&del,int&dc){V3 p;
 for(int k=0;k<v.tc;k++){Ref&r=R[v.ts+k];Tri&t=T[r.t];if(t.del)continue;if(del[k]){t.del=1;dc++;continue;}
  t.v[r.tv]=i0;t.dirty=1;t.err[0]=cErr(t.v[0],t.v[1],p);t.err[1]=cErr(t.v[1],t.v[2],p);t.err[2]=cErr(t.v[2],t.v[0],p);t.err[3]=min(t.err[0],min(t.err[1],t.err[2]));R.push_back(r);}}
static void updMesh(int it){
 if(it>0){int dst=0;for(size_t i=0;i<T.size();i++)if(!T[i].del)T[dst++]=T[i];T.resize(dst);}
 for(auto&v:Vs){v.ts=0;v.tc=0;}for(auto&t:T)for(int j=0;j<3;j++)Vs[t.v[j]].tc++;
 int ts=0;for(auto&v:Vs){v.ts=ts;ts+=v.tc;v.tc=0;}R.resize(T.size()*3);
 for(size_t i=0;i<T.size();i++)for(int j=0;j<3;j++){Vert&v=Vs[T[i].v[j]];R[v.ts+v.tc]={(int)i,j};v.tc++;}
 if(it==0){vector<int> vc,vids;
  for(auto&v:Vs)v.border=0;
  for(size_t i=0;i<Vs.size();i++){Vert&v=Vs[i];vc.clear();vids.clear();
   for(int j=0;j<v.tc;j++){Tri&t=T[R[v.ts+j].t];for(int k=0;k<3;k++){int id=t.v[k],o=0;while(o<(int)vids.size()){if(vids[o]==id)break;o++;}if(o==(int)vids.size()){vc.push_back(1);vids.push_back(id);}else vc[o]++;}}
   for(size_t j=0;j<vc.size();j++)if(vc[j]==1)Vs[vids[j]].border=1;}
  for(auto&v:Vs)v.q=Q();
  for(auto&t:T){V3 p[3];for(int j=0;j<3;j++)p[j]=Vs[t.v[j]].p;V3 n=norm(cross(p[1]-p[0],p[2]-p[0]));t.n=n;
   for(int j=0;j<3;j++)Vs[t.v[j]].q=Vs[t.v[j]].q+Q(n.x,n.y,n.z,-dot(n,p[0]));}
  for(auto&t:T){V3 p;for(int j=0;j<3;j++)t.err[j]=cErr(t.v[j],t.v[(j+1)%3],p);t.err[3]=min(t.err[0],min(t.err[1],t.err[2]));}}}
int main(int argc,char**argv){FILE*f=fopen(argv[1],"rb");uint32_t n,m;fread(&n,4,1,f);fread(&m,4,1,f);Vs.resize(n);T.resize(m);
 for(uint32_t i=0;i<n;i++){double p[5];fread(p,8,5,f);Vs[i].p={p[0],p[1],p[2]};Vs[i].uv[0]=p[3];Vs[i].uv[1]=p[4];}
 for(uint32_t i=0;i<m;i++){uint32_t v[3];fread(v,4,3,f);for(int j=0;j<3;j++)T[i].v[j]=v[j];T[i].del=0;T[i].dirty=0;}fclose(f);
 int target=atoi(argv[3]);double agg=7;int dc=0;vector<int> d0,d1;
 for(int it=0;it<200;it++){if((int)T.size()-dc<=target)break;if(it%5==0){updMesh(it);if(it>0)dc=0;}
  for(auto&t:T)t.dirty=0;double th=0.000000001*pow(double(it+3),agg);
  for(size_t i=0;i<T.size();i++){Tri&t=T[i];if(t.err[3]>th||t.del||t.dirty)continue;
   for(int j=0;j<3;j++)if(t.err[j]<th){int i0=t.v[j],i1=t.v[(j+1)%3];Vert&v0=Vs[i0];Vert&v1=Vs[i1];if(v0.border||v1.border)continue;
    V3 p;cErr(i0,i1,p);d0.assign(v0.tc,0);d1.assign(v1.tc,0);if(flipped(p,i0,i1,v0,d0)||flipped(p,i1,i0,v1,d1))continue;
    {V3 e=v1.p-v0.p;double l2=dot(e,e),t=l2>0?dot(p-v0.p,e)/l2:0;t=t<0?0:t>1?1:t;v0.uv[0]+=(v1.uv[0]-v0.uv[0])*t;v0.uv[1]+=(v1.uv[1]-v0.uv[1])*t;}
    v0.p=p;v0.q=v1.q+v0.q;int ts=R.size();updTris(i0,v0,d0,dc);updTris(i0,v1,d1,dc);int tc=R.size()-ts;
    if(tc<=v0.tc){if(tc)copy(R.begin()+ts,R.end(),R.begin()+v0.ts);}else v0.ts=ts;v0.tc=tc;break;}
   if((int)T.size()-dc<=target)break;}
  fprintf(stderr,"it %d tris %d\n",it,(int)T.size()-dc);}
 updMesh(1);
 // compact vertices
 vector<int> map(Vs.size(),-1);int nv=0;for(auto&t:T)for(int j=0;j<3;j++)if(map[t.v[j]]<0)map[t.v[j]]=nv++;
 FILE*o=fopen(argv[2],"wb");uint32_t on=nv,om=T.size();fwrite(&on,4,1,o);fwrite(&om,4,1,o);vector<int> inv(nv);for(size_t i=0;i<Vs.size();i++)if(map[i]>=0)inv[map[i]]=i;
 for(int k=0;k<nv;k++){Vert&v=Vs[inv[k]];double a[5]={v.p.x,v.p.y,v.p.z,v.uv[0],v.uv[1]};fwrite(a,8,5,o);}for(auto&t:T){uint32_t v[3]={(uint32_t)map[t.v[0]],(uint32_t)map[t.v[1]],(uint32_t)map[t.v[2]]};fwrite(v,4,3,o);}fclose(o);
 fprintf(stderr,"done %d verts %d tris\n",nv,(int)T.size());}

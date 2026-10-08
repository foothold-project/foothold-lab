import os,struct,sys
def atoms(p):
    out=[];f=open(p,'rb');size=os.path.getsize(p);pos=0
    while pos<size:
        f.seek(pos);h=f.read(16)
        if len(h)<8:break
        n,t=struct.unpack('>I4s',h[:8]);t=t.decode('latin1')
        if n==1:n=struct.unpack('>Q',h[8:16])[0]
        if n==0:n=size-pos
        out.append((t,pos,n));pos+=n
    return out,size
for p in sys.argv[1:]:
    a,s=atoms(p);order=[t for t,_,_ in a]
    fs='faststart' if 'moov' in order and 'mdat' in order and order.index('moov')<order.index('mdat') else 'MOOV-AT-END'
    print(f"{s/1e6:7.2f} MB  {fs:11s} {order}  {os.path.basename(p)}")

# Map PTZ direction codes with picture verification. Pulses are short; returns via opposite guess.
import glob, json, socket, struct, subprocess, sys, time
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
HOST="192.168.178.107"; PORT=16668
UP="/private/tmp/claude-501/-Users-davidbuezas-code-icsee-ptz/d3ef8c78-3387-49dd-a6a9-d5c199a754a0/scratchpad/uploads"
OUT="/private/tmp/claude-501/-Users-davidbuezas-code-icsee-ptz/d3ef8c78-3387-49dd-a6a9-d5c199a754a0/scratchpad/apps/carecam"
grp=json.load(open(glob.glob(f"{UP}/**/groupcfg.db",recursive=True)[0])); dev=json.load(open(glob.glob(f"{UP}/**/devcfg.db",recursive=True)[0]))
owner=grp["OwnerToken"]; k0=owner[:16].encode()
RTSP=f"rtsp://admin:admin123456@{HOST}:8554/profile0"
def pk(b): n=16-(len(b)%16) or 16; return b+bytes([n])*n
def up_(b): return b[:-b[-1]] if b and 1<=b[-1]<=16 else b
def enc(b,k,i): return Cipher(algorithms.AES(k),modes.CBC(i)).encryptor().update(pk(b))
def dec(b,k,i):
    try:
        d=up_(Cipher(algorithms.AES(k),modes.CBC(i)).decryptor().update(b)); return d
    except: return None
def rn(s,n):
    b=b""
    while len(b)<n:
        c=s.recv(n-len(b))
        if not c: break
        b+=c
    return b
def send(s,m,body,k,i,plain=False):
    j=json.dumps({"METHOD":m,"SEQID":str(int(time.time()*10)%100000),"BODY":body}).encode()
    p=j if plain else enc(j,k,i); et=0x30 if plain else 0x31
    s.sendall(b"\x23\x24"+bytes([int(m[:2],16),int(m[2:],16)])+struct.pack(">H",len(p))+bytes([et,0])+p)
def recv(s,k,i):
    h=rn(s,8)
    if len(h)<8: return None
    m=f"{h[2]:02X}{h[3]:02X}"; et=h[6]; bl=struct.unpack(">H",h[4:6])[0]; b=rn(s,bl)
    if et==0x31:
        d=dec(b,k,i) or dec(b,k0,k0)
        if d: b=d
    try: return (m,json.loads(b.decode(errors="replace")))
    except: return (m,b[:40].hex())
def snap(tag):
    subprocess.run(["ffmpeg","-y","-loglevel","error","-rtsp_transport","tcp","-timeout","8000000","-i",RTSP,"-frames:v","1","-vf","scale=480:-1",f"{OUT}/dir_{tag}.jpg"],capture_output=True,timeout=30)

s=socket.create_connection((HOST,PORT),timeout=6); s.settimeout(4)
send(s,"3114",{"UserToken":owner,"OsType":"1","SDKVersion":dev.get("SdkVersion","50663936"),"EncType":"49","EncKey":k0.decode(),"EncLoad":k0.decode()},k0,k0,plain=True)
_,r=recv(s,k0,k0); key=r["BODY"]["EncKey"].encode()[:16]; iv=r["BODY"]["EncLoad"].encode()[:16]
print("login",r.get("CODE"))
def move(d,secs=0.8):
    send(s,"3428",{"PTZType":"0","PTZControl":str(d),"Step":"8","Speed":"8"},key,iv); recv(s,key,iv)
    time.sleep(secs)
    send(s,"3428",{"PTZType":"0","PTZControl":"0","Step":"8","Speed":"8"},key,iv); recv(s,key,iv)
    time.sleep(1.2)
snap("00_base")
for d in (1,2,4):   # 3=left already known
    move(d); snap(f"{d}"); print("moved dir",d); move(0)  # extra stop
    # return: opposite pairing guess 1<->2, 4<->3
    back={1:2,2:1,4:3}[d]; move(back); time.sleep(0.5)
snap("99_end")
# probe accept-only for diagonal/extra codes
for d in (5,6,7,8,9,10):
    send(s,"3428",{"PTZType":"0","PTZControl":str(d),"Step":"8","Speed":"8"},key,iv)
    print("code",d,"->",recv(s,key,iv))
    time.sleep(0.15); send(s,"3428",{"PTZType":"0","PTZControl":"0"},key,iv); recv(s,key,iv); time.sleep(0.2)
s.close()

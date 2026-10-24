import numpy as np,glob,sys
f=glob.glob(sys.argv[1]+'/*_LORA868_*.cs8')[0]
ctr=868.85e6;fs=2e6;N=2048
d=np.memmap(f,dtype=np.int8,mode='r')
nf=d.size//(2*N); idx=np.arange(0,nf,5)
fb=np.fft.fftshift(np.fft.fftfreq(N,1/fs))+ctr
bands={'Meshtastic LongFast 869.525':(869.4e6,869.65e6),'LoRaWAN 868.1':(868.03e6,868.17e6),'LoRaWAN 868.3':(868.23e6,868.37e6),'LoRaWAN 868.5':(868.43e6,868.57e6),'867.9':(867.86e6,867.95e6)}
rows=[]
for i in idx:
    x=d[2*N*i:2*N*(i+1)].astype(np.float32); x=x[0::2]+1j*x[1::2]
    p=np.abs(np.fft.fftshift(np.fft.fft(x*np.hanning(N))))**2
    rows.append([p[(fb>a)&(fb<b)].mean() for a,b in bands.values()])
r=10*np.log10(np.array(rows)); dt=5*N/fs
for j,k in enumerate(bands):
    s=r[:,j]-np.median(r[:,j]); act=s>6
    edges=np.sum(np.diff(act.astype(int))==1)
    print('%-28s bursts %3d  time active %4.1f%%  peak +%.1f dB'%(k,edges,100*act.mean(),s.max()))
print('duration %.0f s'%(len(idx)*dt))

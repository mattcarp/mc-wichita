import numpy as np,glob,sys,re,os
fs=2e6;N=4096
for f in sorted(glob.glob(sys.argv[1]+'/*.cs8')):
    m=re.search(r'_([A-Za-z0-9.]+)_(\d+)Hz(?:_ctr(\d+))?',f)
    name,fr=m.group(1),int(m.group(2)); ctr=int(m.group(3) or fr)
    off=fr-ctr
    d=np.fromfile(f,dtype=np.int8,count=2*N*600)
    if d.size<2*N*10: continue
    x=(d[0::2]+1j*d[1::2]).astype(np.complex64)[:N*(d.size//(2*N))].reshape(-1,N)
    p=np.abs(np.fft.fftshift(np.fft.fft(x*np.hanning(N),axis=1),axes=1))**2
    fb=np.fft.fftshift(np.fft.fftfreq(N,1/fs))
    ch=np.abs(fb-off)<8e3; nz=(np.abs(fb-off)>30e3)&(np.abs(fb-off)<150e3)
    s=10*np.log10(p[:,ch].mean(1)); n=10*np.log10(np.median(p[:,nz]))
    snr=s-n
    print('%-8s %11.4f MHz  peak SNR %5.1f dB  median %4.1f dB  active %3d%%'%(name,fr/1e6,snr.max(),np.median(snr),100*(snr>6).mean()))

import csv,glob,sys,collections,statistics as st
for f in sorted(glob.glob(sys.argv[1]+'/sweep_*.csv')):
    acc=collections.defaultdict(list)
    for row in csv.reader(open(f)):
        try:
            lo=int(row[2]);w=float(row[4]);vals=[float(v) for v in row[6:]]
        except: continue
        for i,v in enumerate(vals): acc[round((lo+w*(i+0.5))/1e3)].append(v)
    if not acc: print(f,'empty');continue
    m={k:max(v) for k,v in acc.items()}
    floor=st.median(m.values())
    top=sorted(m.items(),key=lambda x:-x[1])[:8]
    print(f.split('/')[-1],'floor %.1f dB'%floor,' top:',', '.join('%.3f MHz +%.0f'%(k/1e3,v-floor) for k,v in top))

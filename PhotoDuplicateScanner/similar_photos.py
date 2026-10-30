"""Conservative visual candidates; never proof of identical files or pixels.

A disk-backed thumbnail cache and BK-tree avoid all-pairs image comparison.
Complete-link groups prevent a chain of weak matches joining unlike photos.
"""
from itertools import islice
import hashlib
import os
import stat
import zlib
from functools import lru_cache
import numpy as np
from PIL import Image, ImageOps
from photo_match import MAX_PIXELS

GRID=32
DCT=np.cos(np.pi*(np.arange(GRID)+.5)[None,:]*np.arange(8)[:,None]/GRID)


def features(path):
    fields=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
    before=os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or getattr(before,'st_file_attributes',0)&0x400:raise ValueError('Unsupported photo path')
    with open(path,'rb') as f:
        opened=os.fstat(f.fileno())
        if fields(opened)!=fields(before):raise ValueError('Photo changed')
        with Image.open(f) as im:
            if getattr(im,'n_frames',1)!=1 or im.width*im.height>MAX_PIXELS or im.mode not in ('RGB','RGBA','L','LA','P'):raise ValueError('Unsupported similar-photo format')
            with ImageOps.exif_transpose(im) as oriented:
                aspect=oriented.width/oriented.height
                with oriented.convert('RGBA') as rgba:
                    small=rgba.resize((16,16),Image.Resampling.LANCZOS)
                    thumb=np.asarray(small,dtype=np.uint8).copy();small.close()
                    reduced=rgba.resize((32,32),Image.Resampling.LANCZOS)
                    background=Image.new('RGBA',(32,32),'white');background.alpha_composite(reduced);reduced.close()
                    gray=background.convert('L');background.close()
                    a=np.asarray(gray.resize((32,32),Image.Resampling.LANCZOS),dtype=np.float64)
                    d=np.asarray(gray.resize((9,8),Image.Resampling.LANCZOS));gray.close()
        after=os.fstat(f.fileno())
    current=os.lstat(path)
    if fields(before)!=fields(current) or fields(opened)!=fields(after) or before.st_ctime_ns!=current.st_ctime_ns or opened.st_ctime_ns!=after.st_ctime_ns:raise ValueError('Photo changed during similarity check')
    if a.std()<6:raise ValueError('Low-detail photo: confirmed matching only')
    low=(DCT@a@DCT.T).ravel()[1:]
    bits=low>np.median(low)
    ph=sum(int(v)<<i for i,v in enumerate(bits))
    dh=sum(int(v)<<i for i,v in enumerate((d[:,1:]>d[:,:-1]).ravel()))
    return (f'{ph:016x}',f'{dh:016x}',zlib.compress(thumb.tobytes()),aspect),fields(current)


def similarity(a,b):
    if not a or not b or abs(a[3]/b[3]-1)>.01:return None
    ph=(int(a[0],16)^int(b[0],16)).bit_count()
    dh=(int(a[1],16)^int(b[1],16)).bit_count()
    if ph>6 or dh>8:return None
    left=np.frombuffer(zlib.decompress(a[2]),dtype=np.uint8).reshape(16,16,4).astype(np.float32)
    right=np.frombuffer(zlib.decompress(b[2]),dtype=np.uint8).reshape(16,16,4).astype(np.float32)
    if np.abs(left[:,:,3]-right[:,:,3]).mean()>2:return None
    diff=left[:,:,:3]-right[:,:,:3]
    shift=float(diff.mean())
    # Small exposure changes are reviewable, major colour/content edits are not.
    if abs(shift)>25:return None
    error=float(np.abs(diff-shift).mean())
    if error>12:return None
    return round(100*(1-max(ph/64,dh/64,error/255,abs(shift)/510)),1)


class BKTree:
    def __init__(self):self.root=None
    def add(self,value,key):
        node=self.root
        if node is None:self.root=[value,[key],{}];return
        while True:
            distance=(value^node[0]).bit_count()
            if distance==0:node[1].append(key);return
            if distance not in node[2]:node[2][distance]=[value,[key],{}];return
            node=node[2][distance]
    def find(self,value,radius=6):
        todo=[self.root] if self.root else []
        while todo:
            node=todo.pop();distance=(value^node[0]).bit_count()
            if distance<=radius:yield from reversed(node[1])
            todo.extend(child for edge,child in node[2].items() if distance-radius<=edge<=distance+radius)


def scan_similarity(c,stopped,update,now):
    total=c.execute("SELECT count(*) FROM photos WHERE active=1 AND media_type='photo' AND coalesce(sim_checked,0)=0").fetchone()[0]
    update(phase='similarity_hashing',phase_started=now(),hash_total=total,hash_done=0,hash_bytes=0,message='Checking similar photos')
    done=byte_count=0
    for row in c.execute("SELECT path,size,mtime_ns FROM photos WHERE active=1 AND media_type='photo' AND coalesce(sim_checked,0)=0 ORDER BY path"):
        if stopped():return
        try:
            value,fp=features(row['path'])
            if fp[2:]!=(row['size'],row['mtime_ns']):raise ValueError('Photo changed since indexing')
            c.execute('UPDATE photos SET sim_phash=?,sim_dhash=?,sim_thumb=?,sim_aspect=?,sim_checked=1 WHERE path=?',(*value,row['path']))
        except (OSError,ValueError,Image.DecompressionBombError):
            # Similarity is optional. Raw/pixel scan reports unreadable files.
            c.execute('UPDATE photos SET sim_checked=1 WHERE path=?',(row['path'],))
        done+=1;byte_count+=row['size']
        if done%10==0 or done==total:update(hash_done=done,hash_bytes=byte_count,current_path=row['path'],current_folder=os.path.dirname(row['path']))
    if stopped():return
    # One representative per confirmed family. Cache only a few decoded tiny
    # thumbnails, not original photos or every cached thumbnail in RAM.
    c.execute('CREATE TEMP TABLE sim_families AS SELECT match_key,min(path) path FROM photos WHERE active=1 AND media_type=\'photo\' AND match_key IS NOT NULL AND sim_phash IS NOT NULL GROUP BY match_key')
    total=c.execute('SELECT count(*) FROM sim_families').fetchone()[0]
    update(phase='similarity_grouping',phase_started=now(),hash_total=total,hash_done=0,hash_bytes=0,message='Grouping similar photos')
    @lru_cache(maxsize=256)
    def cached(path):
        r=c.execute('SELECT sim_phash,sim_dhash,sim_thumb,sim_aspect FROM photos WHERE path=?',(path,)).fetchone()
        return tuple(r)
    tree=BKTree();groups={};assigned={};members=[]
    # Full path order makes identical scans deterministic.
    for n,row in enumerate(c.execute('SELECT f.match_key,f.path,p.sim_phash FROM sim_families f JOIN photos p ON p.path=f.path ORDER BY f.path'),1):
        if stopped():return
        key,path,ph=row
        chosen=None
        candidates=set(assigned[p] for p in islice(tree.find(int(ph,16)),256))
        for group in sorted(candidates):
            if len(groups[group])<64 and all(similarity(cached(path),cached(p)) is not None for p in groups[group]):chosen=group;break
        if chosen is None:
            chosen=path;groups[chosen]=[];assigned[path]=chosen;tree.add(int(ph,16),path)
        groups[chosen].append(path)
        members.append((key,path,chosen))
        if n%100==0 or n==total:update(hash_done=n)
    # Save only non-singleton groups; rollback leaves the previous complete view.
    c.execute('SAVEPOINT replace_similarity')
    try:
        c.execute('DELETE FROM similarity_members')
        for key,path,group in members:
            if stopped():c.execute('ROLLBACK TO replace_similarity');return
            if len(groups[group])<2:continue
            score=min(similarity(cached(path),cached(p)) for p in groups[group] if p!=path)
            gid='similar:'+hashlib.sha256(group.encode('utf-8')).hexdigest()
            c.execute('INSERT INTO similarity_members SELECT path,?,? FROM photos WHERE active=1 AND media_type=\'photo\' AND match_key=?',(gid,score,key))
        c.execute('RELEASE replace_similarity');c.commit()
    finally:
        cached.cache_clear()

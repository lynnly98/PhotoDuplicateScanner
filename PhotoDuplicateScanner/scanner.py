"""Read-only, durable photo scanner. Worker runs independently of the desktop."""
import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from database import BASE, connect, init
from operation_lock import operation_lock
from photo_match import stable_image_digest, UnsupportedPhoto, refresh_match_keys
from video_match import stable_video_digest, UnsupportedVideo
from media_types import PHOTO_EXTS, VIDEO_EXTS, classify, types_for, type_sql, SCAN_MODES

EXTS = PHOTO_EXTS
CONTROL = BASE / 'data' / 'stop.request'
ROOTS_FILE = BASE / 'data' / 'roots.json'


def now(): return datetime.now().isoformat(timespec='seconds')


def update(c, **fields):
    c.execute('UPDATE scan_status SET '+', '.join(k+'=?' for k in fields)+' WHERE id=1', tuple(fields.values()))
    c.commit()


def error(c, run_id, path, exc):
    c.execute('INSERT INTO scan_errors(run_id,path,error) VALUES(?,?,?)', (run_id,str(path),str(exc)[:700]))
    c.execute('UPDATE scan_status SET errors=errors+1 WHERE id=1')


def stopped(): return CONTROL.exists()


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,'rb',buffering=1024*1024) as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            if stopped(): return None
            h.update(chunk)
    return h.hexdigest()


def enumerator(root,c,run,mode='photos'):
    extensions = (PHOTO_EXTS if mode=='photos' else VIDEO_EXTS if mode=='videos' else PHOTO_EXTS|VIDEO_EXTS)
    stack=[root]
    while stack:
        if stopped(): return
        folder=stack.pop()
        try:
            with os.scandir(folder) as iterator:
                for entry in iterator:
                    if stopped(): return
                    try:
                        if entry.is_dir(follow_symlinks=False): stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False) and Path(entry.name).suffix.lower() in extensions:
                            st=entry.stat(follow_symlinks=False)
                            yield entry.path,int(st.st_size),int(st.st_mtime_ns)
                    except OSError as ex: error(c,run,entry.path,ex)
        except OSError as ex: error(c,run,folder,ex)


def run_scan(mode='photos'):
    allowed = type_sql(mode)
    init()
    roots=json.loads(ROOTS_FILE.read_text(encoding='utf-8'))
    roots=[str(Path(x).resolve()) for x in roots]
    if not roots: raise ValueError('No folders configured')
    run=str(uuid.uuid4())
    c=connect()
    previous_total = c.execute('SELECT COUNT(*) FROM photos WHERE active=1 AND '+allowed).fetchone()[0]
    update(c,run_id=run,scan_mode=mode,phase='indexing',content_skipped=0,scanned=0,hashed=0,errors=0,started=now(),finished=None,
           phase_started=now(),index_estimate=previous_total,hash_total=0,hash_done=0,
           current_path=None,current_folder=None,index_bytes=0,hash_bytes=0,message='Indexing photos')
    count=0
    indexed_bytes=0
    try:
        # Scan each root and deactivate old records only when its enumeration completes.
        for root in roots:
            if stopped(): break
            if not Path(root).is_dir():
                error(c,run,root,'Folder not available. Previous records kept.'); c.commit(); continue
            completed=True
            errors_before=c.execute('SELECT errors FROM scan_status WHERE id=1').fetchone()[0]
            for path,size,mtime in enumerator(root,c,run,mode):
                if stopped(): completed=False; break
                # Metadata changes invalidate hash. Unchanged hashes are re-used.
                c.execute('''INSERT INTO photos(path,root,size,mtime_ns,sha256,last_seen,active,media_type)
                    VALUES(?,?,?,?,NULL,?,1,?)
                    ON CONFLICT(path) DO UPDATE SET
                      root=excluded.root, size=excluded.size,mtime_ns=excluded.mtime_ns,media_type=excluded.media_type,
                      sha256=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns
                                  THEN photos.sha256 ELSE NULL END,
                      image_sha256=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.image_sha256 ELSE NULL END,
                      image_checked=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.image_checked ELSE 0 END,
                      image_error=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.image_error ELSE NULL END,
                      video_sha256=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.video_sha256 ELSE NULL END,
                      video_checked=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.video_checked ELSE 0 END,
                      video_error=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.video_error ELSE NULL END,
                      sim_phash=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.sim_phash ELSE NULL END,
                      sim_dhash=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.sim_dhash ELSE NULL END,
                      sim_thumb=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.sim_thumb ELSE NULL END,
                      sim_aspect=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.sim_aspect ELSE NULL END,
                      sim_checked=CASE WHEN photos.size=excluded.size AND photos.mtime_ns=excluded.mtime_ns THEN photos.sim_checked ELSE 0 END,
                      match_key=NULL,
                      last_seen=excluded.last_seen,active=1''', (path,root,size,mtime,run,classify(path)))
                count+=1
                indexed_bytes+=size
                if count%300==0:
                    update(c,scanned=count,index_bytes=indexed_bytes,current_path=path,current_folder=str(Path(path).parent),message=f'Indexing {root}')
            if stopped(): completed=False
            if c.execute('SELECT errors FROM scan_status WHERE id=1').fetchone()[0] != errors_before:
                completed=False
            if completed:
                # Overlapping roots can otherwise invalidate still-valid files. Validate only paths belonging under this root.
                prefix=root.rstrip('\\/') + os.sep
                c.execute('UPDATE photos SET active=0 WHERE (path=? OR path LIKE ? ESCAPE "!") AND last_seen != ? AND '+allowed,
                          (root,prefix.replace('!','!!').replace('%','!%').replace('_','!_')+'%',run))
            c.commit()
        update(c,scanned=count,index_bytes=indexed_bytes)
        if stopped():
            update(c,phase='paused',finished=now(),message='Stopped safely. Restart scan to reuse cached hashes.'); return
        update(c,phase='hashing',phase_started=now(),message='Hashing same-size candidates')
        # Photos need a raw digest for safe pixel-match cleanup, including files
        # whose metadata changes their size. Videos retain same-size pruning.
        c.execute('CREATE TEMP TABLE hash_candidates(path TEXT PRIMARY KEY,size INTEGER,mtime_ns INTEGER)')
        c.execute('''INSERT INTO hash_candidates SELECT p.path,p.size,p.mtime_ns FROM photos p
           LEFT JOIN (SELECT media_type,size FROM photos WHERE active=1 AND '''+allowed+'''
                 GROUP BY media_type,size HAVING count(*)>1) d
           ON p.media_type=d.media_type AND p.size=d.size
           WHERE p.active=1 AND p.sha256 IS NULL AND '''+allowed.replace('media_type','p.media_type')+'''  ORDER BY p.size,p.path''')
        hash_total=c.execute('SELECT count(*) FROM hash_candidates').fetchone()[0]
        rows=c.execute('SELECT path,size,mtime_ns FROM hash_candidates ORDER BY size,path')
        hashed=0
        processed=0
        hash_bytes=0
        update(c,hash_total=hash_total,hash_done=0)
        for r in rows:
            if stopped(): break
            path=r['path']
            try:
                s=os.stat(path)
                if s.st_size != r['size'] or s.st_mtime_ns != r['mtime_ns']:
                    # Changed during scan; next run will refresh metadata and hash.
                    error(c,run,path,'Modified during scan; skipped')
                else:
                    digest=sha256_file(path)
                    after=os.stat(path)
                    if (after.st_size,after.st_mtime_ns,after.st_ino,after.st_ctime_ns) != (s.st_size,s.st_mtime_ns,s.st_ino,s.st_ctime_ns):
                        error(c,run,path,'Modified while hashing; skipped')
                        digest=None
                    if digest:
                        c.execute('UPDATE photos SET sha256=? WHERE path=? AND size=? AND mtime_ns=?',
                                  (digest,path,r['size'],r['mtime_ns']))
                        hashed+=1
                        hash_bytes+=int(r['size'])
            except OSError as ex: error(c,run,path,ex)
            processed+=1
            if processed%20==0 or processed==hash_total:
                update(c,hashed=hashed,hash_done=processed,hash_bytes=hash_bytes,current_path=path,current_folder=str(Path(path).parent))
        if mode in ('photos','both') and not stopped():
            image_total=c.execute("SELECT count(*) FROM photos WHERE active=1 AND media_type='photo' AND coalesce(image_checked,0)=0").fetchone()[0]
            update(c,phase='image_hashing',phase_started=now(),hash_total=image_total,hash_done=0,hash_bytes=0,message='Comparing photo pixels; metadata ignored')
            image_done=image_bytes=0
            image_rows=c.execute("SELECT path,size,mtime_ns,sha256 FROM photos WHERE active=1 AND media_type='photo' AND coalesce(image_checked,0)=0 ORDER BY path")
            for row in image_rows:
                if stopped():break
                try:
                    if not row['sha256']:
                        raise ValueError('Photo file hash is unavailable. Scan again.')
                    digest,fingerprint=stable_image_digest(row['path'],stopped)
                    if fingerprint[2:]!=(row['size'],row['mtime_ns']):raise ValueError('Photo changed since indexing.')
                    if digest is not None:
                        c.execute('UPDATE photos SET image_sha256=?,image_checked=1,image_error=NULL WHERE path=?',(digest,row['path']))
                except UnsupportedPhoto as exc:
                    c.execute('UPDATE photos SET image_checked=1,image_sha256=NULL,image_error=? WHERE path=?',(str(exc),row['path']))
                except Exception as exc:
                    error(c,run,row['path'],exc)
                    c.execute('UPDATE photos SET image_error=? WHERE path=?',(str(exc)[:700],row['path']))
                image_done+=1;image_bytes+=row['size']
                if image_done%10==0 or image_done==image_total:
                    update(c,hash_done=image_done,hash_bytes=image_bytes,current_path=row['path'],current_folder=str(Path(row['path']).parent))
            processed=image_done
            # hash_done describes the current/final stage, not raw hash count.
        if mode in ('videos','both') and not stopped():
            total=c.execute("SELECT count(*) FROM photos WHERE active=1 AND media_type='video' AND coalesce(video_checked,0)=0").fetchone()[0]
            update(c,phase='video_hashing',phase_started=now(),hash_total=total,hash_done=0,hash_bytes=0,message='Comparing complete video and audio content')
            done=byte_count=0
            for row in c.execute("SELECT path,size,mtime_ns,sha256 FROM photos WHERE active=1 AND media_type='video' AND coalesce(video_checked,0)=0 ORDER BY path"):
                if stopped():break
                update(c,current_path=row['path'],current_folder=str(Path(row['path']).parent))
                try:
                    if not row['sha256']:raise ValueError('File hash unavailable. Scan again.')
                    digest,meta=stable_video_digest(row['path'],stopped)
                    if meta[2:]!=(row['size'],row['mtime_ns']):raise ValueError('Video changed since indexing.')
                    if digest is not None:c.execute('UPDATE photos SET video_sha256=?,video_checked=1,video_error=NULL WHERE path=?',(digest,row['path']))
                except UnsupportedVideo as exc:
                    c.execute('UPDATE photos SET video_checked=1,video_sha256=NULL,video_error=? WHERE path=?',(str(exc),row['path']))
                except Exception as exc:
                    error(c,run,row['path'],exc)
                    c.execute('UPDATE photos SET video_error=? WHERE path=?',(str(exc)[:700],row['path']))
                done+=1;byte_count+=row['size']
                update(c,hash_done=done,hash_bytes=byte_count,current_path=row['path'],current_folder=str(Path(row['path']).parent))
            processed=done
        refresh_match_keys(c)
        if mode in ('photos','both') and not stopped():
            from similar_photos import scan_similarity
            scan_similarity(c,stopped,lambda **fields:update(c,**fields),now)
        limited=c.execute("SELECT count(*) FROM photos WHERE active=1 AND "+allowed+" AND ((media_type='photo' AND image_sha256 IS NULL) OR (media_type='video' AND video_sha256 IS NULL))").fetchone()[0]
        update(c,content_skipped=limited)
        errors=c.execute('SELECT errors FROM scan_status WHERE id=1').fetchone()[0]
        update(c,hashed=hashed,hash_done=processed,hash_bytes=hash_bytes,phase='paused' if stopped() else ('complete_with_errors' if errors else 'complete'),finished=now(),
               message='Stopped safely; rerun to finish.' if stopped() else 'Completed. Review duplicates.')
    except Exception as ex:
        update(c,phase='failed',finished=now(),message=str(ex)[:500]); raise
    finally:
        c.close()
        CONTROL.unlink(missing_ok=True)

def main():
    try:
        parser=argparse.ArgumentParser()
        parser.add_argument('--mode',choices=SCAN_MODES,default='photos')
        args=parser.parse_args()
        with operation_lock():
            run_scan(args.mode)
    except Exception as exc:
        print('Scanner error:',exc,file=sys.stderr); sys.exit(1)


if __name__=='__main__':
    main()

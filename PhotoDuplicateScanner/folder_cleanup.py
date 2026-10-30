"""Recycle result copies in a chosen tree only if an exact copy remains outside.

Disk-backed plans cover every result page. Internal-only duplicates are kept.
"""
import os
import time
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path
from database import connect, init
from operation_lock import operation_lock
from recycle import stable_digest, windows_recycle
from photo_match import match_column, stable_image_digest, verify_matching_content

REVIEW_PAGE_SIZE = 200


def _under(path, root):
    try:
        return os.path.commonpath([root,path]) == root
    except ValueError:  # Different drive letters are separate folder trees.
        return False


def inside(path, root):
    """Check actual resolved paths as well as lexical folder boundaries."""
    root = os.path.normcase(os.path.abspath(root))
    path = os.path.normcase(os.path.abspath(path))
    try:
        return (_under(path,root) and
                _under(os.path.normcase(str(Path(path).resolve(strict=True))),root))
    except (OSError, ValueError, RuntimeError):
        return False


def outside(path, root):
    root = os.path.normcase(os.path.abspath(root))
    path = os.path.normcase(os.path.abspath(path))
    try:
        return (not _under(path,root) and
                not _under(os.path.normcase(str(Path(path).resolve(strict=True))),root))
    except (OSError, ValueError, RuntimeError):
        return False


def info(job_id):
    with closing(connect()) as c:
        row = c.execute('SELECT * FROM folder_jobs WHERE id=?',(job_id,)).fetchone()
        if not row:
            raise ValueError('Folder cleanup plan no longer exists. Review the folder again.')
        return dict(row)


def preview(job_id, page=1):
    with closing(connect()) as c:
        return [dict(r) for r in c.execute('''SELECT path,size,keeper,state,message FROM folder_items
          WHERE job_id=? ORDER BY seq LIMIT ? OFFSET ?''',
          (job_id,REVIEW_PAGE_SIZE,(max(1,int(page))-1)*REVIEW_PAGE_SIZE))]


def plan_folder(folder,media_type='all',match_kind='auto'):
    if match_kind=='similar':raise ValueError('Similar photos require individual review and cannot use bulk folder cleanup.')
    column=match_column(match_kind,media_type)
    if media_type not in ('all','photo','video'):
        raise ValueError('Invalid media type')
    root = str(Path(folder).resolve(strict=True))
    if not Path(root).is_dir():
        raise ValueError('Add at least one available folder.')
    init()
    job_id = str(uuid.uuid4())
    with operation_lock(), closing(connect()) as c, c:
        state = c.execute('SELECT phase,run_id FROM scan_status WHERE id=1').fetchone()
        if state['phase'] not in ('complete','complete_with_errors'):
            raise ValueError('Finish a scan before recycling photos.')
        c.execute('INSERT INTO folder_jobs(id,root,created,scan_run_id,state,mode,media_type,match_kind) VALUES(?,?,?,?,?,?,?,?)',
                  (job_id,root,datetime.now().isoformat(),state['run_id'],'planning','cross_folder',media_type,match_kind))
        prefix = root.rstrip('\\/') + os.sep
        pattern = prefix.replace('!','!!').replace('%','!%').replace('_','!_') + '%'
        # All target copies qualify if their hash also occurs outside the tree.
        # Pick a fixed external keeper for review; rehash it before each recycle.
        scope="media_type IN ('photo','video')" if media_type=='all' else "media_type='"+media_type+"'"
        eligible=" AND image_sha256 IN (SELECT image_sha256 FROM photos WHERE active=1 AND media_type='photo' AND image_sha256 IS NOT NULL GROUP BY image_sha256 HAVING count(DISTINCT sha256)>1)" if match_kind=='pixels' else ''
        rows = c.execute(f'''SELECT path,size,mtime_ns,sha256,{column} match_digest FROM photos
          WHERE active=1 AND {scope} AND {column} IS NOT NULL AND sha256 IS NOT NULL AND path LIKE ? ESCAPE '!' {eligible}
          ORDER BY {column},path COLLATE NOCASE,path''',(pattern,))
        previous = None
        keeper = None
        total = byte_count = 0
        for row in rows:
            if row['match_digest'] != previous:
                previous = row['match_digest']
                match = c.execute(f'''SELECT path FROM photos WHERE active=1 AND {scope} AND {column}=?
                  AND path NOT LIKE ? ESCAPE '!' ORDER BY path COLLATE NOCASE,path LIMIT 1''',
                  (previous,pattern)).fetchone()
                keeper = match['path'] if match else None
            if keeper is None:
                continue
            total += 1
            byte_count += row['size']
            c.execute('''INSERT INTO folder_items(job_id,seq,path,size,mtime_ns,sha256,keeper,match_digest)
              VALUES(?,?,?,?,?,?,?,?)''',
              (job_id,total,row['path'],row['size'],row['mtime_ns'],row['sha256'],keeper,row['match_digest']))
        c.execute("UPDATE folder_jobs SET state='planned',total=?,bytes=? WHERE id=?",
                  (total,byte_count,job_id))
    return info(job_id)


def _verify_item(c, row, root,media_type,match_kind='exact'):
    column=match_column(match_kind,media_type)
    match_digest=row['match_digest'] or row['sha256']
    if row['path'].casefold() == row['keeper'].casefold():
        raise ValueError('Keep at least one unselected copy in every group.')
    if not inside(row['path'],root) or not outside(row['keeper'],root):
        raise ValueError('No verified copy outside the chosen folder. This photo was kept.')
    current = c.execute('SELECT size,mtime_ns,sha256,image_sha256,video_sha256,match_key,active,media_type FROM photos WHERE path=?',
                        (row['path'],)).fetchone()
    retained = c.execute('SELECT sha256,image_sha256,video_sha256,match_key,active,media_type FROM photos WHERE path=?',(row['keeper'],)).fetchone()
    if (not current or not current['active'] or (media_type!='all' and current['media_type']!=media_type) or
        (current['size'],current['mtime_ns'],current['sha256']) != (row['size'],row['mtime_ns'],row['sha256']) or
        not retained or not retained['active'] or retained['media_type']!=current['media_type'] or retained[column] != match_digest or current[column] != match_digest):
        raise ValueError('Scan records changed after confirmation. Review the selection again.')
    digest, fingerprint = stable_digest(row['path'])
    keeper_digest, keeper_fingerprint = stable_digest(row['keeper'])
    if (digest != row['sha256'] or keeper_digest != retained['sha256'] or
        fingerprint[2:] != (row['size'],row['mtime_ns'])):
        raise ValueError('Selected photo changed since scanning. Scan again.')
    if match_kind=='auto':
        verify_matching_content(row['path'],row['keeper'],digest,keeper_digest,match_digest,fingerprint,keeper_fingerprint)
    if match_kind=='pixels':
        target_image,target_meta=stable_image_digest(row['path'])
        keeper_image,keeper_meta=stable_image_digest(row['keeper'])
        if target_image!=match_digest or keeper_image!=match_digest or target_meta!=fingerprint or keeper_meta!=keeper_fingerprint:
            raise ValueError('Photo pixels changed since scanning. Scan again.')
    if fingerprint[:2] == keeper_fingerprint[:2]:
        raise ValueError('The retained file is a hard link to this copy. Both were kept.')
    for name, expected, scope_check in ((row['path'],fingerprint,inside),(row['keeper'],keeper_fingerprint,outside)):
        meta = os.lstat(name)
        if (meta.st_dev,meta.st_ino,meta.st_size,meta.st_mtime_ns) != expected or not scope_check(name,root):
            raise ValueError('A verified photo changed. This photo was kept.')


def execute(job_id, backend=None, progress=None, cancel=None):
    """Run once after confirmation, in batches of 100 metadata rows, not photos."""
    backend = backend or windows_recycle
    with operation_lock(), closing(connect()) as c:
        job = c.execute('SELECT * FROM folder_jobs WHERE id=?',(job_id,)).fetchone()
        if not job or job['state'] != 'planned':
            raise ValueError('This cleanup cannot be run again. Scan and review the folder again.')
        if job['mode'] != 'cross_folder':
            raise ValueError('Old folder-cleanup plans must be reviewed again in this version.')
        scan = c.execute('SELECT phase,run_id FROM scan_status WHERE id=1').fetchone()
        if scan['phase'] not in ('complete','complete_with_errors') or scan['run_id'] != job['scan_run_id']:
            raise ValueError('Scan records changed after confirmation. Review the selection again.')
        c.execute("UPDATE folder_jobs SET state='running' WHERE id=?",(job_id,))
        c.commit()
        done = ok = failed = last_seq = 0
        last_progress = 0
        if progress:
            progress(0,job['total'],0,0)
        try:
            while not (cancel and cancel.is_set()):
                rows = c.execute('''SELECT * FROM folder_items WHERE job_id=? AND seq>?
                  ORDER BY seq LIMIT 100''',(job_id,last_seq)).fetchall()
                if not rows:
                    break
                for row in rows:
                    if cancel and cancel.is_set():
                        break
                    last_seq = row['seq']
                    token = str(uuid.uuid4())
                    message = ''
                    recycled = False
                    c.execute('INSERT INTO recycle_log(id,created,path,sha256,state,message,match_kind) VALUES(?,?,?,?,?,?,?)',
                        (token,datetime.now().isoformat(),row['path'],row['sha256'],'verifying','Folder cleanup: '+job['root'],job['match_kind']))
                    c.commit()
                    try:
                        _verify_item(c,row,job['root'],job['media_type'],job['match_kind'])
                        c.execute("UPDATE recycle_log SET state='requested',message=? WHERE id=?",
                                  ('Verified retained copy: '+row['keeper'],token))
                        c.execute("UPDATE folder_items SET state='requested' WHERE job_id=? AND seq=?",
                                  (job_id,row['seq']))
                        c.commit()
                        backend(row['path'])
                        c.execute('UPDATE photos SET active=0 WHERE path=?',(row['path'],))
                        recycled = True
                    except Exception as exc:
                        message = str(exc)[:1000]
                    item_state = 'recycled' if recycled else 'needs_review'
                    c.execute('UPDATE recycle_log SET state=?,message=? WHERE id=?',
                        (item_state,('Verified retained copy: '+row['keeper']) if recycled else message,token))
                    c.execute('UPDATE folder_items SET state=?,message=? WHERE job_id=? AND seq=?',
                              (item_state,message,job_id,row['seq']))
                    done += 1
                    ok += int(recycled)
                    failed += int(not recycled)
                    c.execute('UPDATE folder_jobs SET done=?,recycled=?,failed=? WHERE id=?',(done,ok,failed,job_id))
                    c.commit()
                    if progress and (time.monotonic()-last_progress>=0.25 or done==job['total']):
                        progress(done,job['total'],ok,failed)
                        last_progress = time.monotonic()
            state = 'cancelled' if cancel and cancel.is_set() and done<job['total'] else 'complete'
            c.execute('UPDATE folder_jobs SET state=? WHERE id=?',(state,job_id))
            c.commit()
        except BaseException:
            c.execute("UPDATE folder_jobs SET state='interrupted' WHERE id=?",(job_id,))
            c.commit()
            raise
        if progress:
            progress(done,job['total'],ok,failed)
    return info(job_id)

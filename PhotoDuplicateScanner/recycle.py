"""Explicitly selected exact copies only. No permanent-delete fallback."""
import hashlib
import os
import stat
import uuid
from datetime import datetime
from pathlib import Path
from database import connect
from operation_lock import operation_lock
from photo_match import match_column, stable_image_digest, verify_matching_content


def stable_digest(path):
    before = os.lstat(path)
    if not stat.S_ISREG(before.st_mode) or getattr(before, 'st_file_attributes', 0) & 0x400:
        raise ValueError('Links and reparse points cannot be recycled by this app.')
    digest = hashlib.sha256()
    with open(path, 'rb') as source:
        opened = os.fstat(source.fileno())
        if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError('File changed before verification.')
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
        after = os.fstat(source.fileno())
    current = os.lstat(path)
    fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if fields(before) != fields(after) or fields(after) != fields(current):
        raise ValueError('File changed during verification. Scan again.')
    return digest.hexdigest(), fields(current)


def windows_recycle(path):
    if os.name != 'nt':
        raise RuntimeError('Recycle operation requires Windows 11.')
    import pythoncom
    from win32com.shell import shell, shellcon
    pythoncom.CoInitialize()
    try:
        operation = pythoncom.CoCreateInstance(
            shell.CLSID_FileOperation, None, pythoncom.CLSCTX_INPROC_SERVER,
            shell.IID_IFileOperation)
        # RECYCLEONDELETE: recycle instead of permanently delete. Never use
        # legacy SHFileOperation / ALLOWUNDO or a filesystem deletion fallback.
        flags = (shellcon.FOF_NOCONFIRMATION | shellcon.FOF_NOERRORUI |
                 shellcon.FOF_SILENT | 0x00080000 | 0x00100000 | 0x20000000)
        operation.SetOperationFlags(flags)
        item = shell.SHCreateItemFromParsingName(str(Path(path).absolute()), None, shell.IID_IShellItem)
        operation.DeleteItem(item, None)
        result = operation.PerformOperations()
        if result or operation.GetAnyOperationsAborted() or os.path.lexists(path):
            raise OSError('Windows did not recycle this file. It may not support the Recycle Bin.')
    finally:
        pythoncom.CoUninitialize()


def prepare(paths, match_kinds=None):
    """Freeze selected records for a reviewable confirmation screen."""
    match_kinds=match_kinds or {}
    c = connect()
    try:
        result = []
        for path in dict.fromkeys(paths):
            row = c.execute('SELECT path,size,mtime_ns,sha256,media_type,image_sha256,video_sha256,match_key,review_key,similarity_score FROM review_photos WHERE path=? AND active=1', (path,)).fetchone()
            if not row or not row['sha256']:
                raise ValueError('Selection is no longer valid. Refresh the scan results.')
            item=dict(row)
            item['match_kind']=match_kinds.get(path,'auto')
            column=match_column(item['match_kind'],item['media_type'])
            if not item[column]:raise ValueError('Selection is no longer valid. Scan again.')
            result.append(item)
        selected = {r['path'].casefold() for r in result}
        for kind,mode,digest in {(r['media_type'],r['match_kind'],r[match_column(r['match_kind'],r['media_type'])]) for r in result}:
            column=match_column(mode,kind)
            members = c.execute(f'SELECT path FROM review_photos WHERE active=1 AND media_type=? AND {column}=?', (kind,digest))
            if not any(r['path'].casefold() not in selected for r in members):
                raise ValueError('Keep at least one unselected copy in every group.')
        for item in result:
            if item['match_kind']=='similar':
                keeper=c.execute('SELECT path,sha256 FROM review_photos WHERE active=1 AND review_key=? ORDER BY path',(item['review_key'],))
                keeper=next((r for r in keeper if r['path'].casefold() not in selected),None)
                if keeper is None:raise ValueError('Keep one unselected photo in the similar group.')
                item['keeper_path']=keeper['path'];item['keeper_sha256']=keeper['sha256']
        return result
    finally:
        c.close()


def recycle_selected(manifest, backend=None):
    """Recheck content and retained copies; journal each independent result."""
    if not manifest:
        raise ValueError('No photos selected.')
    if len(manifest) > 100:
        raise ValueError('Maximum 100 photos per operation.')
    backend = backend or windows_recycle
    with operation_lock():
        fresh = prepare([r['path'] for r in manifest],{r['path']:r.get('match_kind','exact') for r in manifest})
        if fresh != manifest:
            raise ValueError('Scan records changed after confirmation. Review the selection again.')
        c = connect()
        results = []
        selected = {r['path'].casefold() for r in manifest}
        try:
            phase = c.execute('SELECT phase FROM scan_status WHERE id=1').fetchone()[0]
            if phase not in ('complete', 'complete_with_errors'):
                raise ValueError('Finish a scan before recycling photos.')
            for row in manifest:
                path = row['path']
                token = str(uuid.uuid4())
                c.execute('INSERT INTO recycle_log(id,created,path,sha256,state,message,match_kind) VALUES(?,?,?,?,?,?,?)',
                          (token, datetime.now().isoformat(), path, row['sha256'], 'verifying', '',row['match_kind']))
                c.commit()
                try:
                    digest, fingerprint = stable_digest(path)
                    if digest != row['sha256'] or fingerprint[2:4] != (row['size'], row['mtime_ns']):
                        raise ValueError('Selected photo changed since scanning. Scan again.')
                    column=match_column(row['match_kind'],row['media_type'])
                    match_digest=row[column]
                    if row['match_kind']=='pixels':
                        pixels,image_fingerprint=stable_image_digest(path)
                        if pixels!=match_digest or image_fingerprint!=fingerprint:raise ValueError('Photo pixels changed since scanning. Scan again.')
                    keeper = None
                    members = c.execute(f'SELECT path,sha256 FROM review_photos WHERE active=1 AND media_type=? AND {column}=? ORDER BY path', (row['media_type'],match_digest))
                    for member in members:
                        if row['match_kind']=='similar' and member['path']!=row['keeper_path']:continue
                        if member['path'].casefold() in selected:
                            continue
                        try:
                            other_digest, other_fingerprint = stable_digest(member['path'])
                            valid=other_digest==member['sha256']
                            if row['match_kind']=='pixels':
                                pixels,image_fingerprint=stable_image_digest(member['path'])
                                valid=valid and pixels==match_digest and image_fingerprint==other_fingerprint
                            elif row['match_kind']=='similar':
                                from similar_photos import features,similarity
                                left,left_fp=features(path);right,right_fp=features(member['path'])
                                valid=valid and other_digest==row['keeper_sha256'] and left_fp==fingerprint and right_fp==other_fingerprint and similarity(left,right) is not None
                            elif row['match_kind']=='auto':
                                verify_matching_content(path,member['path'],digest,other_digest,match_digest,fingerprint,other_fingerprint)
                            else:valid=valid and other_digest==digest
                            if valid and other_fingerprint[:2] != fingerprint[:2]:
                                keeper = (member['path'], other_fingerprint)
                                break
                        except (OSError, ValueError):
                            continue
                    if keeper is None:
                        raise ValueError('No accessible, verified unselected copy. This photo was kept.')
                    # Recheck both names just before invoking Windows. Users must
                    # not concurrently edit/move photos during this operation.
                    for name, expected in [(path, fingerprint), keeper]:
                        s = os.lstat(name)
                        if (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns) != expected:
                            raise ValueError('A verified photo changed. This photo was kept.')
                    c.execute('UPDATE recycle_log SET state=?,message=? WHERE id=?', ('requested', 'Verified retained copy: ' + keeper[0], token))
                    c.commit()
                    backend(path)
                    c.execute('UPDATE photos SET active=0 WHERE path=?', (path,))
                    c.execute('UPDATE recycle_log SET state=? WHERE id=?', ('recycled', token))
                    c.commit()
                    results.append({'path':path, 'result':'Recycled', 'message':'Restore using Windows Recycle Bin.'})
                except Exception as exc:
                    c.execute('UPDATE recycle_log SET state=?,message=? WHERE id=?', ('needs_review', str(exc)[:1000], token))
                    c.commit()
                    results.append({'path':path, 'result':'Not confirmed', 'message':str(exc)})
            return results
        finally:
            c.close()

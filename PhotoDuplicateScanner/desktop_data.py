"""Bounded, connection-per-job queries for the native desktop UI."""
import json
import os
from contextlib import closing
from pathlib import Path
from database import DATA, connect
from scanner import ROOTS_FILE
from operation_lock import operation_lock
from photo_match import match_column

PAGE_SIZES = (6, 12, 24)
GROUPS_PER_PAGE = 12
COPIES_PER_PAGE = 12


def read_settings():
    try:
        result = json.loads((DATA / 'desktop_settings.json').read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(language=None, thumbnail_size=None, groups_per_page=None, scan_mode=None, result_type=None, theme=None, match_kind=None):
    value = read_settings()
    if match_kind is not None:
        match_column(match_kind)
        value['match_kind']=match_kind
    if theme is not None:
        if theme not in ('light','dark'): raise ValueError('Invalid theme')
        value['theme'] = theme
    if scan_mode is not None:
        from media_types import types_for
        types_for(scan_mode)
        value['scan_mode']=scan_mode
    if result_type is not None:
        if result_type not in ('all','photo','video'):
            raise ValueError('Invalid media type')
        value['result_type']=result_type
    if language is not None:
        value['language'] = language if language in ('en', 'zh') else 'en'
    if thumbnail_size is not None:
        if thumbnail_size not in ('small', 'medium', 'large'):
            raise ValueError('Invalid thumbnail size')
        value['thumbnail_size'] = thumbnail_size
    if groups_per_page is not None:
        if groups_per_page not in PAGE_SIZES:
            raise ValueError('Invalid page size')
        value['groups_per_page'] = groups_per_page
    atomic_json(DATA / 'desktop_settings.json', value)


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def read_roots():
    try:
        roots = json.loads(ROOTS_FILE.read_text(encoding='utf-8'))
        return [r for r in roots if isinstance(r, str)] if isinstance(roots, list) else []
    except (OSError, ValueError):
        return []


def normalized_roots(roots):
    # A selected parent already includes its descendants. Avoid double counting.
    result = []
    for raw in sorted({str(Path(r).resolve()) for r in roots}, key=len):
        key = os.path.normcase(raw).rstrip('\\/') + os.sep
        if not any(key.startswith(os.path.normcase(r).rstrip('\\/') + os.sep) for r in result):
            result.append(raw)
    return result


def operation_busy():
    try:
        with operation_lock():
            return False
    except RuntimeError:
        return True


def status():
    with closing(connect()) as c:
        return dict(c.execute('SELECT * FROM scan_status WHERE id=1').fetchone())


def result_filter(media_type):
    if media_type=='all':return "media_type IN ('photo','video')",()
    if media_type not in ('photo','video'):raise ValueError('Invalid media type')
    return 'media_type=?',(media_type,)


def library(page, sort, member_pages, groups_per_page=GROUPS_PER_PAGE, media_type='all', match_kind='auto'):
    if groups_per_page not in PAGE_SIZES:raise ValueError('Invalid page size')
    column='review_key' if match_kind=='auto' and media_type in ('photo','all') else match_column(match_kind,media_type)
    condition,parameters=result_filter(media_type)
    where=f'active=1 AND {condition} AND {column} IS NOT NULL'
    having='count(*)>1'
    with closing(connect()) as c:
        c.execute('BEGIN')
        grouped=f'SELECT {column} digest,count(*) n,sum(size)-max(size) extra FROM review_photos WHERE {where} GROUP BY {column} HAVING '+having
        summary=c.execute('SELECT count(*),coalesce(sum(n-1),0),coalesce(sum(extra),0) FROM ('+grouped+')',parameters).fetchone()
        total=c.execute('SELECT count(*) FROM review_photos WHERE active=1 AND '+condition,parameters).fetchone()[0]
        pages=max(1,(summary[0]+groups_per_page-1)//groups_per_page)
        page=max(1,min(page,pages))
        order='min(path) COLLATE NOCASE,'+column if sort=='name' else 'sum(size)-max(size) DESC,'+column
        groups=[]
        query=f'SELECT {column} sha256,media_type,max(is_similar) is_similar,min(similarity_score) similarity_score,count(*) n,max(size) size,sum(size)-max(size) extra_bytes FROM review_photos WHERE {where} GROUP BY {column} HAVING '+having+' ORDER BY '+order+' LIMIT ? OFFSET ?'
        for row in c.execute(query,parameters+(groups_per_page,(page-1)*groups_per_page)):
            group=dict(row)
            mp=max(1,min(member_pages.get(row['sha256'],1),(row['n']+COPIES_PER_PAGE-1)//COPIES_PER_PAGE))
            group['member_page']=mp
            group['photos']=[dict(r,match_kind='similar' if group.get('is_similar') else match_kind) for r in c.execute(f'SELECT path,size,mtime_ns,sha256,image_sha256,video_sha256,match_key,review_key,similarity_score,root,media_type FROM review_photos WHERE active=1 AND media_type=? AND {column}=? ORDER BY path LIMIT ? OFFSET ?',(row['media_type'],row['sha256'],COPIES_PER_PAGE,(mp-1)*COPIES_PER_PAGE))]
            groups.append(group)
        return dict(groups=groups,count=summary[0],extras=summary[1],bytes=summary[2],total=total,page=page,pages=pages,groups_per_page=groups_per_page,media_type=media_type,match_kind=match_kind)


def history():
    with closing(connect()) as c:
        return {'latest_scan':dict(c.execute('SELECT * FROM scan_status WHERE id=1').fetchone()),'recycle':[dict(r) for r in c.execute('SELECT created,path,state,message,match_kind FROM recycle_log ORDER BY created DESC LIMIT 100')],
                'errors':[dict(r) for r in c.execute('SELECT run_id,path,error FROM scan_errors ORDER BY id DESC LIMIT 100')],
                'folders':[dict(r) for r in c.execute('SELECT * FROM folder_jobs ORDER BY created DESC LIMIT 20')]}


def active_paths(paths):
    if not paths:
        return set()
    with closing(connect()) as c:
        return {r[0] for r in c.execute('SELECT path FROM photos WHERE active=1 AND path IN ('+
                ','.join('?' for _ in paths)+')',list(paths))}


def result_folders(media_type='all',match_kind='auto'):
    column=match_column(match_kind,media_type)
    condition,parameters=result_filter(media_type)
    with closing(connect()) as c:
        return [dict(r) for r in c.execute(f'SELECT p.root,count(*) n FROM photos p JOIN (SELECT {column} digest FROM photos WHERE active=1 AND {column} IS NOT NULL AND '+condition+f' GROUP BY {column} HAVING count(*)>1) d ON d.digest=p.{column} WHERE p.active=1 AND '+condition.replace('media_type','p.media_type')+' GROUP BY p.root ORDER BY p.root COLLATE NOCASE,p.root',parameters+parameters)]

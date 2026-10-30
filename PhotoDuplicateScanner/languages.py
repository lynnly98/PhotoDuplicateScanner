"""All desktop copy in English and Simplified Chinese. English is the default."""
COPY = {
    'title': ('Photo Duplicate Scanner', '照片与视频重复清理'),
    'heading': ('Duplicate photos & videos', '重复照片与视频'),
    'subtitle': ('Compare files. Keep your favourites. Recycle extra copies.', '比较文件，保留喜欢的，清理多余副本。'),
    'scan_type': ('Scan type', '扫描类型'),
    'scan_photos': ('Photos only', '仅照片'),
    'scan_videos': ('Videos only', '仅视频'),
    'scan_both': ('Photos + Videos', '照片 + 视频'),
    'photos_tab': ('Photos', '照片'),
    'videos_tab': ('Videos', '视频'),
    'duration': ('Duration', '时长'),
    'play_video': ('Play video', '播放视频'),
    'no_player': ('Unable to open the video. Check your default video player.', '无法打开视频，请检查默认视频播放器。'),
    'folder_media': ('Cleanup scope: {kind} only', '清理范围：仅{kind}'),
    'locations': ('Scan locations', '扫描位置'),
    'add': ('+ Add folder', '+ 添加文件夹'),
    'remove': ('Remove selected folder', '移除选中的文件夹'),
    'subfolders': ('All subfolders are included', '包含所有子文件夹'),
    'start': ('Start / resume scan', '开始 / 继续扫描'),
    'stop': ('Stop safely', '安全停止'),
    'export': ('Export Excel', '导出 Excel'),
    'history': ('History & errors', '操作记录与错误'),
    'refresh': ('Refresh results', '刷新结果'),
    'exact': ('Exact duplicates', '完全重复'),
    'similar': ('Similar media · not supported', '相似照片／视频 · 暂不支持'),
    'largest': ('Largest savings first', '按占用空间排序'),
    'thumbnail_size': ('Thumbnail size', '缩略图大小'),
    'small': ('Small', '小'),
    'medium': ('Medium', '中'),
    'large': ('Large', '大'),
    'per_page': ('Groups per page', '每页重复组'),
    'name': ('Folder / path', '按文件路径排序'),
    'details': ('File details', '文件详情'),
    'choose': ('Click a file to see its details', '点击文件查看详情'),
    'path': ('Full path', '完整路径'),
    'size': ('File size', '文件大小'),
    'dimensions': ('Dimensions', '尺寸'),
    'taken': ('Date taken', '拍摄时间'),
    'match': ('Match type', '匹配方式'),
    'sha': ('SHA-256 · identical file contents', 'SHA-256 · 文件内容完全一致'),
    'keep_rule': ('At least one verified copy is kept per group.', '每组至少保留一份已验证的副本。'),
    'open_folder': ('Open containing folder', '打开所在文件夹'),
    'select': ('Select to recycle', '选择删除'),
    'selected_badge': ('Selected', '已选择'),
    'unselected': ('Not selected', '未选择'),
    'selected': ('{n} selected · {size}', '已选择 {n} 个 · {size}'),
    'clear': ('Clear selection', '清空选择'),
    'recycle': ('Move to Recycle Bin', '移到回收站'),
    'recycle_hint': ('Review and confirm first. No permanent-delete fallback.', '先核对清单并确认，不会改为永久删除。'),
    'scope': ('Results include active records from all previous scans. Check full paths.', '结果包括历史扫描中的有效记录，请核对完整路径。'),
    'group': ('Group {n} · {copies} copies · {size} extra', '第 {n} 组 · {copies} 个副本 · 多余副本 {size}'),
    'members': ('Copies {a}–{b} of {n}', '第 {a}–{b} 个，共 {n} 个'),
    'page': ('Page {n} / {total}', '第 {n} / {total} 页'),
    'previous': ('Previous', '上一页'),
    'next': ('Next', '下一页'),
    'empty': ('No confirmed duplicates in this tab. Add folders and scan the selected type.', '此分类暂无已确认的重复文件，请添加文件夹并选择类型扫描。'),
    'loading': ('Loading…', '正在加载…'),
    'unavailable': ('Preview unavailable', '无法预览'),
    'indexed': ('{n:,} files indexed in this tab', '此分类已索引 {n:,} 个文件'),
    'groups': ('{n:,} duplicate groups', '发现 {n:,} 组重复文件'),
    'status_idle': ('Ready to scan', '准备扫描'),
    'status_indexing': ('Finding files…', '正在查找文件…'),
    'status_hashing': ('Checking file contents…', '正在校验文件内容…'),
    'status_complete': ('Scan complete', '扫描完成'),
    'status_complete_with_errors': ('Completed with errors · check details', '扫描完成但有错误，请查看记录'),
    'status_paused': ('Scan paused', '扫描已暂停'),
    'status_failed': ('Scan failed · check details', '扫描失败，请查看记录'),
    'interrupted': ('Worker stopped. Resume to recover.', '扫描进程已停止，请继续扫描以恢复。'),
    'progress': ('Found {n:,} · checked {done:,}/{total:,} · errors {errors:,}', '发现 {n:,} 个 · 已校验 {done:,}/{total:,} · 错误 {errors:,}'),
    'timing': ('Elapsed {elapsed} · ETA {eta}', '已用时 {elapsed} · 预计剩余 {eta}'),
    'finish': ('Estimated finish {value}', '预计完成时间 {value}'),
    'rates': ('{photos:.1f} files/s · {mb:.2f} MB/s', '{photos:.1f} 个/秒 · {mb:.2f} MB/秒'),
    'unknown': ('Unknown', '未知'),
    'eta_note': ('ETA covers hashing only. Indexing MB/s counts sizes found, not bytes read.', '剩余时间仅估算哈希阶段；索引 MB/秒是发现的文件大小，并非实际读取速度。'),
    'error': ('Unable to complete', '无法完成操作'),
    'raw_error': ('System / diagnostic details:', '系统 / 诊断详情（原始信息）：'),
    'no_folders': ('Add at least one available folder.', '请至少添加一个可用文件夹。'),
    'missing_folders': ('These folders are unavailable:\n{paths}', '以下文件夹无法访问：\n{paths}'),
    'limit': ('Select at most 100 files per operation.', '每次最多选择 100 个文件。'),
    'all_selected': ('Keep at least one unselected copy in every group.', '每组至少保留一份未选择的副本。'),
    'busy': ('A scan or file operation is running. Please wait.', '正在扫描或处理文件，请稍候。'),
    'review': ('Review selected copies', '检查删除清单'),
    'review_note': ('Only the paths below will be recycled. Each retained copy is verified again before recycling. Do not edit or move these files in another app during this operation.', '只处理下列路径。删除前会重新验证保留副本。操作期间请勿在其他软件编辑或移动这些文件。'),
    'confirm_check': ('I reviewed these paths and want to recycle these copies.', '我已核对以上路径，并确认将这些副本移到回收站。'),
    'confirm': ('Confirm recycle', '确认移到回收站'),
    'cancel': ('Cancel', '取消'),
    'ok': ('OK', '确定'),
    'close': ('Close', '关闭'),
    'yes': ('Yes', '是'),
    'no': ('No', '否'),
    'working': ('Verifying copies and recycling… Please keep this window open.', '正在验证副本并移到回收站，请保持此窗口打开。'),
    'exporting': ('Preparing Excel report…', '正在生成 Excel 报告…'),
    'export_done': ('Excel report saved:\n{path}', 'Excel 报告已保存：\n{path}'),
    'results': ('Recycle results', '删除结果'),
    'result_summary': ('Recycled {ok} · not confirmed {failed}', '已移到回收站 {ok} 个 · 未确认 {failed} 个'),
    'recycled': ('Recycled', '已移到回收站'),
    'not_confirmed': ('Not confirmed', '未确认'),
    'restore_note': ('Restore using Windows Recycle Bin, then rescan. Space is freed only after you empty the bin. Unsupported drives are refused; no permanent deletion.', '可从 Windows 回收站恢复，恢复后请重新扫描。清空回收站后才释放空间。不支持回收站的设备会被拒绝，不会永久删除。'),
    'result': ('Result', '结果'),
    'message': ('Message', '说明'),
    'created': ('Time', '时间'),
    'run_id': ('Run ID', '扫描编号'),
    'state': ('State', '状态'),
    'errors_tab': ('Scan errors', '扫描错误'),
    'recycle_tab': ('Recycle history', '删除记录'),
    'history_note': ('Latest 100 records. Requested / needs review can mean an interrupted operation; check both the original path and Recycle Bin before retrying.', '显示最近 100 条。已请求 / 待检查可能代表操作中断；重试前请检查原路径和回收站。'),
    'verifying': ('Verifying', '正在验证'),
    'requested': ('Requested', '已请求'),
    'needs_review': ('Needs review', '待检查'),
    'closing': ('Scan continues in the background if you close this window. Close now?', '关闭窗口后扫描仍会在后台继续。现在关闭吗？'),
    'no_restart': ('Selection changed or scan data changed. Refresh and review again.', '选择或扫描资料已改变，请刷新并重新检查清单。'),
    'unavailable_keeper': ('No accessible, verified retained copy. This photo was kept.', '找不到可访问且已验证的保留副本，未删除此文件。'),
    'changed': ('A file changed since scanning. Scan again before recycling.', '文件在扫描后发生变化，请重新扫描再操作。'),
    'unsupported': ('Windows could not recycle this file. It was not permanently deleted.', 'Windows 无法将此文件移到回收站，程序没有执行永久删除。'),
    'details_button': ('Details', '详情'),
    'folder_cleanup': ('Clean a result folder…', '清理结果中的文件夹…'),
    'result_folder_title': ('Choose which result folder to clean', '选择要清理哪个结果文件夹'),
    'result_folder_note': ('Choose the folder to REMOVE duplicate copies from. Matching copies of the active tab type in other result folders will be kept. This covers every result page, including subfolders.', '选择要移除重复副本的文件夹。其他结果文件夹中的相同照片会保留，覆盖所有结果页并包含子文件夹。'),
    'result_folder_count': ('{n:,} files in duplicate results', '重复结果中有 {n:,} 个文件'),
    'review_folder': ('Review duplicates from this folder', '检查此文件夹的重复副本'),
    'folder_link_tip': ('Click to recycle all duplicates from this folder across ALL result pages. Matching copies in other folders are kept.', '点击可回收此文件夹在所有结果页中的重复副本，其他文件夹中的匹配照片会保留。'),
    'remove_from': ('Remove duplicate copies from: {path}', '移除重复副本的位置：{path}'),
    'folder_pick': ('Choose the folder to clean (including subfolders)', '选择要清理的文件夹（包含子文件夹）'),
    'folder_review': ('Review folder cleanup', '检查文件夹清理清单'),
    'folder_policy_legacy': ('Historical V1.5 plan: one copy was kept INSIDE this folder. This old plan cannot be executed in this version.', 'V1.5 历史清单：当时在此文件夹内保留一份。此旧清单不能在本版执行。'),
    'folder_policy': ('Recycle copies in the folder above ONLY when an identical SHA-256 copy is retained OUTSIDE it in the scan results. All matching copies in the chosen folder can be removed, including subfolders, across every result page. Unique files and duplicates found only inside this folder are kept. Nothing outside the chosen folder is recycled. Changed or unavailable files are skipped. Manual checkbox selections are not used.', '只有扫描结果中在此文件夹以外存在相同 SHA-256 副本时，才回收上方文件夹内的匹配照片。覆盖子文件夹及所有结果页，可移除所选文件夹内全部匹配副本。唯一文件及只在此文件夹内部重复的文件保留，不回收外部文件。文件变化或不可访问时跳过，不使用手动勾选。'),
    'folder_counts': ('{n:,} extra copies · {size} · subfolders included', '{n:,} 份多余副本 · {size} · 包含子文件夹'),
    'keeper': ('Copy to keep', '保留的副本'),
    'recycle_path': ('Copies to recycle from chosen folder', '从所选文件夹回收的副本'),
    'keeper_outside': ('Matching copies kept in other folders', '其他文件夹中保留的匹配副本'),
    'planning_folder': ('Preparing folder cleanup list…', '正在准备文件夹清理清单…'),
    'folder_empty': ('No files of the active tab type in this folder have confirmed identical copies outside it. Unique files and internal-only duplicates are kept. Complete a scan first if this folder has not been scanned.', '扫描结果中未找到此文件夹的照片在外部存在已确认的相同副本。唯一文件和仅内部重复的文件保留；若尚未扫描此文件夹，请先完成扫描。'),
    'folder_confirm': ('I confirm recycling the listed copies FROM this folder, keeping the listed matching copies in OTHER folders.', '我确认回收此文件夹内列出的副本，并保留其他文件夹中列出的匹配照片。'),
    'folder_progress': ('Folder cleanup {done:,}/{total:,} · recycled {ok:,} · not confirmed {failed:,}', '文件夹清理 {done:,}/{total:,} · 已回收 {ok:,} · 未确认 {failed:,}'),
    'cancel_cleanup': ('Stop after current file', '处理完当前文件后停止'),
    'stopping': ('Stopping after current file…', '将在当前文件处理完后停止…'),
    'folder_results': ('Folder cleanup results', '文件夹清理结果'),
    'folder_summary': ('Processed {done:,}/{total:,} · recycled {ok:,} · not confirmed {failed:,} · remaining {remaining:,}', '已处理 {done:,}/{total:,} · 已回收 {ok:,} · 未确认 {failed:,} · 剩余 {remaining:,}'),
    'folder_history': ('Folder cleanups (double-click to review)', '文件夹清理（双击查看清单）'),
    'planned': ('Awaiting confirmation', '等待确认'),
    'pending': ('Not processed', '未处理'),
    'running': ('Started (check if interrupted)', '已启动（中断后请检查）'),
    'complete': ('Finished', '已结束'),
    'cancelled': ('Stopped', '已停止'),
    'job_interrupted': ('Interrupted; review before retrying', '已中断，重试前请检查'),
}


def text(language, key, **values):
    return COPY[key][1 if language == 'zh' else 0].format(**values)


def diagnostic(language, message):
    """Translate known safety errors; retain unknown OS errors for diagnosis."""
    if not message:
        return ''
    if language != 'zh':
        return str(message)
    message = str(message)
    direct = {
        'Keep at least one unselected copy in every group.': 'all_selected',
        'Maximum 100 files per operation.': 'limit',
        'Another scan or recycle operation is running. Please wait.': 'busy',
        'No accessible, verified unselected copy. This photo was kept.': 'unavailable_keeper',
        'Selected photo changed since scanning. Scan again.': 'changed',
        'A verified photo changed. This photo was kept.': 'changed',
        'File changed during verification. Scan again.': 'changed',
        'Scan records changed after confirmation. Review the selection again.': 'no_restart',
        'Selection is no longer valid. Refresh the scan results.': 'no_restart',
        'Finish a scan before recycling photos.': 'busy',
        'Windows did not recycle this file. It may not support the Recycle Bin.': 'unsupported',
        'Restore using Windows Recycle Bin.': 'restore_note',
    }
    if message in direct:
        return text(language, direct[message])
    if message.startswith('Verified retained copy: '):
        return '已验证保留副本：' + message[len('Verified retained copy: '):]
    if message == 'Links and reparse points cannot be recycled by this app.':
        return '此程序不处理链接或重解析点。'
    if message == 'Folder not available. Previous records kept.':
        return '文件夹不可访问，已保留历史记录。'
    if message == 'File changed before verification.':
        return '文件在验证前发生变化，请重新扫描。'
    if message == 'No photos selected.':
        return '尚未选择照片。'
    folder_errors = {
        'No verified copy outside the chosen folder. This photo was kept.': '找不到所选文件夹以外的已验证副本，未回收此照片。',
        'Old folder-cleanup plans must be reviewed again in this version.': '旧版文件夹清理清单不能在本版执行，请重新检查结果文件夹。',
        'Folder cleanup plan no longer exists. Review the folder again.': '文件夹清理清单不存在，请重新选择并检查文件夹。',
        'This cleanup cannot be run again. Scan and review the folder again.': '此清理不能再次执行，请重新扫描并检查文件夹。',
        'A file is missing or resolves outside the chosen folder. This copy was kept.': '文件缺失或实际位置超出所选文件夹，未执行回收。',
        'The retained file is a hard link to this copy. Both were kept.': '保留文件与此副本是同一文件的硬链接，未执行回收。',
        'Add at least one available folder.': '请选择一个可访问的文件夹。',
    }
    if message in folder_errors:
        return folder_errors[message]
    known = {
        'No scans yet': '尚未扫描',
        'Indexing photos': '正在索引照片',
        'Hashing same-size candidates': '正在校验相同大小的候选文件',
        'Completed. Review duplicates.': '扫描完成，请检查重复文件。',
        'Completed. Review exact duplicates.': '扫描结束，请检查完全重复照片。',
        'Stopped safely. Restart scan to reuse cached hashes.': '已安全停止，重新开始时将复用缓存哈希。',
        'Stopped safely; rerun to finish.': '已安全停止，请重新运行以完成扫描。',
    }
    if message in known:
        return known[message]
    if message.startswith('Indexing '):
        return '正在索引：' + message[len('Indexing '):]
    if message in ('Modified during scan; skipped', 'Modified while hashing; skipped'):
        return '文件在扫描时变化，已跳过。'
    return text(language, 'raw_error') + '\n' + message

COPY.update({
    'try_pixels': ('Pictures look identical? Choose Same photo — ignore metadata, then run a photo scan if needed.', '画面相同却没有结果？请选择相同照片（忽略元数据），必要时重新扫描照片。'),
    'match_exact': ('Exact files', '完全相同的文件'),
    'match_pixels': ('Same photo — ignore metadata', '相同照片（忽略元数据）'),
    'pixels_note': ('Identical photo pixels, orientation and colour information. Camera metadata may differ.', '照片像素、方向和色彩信息相同；相机元数据可以不同。'),
    'pixels_empty': ('No metadata-different matching photos found. Run a photo scan to build this comparison, or choose Exact files.', '未发现元数据不同的相同照片。请扫描照片以建立比较，或选择完全相同的文件。'),
    'pixels_review': ('These photos have matching pictures but different file contents. Camera notes, dates or other metadata may differ. Review the copy you want to keep before confirming.', '这些照片的画面相同，但文件内容不同；相机备注、日期等元数据可能不同。请检查要保留的副本后再确认。'),
    'status_image_hashing': ('Comparing photo pixels', '正在比较照片像素'),
})

COPY.update({
    'all_results':('All duplicates','全部重复文件'),
    'all_media':('Photos + Videos','照片和视频'),
    'match_auto':('Automatic matching','自动匹配'),
    'automatic_matching':('Automatic duplicate matching','自动重复检测'),
    'automatic_note':('Exact copies and identical photo/video content are checked together.','自动一起检查完全相同的文件及画面、音频相同的照片和视频。'),
    'automatic_review':('Copies may have different dates or other descriptive metadata. Review which copy to keep before confirming.','副本的日期等描述信息可能不同，请检查要保留的副本后确认。'),
    'unified_empty':('No duplicates found. Add folders and finish a scan to compare all copies together.','未发现重复文件。请添加文件夹并完成扫描，以一起比较所有副本。'),
    'status_video_hashing':('Comparing full video and audio','正在比较完整视频和音频'),
})

COPY['limited_content']=('{n} files checked as exact files only','{n} 个文件仅进行了完整文件比较')

COPY.update({
 'match_similar':('Similar photo (review required)','相似照片（需人工检查）'),
 'similar_group':('Similar photos · visual score {score:.1f}% · review differences','相似照片 · 视觉分数 {score:.1f}% · 请检查差异'),
 'similar_score':('Visual {score:.1f}%','视觉 {score:.1f}%'),
 'similar_keeper':('Photo that will be kept','将保留的照片'),
 'similar_review':('Similar photos may differ in quality or content. This is a visual score, not a guarantee of equality. Compare the photos and the retained photo below before confirming. Folder cleanup excludes approximate-only matches.','相似照片的质量或内容可能不同。视觉分数不代表完全相同。确认前请比较照片及下方将保留的照片。文件夹清理不处理仅相似的照片。'),
 'confirmed_group':('Confirmed duplicates · exact file or identical pixels/content','已确认重复 · 文件完全相同或像素/内容相同'),
 'status_similarity_hashing':('Checking similar photos','正在检查相似照片'),
 'status_similarity_grouping':('Grouping similar photos','正在分组相似照片'),
 'automatic_note':('One scan checks exact copies, metadata differences and similar photos. Similar matches need review; folder cleanup uses confirmed duplicates only.','一次扫描检查完全相同、元数据不同及相似照片。相似照片需人工检查；文件夹清理仅处理已确认重复。'),
})

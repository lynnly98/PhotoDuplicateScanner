Photo Duplicate Scanner V2.1 - source edition

One automatic scan checks exact files, identical decoded content with metadata
changes, and conservative similar-photo candidates. The native Duplicates page
retains Photos / Videos tabs. No matching-mode selector is required.

Similar photos use a cached 63-bit DCT perceptual hash, 64-bit difference hash,
aspect ratio, transparency and normalized colour thumbnail checks. Resized,
recompressed and slightly brighter copies may match. Scores describe the visual
comparison, not a probability or proof of equality. Substantial crops, edits,
unsupported formats or low-detail pictures may not match. Static RGB/RGBA/L/LA/P
photos up to 40 megapixels are eligible; exact-file matching remains available
for other formats. Colour profiles are not normalized for similarity.

Confirmed families are kept intact. Complete-link similarity groups require
all representative pairs to pass; transitive chains cannot merge unlike photos.
Groups contain at most 64 confirmed families. Candidate search is bounded to
256 nearby group anchors, so dense collections can be split and some candidates
may be missed. Only compact hashes/paths and a small thumbnail cache reside in
RAM; original photos are decoded one at a time. Fingerprints/thumbnails are
stored in SQLite and reused on subsequent unchanged scans.

Similar photos can be inspected and manually selected for Windows Recycle Bin.
The confirmation explicitly warns about possible quality/content differences
and names an unselected photo that will remain. Target and fixed keeper are
freshly hashed and compared before recycling; missing/changed files fail closed.
No permanent-delete fallback. No automatic photo changes.

Bulk folder cleanup ONLY uses confirmed exact/content duplicates. It cannot
remove approximate-only matches. Excel reports include a Similar photos review
sheet, with scores and paths, alongside confirmed duplicates and errors.
Videos retain the previous exact and full decoded video/audio checks; this
version adds no perceptual video matching.

UPGRADE
Close the old application. Extract the complete portable release into a new
folder. Copy the old data folder beside the new EXE to preserve records/settings.
Back up the data folder before upgrade. SQLite migrations are additive. Run a
new photo/both scan to populate the new visual cache; old raw/content hashes
are reused. Optional cache and reports folders can also be retained.
Keep the EXE and its _internal folder together. Portable needs no installation,
Python, or BAT. This source edition instead needs 64-bit Python 3.14; double-click
Run Photo Scanner.bat. It reuses installed compatible packages before downloading
missing requirements into its project .venv. To build portable, install PyInstaller
and run python -m PyInstaller --clean --noconfirm portable.spec from this folder.

VALIDATION
Python 3.14 on the available Windows host: generated resized/recompressed/brightness
variants, unrelated images, exact and metadata variants, unchanged-cache reuse,
combined scan modes, Photos/Videos categories, English/Chinese, light/dark dropdowns,
manual similarity confirmation/cleanup via test backend, changed/missing-file
protection, folder cleanup exclusion, Excel export and cleanup page reset.
The two reported real-folder pairs are found read-only, with no user files changed.
No clean Windows 11 installation, 100,000-500,000 real-file library, exhaustive
codec/camera collection or every external-drive disconnect scenario was tested.

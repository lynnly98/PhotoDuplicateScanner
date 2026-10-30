"""Allow this project's venv to reuse its base Python's installed packages."""
import re
import sys
from pathlib import Path


def enable(config):
    text = config.read_text(encoding='utf-8')
    updated, count = re.subn(
        r'(?mi)^include-system-site-packages\s*=\s*[^\r\n]*',
        'include-system-site-packages = true', text)
    if count != 1:
        raise RuntimeError('Invalid virtual environment configuration: ' + str(config))
    if updated != text:
        config.write_text(updated, encoding='utf-8')


if __name__ == '__main__':
    if sys.prefix == sys.base_prefix:
        raise RuntimeError('Run this helper with the project virtual environment.')
    enable(Path(sys.prefix) / 'pyvenv.cfg')

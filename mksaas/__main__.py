"""mksaas.__main__ — 支持 python -m mksaas 调用。"""

import sys

from mksaas.cli import main

if __name__ == "__main__":
    sys.exit(main())

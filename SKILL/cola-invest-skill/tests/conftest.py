"""Pytest 共享配置：把 ``bin/`` 加入 ``sys.path``，使测试可导入包内模块。

仓库布局（``bin/`` 是代码根，运行期由 ``cola_fetch.py`` 自行插入 sys.path）：

    cola-invest-skill/
    ├── bin/
    │   ├── cola_fetch.py
    │   └── download_financial_report/...
    ├── tests/
    └── references/
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BIN_DIR = _REPO_ROOT / "bin"

if str(_BIN_DIR) not in sys.path:
    sys.path.insert(0, str(_BIN_DIR))

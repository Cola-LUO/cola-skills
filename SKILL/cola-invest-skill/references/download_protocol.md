# 下载协议（download_protocol）

本文件给出 `cola-fetch` 下载器的命令规范、市场映射与失败处理。`cola-fetch` 是一个**轻量外置 CLI**：只做"按 ticker 路由 → 发请求 → 落盘报告文件"，不调 docling、不调 LLM、不解析内容。

---

## 1. 调用契约（首次需建 venv，之后直接调用）

`cola_fetch.py` 以**相对路径**调用，不注册 PATH；首次运行时 agent 须在工作区建立隔离 venv 并装依赖（幂等，已有则跳过）：

```bash
# 1. 首次：建 venv + 装依赖（已有 .venv 则此两步可跳过）
# ⚠ 下面 venv / pip 三条命令的工具调用必须带 dangerouslyDisableSandbox: true，
#    否则 pymupdf（含原生 mupdf 库）安装内存峰值会顶破沙箱上限，被 OOM killer SIGKILL（exit 137）。
#    （lxml 是预编译 C 扩展 wheel，加装零编译不 OOM，无需额外处理。）
python3 -m venv <skill根>/bin/.venv
<skill根>/bin/.venv/bin/pip install --no-cache-dir --upgrade pip >/dev/null 2>&1
<skill根>/bin/.venv/bin/pip install --no-cache-dir -r <skill根>/bin/requirements.txt

# 2. 之后：永远用 .venv 里的 python 跑
<skill根>/bin/.venv/bin/python <skill根>/bin/cola_fetch.py download \
  --ticker 00700 \
  --annual-years 3 \
  --latest-interim \
  --latest-quarter \
  --workspace-root <当前工作目录>      # 默认 . ，PDF 落到 <workspace-root>/filings/<ticker>/
```

### 参数说明
| 参数 | 必填 | 含义 |
|------|------|------|
| `--ticker` | 是 | 规范股票代码（见 §2），如 `00700` / `600519` / `AAPL` / `BRK-B` |
| `--annual-years N` | 否 | 拉取**最近 N 份年报**（按披露时间倒序），默认 3 |
| `--latest-interim` | 否 | 额外拉最新一期半年报（A/HK 生效，美股忽略） |
| `--latest-quarter` | 否 | 额外拉最新一期季报（A/US 生效，港股可能缺失→自动跳过） |
| `--workspace-root <目录>` | 否 | 工作区根目录，默认 `.`；PDF 落到 `<workspace-root>/filings/<ticker>/` |
| `--sec-user-agent <UA>` | 否 | SEC User-Agent；默认读环境变量 `SEC_USER_AGENT`（见 §8） |

> 用户在对话里另行指定年份/类型时，按用户指定为准，覆盖默认值。

---

## 2. ticker 规范化规则

从用户的话里抽出：**公司名** + **财报类型**+ **年份范围**。
下游下载器根据代码形态自动判市场，**所以必须传入不带后缀的规范代码**：

| 市场 | 形态 | 规范示例 | 禁止形态 |
|------|------|----------|----------|
| 港股 | 4–5 位纯数字 | `00700`、`09988` | `HK.00700`、`0700.HK`、`00700.HK` |
| A股 | 6 位纯数字 | `600519`、`000001`、`300750` | `600519.SH`、`sh600519` |
| 美股 | 字母代码 | `AAPL`、`MSFT`、`BABA` | `NASDAQ:AAPL` |

公司名→ticker 由 LLM 用自身知识完成；拿不准就反问用户要代码，**不要编造**。

---

## 3. 各市场 forms 映射

`cola-fetch` 内部把高级语义（年报/半年报/季报）翻译成各市场对应的 forms 代号：

| 市场 | 年报 | 半年报 | 季报 |
|------|------|--------|------|
| 美股 | `10-K`（境内）/ `20-F`（境外上市） | 无 → 自动忽略 | `10-Q` |
| A股 | `FY` | `H1` | `Q1`–`Q4`（取最近一期） |
| 港股 | `FY` | `H1` | `Q1`–`Q4`（可能缺失→自动跳过，不算失败） |

> 这些映射由 `cola-fetch` 内部完成，**调用方只需传 `--annual-years` / `--latest-interim` / `--latest-quarter` 这三个高级开关**，不必手动指定 forms 代号。

---

## 4. 落盘路径与命名

```
<workspace-root>/filings/<ticker>/
  ├── 港股/A股：<公司名>-<年份>-<forms>.pdf
  └── 美股：<公司名>-<年份>-<forms>.htm
```

港股/A股示例：

```
filings/00700/
  ├── 腾讯控股-2023-FY.pdf
  ├── 腾讯控股-2022-FY.pdf
  ├── 腾讯控股-2021-FY.pdf
  ├── 腾讯控股-2024-H1.pdf
  └── 腾讯控股-2024-Q1.pdf   # 港股若不存在则无此文件，不算失败
```

美股示例：

```
filings/AAPL/
  ├── Apple-2023-FY.htm
  ├── Apple-2022-FY.htm
  └── Apple-2024-Q1.htm
```

- 公司名由 `cola-fetch` 内部根据 ticker 解析（解析不到时退化为 ticker 本身作文件名前缀）。
- 美股 SEC 主文档为 HTML/XBRL 格式，**非 PDF**，故落盘为 `.htm`；港股/A股仍为 `.pdf`。
- `--workspace-root` 默认 `.`（即当前工作目录）；报告落到 `<workspace-root>/filings/<ticker>/`。

---

## 5. 已有则跳过（幂等）

- 下载前 `cola-fetch` 会检查目标路径是否已存在同名报告文件（港股/A股 `.pdf`、美股 `.htm`）。
- **已存在 → 跳过，不重下**。
- 这样同一公司多次分析不会反复拉取，也不浪费带宽。

---

## 6. 三市场示例

venv 建立与首次准备见 §1。调用一律用完整路径（`cola-fetch` 不注册 PATH）：

```bash
# 港股：腾讯控股
<skill根>/bin/.venv/bin/python <skill根>/bin/cola_fetch.py download \
  --ticker 00700 --annual-years 3 --latest-interim --latest-quarter \
  --workspace-root <当前工作目录>

# A股：贵州茅台
<skill根>/bin/.venv/bin/python <skill根>/bin/cola_fetch.py download \
  --ticker 600519 --annual-years 3 --latest-interim --latest-quarter \
  --workspace-root <当前工作目录>

# 美股：Apple
<skill根>/bin/.venv/bin/python <skill根>/bin/cola_fetch.py download \
  --ticker AAPL --annual-years 3 --latest-interim --latest-quarter \
  --workspace-root <当前工作目录>
```

---

## 7. 退出码与失败处理

- 成功：退出码 `0`，并打印汇总，例如：
  ```
  downloaded=2 skipped=1 failed=0
  ```
- 部分失败：退出码 `0`（只要至少有一份成功就视为可继续），但 `failed` 字段非 0；agent 据此决定哪些年份缺料。
- 全部失败：退出码非 `0`。
- **重试策略**：调用方（agent）在失败时重试 1 次；仍失败则在报告里如实标注"未能获取 X 年财报"，不要硬撑。

---

## 8. 运行环境前提

- `cola_fetch.py` 以相对路径调用（见上文调用契约），**不需要**预装到 PATH；首次运行时 agent 自动在 `bin/.venv/` 建立隔离 Python 环境并安装依赖（`httpx` + `pymupdf` + `lxml`），用户零操作。
- 美股下载需要环境变量 `SEC_USER_AGENT`（**不是邮箱号本身**）；这是 SEC 公平访问规则要求的 User-Agent 字符串，SEC 建议 UA 采用官方示例格式 `CompanyName admin@company.com`（公司名 + 空格 + 联系邮箱，无括号、无版本号），例如 `ColaFetch admin@example.com`。这是合规要求，**不是 API key，不收费**。
- 运行 skill 的 agent（CodeBuddy / Claude Code 等）必须具备 shell/terminal 工具，才能从无代码的 SKILL.md 触发本命令。

### 8.1 SEC UA 默认值与限流应对

**默认行为（无需用户介入）**：
- 未设 `SEC_USER_AGENT` 环境变量时，CLI 用预设 UA `ColaFetch admin@example.com`。
- `admin@example.com` 是 RFC 2606 保留的"示例邮箱"（`example.com` 域名专门给文档示例用），格式合法但不是真实邮箱。
- 单次或低频访问够用，SEC 不会限流。**agent 不需要在每次下载前问用户要邮箱。**

**被 SEC 限流时（HTTP 429/503）**：
- `sec_downloader` 内部已实现限流退避（默认等 600 秒后重试 3 次）。
- 退避后仍失败时，CLI 检测到 `was_throttled()` 标志为 `True`，输出明确提示并**退出码 `3`**（区别于普通失败的 `1`）：
  ```
  SEC 限流（429/503）触发。预设 UA 已不够用，请设置环境变量 SEC_USER_AGENT 为真实 UA（含联系邮箱）：
      export SEC_USER_AGENT="ColaFetch 你的邮箱@example.com"
  ```
- agent 看到此提示后，**必须反问用户**：
  > SEC 限流了。请提供 User-Agent 字符串，格式如 `ColaFetch 你的邮箱@example.com`（公司名 + 空格 + 邮箱）。
- 拿到用户提供的 UA 后，用 `--sec-user-agent` 参数重跑（不需要 `export` 环境变量）：
  ```bash
  <skill根>/bin/.venv/bin/python <skill根>/bin/cola_fetch.py download \
    --ticker AAPL --annual-years 3 \
    --sec-user-agent "ColaFetch 用户提供的邮箱" \
    --workspace-root <当前工作目录>
  ```

**永久设置 UA（可选，避免每次输入）**：
```bash
# 加到 ~/.zshrc 或 ~/.bashrc
export SEC_USER_AGENT="ColaFetch 你的真实邮箱@example.com"
```
之后所有 SEC 下载自动用这个 UA，港股/A股不受影响（它们不读此变量）。

**退出码语义**：
| 退出码 | 含义 |
|--------|------|
| `0` | 至少一份报告下载成功 |
| `1` | 全部失败（普通错误，如网络超时、ticker 不存在） |
| `2` | 参数错误（ticker 无法识别、市场不支持） |
| `3` | SEC 限流触发（需用户设真实 UA 后重跑） |

---

## 9. 与「信息来源」铁律的协同

- 财报正文：以 `cola-fetch` 下载的官方源为**主源**——港股/A股为 PDF、美股为 `.htm`（披露易 / 巨潮 / SEC 都是官方一手源）。
- **不要再下一份同公司同市场的财报来充当"第二渠道"**——那不构成独立渠道，只会陷入死循环。
- 数值类交叉验证：用联网检索（新闻 / 财经站点 / FMP）做容差比对，容差规则见 SKILL.md「信息来源」第 1 条。

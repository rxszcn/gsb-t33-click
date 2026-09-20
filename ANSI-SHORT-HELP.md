# 子命令列表页短帮助：三套长度口径并存的问题记录

复现命令（仓库根目录）：

```
.venv/bin/python repro/ansi-short-help.py
```

环境事实：`.venv` 以 editable 方式装的是 `/home/liuyang/gsb/seed/click`，其源码与本仓库 `src/` 完全一致（`diff -rq` 无差异），所以 repro 跑的就是这份代码。下文候选改法在 `/tmp` 的三份仓库拷贝上进行，通过 `PYTHONPATH=<拷贝>/src` 指向各自源码，导入路径已逐一打印确认。

## 一、五组读数（照实抄）

基线源码下运行 `.venv/bin/python repro/ansi-short-help.py` 的完整读数：

```
=== 1) 子命令列表页的短帮助
    colored  留下词数 8 | 可见宽度 69 | 行内还有色码 = True
    plain    留下词数 9 | 可见宽度 76 | 行内还有色码 = False
=== 2) 选项帮助（同一份文本带不带色）
    --alpha        本行词数 9 | 可见宽度 78
    word10         本行词数 7 | 可见宽度 78
    word19         本行词数 0 | 可见宽度 29
    --beta         本行词数 9 | 可见宽度 78
    word10         本行词数 7 | 可见宽度 78
    word19         本行词数 0 | 可见宽度 29
=== 3) 两处宽度算法各自的答复
    term_len 对带色的 abcd = 4 | 同一个串按字符长度数 = 13
=== 4) OSC-8 超链接走两条路
    截断路径产出: 'seg1 seg2 seg3 seg4 seg5 seg6 seg7 seg8...'
    整段按字符长度数 = 164 | term_len 口径 = 164 | 真实可见字符数 = 115
    短例截断产出: 'alpha beta...'
    该产出里还带着链接 = False
    wrap_text 对同一段首行: 'seg1 seg2 seg3 seg4 seg5 seg6 seg7 seg8 seg9'
=== 5) 全角字符在两套口径里的答复
    term_len 对全角八字 = 8 | 屏幕上占的格 = 16
```

第 1 组里的宽度前提：`CliRunner` 在 `testing.py:439` 强制 `formatting.FORCED_WIDTH = 80`，因此 `COLUMNS=50` 不生效，格式化器宽度是 80。列表页预算在 `src/click/core.py:1973`：`limit = formatter.width - 6 - max(命令名长度)`，两条命令名都是 7 字符，所以 `limit = 80 - 6 - 7 = 67`。

## 二、三套口径各住在哪

三套口径在同一条「列表页短帮助」渲染链上并存：

1. **口径 A —— 原始 `len()` 字符数（色码、链接全算）**
   住在 `src/click/utils.py:62` 的 `_make_default_short_help()`：累计预算 `total_length += len(word) + (i > 0)`，回退也是 `len(words[i])`，末尾再加 `len("...")`。列表页在 `src/click/core.py:1249` 经 `get_short_help_str()` 调它，预算由 `src/click/core.py:1973` 算出。这是第 1 组不一致的直接出处。
2. **口径 B —— `term_len()`（剥 CSI 色码后数字符，不按屏幕格）**
   住在 `src/click/_compat.py` 末尾：`term_len(x) = len(strip_ansi(x))`，`strip_ansi` 用的 `_ansi_re` 只认 CSI（`ESC [ ... 终字符`）。它被 `formatting.py` 的 `measure_table()`（`src/click/formatting.py:14`，垫列宽）、`write_dl()`（`src/click/formatting.py:229`，第二列起点和文本宽度）和 `src/click/_textwrap.py` 的 `TextWrapper._wrap_chunks()`（`wrap_text()` 的换行，入口在 `src/click/formatting.py:31`）统一使用。
3. **口径 C —— 真实屏幕占格**
   代码里根本没有这一套。最接近的是 `src/click/_textwrap.py:11` 的 `_truncate_visible()`，它也只跳 CSI，既不跳 OSC，也不按 East Asian Width 算全角宽度。用户在终端网格里实际看到的列宽没有任何函数在量。

三者在一条链上的走向：

```
help 文本
  └─ _make_default_short_help()        口径 A：len()        —— 先截短（只列表页走）
       └─ HelpFormatter.write_dl()
            ├─ measure_table()/垫空格   口径 B：term_len()  —— 定第一列宽度
            └─ wrap_text()/_textwrap    口径 B：term_len()  —— 第二列换行
                 └─ 真正画到屏幕        口径 C：不存在       —— 全角/链接才在此现形
```

选项页（第 2 组）的选项帮助整段交给 `write_dl` → `wrap_text`，**不经过** `_make_default_short_help()`，所以不走口径 A，带不带色换行完全一致（`--alpha`/`--beta` 三行读数逐一相同）。这就是「同一个坑只在子命令列表页咬人」的原因。

## 三、色码、链接、全角分别错在哪几套里

**色码（SGR，如 `\x1b[31m`…`\x1b[0m`，首尾共 9 个非可见字符）**

- 口径 A 错：`len()` 把这 9 个字符算进预算，带色文本提前 1 个词撞线。`word01 … word20` 每个词 6 字符：无色时在第 9 个词累计 `6*9+8=62`、第 10 个词 `69 > 67` 超，回退后保留 9 个词（第 1 组 plain：词数 9、可见宽度 76）；带色时开头多 5、结尾多 4，第 8 个词就累计到 67、第 9 个词 74 超，回退后只保留 8 个词（colored：词数 8、可见宽度 69），色码本身倒还留在输出里（`行内还有色码 = True`）。
- 口径 B 对：`strip_ansi` 能剥 CSI，所以 `term_len("\x1b[31mabcd\x1b[0m") = 4`（第 3 组）。

**OSC-8 超链接（`ESC ] 8 ;; URL BEL 可见文字 ESC ] 8 ;; BEL`）**

- 口径 A 错：整段 164 字符全算（第 4 组「整段按字符长度数 = 164」）。
- 口径 B 也错：`_ansi_re` 只匹配 CSI（`ESC [` 开头），不认 `ESC ]` 开头的 OSC，`term_len` 同样报 164，而真实可见字符只有 115（链接这个词整段 53 字符，其中只有 `docs` 4 个字符可见，不可见部分 49 字符；164−49=115）。
- 截断路径（口径 A）在词边界切，链接是挂在末尾的一个「词」，预算先耗尽，链接整体被切掉：长例 `'seg1 … seg8...'`，短例 `'alpha beta...'`，`该产出里还带着链接 = False` —— 链接直接没了。
- 换行路径（口径 B，`wrap_text`）把 OSC 串当普通字符，45 列预算下从 URL 中间硬切，第 3 行结尾是 `...\x1b]8;;https://example.`、第 4 行是 `com/a/very/long/path/\x07docs\x1b]8;;\x07` —— 链接被劈成两半，两边都不是合法 OSC-8，终端既不渲染成超链接还会漏出 URL 文本。

**全角字符（CJK，屏幕上每个占 2 格）**

- 口径 B 错：`term_len("一二三四五六七八") = 8`，屏幕实际占 16 格（第 5 组）。
- 后果一（垫列宽）：`measure_table` 按 term_len 量第一列，含全角的列名被少垫空格，后续行列错位；第二列宽度同样少给。
- 后果二（换行）：`TextWrapper` 按 term_len 给预算，占 16 格的八个全角字能塞进 `width=8`，整行溢出终端右边界；半角串在同宽度下会被拆词。
- 口径 A 对全角反而是「字符数」，和 term_len 数值相同 —— 也就是 A、B 在全角上一起错（都拿字符数当格数）。

## 四、构造例 1：带色与不带色在列表页留下相同词数

思路：`CliRunner` 下列表页预算恒为 `limit=67`。让可见正文完全相同：前两个词各 10 个 `c`（加空格累计 21），第三个词 46 个 `c`（累计 `21+1+46=68 > 67`），后面再跟一个 `dd`。无色版直接用这段正文；带色版用 `RED + 正文 + OFF` 整段裹色，`split()` 后第一个词变成 `RED + cccccccccc`（15 字符）、最后一个词变成 `dd + OFF`（6 字符）。

输入（基线源码实测）：

```python
RED, OFF = "\x1b[31m", "\x1b[0m"
plain_help   = "cccccccccc cccccccccc " + "c" * 46 + " dd"
colored_help = RED + plain_help + OFF
# 挂在两个同名长（7 字符）的子命令 plain / colored 上，COLUMNS 随意（CliRunner 强制 80）
```

预算推演（两条命令名等长，limit 都是 67，走的都是口径 A 的 `len()`）：

- plain：前两词累计 21；第 3 词 `21 + 1 + 46 = 68 > 67` 撞线，回退保留前 2 词 → `cccccccccc cccccccccc...`。
- colored：第 1 词 15、第 2 词 10，累计 `15 + 1 + 10 = 26`；第 3 词 46，累计 `26 + 1 + 46 = 73 > 67` 撞线，回退保留前 2 词；回退点在第 3 词之前，远早于结尾的 `OFF`，开头的 `RED` 随第一个词被原样带出 → `\x1b[31mcccccccccc cccccccccc...`。

预测：两条可见词数都是 2；带色行 `行内还有色码 = True`，无色行 `False`。

实际列表页输出（基线，`CliRunner(color=True)`）：

```
'  colored  \x1b[31mcccccccccc cccccccccc...' | 留下词数: 2 | 行内还有色码: True
'  plain    cccccccccc cccccccccc...'         | 留下词数: 2 | 行内还有色码: False
```

词数对齐了，但这是「错错得对」——对齐靠的是让两条文本在同一个 bug 口径下撞同一道墙；候选 A/C 修好口径 A 后，两条可见内容长度不同，词数反而会重新拉开（这正是修复后应有的、按可见内容计算的结果）。

## 五、构造例 2：term_len 相同、屏幕占格不同

输入：

```python
half = "abcdefgh"          # 8 个半角
full = "一二三四五六七八"  # 8 个全角
```

读数：`term_len(half) = term_len(full) = 8`，但屏幕占格分别是 8 和 16（第 5 组已是单串版；这里看它在渲染链上的后果）。

`wrap_text(full, width=8)` 原样返回整串 `'一二三四五六七八'`，即 8 格的行预算放进了占 16 格的内容；同样宽度下 `wrap_text("abcdefgh", 8)` 正好一行、`wrap_text("abcdefgh more", 8)` 会拆词。放进 `write_dl` 同一张两列表：

```
cmd1  abcdefgh <- 描述从同一列开始？
cmd2  一二三四五六七八 <- 全角行实际顶出去 8 格
```

两行第二列的起始列相同（第一列 `cmd1`/`cmd2` 等宽），但第二列内容里 `half` 占 8 格、`full` 占 16 格，于是屏幕上第二行的箭头比第一行右移 8 格，且第二行内容超出格式化器自以为的行宽 —— 口径 B 量出的「等长」在口径 C 的屏幕上不等长。这证明只修色码/链接（让 A 向 B 看齐）到顶也只统一到「字符数」，离「屏幕格」还差一层 East Asian Width。

## 六、三种候选改法，各拷一份仓库实测

做法：把仓库拷三份到 `/tmp/cands-1789904381/{a-term-len,b-strip,c-visible}`（只带 `src/`、`tests/`、`repro/`、`pyproject.toml`），各装一种改法，用 `PYTHONPATH=<拷贝>/src /home/liuyang/gsb/repos/t33-click/.venv/bin/python repro/ansi-short-help.py` 跑同一份 repro（导入路径已打印确认指向各拷贝）。三种改法都只动 `src/click/utils.py` 的 `_make_default_short_help()`，不碰口径 B。

- **候选 A —— 预算统一换 `term_len`**：把函数里两处 `len(word)` 换成 `term_len(word)`（`term_len` 从 `._compat` 导入），其余不动。
- **候选 B —— 进截断函数先剥色**：在第一段截断之后、`split()` 之前加一行 `help = strip_ansi(help)`，预算仍是 `len()`。
- **候选 C —— 预算只认可见内容**：新增 `_osc_re`（剥 `ESC ] ... BEL` / `ESC ] ... ESC \\` 的 OSC 串）和 `_visible_len = len(_osc_re.sub("", strip_ansi(x)))`，预算的两处 `len(word)` 换成 `_visible_len(word)`；`words` 原样保留，色码和链接不删。

三处关键实际读数：

| 检查项 | 基线 | A：换 term_len | B：先剥色 | C：只认可见内容 |
| --- | --- | --- | --- | --- |
| 列表页词数 colored / plain | **8 / 9** | **9 / 9** | **9 / 9** | **9 / 9** |
| colored 行内色码在不在 | 在 | **在** | **不在** | **在** |
| 短例（`alpha beta ` + OSC 链接）链接保没保住 | 没保住，产出 `'alpha beta...'`，链接=False | **没保住**，`'alpha beta...'`，链接=False | **没保住**，`'alpha beta...'`，链接=False（`strip_ansi` 剥不掉 OSC，但预算照样把它算长，链接词被整体切掉） | **保住**，产出 `'alpha beta \x1b]8;;https://example.com/a/very/long/path/\x07docs\x1b]8;;\x07'`，链接=True |

三家五组其余读数（第 2、3、5 组及长链接路径）与基线逐字相同：选项页三行词数 9/7/0、`term_len` 带色 abcd=4 vs len=13、全角 8 vs 16、长例截断都停在 `'seg1 … seg8...'`、`wrap_text` 首行仍是 `seg1 … seg9`。也就是说三家都只改了列表页截断这一段，垫列宽和换行（口径 B）的 OSC、全角问题原封不动。

候选 C 的边界也要如实记下：短例链接能保住，是因为可见内容只有 15 字符、整段没触发截断；repro 第 4 组的长例在词边界处预算就耗尽，末尾的链接词同样进不了结果（`'seg1 … seg8...'`），而一旦链接出现在 `wrap_text` 路径（口径 B），仍会被从 URL 中间劈断 —— 这个改动不覆盖那两条路。另外带色文本在色码未闭合处被截时，行尾可能没有 `OFF`（A、C 都有此现象，B 因整体剥色而没有），严格做法还需补一个收尾 reset。

**老用例四种状态**：`tests/test_utils/test_make_default_short_help.py` 与 `tests/test_commands.py`（共 117 项）在基线、A、B、C 下全部 `117 passed`。全绿，但正如题面所说，这判不了对错 —— 老用例的输入全是无色、无链接、无全角的纯 ASCII，三种改法对它们行为一致，取舍只能看 repro。

## 七、站哪条、放弃了什么

**站候选 C（预算只认可见内容，词原样保留）。** 在题目要求对线的三处实测上，它是唯一三项全对的：列表页带不带色词数一致（9/9）、色码保留、短例 OSC 链接原样保住。A 只把口径 A 对齐到口径 B，而 B 本身不认 OSC，链接照样丢；B 用「删掉颜色」换词数一致，违背「颜色要保留」，且对链接、全角毫无作用。

候选 C 放弃/未覆盖的部分，写明白：

- 口径 B 没动：`measure_table` 垫列宽和 `wrap_text` 换行仍用 `term_len`，全角按 1 字符量导致的列错位、行溢出依旧；OSC 长链接走换行路径仍被劈断。
- 长例链接仍会丢：词边界截断先耗尽预算，末尾链接词进不了结果；真正要保链接得在截断时跳过不可见的 OSC 串而不是只让它不计预算。
- 统一到的是「可见字符数」，不是「屏幕格」：全角仍是 1。三套口径要彻底并成一套，需要把 `term_len`、`_textwrap`、`_make_default_short_help` 统一到一个「CSI/OSC 不计 + East Asian Width 计格」的度量上，那超出这三个候选的范围。

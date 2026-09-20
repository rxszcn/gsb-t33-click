# ANSI 短帮助三套长度口径调查

调查对象：`repro/ansi-short-help.py`（用 `.venv/bin/python repro/ansi-short-help.py` 复跑）。
本文不改任何实现与测试，只给读数、定位、构造例和三种候选改法的实测对比。

## 一、repro 五组读数（原样照抄，基线未改码）

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

一个读数前提：`CliRunner` 把 `formatting.FORCED_WIDTH` 强制成 80
（`src/click/testing.py:439`），所以脚本里的 `COLUMNS=50` 不生效，实际排版宽度是
80，列表页预算 `limit = 80 - 6 - 最长命令名(7) = 67`。这就是第 1 组里"可见宽度
76"能超过 50 的原因。

## 二、三套口径各住在哪

1. **截断口径（列表页短帮助）**：`_make_default_short_help`
   （`src/click/utils.py:62`）。预算和回退全程用内置 `len()` 按**字符数**算，
   转义序列的每个字节都吃预算。调用链：列表页 `format_commands` 算出
   `limit = formatter.width - 6 - 最长命令名`（`src/click/core.py:1973`）→
   `Command.get_short_help_str`（`src/click/core.py:1242`）→
   `_make_default_short_help`。
2. **换行排版口径**：`wrap_text`（`src/click/formatting.py:31`）+
   `TextWrapper._wrap_chunks`（`src/click/_textwrap.py`）。每个 chunk 的宽度
   一律过 `term_len`。选项帮助（repro 第 2 组）走的就是这条，不过截断函数。
3. **垫列宽口径**：`measure_table`（`src/click/formatting.py:16`）和
   `HelpFormatter.write_dl` / `write_usage` 里的对齐补空格，同样过 `term_len`。

口径 2、3 共用 `term_len`（`src/click/_compat.py:536`），即
`len(strip_ansi(x))`；而 `strip_ansi` 用的 `_ansi_re`
（`src/click/_compat.py:19`）只匹配 CSI 序列（`\033[` 开头），**不匹配 OSC
序列**（`\033]` 开头，超链接 `\033]8;;...` 就是这类）。

## 三、色码、链接、全角分别错在哪几套

- **SGR 色码**：只错第 1 套。`RED + 文本 + OFF` 多出 9 个字符的预算开销，
  带色版因此少留一个词（8 vs 9）。第 2、3 套的 `term_len` 能把 CSI 色码剥
  掉，不受影响——所以选项帮助那条路带不带色读数完全一样（repro 第 2 组）。
- **OSC-8 超链接**：三套全错。第 1 套把 54 字节的链接控制序列当可见字符数，
  短例里链接整个被回退循环抹掉（`'alpha beta...'`，链接丢失）；第 2、3 套的
  `term_len` 不剥 OSC，链接被算成 50 多"列"，于是 `wrap_text` 首行只放下 9
  个词（纯文本能放 10 个），`measure_table` 也会把含链接的列垫得过宽。
- **全角字符**：三套全错。三套数的都是"字符"不是"屏幕格"，
  `term_len("一二三四五六七八") = 8`，实际占 16 格。截断会多留一倍的视觉宽
  度，换行和垫列同样按半宽算。

## 四、构造：两条列表页词数相同（一带色一不带色）

利用预算 67 下"词边界吸收"：纯文本版前 5 词累计 54 字符、加省略号 57 <= 67，
第 6 词进不来；带色版色码 9 字符开销落在已留词内，前 5 词累计 63、加省略号
66 <= 67，同样留 5 词。

输入（命令名仍用 `plain` / `colored`，`COLUMNS=50`，与 repro 同环境）：

```python
RED, OFF = "\x1b[31m", "\x1b[0m"
words = ["w%09d" % i for i in range(1, 8)]      # 7 个词，每个 10 字符
plain_body   = " ".join(words)                   # 不带色
colored_body = RED + " ".join(words[:5]) + OFF + " " + " ".join(words[5:])
```

预测：两条都留 **5** 个词；`colored` 行行内仍带色码（色码随前 5 词一起保
留），`plain` 行不带。实测（同 repro 第 1 组的跑法）：

```
colored  留下词数 5 | 行内还有色码 = True
plain    留下词数 5 | 行内还有色码 = False
```

raw 行：`'  colored  \x1b[31mw000000001 ... w000000005\x1b[0m...'` 与
`'  plain    w000000001 ... w000000005...'`，与预测一致。

## 五、构造：term_len 相同但屏幕占格不同

```python
a = "abcd"        # term_len(a) == 4，屏幕占 4 格
b = "一二三四"    # term_len(b) == 4，屏幕占 8 格（全角每字 2 格）
```

两串 `term_len` 都是 4，但 `b` 在屏幕上宽一倍。后果实例：`measure_table` 会
给两串补同样多的空格来"对齐"，视觉上列却错开 4 格；`wrap_text` 放 `b` 时也会
按半宽提前换行。

## 六、三种候选改法实测（仓库拷到 /tmp/t33-a、/tmp/t33-b、/tmp/t33-c）

三份都只动 `_make_default_short_help`（各一份 `src/click/utils.py`），用
`PYTHONPATH=/tmp/t33-<x>/src` 盖过 venv 里的 editable 安装后跑同一份 repro：

- **A（预算统一换 term_len）**：截断函数里 `len(word)` 全换 `term_len(word)`。
- **B（进截断函数先剥色）**：函数入口 `help = strip_ansi(help)`。
- **C（预算只认可见内容）**：预算用"剥掉 CSI + OSC 后的可见字符数"计量
  （新增一个同时认 `\033[...` 和 `\033]8;;...` 的正则），输出保留原串。

实测读数（repro 第 1、4 组相关行）：

| 状态 | 列表页词数 plain/colored | 色码在不在 | 短例链接保没保住 |
|------|--------------------------|------------|------------------|
| 基线 | 9 / 8                    | 在         | 没保住（`'alpha beta...'`） |
| A    | 9 / 9                    | 在         | 没保住（`'alpha beta...'`） |
| B    | 9 / 9                    | **不在**（两行都无 `\x1b`） | 没保住（`'alpha beta...'`） |
| C    | 9 / 9                    | 在         | **保住**（产出含完整 `\x1b]8;;...docs...`，不截断） |

老用例核对：`tests/test_utils/test_make_default_short_help.py` +
`tests/test_commands.py` 在基线、A、B、C 四种状态下都是 **117 passed**——
四种状态全绿，判不了对错，只能以 repro 读数为准。

其余各组在 A/B/C 下与基线完全一致：第 2 组（选项帮助不过截断函数）、第 3 组、
第 4 组的 `term_len`/`wrap_text` 读数、第 5 组全角读数都没动——三种改法都只
碰第 1 套口径。

## 七、站哪条、放弃了什么

**站 C（预算只认可见内容）**。它是唯一同时保住颜色（词数拉平到 9/9 且行内色
码还在）和 OSC 链接（短例产出完整链接）的方案；长例仍按真实可见长度 115 > 45
正常截断成 `'seg1 ... seg8...'`，行为合理。

放弃的东西：

- **A 放弃了链接**：`term_len` 不剥 OSC，短例链接照样被抹；只修好了色码。
- **B 放弃了颜色本身**：输出不再带色，等于把"颜色要保留"这个前提丢了；且
  `strip_ansi` 同样不认 OSC，链接照样保不住。
- **C 的代价**：截断函数里要多维护一份"不可见序列"定义（CSI 与 OSC 两类都得
  认，OSC 还有 `\x07` / `\x1b\\` 两种终止符），与 `_compat._ansi_re` 存在重
  复口径；并且 C 只修第 1 套——`wrap_text`/`measure_table` 里 `term_len` 对
  OSC 链接和全角格宽的错（repro 第 4 组首行 9 词、第 5 组 8 vs 16）原样留
  着，不在本次改动范围内。

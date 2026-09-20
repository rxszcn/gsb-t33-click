# 复现：同一份可见文本，带颜色的短帮助比不带颜色的少留一个词；选项帮助那条路不受影响
import click
from click.formatting import term_len
from click.testing import CliRunner

RED, OFF = "\x1b[31m", "\x1b[0m"
body = " ".join("word%02d" % i for i in range(1, 21))

g = click.Group()
g.command("plain", help=body)(lambda: None)
g.command("colored", help=RED + body + OFF)(lambda: None)

print("=== 1) 子命令列表页的短帮助")
r = CliRunner().invoke(g, ["--help"], env={"COLUMNS": "50"}, color=True)
for line in r.output.splitlines():
    if "plain" in line or "colored" in line:
        stripped = line.replace(RED, "").replace(OFF, "")
        print("   ", line.split()[0].ljust(8), "留下词数", len(stripped.split()) - 1,
              "| 可见宽度", term_len(stripped), "| 行内还有色码 =", "\x1b" in line)

print("=== 2) 选项帮助（同一份文本带不带色）")


@click.command()
@click.option("--alpha", help=body)
@click.option("--beta", help=RED + body + OFF)
def c2(alpha, beta):
    pass


r2 = CliRunner().invoke(c2, ["--help"], env={"COLUMNS": "50"}, color=True)
for line in r2.output.splitlines():
    s = line.replace(RED, "").replace(OFF, "")
    if "word" in s:
        print("   ", s.split()[0].ljust(14), "本行词数", len(s.split()) - 2, "| 可见宽度", term_len(s))

print("=== 3) 两处宽度算法各自的答复")
print("    term_len 对带色的 abcd =", term_len(RED + "abcd" + OFF), "| 同一个串按字符长度数 =", len(RED + "abcd" + OFF))

print("=== 4) OSC-8 超链接走两条路")
from click.utils import _make_default_short_help
from click.formatting import wrap_text

link = "\x1b]8;;https://example.com/a/very/long/path/\x07docs\x1b]8;;\x07"
body4 = " ".join("seg%d" % i for i in range(1, 21)) + " " + link
sh4 = _make_default_short_help(body4, max_length=45)
print("    截断路径产出:", repr(sh4))
print("    整段按字符长度数 =", len(body4), "| term_len 口径 =", term_len(body4), "| 真实可见字符数 =", len(body4.replace(link, "docs")))
short4 = "alpha beta " + link
print("    短例截断产出:", repr(_make_default_short_help(short4, max_length=45)))
print("    该产出里还带着链接 =", "\x1b]8;;" in _make_default_short_help(short4, max_length=45))
print("    wrap_text 对同一段首行:", repr(wrap_text(body4, 45, preserve_paragraphs=False).split("\n")[0]))

print("=== 5) 全角字符在两套口径里的答复")
cjk = "一二三四五六七八"
print("    term_len 对全角八字 =", term_len(cjk), "| 屏幕上占的格 =", len(cjk) * 2)


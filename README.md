# IELTS Practice Log · 雅思练习小记

练完一段口语或写作，记下题目、复盘和下次想改的一点。之后按关键词找回记录，看看上次给自己留了什么任务。

After a speaking or writing session, save the topic, a short reflection and one thing to try next time. Search the notes later to pick up where you left off.

这是一个 Python 命令行小工具，数据保存在本地 SQLite 文件中。只用标准库，无需安装第三方包；已在 Python 3.12 下检查。

A small Python command-line tool using a local SQLite file. It uses only the standard library, with no third-party packages. Checked with Python 3.12.

## 先试一条记录 / Try one record

在仓库目录打开终端，运行下面的命令。示例是合成记录，单独放在 `data/demo.sqlite3`，并非个人练习历史。 / Open a terminal in the repository and run these commands. The synthetic example uses a separate `data/demo.sqlite3` file; it is not a personal practice history.

```sh
python practice_log.py --db data/demo.sqlite3 add --skill speaking --topic "Describe a small tool" --minutes 12 --note "The example needs one more detail." --next-step "Explain how the tool helps." --date 2026-10-17
python practice_log.py --db data/demo.sqlite3 list
python practice_log.py --db data/demo.sqlite3 show 1
```

空数据库中的第一条记录编号为 1，新增时会显示 `Saved practice #1.`。`list` 会显示题目和下一步的简短预览；`show 1` 查看完整复盘。 / The first record in an empty database is #1, and adding it prints `Saved practice #1.`. `list` gives a short preview of the topic and next step; `show 1` reads the full reflection.

正式使用时，可以去掉 `--db data/demo.sqlite3`。默认文件为脚本旁的 `data/practice.sqlite3`，不会随启动目录改变。指定其他文件时，把 `--db` 放在 `add`、`list` 等子命令之前。

For normal use, omit `--db data/demo.sqlite3`. The default file is `data/practice.sqlite3` beside the script, independent of the launch directory. Place a custom `--db` option before the subcommand.

## 查找与备份 / Find and back up

```sh
python practice_log.py list --skill writing
python practice_log.py list --query "example" --since 2026-10-01 --limit 10
python practice_log.py backup data/practice-backup-2026-10-17.sqlite3
```

`--query` 在题目、复盘和下一步中查找原文子串，英文忽略大小写；`%` 等符号按文字匹配。`--since` 包含当天。记录先按练习日期、再按编号倒序排列，默认列出最近 20 条，最多 100 条。

`--query` searches literal text across the topic, reflection and next step, ignoring ASCII letter case. Symbols such as `%` are treated as text. `--since` includes that date. Records are ordered by practice date, then ID, newest first. The default limit is 20, with a maximum of 100.

备份另存为新的 SQLite 文件，已有文件不会覆盖。要从备份继续，先把它复制为一个工作文件，再用 `--db` 指向副本。练习数据库和 `data/` 已加入 `.gitignore`。

Backups are new SQLite files; existing files are never overwritten. To continue from a backup, copy it to a working file and point `--db` at that copy. Database files and `data/` are covered by `.gitignore`.

## 代码怎么读 / Reading the code

`practice_log.py` 把数据库操作和命令行入口放在同一个文件里。新增前检查日期与字段长度；SQL 用参数绑定保存文字，避免引号改变查询。每次新增在一个事务里提交。数据库带有应用标记和版本号，误选其他数据库或新版本文件时会拒绝写入。

`practice_log.py` keeps database functions and the command-line entry point in one file. Inputs are validated before insertion. SQL parameters keep quoted text separate from the query, and each addition commits in one transaction. An application marker and schema version reject unrelated or unsupported databases.

备份使用 [`sqlite3.Connection.backup`](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup)，不用自己拼接或导出 SQL。连接用完会关闭。 / Backups use [`sqlite3.Connection.backup`](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup), with connections closed after use.

运行检查： / Run the checks:

```sh
python -m unittest discover -s tests -v
```

检查覆盖文字往返保存、组合筛选、输入错误、备份独立性、拒绝覆盖，以及真实命令行流程。测试使用临时数据库。 / Checks cover text round-trips, combined filters, invalid input, independent backups, overwrite protection and real command-line workflows. They use temporary databases.

一个小练习：在 `parser()` 中把 `list` 的默认条数从 20 改为 10，录入几条合成记录，检查默认结果与显式 `--limit 2` 的区别；再更新说明。 / For a small code exercise, change the default list limit from 20 to 10 in `parser()`. Add a few synthetic records, compare the default result with `--limit 2`, then update the documentation.

## 当前范围 / Current scope

目前只支持口语与写作的自填记录，没有图形界面、编辑、提醒或同步功能。单次时长为 1–240 整数分钟，题目最多 160 字，复盘最多 8000 字，下一步最多 2000 字。它保存复盘，不评定雅思分数。

The current version records speaking and writing practice. It has no GUI, editing, reminders or synchronization. Sessions take 1–240 whole minutes, topics up to 160 characters, reflections up to 8000 and next steps up to 2000. It stores reflections rather than grading IELTS performance.

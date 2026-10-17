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

## 补写复盘 / Update a reflection

```sh
python practice_log.py --db data/demo.sqlite3 edit 1 --note "Add one concrete example." --next-step "Record the answer again."
python practice_log.py --db data/demo.sqlite3 show 1
python practice_log.py --db data/demo.sqlite3 edit 1 --clear-next-step
```

`edit` 只改指定的文字字段。不写 `--note` 就保留原复盘，不写 `--next-step` 就保留原目标；清空时用 `--clear-note` 或 `--clear-next-step`。同一字段的修改与清空选项不能一起使用。

`edit` changes only the named text fields. Omitting `--note` keeps the reflection; omitting `--next-step` keeps the target. Use `--clear-note` or `--clear-next-step` to empty a field. Setting and clearing the same field together is rejected.

练习日期、题目、时长和创建时间保持原值，`show` 中的 `Created at` 指首次保存时间。长度不合要求时，整次修改不会写入。修改会替换旧文字，目前不保存修改历史；需要保留旧版时先备份。

The practice date, topic, duration and creation time stay unchanged. `Created at` in `show` is the original save time. Invalid text lengths reject the whole edit. Edits replace old text without retaining a history; back up first if you need the earlier version.

## 代码怎么读 / Reading the code

`practice_log.py` 把数据库操作和命令行入口放在同一个文件里。新增前检查日期与字段长度；SQL 用参数绑定保存文字，避免引号改变查询。每次新增在一个事务里提交。数据库带有应用标记和版本号，误选其他数据库或新版本文件时会拒绝写入。

`practice_log.py` keeps database functions and the command-line entry point in one file. Inputs are validated before insertion. SQL parameters keep quoted text separate from the query, and each addition commits in one transaction. An application marker and schema version reject unrelated or unsupported databases.

修改时先校验所有传入字段，再用一条 `UPDATE` 提交。语句只列出指定字段，不会先读出整条记录再覆盖未修改的内容，也不需要改变旧数据库的表结构。 / Editing validates all supplied fields before one `UPDATE`. The statement names only those fields, leaving omitted values in the database untouched. Existing databases need no schema change.

备份使用 [`sqlite3.Connection.backup`](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup)，不用自己拼接或导出 SQL。连接用完会关闭。 / Backups use [`sqlite3.Connection.backup`](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Connection.backup), with connections closed after use.

运行检查： / Run the checks:

```sh
python -m unittest discover -s tests -v
```

检查覆盖文字往返保存、组合筛选、修改与清空、原始信息保留、输入错误、备份独立性、拒绝覆盖，以及真实命令行流程。测试使用临时数据库。 / Checks cover text round-trips, combined filters, editing and clearing, original metadata preservation, invalid input, independent backups, overwrite protection and real command-line workflows. They use temporary databases.

一个小练习：在 `parser()` 中把 `list` 的默认条数从 20 改为 10，录入几条合成记录，检查默认结果与显式 `--limit 2` 的区别；再更新说明。 / For a small code exercise, change the default list limit from 20 to 10 in `parser()`. Add a few synthetic records, compare the default result with `--limit 2`, then update the documentation.

## 当前范围 / Current scope

目前只支持口语与写作的自填记录，可以修改复盘与下一步；没有图形界面、提醒或同步功能。单次时长为 1–240 整数分钟，题目最多 160 字，复盘最多 8000 字，下一步最多 2000 字。它保存复盘，不评定雅思分数。

The current version records speaking and writing practice, with editable reflections and next steps. It has no GUI, reminders or synchronization. Sessions take 1–240 whole minutes, topics up to 160 characters, reflections up to 8000 and next steps up to 2000. It stores reflections rather than grading IELTS performance.

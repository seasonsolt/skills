# Skill 源码测试

本目录是 `java-unit-test-hardening` 自带的源码测试，覆盖 `scripts/`、`SKILL.md` 契约、模板和独立运行边界。

在 skill 根目录运行：

```bash
python3 -m pytest tests/ -q
```

全部用例只依赖 skill 自身、Python 标准库、Git 和 pytest；不要求 ai-workspace、CodeGraph、TAPD、OpenSpec 或 Maven。

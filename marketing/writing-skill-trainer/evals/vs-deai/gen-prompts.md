# 生成提示词

每个条件跑 2 次（`<k>` = 1、2），每次是一个独立的 agent，一次写完三个场景。四份提示词的“规则”段相同，只有开头不同。`<work>` 是本目录下的 `work/`。

## 共用规则

```text
Rules:
- Read only the files listed above. Do not read any other file or directory on this machine.
- This is offline writing; you cannot ask questions. The material in each task file is all the information you have. Write each piece in the language of its task file.
- Follow each task's length range and its "do not add" constraints strictly.
- Save each piece to <work>/out/<condition>-<k>/<scenario>.md. The file contains only the piece itself (a title line is optional); no notes, no word counts.
- After writing, measure each piece with python3 and revise if it is out of range. Chinese pieces: count all non-whitespace characters, excluding Markdown heading lines. English piece: count whitespace-separated words, excluding heading lines.

Final reply: only the file paths and their measured lengths.
```

## direct

```text
You are a writer. Complete three independent writing tasks.

Task files (each states the task, the length range and the material):
- <work>/restrained-satire/task.md
- <work>/tech-news/task.md
- <work>/twain-essay/task.md
```

## stopslop

```text
You are a writer. Complete three independent writing tasks, and use the "stop-slop" writing skill while drafting and before delivering.

First read the skill completely: SKILL.md, references/phrases.md, references/structures.md, references/examples.md

Apply the skill's rules and quick checks to all three pieces. Two tasks are in Chinese: apply the rules there as far as they carry over to Chinese.

Task files: (same three)
```

## humanizer / humanizer-samples

```text
You are an editor. Use the "humanizer-zh" skill to edit three existing drafts.

First read the skill completely: humanizer-zh/SKILL.md

Drafts to edit (the user asks: "用 humanizer-zh 润色这篇稿子，让它更自然"):
- <work>/out/direct-<k>/restrained-satire.md, tech-news.md, twain-essay.md

Each draft was written for a task that the edited text must still satisfy (length range, material, "do not add" constraints). The task files: (same three)

One draft is in English: apply the skill there as far as its rules carry over to English, and keep the text in English.
```

`humanizer-samples` 另外加两处：用户的请求改为“……让它更自然，并且更像我给的三篇样本的作者”；每篇稿件列出同场景的 `train/sample-1.md`、`sample-2.md`、`sample-3.md` 作为作者样本，并注明按 skill 里“匹配作者声音：有样本时借鉴”的规则使用，不照抄样本句子。

## trained

```text
You are a writer. Complete three independent writing tasks. Each task has its own Writing Skill that you must load and follow for that task.

For each scenario in: restrained-satire, tech-news, twain-essay
- First read the scenario's skill completely: <scenario>/skill/SKILL.md and <scenario>/skill/references/style-profile.md
- Then read the task: <scenario>/task.md
- Write the piece following that skill's workflow and self-checks.
```

`trained` 的稿件如果带交付说明，放在一行 `---` 之后；评审前会去掉。

## 训练 skill 的提示词

三个场景各用一个 agent，读 `skills/writing-skill-trainer/` 和本场景的 3 篇训练样本，只做 trainer 的 Phase 0—2（范围、证据台账、最小 skill v1），不跑生成、评审和进化轮。离线，不能提问；不读留出样本、任务文件和其他场景。要求 skill 里不出现样本原句，并带任务契约：保留素材里的每条事实，不新增素材外的事实、数字、人物、引语，字数在要求范围内。

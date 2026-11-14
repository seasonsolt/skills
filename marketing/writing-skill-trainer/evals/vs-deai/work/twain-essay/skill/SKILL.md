---
name: deadpan-essay
description: >-
  Writes a humorous first-person English essay from a user-supplied (usually fictional) fact pack
  and a word-count range, using a classic deadpan mechanism set: a narrator who earnestly defends
  a wrong conclusion, mock-rigorous reasoning built from the supplied facts, escalation by
  repetition, long-run/short-verdict sentence rhythm, understatement and register mismatch.
  Use when the user asks for a funny/comic/satirical/deadpan first-person essay, sketch or column
  from given material and length. Keeps every supplied fact and adds none.
---

# Deadpan Essay

Status: v1, provisional (rules extracted from 3 samples; not yet validated by blind evaluation).

Before drafting, **read `references/style-profile.md`** in full. It holds the mechanisms, knobs, anti-patterns and the style self-check. This file holds the task contract and the workflow.

## 1. Input check

You need:
1. **Fact pack**: the material (events, people, numbers, objects, any quoted words).
2. **Length**: a word range, e.g. 600-800 words. Words = whitespace-separated tokens of the essay body, title excluded.
3. Optional: audience, title wish, format notes.

If the length is missing, use 600-900 words and say so in the delivery note. If the fact pack is missing, ask for it; do not write an essay from nothing.

Boundaries:
- Write in an original voice. Do not imitate, name or quote any real author, and do not present the essay as written by one.
- If the material contains real private people, sensitive personal data, or defamatory claims about real people, stop and report instead of joking about it.

## 2. Task contract (overrides every style rule)

1. **Keep every supplied fact.** Each fact in the pack appears in the essay, stated accurately (numbers, names, dates, sequence, outcomes). You may reorder, reframe and misinterpret *as the narrator*, but the fact itself stays true on the page.
2. **Add nothing factual.** No new facts, events, numbers (including numbers computed from supplied ones: no totals, ratios, percentages, averages), people, named places, brands, organisations, sources or quotations.
   - Quoted speech only for words the pack presents as spoken or written. Otherwise use indirect speech that adds no new claim, or the narrator's own unquoted thoughts.
   - Do not give anyone in the pack a goal, promise, decision or opinion the pack does not support.
   - Comparisons and imagery are allowed only if they introduce no checkable claim.
3. **Stay inside the word range.** Aim for the middle. If the material honestly cannot reach the lower bound, deliver close to it and say so in the delivery note; never pad with invented events, scenes or reflections.
4. **First person, English, humorous essay** in continuous prose, unless the user asks for another format.
5. Explicit user instructions beat anything in the style profile.

## 3. Workflow

1. **Inventory the facts.** List every supplied fact as a numbered checklist (private working notes, not output). Mark which are numbers, which are people, which are quoted words, which are concrete moments (where, what was done, what happened).
2. **Check scene material.** Does the pack contain at least one concrete moment involving the narrator? If yes, that is your scene. If no, build the essay from the facts as reasoning and commentary, do not invent a scene, and write "missing scene material" in the delivery note.
3. **Find the wrong premise.** From the facts, pick one inverted conclusion the narrator can sincerely defend (style-profile §1a), and the real foible underneath it (§1c). Test: can the premise be argued using only supplied facts? If not, pick a smaller one.
4. **Choose the engine** that the material supports (style-profile §2-3):
   - several attempts/incidents → escalating series;
   - numbers or comparisons → mock-rigorous reasoning (no new figures);
   - an expert, rule, sign or saying in the pack → mock authority;
   - a procedure or common habit → optional "you" instruction section.
   Use one main engine; a second only if the material clearly supports it.
5. **Plan the arc** in 4-6 beats: entry → facts as evidence → engine → peak → narrator acts on his wrong conclusion → turned ending. Assign every fact on the checklist to a beat. Place the strongest concrete fact at the peak.
6. **Draft** following the profile: earnest narrator, facts stated flatly, long runs resolving into short verdicts, understatement of harm, dignity for trivia, 1-3 asides, at most one emphasized word, modern vocabulary.
7. **Skip what lacks material.** Any move that needs content the pack does not give (an authority, a setback to understate, a procedure to teach, a quoted exchange to open with, a third attempt) is skipped, not supplied.
8. **Run the pre-delivery check** (§4), fix, then deliver (§5).

## 4. Pre-delivery check (hard constraints first)

1. **Length**: count the words of the body. Inside the range? If not, cut or (only with supplied material) expand.
2. **Fact coverage**: tick every item on the fact checklist. Any missing → add it. Any altered (number, name, order, outcome) → restore it.
3. **Additions scan**: read every sentence and ask: does this assert a fact, number, person, place, brand, source or quotation that is not in the pack? Includes computed numbers and goals/decisions attributed to people. Remove or rephrase each one.
4. **Originality**: no sentence or distinctive phrase from any famous humorist; no period pastiche.
5. **Style self-check**: run style-profile §9 and the anti-pattern list in §8. No rule names or method words in the essay.
6. **Format**: first person, English prose, title only if asked or clearly useful (title does not count toward length).

## 5. Output

Default output:

```
[optional title]

[essay body]

---
Delivery note: <word count>; <"all supplied facts used" or list of any omitted with reason>;
<"missing scene material" if applicable>; <"below lower bound: material exhausted" if applicable>.
```

The delivery note is separate from the essay and never contains jokes or rule names.

Failure report (instead of an essay) when the fact pack is missing, contradictory in a way that blocks writing, or raises the boundary issues in §1:

```
Cannot write yet: <reason>. Needed: <specific item(s)>.
```

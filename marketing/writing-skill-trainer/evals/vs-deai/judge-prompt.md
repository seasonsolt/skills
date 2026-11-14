You are a blind judge of writing. You will compare five anonymous drafts per task. You do not know how any draft was produced, and you must not guess.

## Material
Directory {PACKET}/ has three sub-directories: restrained-satire, tech-news, twain-essay. Each holds:
- task.md: the user's task, the length range and the material. The material is the only source of facts.
- ref.md: a piece by the target author (or outlet) that none of the drafts' writers saw. Use it only to learn how this author writes: how judgments are made, how detail and evidence are used, narrator stance, structure, rhythm. It is not a source of facts, and its topic, period and vocabulary are not the target.
- V.md, W.md, X.md, Y.md, Z.md: five anonymous drafts for the task. The letters are assigned at random and differ between tasks.

Read only these files. Do not read any other file or directory.

Lengths were checked by a program and all drafts are inside the range. Do not count, do not penalize length, and do not reward a draft for being longer or fuller.

## What to decide for each task
1. voice_ranking: order the five drafts from closest to farthest from the way the author of ref.md writes. Compare writing mechanisms, not surface features: a draft that pastes period vocabulary, catchphrases or mannerisms on top of generic prose is not close. A draft that copies the reference's topic is not close either.
2. fact_violations: for each draft, list every place where it breaks the task's own fact constraints as stated in task.md. Check item by item against the material:
   - a supplied fact is changed, contradicted, or dropped when dropping it changes the outcome;
   - where task.md forbids additions (facts, numbers, people, quotations, evaluations), each addition. Quote the passage.
   - where task.md is a fiction task that does not forbid additions, invented texture (gesture, setting, sound) is allowed; list only new events, people, numbers or outcomes that change what the material says happened.
   Use an empty list when there is nothing.
3. ai_tells: for each draft, quote up to three passages that read as stock machine-written prose (empty setup, false contrast, aphorism ending, forced triplets, inflated significance, tidy moral). Empty list when there is nothing.
4. overall_ranking: order the five drafts from best to worst as the piece the user should publish for this task, weighing task fulfilment, fact discipline and voice together. A draft with a fact violation ranks below every draft without one.

Be exacting. Ties are not allowed in the rankings, but say in `notes` when two neighbours are nearly indistinguishable.

## Output
Write one JSON file {PACKET}/verdicts.json. Top-level keys are exactly the three task ids. Each value uses exactly these field names:
- "voice_ranking": list of the five letters, closest first
- "overall_ranking": list of the five letters, best first
- "fact_violations": {"V": [...], "W": [...], "X": [...], "Y": [...], "Z": [...]}
- "ai_tells": {"V": [...], "W": [...], "X": [...], "Y": [...], "Z": [...]}
- "voice_reason": one sentence on what separates the top draft from the bottom draft in voice
- "notes": string, optional

After writing, confirm with python3 that the file parses and that each ranking contains each of V, W, X, Y, Z exactly once. Final reply: for each task, one line with the two rankings.

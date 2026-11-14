# Evidence Ledger — deadpan-essay skill v1

Status: provisional (Phases 0-2 only; no generation, judging or evolution has been run; `eval_mode`: none yet)

## 0. Scope record (Phase 0 / input contract)

| Item | Recorded value |
|---|---|
| Mode | Multi-sample extraction ("多篇提炼"), Phases 0-2 only; evaluation run by an external process |
| Samples | 3 training samples, English, Markdown, full text readable: `train/sample-1.md` (~800 words), `train/sample-2.md` (~1,440 words), `train/sample-3.md` (~1,190 words) |
| Genres covered | S1 mock-argument / mock-lecture; S2 first-person narrative of a lesson that turns into mock instruction; S3 first-person anecdote that turns into mock-statistical argument |
| Authorization | Public-domain essays by a long-dead author. Only mechanisms are transferred; the skill must not impersonate the source author or claim his name |
| Target task | User supplies a fictional fact pack + word range; skill writes a humorous first-person English essay using the mechanisms |
| Target reader | General English-language readers of humorous essays (assumed; not specified) |
| Length unit | Words (whitespace-delimited tokens), per the task brief |
| Holdout | Managed externally by the evaluation process; not read here. All three training samples were used for extraction |
| Test prompts | Not authored in this run (Phase 0 test design delegated to the external evaluator, which owns the prompts and holdout) |
| Output location | `work/twain-essay/skill/` as instructed; no existing skill overwritten |
| Workspace / git | No branch, commit or snapshot made; the caller did not request one and the evaluator controls versioning |

### Assumptions (offline: nobody could be asked, conservative defaults chosen)

- A1. Period selection: samples come from one author and one broad period; no period knob needed. Period vocabulary and spellings are treated as surface, not mechanism, and are banned from output.
- A2. Derived numbers: the mock-arithmetic mechanism tempts the writer to compute new figures. Conservative default: no new numerals or quantities, including results of arithmetic on supplied numbers. The writer may combine supplied numbers in words only when the result is already stated or trivially restates them (for example, comparing which of two supplied numbers is larger).
- A3. Quotations: no quoted speech except words the fact pack itself presents as said. The narrator's own thoughts may be rendered as unquoted inner reasoning, since the narrator is the persona the user asked for.
- A4. People: only people/roles named in the pack. The narrator ("I") is allowed. Unnamed crowds already implied by the pack (e.g., "the other passengers" when the pack mentions a crowded train) are allowed as background but never given actions or words that change facts.
- A5. Scene material (trainer §7.1): asking the author is impossible offline and the material is fictional. The skill therefore uses the pack's events as the narrator's scene, and when the pack holds no concrete moment it writes from the facts and says "missing scene material" in the delivery note instead of inventing one.
- A6. Length: when the pack cannot honestly fill the lower bound, deliver near the lower bound and say so in the delivery note; never pad with invented events.

## 1. Article map (paraphrased, no long quotations)

### S1 — mock lecture defending an art that has decayed
1. Task: persuade (mock) an in-group audience that a vice is a virtue that needs better practice.
2. Reader conflict: reader assumes the vice is bad; narrator never argues that point and instead complains about poor craftsmanship.
3. Structure: thesis clarified by distinction → humble-pose preamble → mock syllogism → appeal to proverb and a cited authority → sweeping claim that everybody does it → one concrete social custom used as the case study → refusal to give further particulars.
4. Language: long periodic sentences stacked with dashes and semicolons; short flat verdicts close long stretches; elevated diction applied to a low subject; bracketed aside about the audience.
5. Evidence: one concrete numeric anecdote (calls paid vs. hosts who were absent) carries the joke; the number pair does the work, not adjectives.
6. Safety: contains quoted authority and named public figures; these are source facts, never transferable.

### S2 — narrator learns to ride a bicycle with an instructor
1. Task: narrate (comic) a learning ordeal, then shift to mock how-to.
2. Reader conflict: reader expects a story of learning; narrator reports each disaster as a success or a credit to the machine.
3. Structure: decision → equipment → instructor's plan → repeated crashes with instructor repositioning each time (escalation) → injury reported flatly → absurd self-praise → general "law" of counterintuitive motion → digression comparing with learning a foreign language → second-person instructions for mounting/dismounting, each ending in a fall → final simile punch.
4. Language: plain narrative sentences; flat short sentence after each catastrophe; machine personified as a young animal; shift from "I" to generic "you".
5. Evidence: specific measurements and counts (wheel size, number of falls, days in hospital) make the absurd concrete.
6. Safety: no sensitive data; the brand name and the instructor are source facts, not transferable.

### S3 — narrator fears his bed more than the railway
1. Task: comic anecdote that becomes a mock statistical argument with an inverted moral.
2. Reader conflict: reader believes travel is dangerous; narrator "proves" home is the deadly place.
3. Structure: in-medias-res exchange at a ticket window that makes no sense → backstory of years of travel with no accident, framed as bad luck in a lottery → turns to doing sums → chain of figures, each step plausible, conclusion absurd → mock alarm and resolution → bracket pointing back to the opening → stated moral that inverts into a real point about public grumbling.
4. Language: emphatic capitals on the key reversal; exclamation only at peak alarm; long arithmetic sentences, short reaction sentences.
5. Evidence: numbers are the engine of the joke; a misapplied ratio produces the absurdity; one self-admitted vagueness about a figure.
6. Safety: real places, company names and statistics are source facts, never transferable; derived numbers are the main fabrication risk for the target task.

## 2. Rule ledger

Columns: rule_id | observation | source_refs | evidence_note | effect | scope | confidence | negative_case | fallback | promote_to

| rule_id | observation | source_refs | evidence_note | effect | scope | confidence | negative_case | fallback | promote_to |
|---|---|---|---|---|---|---|---|---|---|
| R-STANCE-01 | Narrator adopts an absurd or inverted premise and defends it in complete earnest; never winks or admits the joke | S1 ¶1-2; S2 ¶1 (crash = fast dismount); S3 ¶1 (bed > train) | All three essays hold a wrong premise straight-faced from first to last line | Reader does the laughing; narrator's sincerity is the joke | invariant | high | None found among samples | If the pack suggests no inversion, pick the narrator's mildest misjudgment of a supplied fact; never invent a new event to create one | style-profile §1, SKILL.md workflow |
| R-STANCE-02 | Narrator reads his own failure, loss or ignorance as achievement, prudence or bad luck | S2 (falls praised, injury credited to prudence); S3 (no accident = losing lottery); S1 (humble pose that is really a boast of the club) | Present in 3/3 with different targets | Self-deprecation without self-pity; builds affection for narrator | invariant | high | S1 aims more at the audience than the self | If the pack has no narrator setback, aim the misreading at a supplied object or custom instead | style-profile §1 |
| R-LOGIC-01 | Mock-rigorous reasoning: each step plausible, connective words ("so", "therefore", "it follows") march the reader to an absurd conclusion | S1 ¶2-3 (syllogism, proverb deduction); S3 ¶1 (ratio chain); S2 (law of falling direction → method for a language) | 3/3, three different engines: syllogism, arithmetic, analogy-as-law | Absurdity feels earned, not random | invariant | high | — | Use only supplied facts as premises; if the pack has no numbers, reason by categories or sequence, not arithmetic | style-profile §2 |
| R-FACT-01 | The joke rides on a concrete, specific fact (a count, a measure, a pair of numbers, a named object) stated flatly; adjectives do little | S1 ¶4 (calls vs. absent hosts); S2 (wheel size, number of falls, days); S3 (miles, deaths) | 3/3 | Specificity makes the absurd believable and supplies the punch | invariant | high | — | Use supplied facts only; if the pack is thin on specifics, use its plainest concrete noun; never invent a figure | style-profile §2, SKILL.md contract |
| R-FACT-02 | Facts are misframed, not misstated: the number/event stays true, the narrator's interpretation is what goes wrong | S3 (true-looking figures, wrong ratio); S2 (true crash, praised as skill) | 2/3 explicit; S1 uses true custom with inverted valuation | Keeps comedy from depending on falsehood | invariant (target-task safety bridge) | medium | S3 includes one deliberate vagueness about a figure | Never alter a supplied fact for a laugh; misread its meaning instead | SKILL.md contract, style-profile §2 |
| R-ESC-01 | Repetition with escalation: the same attempt or item recurs with one variable changed and a worse or wider result | S2 (instructor moves each time, crash repeats); S3 (daily ticket → monthly bundle → quit); S1 (list of when everybody lies widening to sleep and gestures) | 3/3 | Builds rhythm and anticipation; the third or fourth turn lands hardest | invariant | high | — | If the pack lists only one attempt, escalate across the narrator's interpretations, not across invented attempts | style-profile §3 |
| R-RHYTHM-01 | Long accumulating sentence (semicolons, dashes, lists) followed by a short flat verdict sentence | S1 (long periods, then terse judgment); S2 (each crash, then a short calm line); S3 (arithmetic run, then short reaction) | 3/3 | Deadpan timing; the short line is where the laugh lands | invariant | high | — | Always applicable; no material needed | style-profile §4 |
| R-DICTION-01 | Register mismatch: dignified, formal or technical wording for a low or trivial matter, and plain wording for disaster | S1 (art, virtue, lament for a vice); S2 (praise for machine construction; injury told mildly); S3 (statistical gravity for beds) | 3/3 | Mock-heroic lift and understatement both come from mismatch | invariant | high | — | Always applicable; use modern vocabulary, never period words | style-profile §4 |
| R-UNDER-01 | Understatement of pain, damage or embarrassment | S2 (hospital stay told as routine); S3 (no bone broken told as disappointment); S1 (social pain called a mild deflection) | 3/3 | Makes harm funny without cruelty | invariant | high | — | If pack has no harm or setback, skip | style-profile §4 |
| R-ASIDE-01 | Self-interrupting asides: dashes that break off a name or thought, brackets addressing the reader, a refusal to give "particulars" | S1 (several broken-off sentences, bracket about the room); S3 (bracket pointing back to opening); S2 (parenthetical pedantry about a word) | 3/3, varying density (heavy S1, light S2/S3) | Creates a talking voice and comic retreat | invariant (density is a knob) | medium | S2 uses only one | Use 1-3 per essay; asides may never carry new facts | style-profile §5 |
| R-TARGET-01 | Under the absurd conclusion sits a real, recognisable human foible that the essay actually exposes (social pretence, alarmist press, the body's stubborn habits) | S1 (polite hypocrisy); S3 (sensational reporting, public grumbling); S2 (instinct vs. learning) | 3/3 | Gives the humor a point; ending can tilt toward it | invariant | medium | S2's target is gentler and less social | If the pack implies no foible, aim at the narrator's own misplaced confidence; do not invent a social claim | style-profile §1, §6 |
| R-AUTH-01 | Mock authority: the narrator cites proverbs, experts, records or his own "research" earnestly in support of the absurd premise | S1 (proverb, historian); S2 (the Expert's assurances); S3 (statistics, census) | 3/3 | Parodies argument by evidence | conditional (requires an authority in the pack) | medium | — | Only authorities, documents, experts or sayings present in the pack; otherwise the narrator's own observation is the only "evidence". Never invent a quotation or a source | style-profile §2, SKILL.md contract |
| R-ANALOGY-01 | Homely comparison that is apt and deflating (an animal for a machine, a domestic image for a fiasco), usually one per stretch, often at the end | S2 (young horse for bicycle, burning house simile, language-learning digression); S1 (one comparison for his humble position) | 2/3 | Fast picture, comic deflation | conditional | medium | S3 has almost none | Optional knob; 0-3 per essay; comparisons may not introduce facts | style-profile §4 |
| R-PERSON-01 | Shift from "I" narrative to generic "you" instruction or "we" generalization once a lesson is extracted | S2 (second half is how-to); S1 ("we", "none of us") | 2/3 | Turns private fiasco into universal mock-advice | conditional | medium | S3 stays in "I" until the advice line | Use when the pack involves a learnable procedure or a common habit; otherwise stay in "I" | style-profile §3 |
| R-END-01 | Ending lands on a short reversal or a mock moral that tilts toward the real target; no summary, no sincere lesson | S3 (inverted moral); S2 (final simile punch); S1 (abrupt refusal of more particulars) | 3/3 end on a punch; only S3 states a "moral" | Leaves on the laugh | invariant (form is a knob) | medium | S1's ending is a retreat rather than a moral | If the pack offers no takeaway, end on the narrator's last misreading of a supplied fact | style-profile §6 |
| R-OPEN-01 | Opening varies: odd exchange in medias res (S3), decision mid-thought (S2), clarifying distinction of the thesis (S1) | S1-S3 openings | 3 different openings | Shows openings are not templated | invariant as freedom; surface form is a knob | high | — | Pick an opening type from the pack's material; dialogue opening only if the pack supplies the words | style-profile §3 |
| I-01 | Explicit stated-moral formula announcing the lesson of the piece | S3 end | 1/3 | — | incidental | — | — | — | not promoted (would become a template) |
| I-02 | Language-learning digression | S2 | 1/3 | — | incidental | — | — | — | not promoted; generalized only as "a digression that returns as method" knob inside R-ANALOGY-01 |
| I-03 | Pretended uncertainty about a figure | S3 | 1/3 | — | incidental + safety risk | — | — | — | not promoted: would blur supplied facts |
| I-04 | All-caps emphasis / italic emphasis on single words | S2, S3 caps; S1 italics | surface typography | — | incidental surface | — | — | — | knob only: at most one emphasized word per essay |
| I-05 | Period diction and spellings (contractions of the era, antique words) | S1-S3 | surface | — | incidental surface (banned) | — | — | — | banned in style-profile anti-patterns |
| S-01 | Keep every supplied fact; add no facts, numbers, people, places, brands, quotations | task brief | user constraint | — | safety / user_constraint | — | — | — | SKILL.md contract |
| S-02 | No sentences or distinctive phrases copied from the source author; no imitation of his name, signature, or famous lines | trainer hard rule 2 | — | — | safety | — | — | — | SKILL.md, style-profile anti-patterns |
| S-03 | Length within requested word range | task brief | user constraint | — | safety / user_constraint | — | — | — | SKILL.md contract |
| S-04 | Do not reproduce source typos or OCR-style defects | §3 below | — | — | safety | — | — | — | style-profile anti-patterns |

Counts: invariant 13 (R-STANCE-01/02, R-LOGIC-01, R-FACT-01/02, R-ESC-01, R-RHYTHM-01, R-DICTION-01, R-UNDER-01, R-ASIDE-01, R-TARGET-01, R-END-01, R-OPEN-01), conditional 3 (R-AUTH-01, R-ANALOGY-01, R-PERSON-01), incidental 5, safety 4.

Promotion note: trainer §3 allows core candidacy at ≥3 samples across ≥2 genres; all invariants meet that bar but remain **candidates pending regression** — no rule is `validated` until the external evaluation runs.

Counter-example check: no sample lacks the deadpan stance, the fact-carries-joke move, or the long/short rhythm, so these stay core. Asides and analogies vary strongly in density, so they are knobs with ranges, not quotas.

## 3. Corpus defects (not to be learned as style)

- S2: typo "a" for "and" in the opening purchase sentence; a duplicated "in" in the mounting instructions; a garbled verb phrase after the first crash; entire text flattened to one paragraph.
- S3: "the the lot" (duplicated word); entire text flattened to one paragraph; stray space before "--or".
- S1: excerpt ends mid-essay (continues in the original); underscore italics are Markdown artifacts.
- Paragraphing in all samples is unreliable, so no rule about paragraph length was extracted (rhythm rules are sentence-level only).

## 4. Originality note

The skill files contain no sentence copied from the samples. Examples are freshly written on unrelated subjects. Short paraphrases above serve only to locate evidence.

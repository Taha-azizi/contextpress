# Long-document benchmark (solid prose)

Tier 1 only, profile **`rag_doc`**, `token_budget=None`. This is the study for continuous text — essays, books, and encyclopedia articles — not chat logs and not tool JSON.

The 222-item fidelity report is still the chat/agent headline ([`INFO_FIDELITY.md`](INFO_FIDELITY.md)). It under-represents this job: almost every item there is a conversation, and the seven “files” rows are short repo docs.

## Method

1. Take a public-domain Gutenberg book or a CC BY-SA Wikipedia extract.
2. Cut a passage of about **2k / 8k / 20k** cl100k tokens (skip the first
   ~1.5k tokens of a long book so the window is body text, not the title page).
3. Pick an **anchor sentence** in the first fifth of that passage and ask
   a question that quotes its opening words. The question is the last user
   turn, so recency and trim are not allowed to rewrite it.
4. Compress twice:
   - **monolith** — system + one passage turn + question.
   - **chunked** — system + section turns (~700 tokens, at least 8) + question.
5. Record token savings, wall time, whether the question and system turn
   are byte-identical, **anchor-word retention** (content words of length
   ≥ 5 from the anchor sentence, whole-word match in the compressed
   passage), and **number retention** (unique 3+ digit numbers, decimals,
   and ISO dates from the full passage).

Full source text is not committed (`benchmarks/data/` is gitignored).
Re-run: `python -m benchmarks.run_longform`.

### Why two packings

Turn-level recency still skips the last three non-system turns, and
trim still needs a longer thread than a passage plus a question.
From 0.7.3, `medium` and `high` also sentence-rank a `rag_doc` turn
longer than 1,500 tokens when it is not the question. `low` does not.
Chunked sections in this study stay under that bar, so they still
show the older turn-level path.

### Sources

| id | title | kind | license |
| --- | --- | --- | --- |
| `austen-pnp` | Pride and Prejudice | fiction | Public domain (Project Gutenberg) |
| `shelley-frank` | Frankenstein | fiction | Public domain (Project Gutenberg) |
| `melville-moby` | Moby-Dick | fiction | Public domain (Project Gutenberg) |
| `dickens-cities` | A Tale of Two Cities | fiction | Public domain (Project Gutenberg) |
| `darwin-origin` | On the Origin of Species | nonfiction | Public domain (Project Gutenberg) |
| `smith-wealth` | The Wealth of Nations | nonfiction | Public domain (Project Gutenberg) |
| `machiavelli-prince` | The Prince | nonfiction | Public domain (Project Gutenberg) |
| `wells-worlds` | The War of the Worlds | fiction | Public domain (Project Gutenberg) |
| `wiki-french-rev` | French Revolution | nonfiction | CC BY-SA (Wikipedia extract; text not republished) |
| `wiki-roman` | Roman Empire | nonfiction | CC BY-SA (Wikipedia extract; text not republished) |
| `wiki-dna` | DNA | nonfiction | CC BY-SA (Wikipedia extract; text not republished) |
| `wiki-photosynthesis` | Photosynthesis | nonfiction | CC BY-SA (Wikipedia extract; text not republished) |

### Sources skipped

- wiki-dna 20k: passage shorter than 70% of target, skipped
- wiki-photosynthesis 20k: passage shorter than 70% of target, skipped

## Headline

Every row reports **token save**, **information loss**, and
**adjusted save** (`token save − information loss`).
Information loss pools the asked sentence (filler words excluded),
numbers, and same-line two-word names. Anchor and number columns
are the parts of that loss.


### Chunked passage (`rag_doc` retrieval context)

| length | preset | n | token save | info loss | adjusted save | anchor kept | numbers kept | names kept |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2k | `low` | 12 | 3.9% | 0.3% | 3.6% | 99.4% | 100.0% | 100.0% |
| 2k | `medium` | 12 | 11.9% | 0.3% | 11.6% | 99.4% | 100.0% | 100.0% |
| 2k | `high` | 12 | 37.4% | 0.3% | 37.1% | 99.4% | 100.0% | 100.0% |
| 8k | `low` | 12 | 7.0% | 1.2% | 5.8% | 96.4% | 100.0% | 98.5% |
| 8k | `medium` | 12 | 16.2% | 2.7% | 13.4% | 96.4% | 100.0% | 95.6% |
| 8k | `high` | 12 | 61.4% | 6.2% | 55.2% | 95.2% | 100.0% | 89.6% |
| 20k | `low` | 10 | 6.1% | 0.4% | 5.7% | 96.3% | 100.0% | 99.9% |
| 20k | `medium` | 10 | 21.8% | 0.3% | 21.6% | 96.3% | 100.0% | 100.0% |
| 20k | `high` | 10 | 79.3% | 18.6% | 60.7% | 96.3% | 100.0% | 73.2% |

### Single pasted passage (monolith)

| length | preset | n | token save | info loss | adjusted save | anchor kept | numbers kept | names kept |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2k | `low` | 12 | 6.1% | 0.3% | 5.8% | 99.4% | 100.0% | 100.0% |
| 2k | `medium` | 12 | 52.7% | 0.3% | 52.4% | 99.4% | 100.0% | 100.0% |
| 2k | `high` | 12 | 88.3% | 0.3% | 88.0% | 99.4% | 100.0% | 100.0% |
| 8k | `low` | 12 | 6.1% | 0.1% | 6.0% | 100.0% | 100.0% | 99.8% |
| 8k | `medium` | 12 | 55.6% | 1.7% | 53.9% | 100.0% | 100.0% | 96.8% |
| 8k | `high` | 12 | 95.8% | 17.6% | 78.2% | 100.0% | 100.0% | 67.2% |
| 20k | `low` | 10 | 6.9% | 0.4% | 6.6% | 96.3% | 100.0% | 99.9% |
| 20k | `medium` | 10 | 56.1% | 11.5% | 44.6% | 96.3% | 100.0% | 83.6% |
| 20k | `high` | 10 | 98.0% | 37.4% | 60.6% | 95.7% | 100.0% | 45.8% |

## Where the tokens go (chunked, mean tokens removed per stage)

Figures are the mean of tokens removed (`-token_delta`) across every
work in the cell. A stage that did not change the text counts as zero,
so a dash is not hiding a subset. `structure` is on for `rag_doc` and
does nothing to clean prose. Lexical, abbrev, alias, and resolution
stay off on this profile.

| length | preset | structure | filler | repetition | trim | recency |
| --- | --- | --- | --- | --- | --- | --- |
| 2k | `low` | 0.0 | 78.3 | 0.0 | 0.0 | 0.0 |
| 2k | `medium` | 0.0 | 78.3 | 0.0 | 0.0 | 165.3 |
| 2k | `high` | 0.0 | 78.3 | 0.0 | 638.7 | 72.8 |
| 8k | `low` | 0.0 | 413.5 | 143.7 | 0.0 | 0.0 |
| 8k | `medium` | 0.0 | 413.5 | 143.7 | 0.0 | 761.6 |
| 8k | `high` | 0.0 | 413.5 | 143.7 | 4284.2 | 206.0 |
| 20k | `low` | 0.0 | 1218.2 | 0.0 | 0.0 | 0.0 |
| 20k | `medium` | 0.0 | 1218.2 | 0.0 | 0.0 | 3204.0 |
| 20k | `high` | 0.0 | 1218.2 | 0.0 | 14333.7 | 294.2 |

## Fiction vs nonfiction (chunked, 8k tokens)

| kind | preset | n | token save | info loss | adjusted save |
| --- | --- | ---: | ---: | ---: | ---: |
| fiction | `low` | 5 | 7.2% | 0.3% | 6.9% |
| fiction | `medium` | 5 | 24.5% | 6.3% | 18.2% |
| fiction | `high` | 5 | 62.5% | 10.5% | 52.0% |
| nonfiction | `low` | 7 | 6.8% | 1.7% | 5.1% |
| nonfiction | `medium` | 7 | 10.2% | 0.6% | 9.6% |
| nonfiction | `high` | 7 | 60.7% | 3.7% | 57.0% |

## Gutenberg vs Wikipedia (monolith, 8k)

This table is `low` only. 19th-century books contain filler words
the stage strips (`very`, `quite`, `rather`). Encyclopedia extracts
mostly do not. `medium` and `high` no longer stay on this row.

| family | n | token save | info loss | adjusted save |
| --- | ---: | ---: | ---: | ---: |
| gutenberg | 8 | 8.8% | 0.2% | 8.6% |
| wikipedia | 4 | 0.6% | 0.0% | 0.6% |

## Contracts

- Question turn byte-identical: **204/204**.
- System turn byte-identical: **204/204**.
- On `rag_doc`, filler does not rewrite the last user turn, so a
  quoted question that contains `very` or `quite` stays intact.

## What the numbers say

- **A pasted chapter gets `medium` and `high` inside the turn (0.7.3).**
  A `rag_doc` turn over 1,500 tokens that is not the question is cut
  to sentences that match the question, plus a lead. Monolith 8k mean
  save is `low` **6.1%**, `medium` **55.6%** (anchor 100.0%), `high` **95.8%**. Monolith 20k `high` is **98.0%** save
  with anchor 95.7%. `high` keeps a two-sentence lead plus matches. Passage numbers
  are 100.0% at 20k.
- **Chunk the passage and `medium` starts to move, with a wide spread.**
  Quote the median: chunked `medium` is **5.8%** / **10.3%** / **12.3%** at 2k / 8k / 20k (means 11.9%, 16.2%, 21.8%; sd 26.2 at 20k). A few works where the question
  misses most sections pull the mean up. Anchor words stay high (96.3% at 20k). Whole-passage numbers
  are 100.0% after off-query
  sections are shortened.
- **`low` is filler, not summarization.**
  Chunked 8k `low` mean save is **7.0%**
  with numbers still 100.0%. Repetition
  is small and uneven (it shows up at 8k and not at 20k in this run).
- **Chunked `high` still drops the middle, and keeps the asked section.**
  Mean save rises **37.4%** → **61.4%** → **79.3%**.
  Trim also keeps a section whose best sentence matches the question.
  Anchor retention is 99.4% at 2k, 95.2% at 8k, and 96.3% at 20k.
  Passage numbers kept are 100.0% at 8k and 100.0% at 20k. Figures outside that
  section are still dropped.
- **Use this corpus for a pasted chapter, and the 222-item study for chat.**
  On a pasted chapter, `low` is still about 6%. `medium` and `high`
  now cut inside that one turn. Chunked `high` is still a middle-cut.

## How to read this

- **Chunked `medium` / `high`** is the job contextpress is built to win:
  many sections in the window, one question at the end. Savings should
  climb with length because more of the passage sits outside the
  protected tail.
- **Monolith `low`** is filler only. **Monolith `medium`** keeps about
  a third of the sentences, including every sentence whose TF-IDF
  similarity to the question is at least 0.3, plus a four-sentence
  lead. **Monolith `high`** keeps that relevant set and a
  two-sentence lead, so figures outside those sentences are dropped.
- **Anchor retention** checks the sentence the question points at.
  **Number retention** checks the whole passage, including sections
  the preset is allowed to summarize or drop.
- This is still not an LLM answer-quality judge. It measures tokens
  removed and whether the pointed-at sentence and the numeric spans
  are still in the prompt.

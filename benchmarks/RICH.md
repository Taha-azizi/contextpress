# Rich long-document benchmark

Measured with the working tree of contextpress **0.7.4**. This file does not bump the package version.

[`LONGFORM.md`](LONGFORM.md) is the smaller gate study: 12 works, one question in the first fifth, anchor words and numbers. This study is the broader cut.

## What is richer

- More works, split into fiction, science, history, politics, philosophy, and essays.
- Lengths **4k, 8k, 16k, and 32k** tokens (cl100k), not only 2k/8k/20k.
- The question is planted **early, in the middle, and late**.
  The main grid uses the middle.
- Every table reports three numbers together: token save, information
  loss, and adjusted save.
- Save means and adjusted save means have a percentile bootstrap 95%
  interval across works (2,000 resamples, seed 0).

Profile `rag_doc`, `token_budget=None`, no LLM. Full text is not committed.
Re-run: `python -m benchmarks.run_rich`.

## The three KPIs

Critical facts are pooled, not averaged as percents: content words from the asked sentence, distinct numbers (3+ digits, decimals, ISO dates), and distinct two-word names on the same line (`Elizabeth Bennet`). Filler words the `low` preset removes (`pretty`, `absolutely`) are not facts. A line break does not glue two capitalized words into a name. Ordinary sentences that are not one of those facts are allowed to go. Dropping them is the compression, not the information loss.

| KPI | Meaning | Better |
| --- | --- | --- |
| **Token save** | Percent of input tokens removed. | Higher |
| **Information loss** | Percent of critical facts no longer in the passage. Counts are pooled across works. | Lower |
| **Adjusted save** | `token save − information loss`. Can be negative. | Higher |

A point of critical-fact loss cancels a point of token save. A 6% save that loses 2% of facts scores 4. A 57% save that loses 49% of facts scores 8. A cut that loses more facts than tokens scores below zero.

### Sources used

| id | title | domain |
| --- | --- | --- |
| `austen-pnp` | Pride and Prejudice | fiction |
| `shelley-frank` | Frankenstein | fiction |
| `melville-moby` | Moby-Dick | fiction |
| `dickens-cities` | A Tale of Two Cities | fiction |
| `wells-worlds` | The War of the Worlds | fiction |
| `darwin-origin` | On the Origin of Species | science |
| `darwin-descent` | The Descent of Man | science |
| `russell-problems` | The Problems of Philosophy | philosophy |
| `aurelius-meditations` | Meditations | philosophy |
| `thoreau-walden` | Walden | essay |
| `douglass-narrative` | Narrative of Frederick Douglass | history |
| `dubois-souls` | The Souls of Black Folk | history |
| `smith-wealth` | The Wealth of Nations | politics |
| `machiavelli-prince` | The Prince | politics |
| `mill-liberty` | On Liberty | politics |
| `hobbes-leviathan` | Leviathan | politics |
| `federalist` | The Federalist Papers | politics |
| `wiki-french-rev` | French Revolution | history |
| `wiki-roman` | Roman Empire | history |
| `wiki-civil-war` | American Civil War | history |
| `wiki-ww2` | World War II | history |
| `wiki-industrial` | Industrial Revolution | history |
| `wiki-byzantine` | Byzantine Empire | history |
| `wiki-constitution` | United States Constitution | politics |
| `wiki-dna` | DNA | science |
| `wiki-photosynthesis` | Photosynthesis | science |
| `wiki-evolution` | Evolution | science |
| `wiki-quantum` | Quantum mechanics | science |
| `wiki-tectonics` | Plate tectonics | science |
| `wiki-black-hole` | Black hole | science |
| `wiki-periodic` | Periodic table | science |

### Skipped

- wiki-french-rev 32k: source shorter than 70% of target
- wiki-roman 32k: source shorter than 70% of target
- wiki-civil-war 32k: source shorter than 70% of target
- wiki-ww2 32k: source shorter than 70% of target
- wiki-byzantine 32k: source shorter than 70% of target
- wiki-constitution 32k: source shorter than 70% of target
- wiki-dna 32k: source shorter than 70% of target
- wiki-photosynthesis 16k: source shorter than 70% of target
- wiki-photosynthesis 32k: source shorter than 70% of target
- wiki-evolution 32k: source shorter than 70% of target
- wiki-quantum 32k: source shorter than 70% of target
- wiki-tectonics 32k: source shorter than 70% of target
- wiki-black-hole 32k: source shorter than 70% of target
- wiki-periodic 32k: source shorter than 70% of target

## Chunked passage, question in the middle

| length | preset | n | token save | save CI | info loss | adjusted save | adj. CI | anchor kept | numbers kept | names kept |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 4k | `low` | 31 | 5.3% | 3.5–7.8 | 0.1% | 5.3% | 3.4–7.8 | 100.0% | 100.0% | 99.9% |
| 4k | `medium` | 31 | 9.5% | 6.8–12.4 | 3.4% | 6.1% | 3.2–9.2 | 100.0% | 95.1% | 95.7% |
| 4k | `high` | 31 | 43.0% | 40.6–45.6 | 29.9% | 13.1% | 8.0–19.2 | 99.7% | 64.6% | 59.4% |
| 8k | `low` | 31 | 8.4% | 5.4–12.6 | 5.6% | 2.8% | -1.4–6.1 | 98.3% | 98.2% | 91.7% |
| 8k | `medium` | 31 | 20.0% | 13.8–26.6 | 12.5% | 7.5% | 1.3–14.0 | 95.7% | 86.6% | 86.0% |
| 8k | `high` | 31 | 56.8% | 53.7–60.0 | 43.1% | 13.7% | 8.8–19.6 | 94.6% | 50.1% | 51.4% |
| 16k | `low` | 30 | 6.6% | 4.8–8.7 | 2.3% | 4.2% | 3.0–5.7 | 98.5% | 99.1% | 97.0% |
| 16k | `medium` | 30 | 13.1% | 7.9–19.4 | 6.0% | 7.1% | 3.5–11.1 | 98.5% | 91.6% | 94.5% |
| 16k | `high` | 30 | 74.4% | 71.9–76.7 | 60.6% | 13.9% | 9.9–19.2 | 95.3% | 36.8% | 33.8% |
| 32k | `low` | 18 | 28.3% | 17.4–41.0 | 10.7% | 17.6% | 10.8–24.3 | 83.7% | 93.3% | 88.5% |
| 32k | `medium` | 18 | 38.0% | 28.4–48.4 | 19.4% | 18.6% | 8.8–26.1 | 83.7% | 81.3% | 79.9% |
| 32k | `high` | 18 | 83.4% | 82.1–84.6 | 71.6% | 11.8% | 9.0–14.6 | 78.0% | 24.2% | 23.2% |

## Pasted passage, question in the middle

| length | preset | n | token save | save CI | info loss | adjusted save | adj. CI | anchor kept | numbers kept | names kept |
| --- | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | ---: |
| 4k | `low` | 31 | 5.9% | 4.1–8.1 | 0.1% | 5.9% | 4.1–8.0 | 100.0% | 100.0% | 99.9% |
| 4k | `medium` | 31 | 56.6% | 54.4–58.8 | 42.8% | 13.8% | 9.7–19.3 | 100.0% | 41.6% | 45.4% |
| 4k | `high` | 31 | 95.7% | 95.3–96.1 | 74.4% | 21.3% | 16.0–29.2 | 100.0% | 3.5% | 2.8% |
| 8k | `low` | 31 | 6.1% | 4.2–8.5 | 0.1% | 6.1% | 4.2–8.4 | 100.0% | 100.0% | 99.9% |
| 8k | `medium` | 31 | 57.1% | 55.1–59.2 | 47.4% | 9.7% | 5.7–14.3 | 100.0% | 42.0% | 46.6% |
| 8k | `high` | 31 | 97.9% | 97.7–98.0 | 84.9% | 13.0% | 9.7–17.9 | 99.7% | 1.7% | 1.8% |
| 16k | `low` | 30 | 5.9% | 4.2–7.6 | 0.2% | 5.7% | 4.0–7.3 | 99.7% | 100.0% | 99.7% |
| 16k | `medium` | 30 | 56.8% | 54.7–58.5 | 51.6% | 5.2% | 2.2–8.1 | 99.7% | 40.5% | 45.5% |
| 16k | `high` | 30 | 98.9% | 98.8–99.0 | 90.9% | 8.0% | 6.1–11.1 | 99.7% | 1.7% | 1.2% |
| 32k | `low` | 18 | 7.7% | 6.6–8.6 | 0.5% | 7.2% | 6.2–8.2 | 99.1% | 100.0% | 99.3% |
| 32k | `medium` | 18 | 55.2% | 52.5–57.4 | 50.9% | 4.3% | -1.0–9.5 | 99.1% | 38.0% | 46.3% |
| 32k | `high` | 18 | 99.4% | 99.3–99.5 | 90.0% | 9.4% | 7.2–13.6 | 99.1% | 1.1% | 1.0% |

## Question position (8k tokens)

Early is the first fifth. Late is near the end, which for a chunked thread sits in the tail trim is not allowed to drop. Middle is the harder case.

| packing | position | preset | n | token save | info loss | adjusted save |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| chunked | early | `low` | 31 | 8.4% | 5.7% | 2.7% |
| chunked | early | `medium` | 31 | 21.1% | 13.1% | 8.1% |
| chunked | early | `high` | 31 | 64.5% | 49.8% | 14.7% |
| chunked | middle | `low` | 31 | 8.4% | 5.6% | 2.8% |
| chunked | middle | `medium` | 31 | 20.0% | 12.5% | 7.5% |
| chunked | middle | `high` | 31 | 56.8% | 43.1% | 13.7% |
| chunked | late | `low` | 31 | 8.4% | 5.4% | 3.1% |
| chunked | late | `medium` | 31 | 15.0% | 11.2% | 3.8% |
| chunked | late | `high` | 31 | 61.5% | 47.8% | 13.8% |
| monolith | early | `low` | 31 | 6.1% | 0.1% | 6.1% |
| monolith | early | `medium` | 31 | 57.9% | 48.9% | 9.0% |
| monolith | early | `high` | 31 | 97.8% | 85.6% | 12.2% |
| monolith | middle | `low` | 31 | 6.1% | 0.1% | 6.1% |
| monolith | middle | `medium` | 31 | 57.1% | 47.4% | 9.7% |
| monolith | middle | `high` | 31 | 97.9% | 84.9% | 13.0% |
| monolith | late | `low` | 31 | 6.1% | 0.1% | 6.1% |
| monolith | late | `medium` | 31 | 57.3% | 49.4% | 7.9% |
| monolith | late | `high` | 31 | 97.9% | 85.3% | 12.6% |

## Domain (chunked, 8k, question in the middle)

| domain | preset | n | token save | info loss | adjusted save |
| --- | --- | ---: | ---: | ---: | ---: |
| essay | `low` | 1 | 8.3% | 0.0% | 8.3% |
| essay | `medium` | 1 | 8.3% | 0.0% | 8.3% |
| essay | `high` | 1 | 58.3% | 20.8% | 37.5% |
| fiction | `low` | 5 | 7.2% | 0.3% | 6.9% |
| fiction | `medium` | 5 | 19.9% | 19.5% | 0.4% |
| fiction | `high` | 5 | 58.9% | 55.6% | 3.3% |
| history | `low` | 8 | 11.1% | 8.7% | 2.4% |
| history | `medium` | 8 | 23.6% | 13.7% | 9.9% |
| history | `high` | 8 | 54.7% | 42.1% | 12.6% |
| philosophy | `low` | 2 | 7.6% | 0.0% | 7.6% |
| philosophy | `medium` | 2 | 7.6% | 0.0% | 7.6% |
| philosophy | `high` | 2 | 53.6% | 31.5% | 22.1% |
| politics | `low` | 6 | 12.1% | 5.6% | 6.5% |
| politics | `medium` | 6 | 21.3% | 5.9% | 15.5% |
| politics | `high` | 6 | 61.5% | 45.0% | 16.5% |
| science | `low` | 9 | 4.4% | 2.1% | 2.2% |
| science | `medium` | 9 | 19.9% | 13.5% | 6.4% |
| science | `high` | 9 | 54.8% | 39.2% | 15.6% |

## Each work at 8k, question in the middle

Each cell is **token save / information loss / adjusted save**.

| work | domain | chunked low | chunked medium | chunked high | pasted medium |
| --- | --- | --- | --- | --- | --- |
| `aurelius-meditations` | philosophy | 7.1% / 0.0% / 7.1% | 7.1% / 0.0% / 7.1% | 49.0% / 37.3% / 11.7% | 52.6% / 47.1% / 5.6% |
| `austen-pnp` | fiction | 8.5% / 0.0% / 8.5% | 22.6% / 49.5% / -27.0% | 54.5% / 73.9% / -19.3% | 52.9% / 60.4% / -7.4% |
| `darwin-descent` | science | 6.1% / 0.0% / 6.1% | 6.1% / 0.0% / 6.1% | 57.0% / 59.7% / -2.7% | 39.6% / 54.8% / -15.2% |
| `darwin-origin` | science | 7.9% / 0.0% / 7.9% | 23.8% / 19.4% / 4.4% | 73.3% / 51.6% / 21.7% | 48.9% / 25.8% / 23.0% |
| `dickens-cities` | fiction | 5.6% / 0.0% / 5.6% | 5.6% / 0.0% / 5.6% | 58.1% / 32.1% / 26.0% | 50.7% / 21.4% / 29.3% |
| `douglass-narrative` | history | 7.7% / 0.0% / 7.7% | 63.5% / 28.1% / 35.4% | 70.9% / 28.1% / 42.8% | 54.8% / 25.0% / 29.8% |
| `dubois-souls` | history | 8.2% / 0.0% / 8.2% | 43.1% / 29.0% / 14.1% | 65.4% / 59.4% / 5.9% | 59.4% / 46.4% / 13.0% |
| `federalist` | politics | 8.5% / 0.0% / 8.5% | 8.5% / 0.0% / 8.5% | 50.0% / 20.7% / 29.3% | 57.8% / 37.9% / 19.8% |
| `hobbes-leviathan` | politics | 6.1% / 0.0% / 6.1% | 15.8% / 1.6% / 14.2% | 66.0% / 39.1% / 26.9% | 54.7% / 42.2% / 12.5% |
| `machiavelli-prince` | politics | 7.0% / 0.0% / 7.0% | 7.0% / 0.0% / 7.0% | 59.2% / 58.7% / 0.5% | 56.4% / 62.7% / -6.2% |
| `melville-moby` | fiction | 6.6% / 0.9% / 5.7% | 6.6% / 0.9% / 5.7% | 50.9% / 53.8% / -3.0% | 48.4% / 32.5% / 16.0% |
| `mill-liberty` | politics | 8.5% / 0.0% / 8.5% | 8.5% / 0.0% / 8.5% | 57.4% / 21.7% / 35.6% | 54.1% / 47.8% / 6.3% |
| `russell-problems` | philosophy | 8.1% / 0.0% / 8.1% | 8.1% / 0.0% / 8.1% | 58.3% / 18.2% / 40.1% | 60.2% / 36.4% / 23.8% |
| `shelley-frank` | fiction | 8.0% / 0.0% / 8.0% | 50.2% / 11.8% / 38.4% | 72.6% / 35.3% / 37.3% | 56.3% / 41.2% / 15.1% |
| `smith-wealth` | politics | 17.8% / 0.0% / 17.8% | 63.5% / 0.0% / 63.5% | 78.4% / 7.1% / 71.2% | 58.4% / 0.0% / 58.4% |
| `thoreau-walden` | essay | 8.3% / 0.0% / 8.3% | 8.3% / 0.0% / 8.3% | 58.3% / 20.8% / 37.5% | 55.3% / 29.2% / 26.2% |
| `wells-worlds` | fiction | 7.5% / 0.0% / 7.5% | 14.7% / 3.4% / 11.2% | 58.5% / 27.6% / 31.0% | 60.5% / 27.6% / 33.0% |
| `wiki-black-hole` | science | 2.4% / 0.9% / 1.5% | 34.4% / 22.4% / 12.0% | 48.4% / 28.4% / 20.0% | 61.0% / 43.1% / 17.9% |
| `wiki-byzantine` | history | 0.5% / 0.0% / 0.5% | 0.5% / 0.0% / 0.5% | 46.6% / 42.8% / 3.8% | 58.8% / 41.9% / 16.9% |
| `wiki-civil-war` | history | 0.5% / 0.0% / 0.5% | 0.5% / 0.0% / 0.5% | 50.4% / 42.9% / 7.6% | 58.0% / 51.0% / 6.9% |
| `wiki-constitution` | politics | 24.7% / 11.6% / 13.1% | 24.7% / 11.6% / 13.1% | 58.2% / 52.8% / 5.5% | 56.1% / 57.4% / -1.3% |
| `wiki-dna` | science | 0.7% / 0.0% / 0.7% | 17.8% / 2.8% / 15.0% | 52.0% / 16.7% / 35.3% | 61.4% / 61.1% / 0.3% |
| `wiki-evolution` | science | 0.8% / 0.0% / 0.8% | 0.8% / 0.0% / 0.8% | 55.2% / 28.6% / 26.6% | 58.3% / 61.9% / -3.6% |
| `wiki-french-rev` | history | 12.9% / 3.2% / 9.7% | 12.9% / 3.2% / 9.7% | 45.9% / 33.8% / 12.2% | 64.8% / 50.3% / 14.5% |
| `wiki-industrial` | history | 0.3% / 0.0% / 0.3% | 9.5% / 11.4% / -1.9% | 52.8% / 46.0% / 6.8% | 59.6% / 56.4% / 3.2% |
| `wiki-periodic` | science | 0.9% / 0.0% / 0.9% | 14.0% / 4.8% / 9.3% | 55.7% / 45.2% / 10.5% | 60.1% / 42.9% / 17.2% |
| `wiki-photosynthesis` | science | 0.5% / 0.0% / 0.5% | 25.8% / 14.5% / 11.3% | 42.4% / 22.6% / 19.8% | 60.0% / 58.1% / 2.0% |
| `wiki-quantum` | science | 9.9% / 0.0% / 9.9% | 28.5% / 22.2% / 6.3% | 43.0% / 22.2% / 20.8% | 76.4% / 22.2% / 54.2% |
| `wiki-roman` | history | 0.7% / 0.0% / 0.7% | 0.7% / 0.0% / 0.7% | 47.3% / 27.8% / 19.5% | 57.2% / 44.4% / 12.7% |
| `wiki-tectonics` | science | 10.2% / 9.6% / 0.6% | 27.7% / 20.2% / 7.5% | 66.2% / 57.7% / 8.5% | 56.7% / 37.5% / 19.2% |
| `wiki-ww2` | history | 58.1% / 48.8% / 9.3% | 58.1% / 48.8% / 9.3% | 58.1% / 48.8% / 9.3% | 60.6% / 52.2% / 8.5% |

## Notes

- Question turn byte-identical: **1032/1032** public runs.
- Approximate gpt-4o-mini input dollars saved on chunked 8k `high`, summed across 31 works: **$0.0212**.
- At 4k–16k, `low` is filler: about 5–9% saved, numbers nearly all kept.
  At 32k chunked, `low` jumps because repetition drops near-duplicate
  sections in long books. Most Wikipedia extracts were shorter than
  32k and are not in that row.
- Pasted `medium` / `high` cut inside the single turn (0.7.3). Chunked `high` drops other sections and keeps the one that matches the question (0.7.4).
- A synthetic control is not mixed into the tables above.

## Synthetic control (8k technical prose, middle question)

Repeated module sentences with a unique figure in each, plus one asked sentence. Not a published book.

| packing | preset | token save | info loss | adjusted save |
| --- | --- | ---: | ---: | ---: |
| chunked | `low` | 90.3% | 85.8% | 4.5% |
| chunked | `medium` | 90.3% | 85.8% | 4.5% |
| chunked | `high` | 90.3% | 85.8% | 4.5% |
| monolith | `low` | 0.0% | 0.0% | 0.0% |
| monolith | `medium` | 66.1% | 68.6% | -2.5% |
| monolith | `high` | 98.1% | 97.6% | 0.6% |

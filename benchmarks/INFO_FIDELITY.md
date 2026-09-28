# Token savings vs information loss

Deterministic fidelity study (no LLM judge). **222** items × **3** presets = **666** runs in **215s**.

## Method

1. **Critical information loss** (headline) — extract factoids from non-system turns: URLs, emails, paths, versions/decimals/3+ digit numbers, ISO dates, `snake_case` / `CamelCase` ids. Retention uses token boundaries (so `10` does not count as kept inside `2010`). Quotes and 1–2 digit integers are excluded (too much discourse noise). `critical_info_loss_pct = 100 × (1 − retained/total)`. **Quote the weighted figure** (facts pooled across items).
2. **Soft information loss** — `100 × (1 − TF-IDF cosine)` of the full thread (hedges, deleted turns, synonym swaps). Not the same as lost IDs.
3. **Contract checks** — system prompt unchanged; last-user keywords present.

Wording stages (`low`) should show **token save >> critical loss**. Recency (`medium`) may drop IDs in shortened older sentences. Trim (`high`) removes mid-thread turns.

## Headline (all items)

The three benchmark KPIs are **token save**, **information loss** (weighted critical-fact loss: numbers, URLs, paths, ids), and **adjusted save** = `token save − information loss`.

| preset | token save | info loss | adjusted save | mean critical loss | soft loss | facts kept |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `low` | 6.0% | **1.6%** | **4.4%** | 1.0% | 3.5% | 99.0% |
| `medium` | 22.7% | **15.2%** | **7.5%** | 18.7% | 6.0% | 81.3% |
| `high` | 47.7% | **27.3%** | **20.4%** | 37.6% | 13.0% | 62.4% |

### Soundbite form

Quote **mean token save** + **weighted critical loss** (facts pooled). Median is the typical chat.

- **`low`**: **6.0%** token save, **1.6%** information loss, **4.4%** adjusted save (98.4% of factoids retained). Soft/bulk wording loss ≈ 3.5%.
  - Chats: **5.9%** tokens saved, **1.6%** weighted / **0.0%** median critical loss.
- **`medium`**: **22.7%** token save, **15.2%** information loss, **7.5%** adjusted save (84.8% of factoids retained). Soft/bulk wording loss ≈ 6.0%.
  - Chats: **23.5%** tokens saved, **22.6%** weighted / **0.0%** median critical loss.
- **`high`**: **47.7%** token save, **27.3%** information loss, **20.4%** adjusted save (72.7% of factoids retained). Soft/bulk wording loss ≈ 13.0%.
  - Chats: **50.8%** tokens saved, **45.0%** weighted / **33.3%** median critical loss.

## Chat-only (long threads — main product story)

| preset | token save | info loss | adjusted save | median critical loss | soft loss | system OK | last-user OK |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `low` | 5.9% | **1.6%** | **4.3%** | 0.0% | 3.8% | 100.0% | 100.0% |
| `medium` | 23.5% | **22.6%** | **0.8%** | 0.0% | 6.4% | 100.0% | 100.0% |
| `high` | 50.8% | **45.0%** | **5.8%** | 33.3% | 14.0% | 100.0% | 99.5% |

## By bucket × preset (token save / info loss / adjusted save)

| bucket | n | low | medium | high |
| --- | --- | --- | --- | --- |
| agent | 5 | 11.3% / 2.7% / 8.6% | 11.3% / 2.7% / 8.6% | 11.3% / 2.7% / 8.6% |
| agent_tools | 8 | 0.2% / 0.0% / 0.2% | 1.1% / 0.0% / 1.1% | 5.7% / 4.3% / 1.3% |
| chat | 202 | 5.9% / 1.6% / 4.3% | 23.5% / 22.6% / 0.8% | 50.8% / 45.0% / 5.8% |
| files | 7 | 13.1% / 0.0% / 13.1% | 33.4% / 14.4% / 18.9% | 33.8% / 17.3% / 16.5% |

## Highest critical loss examples (`medium`, chats with ≥5 critical spans)

| id | tok save | critical loss | retained/total | lost examples |
| --- | --- | --- | --- | --- |
| sharegpt:NhvViwM_0 | 30.83% | 88.14% | 7/59 | `ProMecatronic, RoboGenius, MecaMinds, CyberMecas, MecaWiz…` |
| wildchat:f7fe2dbfaa14 | 58.31% | 81.08% | 7/37 | `https://levelup.gitconnected.com/automating-instagram-pos…` |
| ultrachat:4 | 37.64% | 80.0% | 1/5 | `2013, 2014, 2018, 2009` |
| capybara:0 | 17.11% | 80.0% | 1/5 | `1756, 1791, 1770, 1827` |
| wildchat:034d3607cf21 | 74.4% | 71.43% | 2/7 | `2018, 1.7, 900, 2016, 2024` |
| wildchat:7c0a9594c7a0 | 40.47% | 70.0% | 3/10 | `Video_Backup, Music_Backup, Images_Backup, Archived_softw…` |
| ultrachat:2 | 35.85% | 62.5% | 3/8 | `100, 2040, 2020, 2050, 000` |
| oasst:c866c106 | 29.45% | 62.5% | 3/8 | `https://developers.google.com/search/docs/fundamentals/se…` |

## How to read this

- **Critical loss near 0% on `low`** means versions, URLs, and IDs almost always survive wording stages (filler/lexical/abbrev/alias).
- **Higher critical + soft loss on `medium`** is mostly **recency** shortening older turns (IDs in dropped sentences). **`high`** also **trims** the middle of long threads — that is the large fact drop.
- Soft loss can exceed critical loss when hedges/prose are deleted but the remaining text still contains the IDs/numbers.
- This is **not** an LLM-as-judge of answer quality. It answers: *are the hard facts still in the prompt?*

Raw rows: `benchmarks/results/info_fidelity.jsonl`. Aggregates: `benchmarks/results/info_fidelity_summary.json`.

Re-run: `python -m benchmarks.info_fidelity`

# Contextpress savings — full measurement report

Tier-1 only. **222** corpus items × **3** presets = **666** compressions in **39s**.

Raw rows: `benchmarks/results/runs.jsonl`. Aggregates: `benchmarks/results/summary.json`.

## Overall (all items, no marketing filter)

| preset | n | mean % | median % | p10 | p90 | median tokens saved |
| --- | --- | --- | --- | --- | --- | --- |
| low | 222 | 6.0% | 2.1% | 0.1% | 17.3% | 26 |
| medium | 222 | 47.7% | 49.4% | 7.5% | 77.0% | 624 |
| high | 222 | 47.7% | 50.0% | 7.5% | 77.0% | 630 |

## By job bucket

| bucket | n | low med% | medium med% | high med% |
| --- | --- | --- | --- | --- |
| agent | 5 | 7.5% | 7.5% | 7.5% |
| agent_tools | 8 | 0.0% | 2.1% | 2.1% |
| chat | 202 | 2.2% | 53.6% | 53.6% |
| files | 7 | 1.4% | 43.0% | 43.0% |

## By source family

| source | n | low | medium | high |
| --- | --- | --- | --- | --- |
| Capybara | 25 | 1.1% | 17.8% | 17.8% |
| Files / docs | 3 | 9.4% | 43.0% | 43.0% |
| GitHub API JSON | 3 | 7.3% | 7.3% | 7.3% |
| GitHub issues | 4 | 8.5% | 70.5% | 70.5% |
| Glaive tools | 8 | 0.0% | 2.1% | 2.1% |
| HH-RLHF | 25 | 4.2% | 33.1% | 33.1% |
| In-repo examples | 3 | 22.8% | 22.8% | 22.8% |
| OASST1 | 16 | 1.9% | 68.8% | 68.8% |
| OASST2 | 10 | 2.1% | 71.4% | 71.4% |
| ShareGPT | 43 | 2.6% | 62.7% | 62.7% |
| Stack Overflow | 3 | 1.3% | 43.1% | 43.1% |
| UltraChat | 34 | 1.4% | 52.0% | 52.0% |
| WildChat | 45 | 2.5% | 60.5% | 60.5% |

## What each method saved (token Δ by stage)

For each preset, stages that changed tokens. `sum_saved` is total tokens removed by that stage across all items; `median %` is that stage's savings as a share of the item's input tokens.

### Preset `low`

| stage | n>0 | sum tokens saved | median tok | median % | mean % |
| --- | --- | --- | --- | --- | --- |
| abbrev | 66 | 276 | 3 | 0.2% | 0.31% |
| alias | 119 | 3021 | 18 | 1.1% | 1.51% |
| filler | 158 | 4502 | 11 | 0.9% | 1.51% |
| lexical | 159 | 895 | 3 | 0.3% | 0.41% |
| repetition | 27 | 14784 | 362 | 21.6% | 23.82% |
| structure | 21 | 4651 | 17 | 0.9% | 7.77% |

### Preset `medium`

| stage | n>0 | sum tokens saved | median tok | median % | mean % |
| --- | --- | --- | --- | --- | --- |
| abbrev | 66 | 276 | 3 | 0.2% | 0.31% |
| alias | 119 | 3021 | 18 | 1.1% | 1.51% |
| filler | 158 | 4502 | 11 | 0.9% | 1.51% |
| lexical | 159 | 895 | 3 | 0.3% | 0.41% |
| recency | 144 | 41774 | 204 | 13.3% | 17.46% |
| repetition | 27 | 14784 | 362 | 21.6% | 23.82% |
| structure | 21 | 4651 | 17 | 0.9% | 7.77% |
| trim | 201 | 107834 | 370 | 30.6% | 33.15% |

### Preset `high`

| stage | n>0 | sum tokens saved | median tok | median % | mean % |
| --- | --- | --- | --- | --- | --- |
| abbrev | 66 | 276 | 3 | 0.2% | 0.31% |
| alias | 119 | 3021 | 18 | 1.1% | 1.51% |
| filler | 158 | 4502 | 11 | 0.9% | 1.51% |
| lexical | 159 | 895 | 3 | 0.3% | 0.41% |
| recency | 143 | 41706 | 204 | 13.4% | 17.54% |
| repetition | 27 | 14784 | 362 | 21.6% | 23.82% |
| resolution | 2 | 507 | 254 | 21.2% | 21.18% |
| structure | 21 | 4651 | 17 | 0.9% | 7.77% |
| trim | 200 | 107558 | 372 | 30.6% | 33.21% |

## Every item × preset

| id | bucket | source | turns | tok in | low % | med % | high % | low top stages (tok) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| capybara:0 | chat | Capybara | 6 | 1046 | 0.0% | 17.9% | 17.9% | lexical:3 |
| capybara:1 | chat | Capybara | 6 | 636 | 0.8% | 2.8% | 2.8% | alias:11, lexical:1 |
| capybara:10 | chat | Capybara | 6 | 822 | 1.7% | 9.8% | 9.8% | lexical:7, abbrev:5, filler:2 |
| capybara:11 | chat | Capybara | 8 | 1024 | 0.9% | 28.0% | 28.0% | lexical:6, filler:3 |
| capybara:12 | chat | Capybara | 8 | 1326 | 0.0% | 39.2% | 39.2% | lexical:3, abbrev:2 |
| capybara:13 | chat | Capybara | 6 | 998 | 1.9% | 17.8% | 17.8% | lexical:11, filler:8 |
| capybara:14 | chat | Capybara | 6 | 906 | 1.8% | 8.2% | 8.2% | filler:14, lexical:2 |
| capybara:15 | chat | Capybara | 6 | 1088 | 5.2% | 11.0% | 11.0% | filler:26, alias:24, lexical:6 |
| capybara:16 | chat | Capybara | 8 | 901 | 1.4% | 27.6% | 27.6% | filler:11, alias:2 |
| capybara:17 | chat | Capybara | 8 | 1025 | 0.9% | 36.4% | 36.4% | lexical:15 |
| capybara:18 | chat | Capybara | 6 | 890 | 0.3% | 2.1% | 2.1% | lexical:3 |
| capybara:19 | chat | Capybara | 8 | 1107 | 0.0% | 37.4% | 37.4% | lexical:4, alias:4 |
| capybara:2 | chat | Capybara | 8 | 839 | 1.7% | 29.6% | 29.6% | filler:7, alias:6, lexical:1 |
| capybara:20 | chat | Capybara | 8 | 1378 | 0.6% | 37.8% | 37.8% | lexical:6, filler:2 |
| capybara:21 | chat | Capybara | 6 | 514 | 1.0% | 5.8% | 5.8% | filler:3, lexical:2 |
| capybara:22 | chat | Capybara | 6 | 828 | 1.2% | 3.5% | 3.5% | lexical:15 |
| capybara:23 | chat | Capybara | 6 | 870 | 2.2% | 12.6% | 12.6% | alias:13, abbrev:4, lexical:3 |
| capybara:24 | chat | Capybara | 8 | 1026 | 0.0% | 35.8% | 35.8% | alias:4, lexical:1 |
| capybara:3 | chat | Capybara | 6 | 749 | 1.3% | 4.5% | 4.5% | filler:6, lexical:4 |
| capybara:4 | chat | Capybara | 6 | 882 | 5.2% | 26.9% | 26.9% | lexical:35, alias:9, filler:2 |
| capybara:5 | chat | Capybara | 6 | 1002 | 2.0% | 9.1% | 14.9% | alias:18, lexical:1, abbrev:1 |
| capybara:6 | chat | Capybara | 8 | 872 | 0.9% | 18.0% | 18.0% | lexical:5, alias:5 |
| capybara:7 | chat | Capybara | 8 | 1181 | 0.5% | 35.1% | 35.1% | lexical:6 |
| capybara:8 | chat | Capybara | 6 | 511 | 1.4% | 4.9% | 4.9% | filler:6, lexical:1 |
| capybara:9 | chat | Capybara | 6 | 724 | 1.1% | 2.8% | 2.8% | lexical:5, filler:2, abbrev:1 |
| files:contextpress_docs | files | Files / docs | 8 | 8950 | 0.1% | 5.4% | 5.4% | filler:8, structure:1 |
| files:flask_requests_docs | files | Files / docs | 6 | 7668 | 9.4% | 52.1% | 52.1% | filler:721, structure:2 |
| github:flask_events_pretty | agent | GitHub API JSON | 6 | 6433 | 7.5% | 7.5% | 7.5% | structure:472, lexical:8 |
| github:flask_issues_pretty | agent | GitHub API JSON | 6 | 3872 | 7.3% | 7.3% | 7.3% | structure:255, filler:21, lexical:8 |
| github:pallets/flask#4027 | chat | GitHub issues | 25 | 2002 | 5.2% | 79.5% | 79.5% | filler:55, alias:43, structure:3 |
| github:pallets/flask#4494 | chat | GitHub issues | 20 | 1882 | 11.7% | 87.2% | 87.2% | repetition:170, filler:30, structure:17 |
| github:pallets/flask#5881 | chat | GitHub issues | 19 | 2270 | 4.0% | 61.5% | 61.5% | filler:48, alias:41, lexical:3 |
| github:psf/requests#5642 | chat | GitHub issues | 4 | 435 | 23.7% | 23.7% | 23.7% | structure:86, filler:13, abbrev:3 |
| github:requests_commits_pretty | agent | GitHub API JSON | 6 | 11791 | 4.2% | 4.2% | 4.2% | structure:434, lexical:60 |
| glaive:1 | agent_tools | Glaive tools | 9 | 388 | 1.0% | 26.8% | 26.8% | lexical:3, abbrev:1 |
| glaive:2 | agent_tools | Glaive tools | 7 | 432 | 0.0% | 2.5% | 2.5% | — |
| glaive:3 | agent_tools | Glaive tools | 7 | 311 | 0.0% | 4.8% | 4.8% | — |
| glaive:4 | agent_tools | Glaive tools | 7 | 265 | 0.4% | 9.4% | 9.4% | alias:1 |
| glaive:5 | agent_tools | Glaive tools | 8 | 372 | 0.0% | 1.6% | 1.6% | — |
| glaive:6 | agent_tools | Glaive tools | 5 | 277 | 0.0% | 0.0% | 0.0% | — |
| glaive:8 | agent_tools | Glaive tools | 6 | 386 | 0.0% | 0.0% | 0.0% | — |
| glaive:9 | agent_tools | Glaive tools | 5 | 240 | 0.0% | 0.0% | 0.0% | — |
| guanaco:154 | chat | ShareGPT | 6 | 1111 | 0.0% | 71.7% | 71.7% | — |
| guanaco:196 | chat | ShareGPT | 6 | 530 | 0.0% | 50.0% | 50.0% | — |
| guanaco:40 | chat | ShareGPT | 6 | 807 | 5.8% | 44.4% | 44.4% | filler:38, alias:7, lexical:2 |
| hh:104 | chat | HH-RLHF | 6 | 499 | 3.8% | 26.1% | 26.1% | filler:15, lexical:3, alias:1 |
| hh:108 | chat | HH-RLHF | 10 | 382 | 4.2% | 47.1% | 47.1% | filler:16 |
| hh:115 | chat | HH-RLHF | 12 | 498 | 5.2% | 71.5% | 71.5% | filler:24, lexical:2 |
| hh:159 | chat | HH-RLHF | 10 | 626 | 2.6% | 43.0% | 43.0% | filler:15, lexical:1 |
| hh:161 | chat | HH-RLHF | 6 | 348 | 9.2% | 15.2% | 15.2% | filler:32 |
| hh:184 | chat | HH-RLHF | 4 | 379 | 7.7% | 22.7% | 22.7% | filler:26, lexical:3 |
| hh:186 | chat | HH-RLHF | 10 | 366 | 3.5% | 46.2% | 46.2% | filler:12, lexical:1 |
| hh:192 | chat | HH-RLHF | 12 | 874 | 4.3% | 58.7% | 58.7% | filler:36, lexical:1, alias:1 |
| hh:199 | chat | HH-RLHF | 20 | 598 | 1.5% | 63.4% | 63.4% | filler:7, lexical:2 |
| hh:209 | chat | HH-RLHF | 8 | 400 | 2.5% | 13.2% | 13.2% | filler:9, alias:1 |
| hh:225 | chat | HH-RLHF | 8 | 369 | 4.6% | 30.1% | 30.1% | filler:13, lexical:4 |
| hh:231 | chat | HH-RLHF | 6 | 343 | 3.5% | 25.4% | 25.4% | filler:9, lexical:3 |
| hh:240 | chat | HH-RLHF | 6 | 361 | 1.9% | 2.5% | 2.5% | filler:6, lexical:1 |
| hh:31 | chat | HH-RLHF | 8 | 377 | 4.5% | 29.7% | 29.7% | filler:16, lexical:1 |
| hh:35 | chat | HH-RLHF | 20 | 505 | 3.0% | 77.0% | 77.0% | alias:8, filler:7 |
| hh:357 | chat | HH-RLHF | 6 | 376 | 5.3% | 30.1% | 30.1% | filler:18, lexical:2 |
| hh:38 | chat | HH-RLHF | 8 | 452 | 4.0% | 43.6% | 43.6% | filler:18 |
| hh:382 | chat | HH-RLHF | 8 | 384 | 5.5% | 33.1% | 33.1% | filler:21 |
| hh:428 | chat | HH-RLHF | 8 | 480 | 2.9% | 47.5% | 47.5% | filler:10, lexical:3, abbrev:1 |
| hh:44 | chat | HH-RLHF | 6 | 593 | 6.4% | 24.4% | 24.4% | filler:32, abbrev:4, lexical:2 |
| hh:444 | chat | HH-RLHF | 6 | 555 | 5.4% | 37.1% | 37.1% | filler:28, lexical:2 |
| hh:445 | chat | HH-RLHF | 8 | 363 | 3.3% | 43.0% | 43.0% | filler:12 |
| hh:450 | chat | HH-RLHF | 6 | 387 | 5.9% | 7.0% | 7.0% | filler:23 |
| hh:53 | chat | HH-RLHF | 6 | 423 | 4.5% | 7.1% | 7.1% | filler:19 |
| hh:83 | chat | HH-RLHF | 18 | 453 | 2.0% | 74.2% | 74.2% | filler:7, lexical:2 |
| inrepo:agent_json | agent | In-repo examples | 5 | 803 | 14.9% | 14.9% | 14.9% | structure:117, lexical:3 |
| inrepo:fenced_json | files | In-repo examples | 3 | 246 | 36.6% | 36.6% | 36.6% | structure:90 |
| inrepo:openai_tools | agent | In-repo examples | 5 | 145 | 22.8% | 22.8% | 22.8% | structure:33 |
| oasst2:00353343 | chat | OASST2 | 12 | 692 | 2.0% | 70.7% | 70.7% | lexical:7, filler:3, abbrev:3 |
| oasst2:0043c58b | chat | OASST2 | 12 | 1777 | 0.5% | 80.0% | 80.0% | filler:5, lexical:4 |
| oasst2:006e443d | chat | OASST2 | 12 | 1038 | 2.7% | 79.5% | 79.5% | filler:16, lexical:11, abbrev:1 |
| oasst2:009ed0fe | chat | OASST2 | 17 | 2072 | 2.1% | 57.6% | 57.6% | filler:32, lexical:10, abbrev:1 |
| oasst2:00a5b5a5 | chat | OASST2 | 12 | 1767 | 3.0% | 50.9% | 50.9% | filler:51, abbrev:2 |
| oasst2:00b335e0 | chat | OASST2 | 12 | 861 | 2.1% | 69.3% | 69.3% | filler:8, alias:6, abbrev:4 |
| oasst2:010bc579 | chat | OASST2 | 12 | 1713 | 4.3% | 88.2% | 88.2% | alias:40, filler:29, lexical:5 |
| oasst2:012069b9 | chat | OASST2 | 12 | 1258 | 2.1% | 72.2% | 72.2% | filler:17, alias:5, lexical:2 |
| oasst2:0172747b | chat | OASST2 | 12 | 1335 | 1.9% | 62.9% | 62.9% | alias:13, abbrev:6, lexical:3 |
| oasst2:017eb4a5 | chat | OASST2 | 12 | 1184 | 2.2% | 83.2% | 83.2% | filler:20, lexical:4, alias:2 |
| oasst:3b863a2e | chat | OASST1 | 14 | 1162 | 2.9% | 30.7% | 30.7% | filler:19, alias:6, lexical:5 |
| oasst:50c933f5 | chat | OASST1 | 12 | 635 | 1.9% | 35.8% | 35.8% | filler:6, abbrev:6 |
| oasst:6ab24d72 | chat | OASST1 | 12 | 1326 | 1.1% | 64.1% | 64.1% | alias:7, abbrev:5, filler:3 |
| oasst:710feb81 | chat | OASST1 | 12 | 2213 | 1.1% | 59.8% | 59.8% | filler:15, alias:7, lexical:2 |
| oasst:7cce4047 | chat | OASST1 | 13 | 1533 | 1.8% | 72.7% | 72.7% | filler:24, lexical:3, alias:1 |
| oasst:82421023 | chat | OASST1 | 13 | 2755 | 2.2% | 74.6% | 74.6% | alias:40, lexical:13, filler:7 |
| oasst:91a934ba | chat | OASST1 | 13 | 1708 | 3.5% | 61.9% | 61.9% | filler:27, lexical:16, alias:10 |
| oasst:99b7abf2 | chat | OASST1 | 12 | 1591 | 3.2% | 88.2% | 88.2% | alias:37, filler:8, abbrev:4 |
| oasst:a25bf9ca | chat | OASST1 | 13 | 796 | 3.4% | 33.3% | 33.3% | alias:20, lexical:4, filler:3 |
| oasst:af04d707 | chat | OASST1 | 12 | 643 | 1.4% | 34.8% | 34.8% | filler:8, lexical:1 |
| oasst:c4e39302 | chat | OASST1 | 10 | 1224 | 1.7% | 68.5% | 68.5% | filler:14, lexical:7 |
| oasst:c522beae | chat | OASST1 | 12 | 2169 | 1.1% | 69.1% | 69.1% | filler:16, lexical:9 |
| oasst:c866c106 | chat | OASST1 | 12 | 1633 | 0.6% | 69.5% | 69.5% | lexical:6, filler:3 |
| oasst:ca4d0c93 | chat | OASST1 | 12 | 1865 | 46.3% | 81.0% | 81.0% | repetition:706, alias:82, filler:75 |
| oasst:d65de35b | chat | OASST1 | 12 | 1694 | 0.8% | 70.5% | 70.5% | filler:6, alias:5, lexical:3 |
| oasst:e087c390 | chat | OASST1 | 13 | 2676 | 3.5% | 70.7% | 70.7% | alias:55, filler:37, lexical:1 |
| openapi:petstore3 | files | Files / docs | 3 | 6918 | 43.0% | 43.0% | 43.0% | structure:2973 |
| sharegpt:0Mi7fg7_0 | chat | ShareGPT | 12 | 1846 | 1.8% | 58.6% | 58.6% | alias:35, abbrev:2 |
| sharegpt:5IjWRg9_0 | chat | ShareGPT | 8 | 1289 | 23.4% | 33.0% | 33.0% | repetition:244, alias:36, abbrev:11 |
| sharegpt:6YMEjv4_0 | chat | ShareGPT | 12 | 1017 | 6.1% | 65.2% | 65.2% | alias:48, lexical:9, filler:5 |
| sharegpt:9zcTaA1_0 | chat | ShareGPT | 10 | 1849 | 1.5% | 51.0% | 51.0% | abbrev:16, alias:9, lexical:2 |
| sharegpt:ACt45V7_11 | chat | ShareGPT | 17 | 1201 | 3.2% | 72.0% | 72.0% | alias:31, abbrev:4, lexical:3 |
| sharegpt:BmS3AX0_0 | chat | ShareGPT | 10 | 1869 | 1.4% | 68.0% | 68.0% | filler:23, abbrev:3 |
| sharegpt:BmS3AX0_10 | chat | ShareGPT | 8 | 716 | 1.3% | 61.3% | 61.3% | filler:6, lexical:3 |
| sharegpt:DfkWNPQ_0 | chat | ShareGPT | 8 | 1121 | 1.7% | 35.1% | 35.1% | alias:16, lexical:2, filler:1 |
| sharegpt:LuMzUEg_19 | chat | ShareGPT | 13 | 2283 | 3.0% | 63.4% | 63.4% | filler:40, alias:19, lexical:9 |
| sharegpt:LuMzUEg_31 | chat | ShareGPT | 9 | 2154 | 1.9% | 60.8% | 60.8% | alias:22, filler:12, lexical:5 |
| sharegpt:MKrcrHj_0 | chat | ShareGPT | 10 | 935 | 16.9% | 68.9% | 68.9% | repetition:115, alias:27, filler:12 |
| sharegpt:NhvViwM_0 | chat | ShareGPT | 12 | 1570 | 1.3% | 66.2% | 66.2% | alias:11, lexical:10 |
| sharegpt:QWJhYvA_0 | chat | ShareGPT | 12 | 1833 | 1.5% | 62.5% | 62.5% | alias:25, lexical:10 |
| sharegpt:THAybyi_0 | chat | ShareGPT | 10 | 1171 | 5.1% | 53.4% | 53.4% | filler:43, alias:17 |
| sharegpt:UGg8d44_9 | chat | ShareGPT | 17 | 1997 | 3.0% | 69.4% | 69.4% | alias:34, filler:23, lexical:2 |
| sharegpt:etlVnIy_0 | chat | ShareGPT | 14 | 1951 | 2.2% | 74.7% | 74.7% | alias:26, lexical:13, abbrev:4 |
| sharegpt:fud9GZG_0 | chat | ShareGPT | 8 | 2006 | 2.5% | 51.9% | 51.9% | alias:50 |
| sharegpt:fud9GZG_19 | chat | ShareGPT | 9 | 1869 | 21.6% | 69.8% | 69.8% | repetition:285, alias:116, abbrev:3 |
| sharegpt:fud9GZG_7 | chat | ShareGPT | 13 | 2252 | 35.1% | 62.7% | 62.7% | repetition:682, alias:106, abbrev:2 |
| sharegpt:gcVkCKD_0 | chat | ShareGPT | 8 | 1854 | 2.9% | 45.7% | 45.7% | filler:35, structure:18 |
| sharegpt:idMLILF_0 | chat | ShareGPT | 12 | 1863 | 48.4% | 61.4% | 61.4% | repetition:665, alias:167, filler:69 |
| sharegpt:j0gtTrY_0 | chat | ShareGPT | 10 | 682 | 4.4% | 40.2% | 40.2% | alias:23, lexical:7 |
| sharegpt:pngR6CU_0 | chat | ShareGPT | 8 | 1072 | 4.4% | 19.6% | 19.6% | filler:38, alias:9 |
| sharegpt:tFAvE80_0 | chat | ShareGPT | 14 | 2292 | 2.4% | 56.4% | 56.4% | alias:41, filler:9, lexical:3 |
| sharegpt:tFAvE80_31 | chat | ShareGPT | 9 | 1948 | 1.6% | 60.3% | 60.3% | alias:32 |
| sharegpt:tFAvE80_39 | chat | ShareGPT | 11 | 2405 | 4.9% | 64.9% | 64.9% | alias:69, filler:45, abbrev:2 |
| sharegpt:tgKByb7_0 | chat | ShareGPT | 10 | 2117 | 2.8% | 48.6% | 48.6% | alias:58, lexical:1 |
| sharegpt:uEDRWak_0 | chat | ShareGPT | 14 | 2052 | 2.4% | 59.1% | 59.1% | alias:19, repetition:16, filler:14 |
| sharegpt:uXyoBKr_5 | chat | ShareGPT | 9 | 2084 | 2.6% | 33.0% | 33.0% | filler:47, alias:7, abbrev:1 |
| sharegpt:vH787Fr_0 | chat | ShareGPT | 18 | 1550 | 8.6% | 77.5% | 77.5% | repetition:115, alias:18, lexical:6 |
| sharegpt:wNBG8Gp_0 | chat | ShareGPT | 16 | 2145 | 2.0% | 64.4% | 64.4% | filler:23, alias:18, lexical:2 |
| sharegpt:wNBG8Gp_15 | chat | ShareGPT | 9 | 2177 | 0.1% | 71.2% | 71.2% | structure:1 |
| sharegpt:wNBG8Gp_23 | chat | ShareGPT | 11 | 2148 | 1.1% | 66.0% | 66.0% | filler:16, abbrev:4, lexical:3 |
| sharegpt:wNBG8Gp_33 | chat | ShareGPT | 19 | 2348 | 1.5% | 68.2% | 68.2% | filler:20, alias:10, lexical:4 |
| sharegpt:wNBG8Gp_51 | chat | ShareGPT | 15 | 2020 | 2.6% | 78.7% | 78.7% | alias:44, abbrev:5, lexical:3 |
| sharegpt:wNBG8Gp_65 | chat | ShareGPT | 15 | 1940 | 7.2% | 77.4% | 77.4% | repetition:107, filler:26, structure:4 |
| sharegpt:xd92L6L_0 | chat | ShareGPT | 16 | 1915 | 11.8% | 68.6% | 68.6% | repetition:141, filler:54, alias:27 |
| sharegpt:xd92L6L_63 | chat | ShareGPT | 17 | 1752 | 3.5% | 78.2% | 78.2% | alias:41, lexical:11, filler:9 |
| sharegpt:xd92L6L_80 | chat | ShareGPT | 16 | 1857 | 8.0% | 70.2% | 70.2% | repetition:100, filler:42, alias:6 |
| sharegpt:zWauOni_0 | chat | ShareGPT | 8 | 1164 | 0.9% | 40.8% | 40.8% | filler:7, abbrev:2, lexical:1 |
| so:231767 | files | Stack Overflow | 6 | 3652 | 1.3% | 56.1% | 56.1% | filler:47 |
| so:3940128 | files | Stack Overflow | 6 | 320 | 0.0% | 0.0% | 0.0% | — |
| so:82831 | files | Stack Overflow | 6 | 487 | 1.4% | 43.1% | 43.1% | filler:7 |
| ultrachat:0 | chat | UltraChat | 8 | 640 | 0.5% | 42.3% | 42.3% | filler:3 |
| ultrachat:1 | chat | UltraChat | 12 | 1405 | 2.2% | 74.7% | 74.7% | filler:14, alias:12, lexical:5 |
| ultrachat:12 | chat | UltraChat | 12 | 840 | 0.7% | 60.2% | 60.2% | filler:4, lexical:2 |
| ultrachat:2 | chat | UltraChat | 8 | 2918 | 2.8% | 55.6% | 55.6% | filler:38, alias:34, abbrev:9 |
| ultrachat:20 | chat | UltraChat | 8 | 579 | 0.0% | 35.4% | 35.4% | lexical:4 |
| ultrachat:21 | chat | UltraChat | 10 | 1515 | 1.6% | 58.4% | 58.4% | lexical:15, alias:15 |
| ultrachat:22 | chat | UltraChat | 8 | 1468 | 0.8% | 43.6% | 43.6% | alias:7, lexical:4, filler:1 |
| ultrachat:23 | chat | UltraChat | 8 | 1018 | 2.1% | 43.4% | 43.4% | alias:23, lexical:1 |
| ultrachat:24 | chat | UltraChat | 8 | 1986 | 9.9% | 33.6% | 33.6% | filler:186, alias:10 |
| ultrachat:26 | chat | UltraChat | 8 | 913 | 4.7% | 42.4% | 42.4% | alias:32, filler:7, abbrev:4 |
| ultrachat:28 | chat | UltraChat | 8 | 1934 | 5.1% | 61.0% | 61.0% | alias:67, lexical:23, filler:8 |
| ultrachat:29 | chat | UltraChat | 8 | 1356 | 0.9% | 40.6% | 40.6% | alias:6, abbrev:5, lexical:3 |
| ultrachat:30 | chat | UltraChat | 12 | 1181 | 5.3% | 60.3% | 60.3% | alias:47, filler:16 |
| ultrachat:35 | chat | UltraChat | 14 | 1793 | 2.7% | 77.7% | 77.7% | alias:20, abbrev:19, lexical:5 |
| ultrachat:36 | chat | UltraChat | 14 | 2086 | 6.0% | 71.8% | 71.8% | alias:106, filler:18, lexical:2 |
| ultrachat:38 | chat | UltraChat | 14 | 1458 | 1.0% | 73.9% | 73.9% | filler:12, lexical:1, abbrev:1 |
| ultrachat:4 | chat | UltraChat | 8 | 2107 | 2.8% | 59.3% | 59.3% | alias:54, filler:5 |
| ultrachat:40 | chat | UltraChat | 8 | 938 | 3.2% | 39.5% | 39.5% | alias:15, lexical:10, filler:5 |
| ultrachat:42 | chat | UltraChat | 8 | 968 | 0.5% | 32.8% | 32.8% | filler:3, lexical:2 |
| ultrachat:43 | chat | UltraChat | 8 | 1084 | 0.7% | 46.9% | 46.9% | filler:4, abbrev:3 |
| ultrachat:45 | chat | UltraChat | 12 | 991 | 0.3% | 56.2% | 56.2% | filler:3 |
| ultrachat:50 | chat | UltraChat | 8 | 1895 | 62.7% | 62.7% | 62.7% | repetition:1151, alias:29, lexical:9 |
| ultrachat:52 | chat | UltraChat | 8 | 936 | 1.4% | 41.8% | 41.8% | filler:6, alias:4, lexical:3 |
| ultrachat:54 | chat | UltraChat | 8 | 1552 | 1.3% | 61.3% | 61.3% | filler:18, lexical:2 |
| ultrachat:57 | chat | UltraChat | 8 | 1517 | 0.9% | 41.9% | 41.9% | lexical:21, alias:2 |
| ultrachat:60 | chat | UltraChat | 8 | 918 | 0.0% | 40.7% | 40.7% | lexical:1 |
| ultrachat:63 | chat | UltraChat | 8 | 993 | 26.4% | 56.2% | 56.2% | repetition:248, filler:14 |
| ultrachat:64 | chat | UltraChat | 10 | 1038 | 0.0% | 47.2% | 47.2% | lexical:1 |
| ultrachat:66 | chat | UltraChat | 8 | 1886 | 0.3% | 50.3% | 50.3% | alias:14, lexical:3 |
| ultrachat:74 | chat | UltraChat | 10 | 1779 | 1.5% | 53.7% | 53.7% | alias:30, abbrev:2 |
| ultrachat:76 | chat | UltraChat | 8 | 1444 | 1.3% | 48.1% | 48.1% | alias:12, filler:7 |
| ultrachat:8 | chat | UltraChat | 14 | 1850 | 1.3% | 58.6% | 58.6% | alias:16, filler:6, lexical:2 |
| ultrachat:80 | chat | UltraChat | 12 | 1455 | 0.0% | 46.5% | 46.5% | lexical:2 |
| ultrachat:9 | chat | UltraChat | 8 | 1251 | 2.1% | 55.1% | 55.1% | filler:18, alias:5, lexical:3 |
| wildchat:0101919a0f86 | chat | WildChat | 12 | 965 | 0.6% | 51.9% | 51.9% | lexical:2, filler:2, abbrev:2 |
| wildchat:0270ea8253c4 | chat | WildChat | 18 | 1435 | 30.0% | 85.8% | 85.8% | repetition:362, alias:29, abbrev:19 |
| wildchat:034d3607cf21 | chat | WildChat | 6 | 1328 | 3.5% | 74.3% | 74.3% | filler:20, alias:18, lexical:4 |
| wildchat:0414fb6ec751 | chat | WildChat | 16 | 3766 | 31.6% | 79.7% | 79.7% | repetition:1066, filler:117, lexical:6 |
| wildchat:0b0c87ae5f7c | chat | WildChat | 8 | 509 | 0.6% | 40.3% | 40.3% | alias:3 |
| wildchat:1861202d2825 | chat | WildChat | 8 | 3091 | 1.7% | 68.3% | 68.3% | lexical:26, filler:25, alias:1 |
| wildchat:1acdcdad76b7 | chat | WildChat | 10 | 3067 | 2.0% | 62.8% | 62.8% | filler:30, alias:18, lexical:12 |
| wildchat:21736ca18f67 | chat | WildChat | 8 | 2174 | 0.0% | 45.2% | 45.2% | lexical:6, abbrev:1 |
| wildchat:2203630c5af0 | chat | WildChat | 6 | 2254 | 1.9% | 45.6% | 45.6% | filler:21, alias:21, lexical:2 |
| wildchat:2bbdb06d8130 | chat | WildChat | 10 | 1282 | 1.2% | 41.7% | 49.9% | filler:8, lexical:7, abbrev:1 |
| wildchat:2bcddb7c5cf0 | chat | WildChat | 6 | 1306 | 2.8% | 36.1% | 36.1% | filler:22, alias:9, lexical:5 |
| wildchat:3ae27f2a3859 | chat | WildChat | 6 | 577 | 5.0% | 39.5% | 39.5% | filler:16, alias:13 |
| wildchat:3e588671f3e5 | chat | WildChat | 8 | 686 | 1.3% | 33.8% | 33.8% | lexical:6, alias:3 |
| wildchat:47042f7ff92f | chat | WildChat | 10 | 2757 | 38.6% | 58.1% | 58.1% | repetition:949, filler:92, lexical:22 |
| wildchat:49f2df1f5703 | chat | WildChat | 12 | 3545 | 46.9% | 81.8% | 81.8% | repetition:1517, filler:122, alias:25 |
| wildchat:534630ac1768 | chat | WildChat | 6 | 2275 | 40.9% | 40.9% | 40.9% | repetition:889, alias:32, abbrev:4 |
| wildchat:63c1886ef9f2 | chat | WildChat | 8 | 1519 | 2.0% | 63.9% | 63.9% | filler:21, alias:4, abbrev:3 |
| wildchat:7a978bad7519 | chat | WildChat | 8 | 2650 | 0.1% | 41.2% | 41.2% | lexical:3, abbrev:1 |
| wildchat:7c0a9594c7a0 | chat | WildChat | 10 | 2602 | 4.9% | 61.0% | 61.0% | alias:85, filler:43 |
| wildchat:7e027908ee9f | chat | WildChat | 28 | 3675 | 56.7% | 89.3% | 89.3% | repetition:1992, alias:72, filler:19 |
| wildchat:8da7b68f06d5 | chat | WildChat | 6 | 744 | 23.8% | 23.8% | 23.8% | repetition:157, filler:15, alias:3 |
| wildchat:920e334e7283 | chat | WildChat | 6 | 1587 | 1.6% | 46.7% | 46.7% | lexical:11, filler:9, alias:4 |
| wildchat:93102890ae35 | chat | WildChat | 6 | 826 | 0.0% | 0.6% | 0.6% | lexical:1, abbrev:1 |
| wildchat:a47a2648047c | chat | WildChat | 18 | 3863 | 8.0% | 80.0% | 80.0% | filler:229, alias:60, lexical:18 |
| wildchat:aa7c3f49343e | chat | WildChat | 14 | 3064 | 2.5% | 61.9% | 61.9% | filler:29, repetition:26, alias:20 |
| wildchat:b04d39881b88 | chat | WildChat | 14 | 5033 | 17.4% | 88.7% | 88.7% | repetition:776, alias:57, filler:23 |
| wildchat:b81af0407cbd | chat | WildChat | 6 | 653 | 0.5% | 6.1% | 6.1% | filler:2, lexical:1 |
| wildchat:bbd23700fb46 | chat | WildChat | 14 | 4617 | 29.9% | 55.4% | 55.4% | repetition:998, filler:350, lexical:20 |
| wildchat:bd550ee6f14c | chat | WildChat | 8 | 808 | 1.9% | 44.8% | 44.8% | filler:7, abbrev:6, lexical:2 |
| wildchat:beba14d11b0b | chat | WildChat | 6 | 1329 | 6.3% | 42.9% | 42.9% | alias:46, filler:38 |
| wildchat:c44e503d8db7 | chat | WildChat | 8 | 1207 | 6.8% | 70.9% | 70.9% | alias:53, filler:22, lexical:7 |
| wildchat:c532fad81ab3 | chat | WildChat | 22 | 2393 | 2.8% | 78.7% | 78.7% | filler:31, alias:29, lexical:7 |
| wildchat:c9c9dcd5652e | chat | WildChat | 8 | 1061 | 3.9% | 48.8% | 48.8% | filler:35, lexical:5, abbrev:1 |
| wildchat:cd80a7669840 | chat | WildChat | 10 | 1323 | 39.5% | 72.3% | 72.3% | repetition:487, alias:35, lexical:2 |
| wildchat:d257adf7aa74 | chat | WildChat | 8 | 1162 | 0.5% | 53.6% | 53.6% | filler:3, abbrev:2, lexical:1 |
| wildchat:d40b465828f4 | chat | WildChat | 12 | 1588 | 38.2% | 60.5% | 60.5% | repetition:516, filler:91 |
| wildchat:d7a96b20581d | chat | WildChat | 10 | 1163 | 0.9% | 63.6% | 63.6% | lexical:6, filler:3, alias:1 |
| wildchat:dd79bb6a46ba | chat | WildChat | 16 | 2151 | 2.2% | 79.9% | 79.9% | filler:21, alias:16, lexical:10 |
| wildchat:e61a357cafc6 | chat | WildChat | 18 | 2156 | 0.7% | 76.2% | 76.2% | lexical:6, abbrev:5, filler:3 |
| wildchat:eb1c9456d61d | chat | WildChat | 14 | 1577 | 23.1% | 82.8% | 82.8% | repetition:304, abbrev:26, alias:23 |
| wildchat:efca2d50d694 | chat | WildChat | 8 | 980 | 0.0% | 74.8% | 74.8% | lexical:1 |
| wildchat:f3af4414c242 | chat | WildChat | 6 | 757 | 0.0% | 30.9% | 30.9% | abbrev:2 |
| wildchat:f7fe2dbfaa14 | chat | WildChat | 8 | 2173 | 6.0% | 73.5% | 73.5% | structure:138, lexical:2, abbrev:1 |
| wildchat:fbd2fbd5b3ae | chat | WildChat | 32 | 2090 | 1.6% | 67.3% | 67.3% | lexical:18, filler:12, alias:3 |
| wildchat:ffe98a5fca19 | chat | WildChat | 10 | 1080 | 0.7% | 46.9% | 46.9% | alias:24, lexical:7, abbrev:1 |

Re-run: `python -m benchmarks.run_savings --rebuild-corpus` (add `--refresh` to re-download HF caches).

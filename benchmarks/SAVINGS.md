# Cut LLM input cost where context actually bloats

Contextpress is for **long chats, files stuffed into the prompt, and pretty-printed tool JSON** — the work that repeats on every API call. It is not for a two-line FAQ. Those jobs are out of this report.

On **206 in-scope workloads**, `medium` cut about **53% of input tokens**. `low` (minify JSON, lexical word swaps, drop filler) cut about **2%** overall, and about **11%** on pretty tool JSON.

## What that is worth in a real month

Assume **70% of an LLM bill is input** (history, files, tools) and 30% is the completion. Savings below use the in-scope **53%** input cut at `medium` (about **37% off the whole invoice** under that split). List prices: gpt-4o input $2.50 / 1M tokens; Claude Sonnet ~$3 / 1M. Your mix will differ; the shape of the math will not.

| who | LLM bill | saved at 53% input | per year | that money is |
| --- | --- | --- | --- | --- |
| Solo / freelancer already spending ~$150/month on API | $150/mo | $56/mo | $668/yr | a month of ChatGPT Plus, or two extra long coding sessions you no longer have to truncate |
| Small startup at ~$5,000/month LLM | $5,000/mo | $1,855/mo | $22,260/yr | a year of a seat like Linear/Notion, or a contractor day each month |
| Product with agents at ~$20,000/month LLM | $20,000/mo | $7,420/mo | $89,040/yr | a junior-engineer intern month, or a dedicated staging GPU you were about to rent to 'just use a bigger context model' |

### Opportunity cost (usually the better pitch)

Keep the same bill and buy **~53% more context** instead of a smaller invoice:

- A developer who hits the wall at turn 20 can keep ~53% more of the thread and stop pasting 'summary so far' by hand.
- A startup can attach ~53% more retrieved files per question before jumping to a 128k/1M model tier.
- An agent product can retain pretty tool traces instead of dropping them, without paying another model to summarize first. Contextpress itself is **$0 API** — it runs on CPU.

`low` does not drop mid-thread turns, but it does swap wording and strip hedges. Same $5k/month startup at `low` is about **$70/month** ($840/year). `medium` adds trim (drop the middle of long chats) plus recency.

## Answer-quality risk (rough, no judge model)

We did not A/B the model's final reply. Risk is what the pipeline is **allowed to delete**, plus the contract: system prompt stays; the last 3 non-system turns stay verbatim. Trim (on `medium` / `high`) drops the middle of long threads and leaves a stub.

| preset | input cut (in-scope median) | risk to the final answer |
| --- | --- | --- |
| `low` | ~2% | **Low.** Does not drop turns. Lexical may change wording (utilize → use); filler strips empty hedges. Skip on tone-sensitive or quote-verbatim threads. |
| `medium` | ~53% | **Low–medium.** Long chats drop the middle (opening + last 3 stay). Older leftover turns may also be extractively shortened. Fine for 'continue this work'. Not for audits that need every old number verbatim. |
| `high` | ~53% | **Medium.** Finished threads can collapse to a stub. Use when old resolved topics should leave the window. |

Do not use a hard `token_budget` as a 'savings' number — that is truncation. It can drop tools and, as a last resort, the system prompt.

## Where the cut actually comes from

| job | n | low | medium | high |
| --- | --- | --- | --- | --- |
| Agent / tool JSON | 4 | 11.2% | 11.2% | 11.2% |
| agent_tools | 2 | 0.7% | 18.1% | 18.1% |
| Long chats | 194 | 2.3% | 55.9% | 55.9% |
| Files in the prompt | 6 | 5.4% | 43.0% | 43.0% |

| preset | median | p10 | p90 |
| --- | --- | --- | --- |
| low | 2.4% | 0.5% | 22.2% |
| medium | 53.5% | 22.7% | 77.3% |
| high | 53.5% | 22.7% | 77.3% |

**Chats:** `low` does not drop turns. Lexical swaps multi-token words; filler strips hedges. `medium` **trims the middle** (opening + last 3 + a stub) and may recency-shrink the leftover opening.

Long chats in this run (not a single example):

| id | turns in | low | medium |
| --- | --- | --- | --- |
| github:pallets/flask#5881 | 19 | 2,270→2,178 (4.05%) | 2,270→874 (61.5%) |
| github:pallets/flask#4027 | 25 | 2,002→1,897 (5.24%) | 2,002→410 (79.52%) |
| github:pallets/flask#4494 | 20 | 1,882→1,662 (11.69%) | 1,882→241 (87.19%) |
| github:psf/requests#5642 | 4 | 435→332 (23.68%) | 435→332 (23.68%) |
| wildchat:b04d39881b88 | 14 | 5,033→4,158 (17.39%) | 5,033→569 (88.69%) |
| wildchat:bbd23700fb46 | 14 | 4,617→3,235 (29.93%) | 4,617→2,060 (55.38%) |
| wildchat:a47a2648047c | 18 | 3,863→3,556 (7.95%) | 3,863→774 (79.96%) |
| wildchat:0414fb6ec751 | 16 | 3,766→2,575 (31.63%) | 3,766→764 (79.71%) |
| wildchat:7e027908ee9f | 28 | 3,675→1,592 (56.68%) | 3,675→393 (89.31%) |
| wildchat:49f2df1f5703 | 12 | 3,545→1,881 (46.94%) | 3,545→647 (81.75%) |

### Flask #4494 — `low` vs `medium` (full compressed threads)

Original: 20 turns, 1,882 tokens. [Issue](https://github.com/pallets/flask/issues/4494).

Original (head/tail listing):

```
system: You track public GitHub issues and summarize status.
user: Issue #4494: Flask failing to startup due to Jinja2 breaking change /  / **This issue tracker is a tool to address bugs in Flask itself. Please use / Pallets Discord or Stack Overflow for questions about your own code.**…
user: Comment by jamesL92: / Noticed that flask 2.0.x doesn't have this issue, but may want to backfix if Flask 1.1.x is still being supported with patch fixes
user: Comment by davidism: / You are using an unsupported version of Flask, please update to the latest version if possible. Additionally, please use a tool like [pip-tools](https://pypi.org/project/pip-tools/) to pin your dep…
… 13 turns omitted in this listing …
user: Comment by tachyondecay: / > i am still having this issue with the latest version of Flask /  / You really aren't, as that has [changed in the latest version](https://github.com/pallets/flask/blob/2.1.1/src/flask/app.py#…
user: Comment by Sundava: / Can you please stop introducing breaking changes in minor versions ?  /  / And yeah, I know about the pamphlet about "SemVer will not save you", which by the way states the problem is people incorre…
user: What is the current status and likely resolution?
```

**low:** 1,882 → 1,662 (11.69%), turns 20 → 18. stages: structure, lexical, filler, abbrev, alias, repetition

```
system: You track public GitHub issues and summarize status.
user: Issue #4494: Flask failing to startup due to Jinja2 breaking change /  / **This issue tracker is a tool to address bugs in Flask itself. Please use / Pallets Discord or Stack Overflow for questions about your own code.**…
user: Comment by jamesL92: / Noticed that flask 2.0.x doesn't have this issue, but may want to backfix if Flask 1.1.x is still being supported with patch fixes
user: Comment by aktiver: > You are using an unsupported version of Flask, please update to the latest version if possible. Additionally, please use a tool like [pip-tools](https://pypi.org/project/pip-tools/) to pin your depe…
user: Comment by ThiefMaster: When installing your dependencies you specify them without versions (in requirements.in) and then use `pip-compile` to build a `requirements.txt` with pinned version numbers. Then those version nu…
user: Comment by aktiver: / How can we keep using Flask==1.1.1? We have an entire app built on it that will take a significant time to refac for Flask 2.x.
user: Comment by ThiefMaster: As someone maintaining a large Flask-based project, I don't think it will take you a "meaning time" to make it compatible with Flask 2.0, unless you are still on Python 2.7 of course.., pin Flask'…
user: Comment by aktiver: > As someone maintaining a large Flask-based project, I don't think it will take you a "meaning time" to make it compatible with Flask 2.0, unless you are still on Python 2.7 of course.. > >, pin Flas…
user: Comment by ThiefMaster: / You need to add it as an explicit dependency
user: Comment by aktiver: / > You need to add it as an explicit dependency /  / I have done that, and it does not work, see reqs.txt here: / ``` / Jinja2==3.0.3 / itsdangerous==2.0.1 / Flask==1.1.1 / ``` / 
user: Comment by supreme-core: / it works for me /  / > > You need to add it as an explicit dependency / >  / > I have done that, and it does not work, see reqs.txt here: / > ``` / > Jinja2==3.0.3 / > itsdangerous==2.0.1 / > F…
user: Comment by aruna-muthu: / > after pinning Jinja2 to 3.0.3, there encounter another error.. ` from werkzeug.wrappers import BaseResponse ImportError (WIBI): cannot import name 'BaseResponse' from 'werkzeug.wrappers'` and …
user: Comment by sandeep-yarasani: / > after pinning Jinja2 to 3.0.3, there encounter another error.. / > ``` / >     from werkzeug.wrappers import BaseResponse / > ImportError: cannot import name 'BaseResponse' from 'werkzeug…
user: Comment by sandeep-yarasani: > > after pinning Jinja2 to 3.0.3, there encounter another error.. ` from werkzeug.WIBI: cannot import name 'BaseResponse' from 'werkzeug.wrappers'` and my requirements.txt is `Jinja2==3.0.3 …
user: Comment by tachyondecay: > using the above mentioned library versions did resolve this issue, but I am curious as to what caused this error in the first palce You are using an outdated version of Flask, and newer version…
user: Comment by tachyondecay: > i am still having this issue with the latest version of Flask You aren't, as that has [changed in the latest version](https://github.com/pallets/flask/blob/2.1.1/src/flask/app.py#L25). Please a…
user: Comment by Sundava: Can you please stop introducing breaking changes in minor versions? And yeah, I know about the pamphlet about "SemVer will not save you", which states the problem is people incorrectly using SemVer. O…
user: What is the current status and likely resolution?
```

**medium:** 1,882 → 241 (87.19%), turns 20 → 7. stages: structure, lexical, filler, abbrev, alias, repetition, trim, recency

```
system: You track public GitHub issues and summarize status.
user: **This issue tracker is a tool to address bugs in Flask itself. Please use Pallets Discord or Stack Overflow for questions about your own code.
user: Comment by jamesL92: / Noticed that flask 2.0.x doesn't have this issue, but may want to backfix if Flask 1.1.x is still being supported with patch fixes
assistant: [12 earlier messages omitted]
user: Comment by tachyondecay: > i am still having this issue with the latest version of Flask You aren't, as that has [changed in the latest version](https://github.com/pallets/flask/blob/2.1.1/src/flask/app.py#L25). Please a…
user: Comment by Sundava: Can you please stop introducing breaking changes in minor versions? And yeah, I know about the pamphlet about "SemVer will not save you", which states the problem is people incorrectly using SemVer. O…
user: What is the current status and likely resolution?
```

**Files:** several docs pasted into one prompt (project README + roadmap + changelog, Flask/Requests docs, OpenAPI, long SO threads). Same pattern: `low` if the files are pretty JSON; `medium` if they are long prose you only need the relevant parts of.

**Agents:** pretty-printed tool JSON. `low` is the whole product here — whitespace and duplicate log lines — **risk ignore**.

## Proof points

### Long chat / support thread

1,882 → 241 tokens (**87.19%** at `medium`; turns 20 → 7).
Source: https://github.com/pallets/flask/issues/4494
Real public issue thread (all comment turns are user-authored).

```
Issue #4494: Flask failing to startup due to Jinja2 breaking change

**This issue tracker is a tool to address bugs in Flask itself. Please use
Pallets Discord or Stack Overflow for questions about your own code.**

Since Jinja2 version 3.1.0 was released yesterday, Flask is failing to startup.

**Describe how to replicate the bug.**

Run a basic flask app, it fails to start up with the following traceback:
```
Traceback (most recent call last):

  File "applicatio…
```

### Files in the prompt

7,668 → 3,671 tokens (**52.13%** at `medium`; turns 6 → 6).
Source: https://github.com/pallets/flask
Several docs pasted into one prompt — file-summarization job.

```
FILE docs/quickstart.rst

Quickstart
==========

Eager to get started? This page gives a good introduction to Flask.
Follow :doc:`installation` to set up a project and install Flask first.


A Minimal Application
---------------------

A minimal Flask application looks something like this:

.. code-block:: python

    from flask import Flask

    app = Flask(__name__)

    @app.route("/")
    def hello_world():
        return "<p>Hello, World!</p>"

So what did that code do?
…
```

### Agent tool JSON (safe preset)

6,433 → 5,953 tokens (**7.46%** at `low`; turns 6 → 6).
Source: https://api.github.com/repos/pallets/flask/events
Pretty-printed API JSON, as in notebooks and agent logs.

```
Tool result:
[
  {
    "id": "13934044391",
    "type": "ForkEvent",
    "actor": {
      "id": 75060025,
      "login": "Jerrywu108150",
      "display_login": "Jerrywu108150",
      "gravatar_id": "",
      "url": "https://api.github.com/users/Jerrywu108150",
      "avatar_url": "https://avatars.githubusercontent.com/u/75060025?"
    },
    "repo": {
      "id": 596892,
      "name": "pallets/flask",
      "url": "https://api.github.com/repos/pallets/flask"
    },
    "payl…
```

## What we left out on purpose

Two-turn support FAQs, already-minified JSON, and short dense encyclopedia pages barely move. They are **not** the customer. This write-up keeps jobs that saved at least **5%** on some preset (the jobs you would actually turn it on for).

16 items were measured and dropped from the story (under the cut).

## How this was measured

Tier 1 only (no LLM compressor). 222 raw items → 206 in-scope. 888 compressions in 218s. Re-run: `python -m benchmarks.run_savings --rebuild-corpus`.

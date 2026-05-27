# Investment Workflow System

A code-first workflow that turns current technology and macro-event signals into a compact investment brief.

## What it does

1. Pulls recent news from configurable RSS queries.
2. Deduplicates and classifies events into themes, industries, and asset buckets.
3. Scores positive and negative impact signals.
4. Produces a final report with:
   - overall stance
   - top directions to watch
   - directions to avoid
   - conservative / balanced / aggressive strategy suggestions
   - one highest-priority action
   - key risks
   - confidence

The pipeline works in two modes:

- **Deterministic mode**: standard library only, no model key required.
- **LLM-assisted mode**: if an OpenAI-compatible API is configured, the system rewrites the structured analysis into a cleaner final brief.

It also supports three delivery targets:

- **file**
- **stdout**
- **feishu**

## Project layout

```text
investment-workflow-system/
├── .github/workflows/daily-investment-digest.yml
├── .env.example
├── README.md
└── investment_workflow/
    ├── __init__.py
    ├── __main__.py
    ├── config.py
    ├── delivery.py
    ├── feeds.py
    ├── main.py
    ├── models.py
    ├── pipeline.py
    ├── providers.py
    └── renderers.py
```

## Quick start

```bash
cd /Users/tonystark/copilot_workspace/investment-workflow-system
cp .env.example .env
python3 -m investment_workflow --stdout
```

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `NEWS_QUERIES` | No | Comma-separated search topics. |
| `MAX_ARTICLES_PER_QUERY` | No | Per-query article cap. Default `8`. |
| `MAX_ARTICLES_TOTAL` | No | Global article cap. Default `30`. |
| `REQUEST_TIMEOUT_SECONDS` | No | HTTP timeout. Default `20`. |
| `DELIVERY_MODE` | No | Comma-separated targets: `file`, `stdout`, `feishu`. Default `file`. |
| `OUTPUT_DIR` | No | Output directory. Default `outputs`. |
| `FEISHU_WEBHOOK_URL` | No | Feishu custom bot webhook URL. Required if `DELIVERY_MODE` includes `feishu`. |
| `LLM_API_BASE_URL` | No | OpenAI-compatible API base URL. |
| `LLM_API_KEY` | No | API key for the model provider. |
| `LLM_MODEL` | No | Model name to call. |

If any one of `LLM_API_BASE_URL`, `LLM_API_KEY`, or `LLM_MODEL` is set, all three must be set.

## Run modes

Write report files:

```bash
python3 -m investment_workflow
```

Print the Markdown brief to the terminal:

```bash
python3 -m investment_workflow --stdout
```

Write files and push to Feishu:

```bash
DELIVERY_MODE=file,feishu FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/xxx' python3 -m investment_workflow
```

Write to a custom directory:

```bash
python3 -m investment_workflow --output-dir ./outputs
```

## Output files

Each run writes:

- `report.md`
- `report.json`

into a timestamped directory under `OUTPUT_DIR`.

## Feishu integration

The simplest integration is a **Feishu custom bot webhook**.

### 1. Create the bot webhook

In Feishu:

1. Open the group that should receive the digest.
2. Add a **custom bot**.
3. Copy the generated webhook URL.
4. If Feishu enables keyword restrictions for the bot, add a keyword such as `投资结论`.

### 2. Configure local delivery

In `.env`:

```bash
DELIVERY_MODE=file,feishu
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your-webhook-id
```

Then run:

```bash
python3 -m investment_workflow
```

### 3. Configure GitHub Actions delivery

If this project is pushed to a GitHub repository, set:

- repository secret: `FEISHU_WEBHOOK_URL`
- repository variable: `DELIVERY_MODE=file,feishu`

Then the included workflow will automatically send the digest to Feishu on every scheduled run.

## GitHub Actions automation

The included workflow:

- runs on a daily cron
- supports manual dispatch
- stores the generated report as an artifact
- can send the digest directly to Feishu if the webhook secret is configured

Add these repository secrets if you want LLM-assisted summaries:

- `FEISHU_WEBHOOK_URL`
- `LLM_API_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`

You can customize these repository variables:

- `NEWS_QUERIES`
- `DELIVERY_MODE`

### Keep it running continuously

The easiest always-on setup is:

1. Push this folder to a GitHub repository.
2. Enable **GitHub Actions** for that repository.
3. Add `FEISHU_WEBHOOK_URL` as a secret.
4. Set `DELIVERY_MODE=file,feishu` as a repository variable.
5. Leave the included scheduled workflow enabled.

After that, GitHub runs it automatically every day without your local computer staying online.

## How the scoring works

The deterministic pipeline uses:

- theme keyword matching
- positive / negative catalyst keywords
- recency weighting
- event-risk signals

This gives you a stable baseline workflow before introducing a model-driven summary layer.

## Important note

This project is an automation starter for research summaries, not personal financial advice. You should still review outputs before acting on them.

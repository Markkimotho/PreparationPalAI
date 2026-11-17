---
description: Run PreparationPalAI on the shared AI gateway, check it, and diagnose model-service failures.
---
# AI gateway inference

Hosted deployments send every model call through an OpenAI-compatible gateway
(LiteLLM, in the separate `ai-gateway` repository). Self-hosted installations keep
Ollama. One setting chooses: `INFERENCE_BACKEND=ollama` (default) or `gateway`.

## Configure

| Setting | Meaning |
| --- | --- |
| `INFERENCE_BACKEND` | `gateway` turns on the gateway for chat, structured output, moderation, vision, and embeddings. |
| `GATEWAY_BASE_URL` | Gateway origin on the private network, for example `http://litellm:4000`. No credentials in the URL. |
| `GATEWAY_API_KEY` | The app's virtual key. Create with `ai-gateway/scripts/new_app_key.sh preparationpal-prod <monthly-usd>`. Server-side only. |
| `OLLAMA_MODEL` | Default alias in gateway mode. Defaults to `open-default` when unset. |
| `GUARD_ALIAS`, `VISION_ALIAS`, `EMBEDDING_ALIAS` | Aliases for moderation, drawing review, and embeddings. Defaults: `guard`, `vision-open`, `embed-default`. |
| `EMBEDDING_DIMENSIONS` | Optional Matryoshka size. Leave unset until the provider is verified to honour it. |

Start the stack with `docker compose -f docker-compose.hosted.yml -f docker-compose.production.yml up -d --build`.
The hosted file defines no Ollama service and joins the external `ai-gateway` network.

## What happens on each request

1. Moderation of the input runs on the `guard` alias, never on the learner's chosen model.
2. The chosen alias answers. Structured requests send a JSON schema as `response_format`.
3. Output moderation and, for grounded answers or quiz items, verification run on `guard`.
4. Each call records a usage record (alias, purpose, tokens, estimated flag) through
   `app/metering.py`. If the provider omits usage, tokens are estimated from characters
   and the record is flagged `estimated`.
5. Every call sends `user=<workspace>` and `metadata.spend_logs_metadata={action, request_id}`
   so the gateway's spend logs can be matched to the app.

A single learner action therefore makes about three model calls. Guard calls use a small,
cheap model, and each one is metered.

## Model list and failures

- Learners see `open-*` and `premium-*` aliases from the gateway's `/v1/models`, cached for
  30 seconds. Guard, vision, embedding, and `*-fallback` aliases stay internal.
- A saved local model name (for example `qwen2.5:7b`) returns 409 and lists the available models.
- Model downloads return 404 in gateway mode.
- If the gateway is down or returns 5xx or 429, the learner sees "The model service is unavailable.
  Please retry." (HTTP 503, or an SSE error frame). No usage is recorded for a failed call.
- `/health/ready` reports `gateway`, `chat_model`, `embedding_model`, and `vectorstore`.

## Check a deployment

```bash
python scripts/smoke_gateway.py https://your-host --token <workspace key>
```

It runs health, model list, a two-question quiz, and one streamed answer, and exits non-zero on
any failure. Then read the recorded usage from the gateway (`GET /spend/logs/v2` with
`end_user=<workspace>` and a date range).

## Embeddings and existing data

Each gateway embedding model gets its own Chroma collection
(`rag-chatbot--<alias>[-<dimensions>]`), so switching models never mixes vector sizes. Existing
self-hosted data stays in `rag-chatbot`. Material uploaded before a switch must be uploaded again
to be searchable under the new model.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| Every request returns 503 | Gateway unreachable or the key's budget is exhausted. Check `/health/ready` and the gateway logs. |
| Fallback never used | The key is not allowed to call the `*-fallback` aliases. Recreate it with the key script. |
| Answers say safety checking is unavailable | The `guard` alias failed with a non-gateway error. Check the guard model in the gateway config. |
| Usage records are all `estimated` | The provider omits `usage`. Check the alias mapping or the provider. |

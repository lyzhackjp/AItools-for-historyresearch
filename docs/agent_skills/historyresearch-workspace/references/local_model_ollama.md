# Local Model / Ollama

Use this when a task needs local LLM testing, small-model compatibility, or `local_llm` backend validation.

## Defaults

- Provider: `ollama`
- Backend: `local_llm`
- Base URL: `http://localhost:11434`
- OpenAI-compatible URLs ending in `/v1` must be normalized before calling Ollama native `/api/chat`.
- Preferred smoke prompt: `Say OK only.`
- Conservative smoke params: `temperature=0.1`, `max_tokens<=64`, `timeout>=120`.

## Small-Model Prompt Rules

- Ask for one operation at a time.
- Prefer plain text output for smoke tests.
- Avoid JSON until the connection and basic instruction following are verified.
- Keep historical text snippets short and non-sensitive.
- If JSON is required, include one tiny schema and allow fallback parsing.

## Fallback Rules

- Treat empty content as a failed backend result, not as success.
- If `local_llm` returns `empty_content`, `length_limited`, malformed JSON, or low confidence, fall back to `script` or another configured backend.
- Preserve attempted backend metadata so workflow reports can show `local_llm -> script` or similar chains.
- Do not store full prompts or sensitive source text in logs.

## Task Layer

- `TaskManager` includes `summary_local_small` for local Ollama summary smoke tests.
- The preset should remain short-context and low-token so small models can complete it.
- Users may override `OLLAMA_MODEL`; otherwise the workspace default may target the locally available small model.

# Agent Operating Notes

This repository implements a Shanghai-only real estate Agent MVP.

## Non-Negotiable Rules

- Every listing search, recommendation, policy answer, rental/sale flow, marketing copy, and document answer must stay within `city='上海'`.
- Outside-Shanghai requests are refused by `CityGuard`.
- Public marketing copy requires a verified listing with active entrustment.
- OpenAI client creation is centralized in `app/services/openai_service.py`.
- OpenAI API keys are read only from `OPENAI_API_KEY`.
- Tests should remain runnable without a real OpenAI API key.

## Local Development

```bash
docker compose up -d db
python scripts/init_db.py
python scripts/seed_demo_data.py
pytest
```


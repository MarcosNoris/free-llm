# Free LLM API resources

A source-backed list of services offering free hosted LLM API usage, recurring credits, or limited trials.

**Provider offers reviewed: {{REVIEW_DATE}}.** Each entry links to official sources. A catalog refresh does not re-verify an offer or update its review date. Access was checked against public documentation, not by creating accounts or making inference calls.

> [!NOTE]
> Free quotas, recurring credits, trials and compute grants are different offers. Check model eligibility, account verification, regional availability, data-use terms and billing in the provider's console before using an API.

> [!WARNING]
> Please do not abuse these services. This list excludes unofficial services that reverse-engineer consumer chatbots. Free consumer chat access does not imply free API access.

{{TOC}}

{{PROVIDER_SECTIONS}}

## Maintaining this list

Edit `src/providers.py` for offers, categories, conditions, official sources and review dates. Edit `src/README_template.md` for shared text. Do not edit the generated README directly.

Regenerate offline with Python 3.10 or newer (no API keys or third-party dependencies required):

```bash
python src/pull_available_models.py
python src/pull_available_models.py --check
python -m unittest discover -s tests
```

Optionally refresh the public OpenRouter free-model snapshot:

```bash
python src/pull_available_models.py --refresh-models
```

The scheduled workflow only refreshes public model metadata. It does not make billable inference requests or infer free access from an authenticated model listing. Other providers link to their current official catalogs and limits instead of retaining unverified 2025 model tables. Fetching, rendering and staging complete before either output is replaced. If a replacement fails, earlier replacements are rolled back; a rollback failure reports where recovery files were retained. This does not guarantee recovery from a process or machine crash, or concurrent writers. Snapshot timestamps show when model metadata was retrieved, independently of offer review dates.

When updating one provider, set its `reviewed_on` field to the actual review date; change the global review date only after reviewing the whole list. If a current offer cannot be established, retain it under **Offers needing verification** instead of inventing a quota or treating missing evidence as a confirmed discontinuation.

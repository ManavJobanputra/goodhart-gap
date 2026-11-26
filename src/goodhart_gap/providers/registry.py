"""Provider registry: build a provider from a model config name."""

from __future__ import annotations

from goodhart_gap.providers.base import Provider
from goodhart_gap.providers.cost import get_model
from goodhart_gap.providers.openai_compat import OpenAICompatProvider


def make_provider(model_name: str, **kwargs) -> Provider:
    cfg = get_model(model_name)
    return OpenAICompatProvider(cfg, **kwargs)

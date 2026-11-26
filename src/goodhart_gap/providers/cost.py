"""Model config and cost accounting.

Cost is computed conservatively at PEAK prices (the higher of peak/off-peak) so
the budget tracker never under-counts. Cache-hit tokens are billed at the
cache-hit rate when the provider reports them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

MODELS_PATH = Path("configs/models.yaml")


@dataclass
class ModelConfig:
    name: str
    provider: str
    base_url: str
    api_key_env: str
    model: str
    price_input_cache_hit: float
    price_input_cache_miss: float
    price_output: float
    thinking_default: str = "enabled"
    context_tokens: int = 1_000_000
    max_output_tokens: int = 384_000
    price_checked: str = ""


def load_models(path: Path | None = None) -> dict[str, ModelConfig]:
    p = path or MODELS_PATH
    data = yaml.safe_load(p.read_text())
    out: dict[str, ModelConfig] = {}
    for name, m in data["models"].items():
        out[name] = ModelConfig(
            name=name,
            provider=m["provider"],
            base_url=m["base_url"],
            api_key_env=m.get("api_key_env", ""),
            model=m["model"],
            price_input_cache_hit=float(m.get("price_input_cache_hit", 0.0)),
            price_input_cache_miss=float(m.get("price_input_cache_miss", 0.0)),
            price_output=float(m.get("price_output", 0.0)),
            thinking_default=m.get("thinking_default", "enabled"),
            context_tokens=int(m.get("context_tokens", 1_000_000)),
            max_output_tokens=int(m.get("max_output_tokens", 384_000)),
            price_checked=m.get("price_checked", ""),
        )
    return out


def get_model(name: str, path: Path | None = None) -> ModelConfig:
    models = load_models(path)
    if name not in models:
        raise KeyError(f"unknown model {name!r}; known: {sorted(models)}")
    return models[name]


def compute_cost(
    cfg: ModelConfig,
    prompt_tokens: int,
    completion_tokens: int,
    cache_hit_tokens: int = 0,
) -> float:
    """Return USD cost, using cache-hit pricing for reported hit tokens.

    prompt_tokens is the total input; cache_hit_tokens is the portion billed at
    the cache-hit rate. The remainder is billed at cache-miss rate.
    """
    hit = max(0, min(cache_hit_tokens, prompt_tokens))
    miss = max(0, prompt_tokens - hit)
    cost = (
        hit / 1_000_000 * cfg.price_input_cache_hit
        + miss / 1_000_000 * cfg.price_input_cache_miss
        + completion_tokens / 1_000_000 * cfg.price_output
    )
    return cost

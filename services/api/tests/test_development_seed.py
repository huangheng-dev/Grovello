from types import SimpleNamespace

import pytest

from grovello import development_seed


async def test_development_seed_is_disabled_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        development_seed,
        "get_settings",
        lambda: SimpleNamespace(environment="production"),
    )

    with pytest.raises(RuntimeError, match="disabled in production"):
        await development_seed.seed_development_access()

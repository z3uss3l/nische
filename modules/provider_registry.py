"""Production-safe local dataset adapter registry.

Configure NISCHE_DATASETS_DIR to import actual provider snapshots already downloaded
by an authorized source connector. Each JSON file is one provider snapshot.
No unconfigured network requests are made.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from .provider_policy import ProviderPolicy,AccessMode
from .refresh_runtime import ProviderAdapter


def build_adapters():
    root=os.environ.get("NISCHE_DATASETS_DIR","").strip()
    if not root:
        return []
    directory=Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise FileNotFoundError(f"NISCHE_DATASETS_DIR does not exist: {directory}")
    adapters=[]
    for file in sorted(directory.glob("*.json")):
        provider=file.stem
        if not provider.replace("_","").replace("-","").isalnum():
            continue
        def fetch(path=file):
            with path.open("r",encoding="utf-8") as stream:
                return json.load(stream)
        # Local files are not remote requests and do not consume network budget.
        adapters.append(ProviderAdapter(ProviderPolicy(provider,AccessMode.LOCAL,
                          max_fetches_per_day=10000),fetch))
    return adapters

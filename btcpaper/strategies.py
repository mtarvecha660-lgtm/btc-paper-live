"""Loads strategy plug-ins from the strategies/ folder."""
import importlib.util
import sys

import numpy as np
import pandas as pd

from .config import STRATEGY_DIR, ROOT

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class Strategy:
    def __init__(self, module, path, params=None):
        self.module = module
        self.path = path
        self.name = getattr(module, "NAME", path.stem)
        self.description = getattr(module, "DESCRIPTION", "")
        self.params = dict(getattr(module, "PARAMS", {}))
        if params:
            self.params.update(params)
        self.grid = dict(getattr(module, "GRID", {}))

    def signals(self, df):
        out = self.module.compute(df.copy(), dict(self.params))
        if not isinstance(out, pd.DataFrame) or len(out) != len(df):
            raise ValueError(f"{self.name}.compute must return a DataFrame with the same rows as its input")
        for c in ("enter", "exit", "stop"):
            if c not in out:
                raise ValueError(f"{self.name}.compute must return a column '{c}'")
        out["enter"] = out["enter"].fillna(False).astype(bool)
        out["exit"] = out["exit"].fillna(False).astype(bool)
        out["stop"] = out["stop"].astype(float)
        if "trail_stop" in out:
            out["trail_stop"] = out["trail_stop"].astype(float)
        if "note" not in out:
            out["note"] = ""
        out["note"] = out["note"].fillna("").astype(str)
        return out

    def with_params(self, params):
        return Strategy(self.module, self.path, {**self.params, **params})


def _parse_value(v):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return {"true": True, "false": False}.get(v.lower(), v)


def parse_params(pairs):
    out = {}
    for p in pairs or []:
        k, _, v = p.partition("=")
        out[k.strip()] = _parse_value(v.strip())
    return out


def strategy_files():
    return sorted(f for f in STRATEGY_DIR.glob("*.py") if not f.name.startswith("_"))


def load(name_or_path, params=None):
    path = None
    for f in strategy_files():
        if f.stem == name_or_path or str(f) == str(name_or_path):
            path = f
    if path is None:
        from pathlib import Path
        p = Path(name_or_path)
        if p.exists():
            path = p
    if path is None:
        names = ", ".join(f.stem for f in strategy_files())
        raise SystemExit(f"no strategy named {name_or_path!r}. Available: {names}")
    spec = importlib.util.spec_from_file_location(f"strategies.{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "compute"):
        raise SystemExit(f"{path.name} has no compute(df, p) function")
    return Strategy(mod, path, params)


def load_all():
    return [load(f.stem) for f in strategy_files()]

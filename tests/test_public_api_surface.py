"""Golden test: the public API surface of settfex (L1 backward-compat gate).

Walks every public module under ``settfex`` and builds a deterministic, structural
snapshot of the exported surface: function/method signatures, class bases and full
MROs (the exception-hierarchy contract), Pydantic model fields (name, annotation,
required flag, default, alias), computed fields, plain properties, enum members,
and module-level constants. The snapshot is compared against the committed golden
``tests/golden/api_surface.json`` — any diff is a potential L1 break (removed or
renamed export, changed signature, narrowed type, changed default, changed
exception base, removed/renamed field, required<->optional flip, changed alias).

Regenerate (only for an INTENDED, reviewed surface change):

    uv run python -m tests.test_public_api_surface --regen

Running ``--regen`` twice must produce a zero git diff (determinism gate). The
snapshot never records free-form reprs of pydantic internals: models are recorded
structurally from ``model_fields`` (never ``inspect.signature`` on a BaseModel —
pydantic synthesizes ``__init__`` and its rendering is pydantic-version-sensitive).
"""

import importlib
import importlib.metadata
import inspect
import json
import pkgutil
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

GOLDEN_PATH = Path(__file__).parent / "golden" / "api_surface.json"

# model_config keys that are part of the behavioral contract (serialization/intake
# semantics); other keys are implementation detail and deliberately not recorded.
_CONTRACT_CONFIG_KEYS = (
    "populate_by_name",
    "str_strip_whitespace",
    "extra",
    "arbitrary_types_allowed",
    "frozen",
)


def _fmt_ann(ann: Any) -> str | None:
    """Normalize an annotation to a cross-version-stable string."""
    if ann is inspect.Parameter.empty or ann is inspect.Signature.empty:
        return None
    s = ann if isinstance(ann, str) else inspect.formatannotation(ann)
    s = s.replace("typing.", "").replace("collections.abc.", "").replace("NoneType", "None")
    return " ".join(s.split())


def _fmt_default(value: Any) -> str:
    """Stable string form for a default value (never a memory address)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    if isinstance(value, Enum):
        return f"{type(value).__name__}.{value.name}"
    return f"<{type(value).__name__}>"


def _dotted(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _function_entry(func: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": "coroutine" if inspect.iscoroutinefunction(func) else "function",
        "params": [],
    }
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        p: dict[str, Any] = {"name": name, "param_kind": param.kind.name}
        ann = _fmt_ann(param.annotation)
        if ann is not None:
            p["annotation"] = ann
        if param.default is not inspect.Parameter.empty:
            p["default"] = _fmt_default(param.default)
        entry["params"].append(p)
    entry["returns"] = _fmt_ann(sig.return_annotation)
    return entry


def _class_methods(cls: type, *, include_init: bool) -> dict[str, Any]:
    """Public methods defined on settfex classes in the MRO (first definition wins)."""
    methods: dict[str, Any] = {}
    for klass in cls.__mro__:
        if not klass.__module__.startswith("settfex"):
            continue
        for name, member in vars(klass).items():
            if name.startswith("_") and not (include_init and name == "__init__"):
                continue
            if name in methods:
                continue
            if isinstance(member, (classmethod, staticmethod)):
                entry = _function_entry(member.__func__)
                entry["kind"] = "classmethod" if isinstance(member, classmethod) else "staticmethod"
                methods[name] = entry
            elif inspect.isfunction(member):
                methods[name] = _function_entry(member)
    return methods


def _class_entry(cls: type) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "bases": [_dotted(b) for b in cls.__bases__],
        "mro": [_dotted(c) for c in cls.__mro__],
    }
    if issubclass(cls, BaseModel):
        entry["kind"] = "pydantic_model"
        fields: dict[str, Any] = {}
        for fname, finfo in cls.model_fields.items():
            f: dict[str, Any] = {
                "annotation": _fmt_ann(finfo.annotation),
                "required": finfo.is_required(),
                "alias": finfo.alias,
            }
            if finfo.default_factory is not None:
                f["default_factory"] = getattr(finfo.default_factory, "__name__", "<factory>")
            elif not finfo.is_required():
                f["default"] = _fmt_default(finfo.default)
            fields[fname] = f
        entry["fields"] = fields
        entry["computed_fields"] = {
            name: {"annotation": _fmt_ann(info.return_type)}
            for name, info in cls.model_computed_fields.items()
        }
        entry["properties"] = sorted(
            name
            for name, member in inspect.getmembers(cls, lambda m: isinstance(m, property))
            if not name.startswith("_") and name not in cls.model_computed_fields
        )
        config: dict[str, Any] = dict(cls.model_config)
        entry["model_config"] = {key: config[key] for key in _CONTRACT_CONFIG_KEYS if key in config}
        entry["methods"] = _class_methods(cls, include_init=False)
    elif issubclass(cls, BaseException):
        entry["kind"] = "exception"
        entry["methods"] = _class_methods(cls, include_init=True)
    elif issubclass(cls, Enum):
        entry["kind"] = "enum"
        entry["members"] = {member.name: member.value for member in cls}
        entry["methods"] = _class_methods(cls, include_init=False)
    else:
        entry["kind"] = "class"
        entry["properties"] = sorted(
            name
            for name, member in inspect.getmembers(cls, lambda m: isinstance(m, property))
            if not name.startswith("_")
        )
        entry["methods"] = _class_methods(cls, include_init=True)
    return entry


def _module_entry(module: Any) -> dict[str, Any]:
    exports: list[str] = []
    functions: dict[str, Any] = {}
    classes: dict[str, Any] = {}
    constants: dict[str, Any] = {}
    for name, obj in vars(module).items():
        if name.startswith("_") or inspect.ismodule(obj):
            continue
        obj_module = getattr(obj, "__module__", "")
        is_settfex = isinstance(obj_module, str) and obj_module.startswith("settfex")
        is_typing_form = obj_module == "typing"
        is_simple_const = name.isupper() and isinstance(obj, (str, int, float, bool))
        if not (is_settfex or is_typing_form or is_simple_const or name.isupper()):
            continue
        exports.append(name)
        defined_here = obj_module == module.__name__
        if inspect.isclass(obj) and defined_here:
            classes[name] = _class_entry(obj)
        elif inspect.isfunction(obj) and defined_here:
            functions[name] = _function_entry(obj)
        elif name.isupper():
            if isinstance(obj, (str, int, float, bool)):
                constants[name] = {"type": type(obj).__name__, "value": obj}
            else:
                constants[name] = {"type": type(obj).__name__}
    return {
        "all": list(getattr(module, "__all__", None) or []) or None,
        "exports": sorted(exports),
        "functions": functions,
        "classes": classes,
        "constants": constants,
    }


def build_snapshot() -> dict[str, Any]:
    """Build the full public-surface snapshot for the installed settfex package."""
    import settfex

    def _onerror(module_name: str) -> None:
        raise ImportError(f"failed to import {module_name} while walking the package")

    module_names = ["settfex"]
    for info in pkgutil.walk_packages(settfex.__path__, prefix="settfex.", onerror=_onerror):
        if any(part.startswith("_") for part in info.name.split(".")):
            continue
        module_names.append(info.name)

    modules = {name: _module_entry(importlib.import_module(name)) for name in sorted(module_names)}
    return {"format_version": 1, "package": "settfex", "modules": modules}


def canonical(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


class TestPublicApiSurface:
    def test_surface_matches_golden(self):
        """Any diff here is a potential L1 break — investigate before touching the golden.

        Regenerate ONLY for an intended, reviewed surface change:
        uv run python -m tests.test_public_api_surface --regen
        """
        assert GOLDEN_PATH.exists(), (
            f"missing golden {GOLDEN_PATH} — generate it with "
            "`uv run python -m tests.test_public_api_surface --regen`"
        )
        golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        current = build_snapshot()
        assert current == golden

    def test_version_sync(self):
        """pyproject.toml and settfex.__version__ carry the version in two places —
        they must never drift (release.yml validates only pyproject at tag time)."""
        import settfex

        assert settfex.__version__ == importlib.metadata.version("settfex")


if __name__ == "__main__":
    snap = build_snapshot()
    text = canonical(snap)
    if "--regen" in sys.argv[1:]:
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN_PATH.write_text(text, encoding="utf-8")
        print(f"wrote {GOLDEN_PATH} ({len(text.splitlines())} lines)")
    else:
        sys.stdout.write(text)

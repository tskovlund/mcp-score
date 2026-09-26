"""The committed tool reference must match what the generator renders."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

_GENERATOR_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "generate_reference.py"
)


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_reference", _GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


generator = _load_generator()


def test_reference_matches_the_registered_tools() -> None:
    # Arrange
    committed = generator.REFERENCE_PATH.read_text()

    # Act
    generated = asyncio.run(generator.render_reference())

    # Assert: run `uv run scripts/generate_reference.py` after changing a tool
    assert committed == generated


def test_docstring_arguments_become_table_rows() -> None:
    # Arrange
    docstring = (
        "Do a thing.\n\nMore detail.\n\nArgs:\n"
        "    measure: Measure number (1-indexed).\n"
        "    text: Some text that wraps\n        onto a second line.\n\n"
        "Trailing note.\n"
    )

    # Act
    body, arguments, tail = generator.split_docstring(docstring)

    # Assert
    assert body == "Do a thing.\n\nMore detail."
    assert arguments == {
        "measure": "Measure number (1-indexed).",
        "text": "Some text that wraps onto a second line.",
    }
    assert tail == "Trailing note."


def test_parameter_table_reads_types_and_defaults_from_the_schema() -> None:
    # Arrange
    schema = {
        "properties": {
            "measure": {"type": "integer"},
            "staff": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "default": None,
            },
            "text": {"type": "string", "default": "A"},
        },
        "required": ["measure"],
    }

    # Act
    rendered = generator.parameter_table(schema, {"measure": "Measure number."})

    # Assert: prettier-style padded pipe table
    assert rendered.splitlines() == [
        "| Parameter | Type          | Default    | Description     |",
        "| --------- | ------------- | ---------- | --------------- |",
        "| `measure` | `int`         | (required) | Measure number. |",
        "| `staff`   | `int \\| None` | `None`     |                 |",
        '| `text`    | `str`         | `"A"`      |                 |',
    ]


def test_result_renders_fields_and_collects_shared_models() -> None:
    # Arrange: the shape the SDK publishes for a model with a nested model
    schema = {
        "title": "Passage",
        "description": "The measures read.",
        "$defs": {
            "Element": {"title": "Element", "properties": {"type": {"type": "integer"}}}
        },
        "properties": {
            "elements": {"type": "array", "items": {"$ref": "#/$defs/Element"}},
            "warning": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "Why reading stopped.",
            },
        },
    }
    shared: dict[str, dict[str, object]] = {}

    # Act
    rendered = generator.render_result(schema, shared)

    # Assert
    assert rendered.splitlines() == [
        "**Returns** `Passage`: The measures read.",
        "",
        "| Field      | Type            | Description          |",
        "| ---------- | --------------- | -------------------- |",
        "| `elements` | `list[Element]` |                      |",
        "| `warning`  | `str \\| None`   | Why reading stopped. |",
    ]
    assert list(shared) == ["Element"]


def test_wrapped_plain_result_renders_its_type() -> None:
    # Arrange: the SDK wraps a non-model return value as {"result": ...}
    schema = {
        "title": "score_generation_guideOutput",
        "properties": {"result": {"type": "string"}},
    }

    # Act / Assert
    assert generator.render_result(schema, {}) == "**Returns** `str`."


def test_open_model_renders_a_sentence_instead_of_an_empty_table() -> None:
    # Arrange
    schema = {"title": "ApplicationReply", "additionalProperties": True}

    # Act
    rendered = generator.render_result(schema, {})

    # Assert
    assert rendered.endswith("Whatever fields the application sends.")

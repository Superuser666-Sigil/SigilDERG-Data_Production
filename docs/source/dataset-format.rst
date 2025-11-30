Dataset Format
==============

This document describes the output format of the Sigil Pipeline.

JSONL Format
------------

The pipeline outputs JSONL (JSON Lines) files with one JSON object per line.

Basic Structure
~~~~~~~~~~~~~~~

.. code-block:: json

   {"prompt": "Write a Rust function...", "gen": "pub fn example() {...}"}
   {"prompt": "Implement a struct...", "gen": "struct Config {...}"}

Required Fields
~~~~~~~~~~~~~~~

* ``prompt`` (string): The instruction/prompt text
* ``gen`` (string): The expected code output

Metadata Fields (Phase-2)
~~~~~~~~~~~~~~~~~~~~~~~~~

When ``remove_metadata=False``, additional fields are included:

* ``_source_crate`` (string): Name of the source crate
* ``_source_file`` (string): Path to the source file
* ``_task_type`` (string): Task type (code_generation, transformations, error_fixing, explanations)
* ``_source`` (string): Dataset source identifier (phase2, phase1_compat, etc.)

The ``split`` field (train/val) is preserved even when metadata is removed.

Task Types
----------

The Phase-2 instruct mode generates diverse task types:

Code Generation (70%)
~~~~~~~~~~~~~~~~~~~~~

Standard code generation from natural language prompts:

.. code-block:: json

   {
     "prompt": "Write a Rust function parse_config that reads a configuration file.",
     "gen": "pub fn parse_config(path: &str) -> Result<Config, Error> {...}"
   }

Transformations (15%)
~~~~~~~~~~~~~~~~~~~~~

Code transformation tasks:

* sync → async conversion
* match → ? operator conversion
* unwrap → explicit error handling
* for loop → iterator conversion

.. code-block:: json

   {
     "prompt": "Convert this synchronous function to async using Tokio.",
     "gen": "#[tokio::main]\nasync fn fetch_data() {...}"
   }

Error Fixing (10%)
~~~~~~~~~~~~~~~~~~

Fix compiler errors in broken code:

.. code-block:: json

   {
     "prompt": "This Rust code fails with error E0382: use of moved value. Fix it.",
     "gen": "fn process(data: Data) -> Result {...}"
   }

Explanations (5%)
~~~~~~~~~~~~~~~~~

Explain code functionality:

.. code-block:: json

   {
     "prompt": "Explain this Rust function in simple terms: ...",
     "gen": "This function takes a list of numbers and returns the sum..."
   }

Format Compatibility
--------------------

Phase-1 Compatible Mode
~~~~~~~~~~~~~~~~~~~~~~~

Uses the exact Phase 1 format:

* Fixed prompt: "Write a Rust code snippet. Output only the code."
* No backticks in code
* No metadata fields

Phase-2 Instruct Mode
~~~~~~~~~~~~~~~~~~~~~

Uses natural language prompts:

* Variable prompts based on code patterns and documentation
* Semantic chunking (functions, impl blocks, modules)
* Task type diversity

File Size and Chunking
----------------------

Phase-2 Mode Limits
~~~~~~~~~~~~~~~~~~~

* ``max_sft_lines``: Maximum lines per snippet (default: 200)
* ``max_sft_chars``: Maximum characters per snippet (default: 8000)

These ensure training samples are appropriately sized for SFT.

Semantic Chunking
~~~~~~~~~~~~~~~~~

Code is split at semantic boundaries:

* Function definitions
* Impl blocks (max 5 methods)
* Struct/Enum/Trait definitions
* Module definitions (max 10 items)

Encoding
--------

* **Character Encoding**: UTF-8
* **Line Endings**: Unix-style (\\n)
* **JSON Escaping**: Standard JSON escaping for special characters






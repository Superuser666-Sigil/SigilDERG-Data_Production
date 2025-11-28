Configuration
=============

The pipeline uses a ``PipelineConfig`` dataclass for all settings. Configuration can be
provided via:

1. Python constructor arguments
2. JSON configuration files
3. YAML configuration files
4. Command-line arguments

PipelineConfig Reference
------------------------

.. autoclass:: sigil_pipeline.config.PipelineConfig
   :members:
   :undoc-members:

Crate Selection
~~~~~~~~~~~~~~~

* ``crates`` - List of crate names to analyze
* ``crate_list_path`` - Path to file containing crate names (one per line)
* ``limit`` - Maximum number of crates to process

Quality Thresholds
~~~~~~~~~~~~~~~~~~

* ``allow_edition_2018`` - Allow Rust 2018 edition crates (default: False)
* ``max_bad_code_warnings`` - Maximum bad_code clippy warnings (default: 0)
* ``max_clippy_warnings`` - Maximum total clippy warnings (deprecated)
* ``require_docs`` - Require documentation comments (default: True)
* ``min_doc_coverage`` - Minimum documentation coverage ratio (default: 0.0)

License Filtering
~~~~~~~~~~~~~~~~~

* ``allowed_licenses`` - List of allowed license names
* ``enable_license_scan`` - Enable license checking (default: True)

Unsafe Code Filtering
~~~~~~~~~~~~~~~~~~~~~

* ``max_unsafe_items`` - Maximum allowed unsafe code items (None = no limit)
* ``max_outdated_ratio`` - Maximum outdated dependency ratio (None = no limit)

Phase-2 Configuration
~~~~~~~~~~~~~~~~~~~~~

* ``prompt_mode`` - Prompt generation mode ("phase1_compat" or "instruct")
* ``max_sft_lines`` - Maximum lines per snippet (default: 200)
* ``max_sft_chars`` - Maximum characters per snippet (default: 8000)
* ``task_type_mix`` - Task type distribution dictionary

Example Configuration Files
---------------------------

JSON Configuration
~~~~~~~~~~~~~~~~~~

.. code-block:: json

   {
     "crates": ["serde", "tokio"],
     "output_path": "output/dataset.jsonl",
     "max_threads": 4,
     "prompt_mode": "instruct"
   }

YAML Configuration
~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   crates:
     - serde
     - tokio
   output_path: output/dataset.jsonl
   max_threads: 4
   prompt_mode: instruct
   task_type_mix:
     code_generation: 0.70
     transformations: 0.15
     error_fixing: 0.10
     explanations: 0.05

Loading Configuration
---------------------

.. code-block:: python

   from sigil_pipeline.config import PipelineConfig

   # From JSON
   config = PipelineConfig.from_json("config.json")

   # From YAML
   config = PipelineConfig.from_yaml("config.yaml")

   # From dictionary
   config = PipelineConfig.from_dict({
       "crates": ["serde"],
       "output_path": "output/dataset.jsonl"
   })


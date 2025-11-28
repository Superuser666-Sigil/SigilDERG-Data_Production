Quick Start
===========

This guide will get you up and running with Sigil Pipeline in minutes.

Basic Usage
-----------

Analyze Specific Crates
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python -m sigil_pipeline.main --crates serde tokio actix-web

Use a Crate List File
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python -m sigil_pipeline.main --crate-list data/crate_list.txt

Phase-2 Instruct Mode
~~~~~~~~~~~~~~~~~~~~~

Generate diverse task types with semantic chunking:

.. code-block:: bash

   python -m sigil_pipeline.main \
       --prompt-mode instruct \
       --max-sft-lines 200 \
       --max-sft-chars 8000 \
       --output output/phase2_dataset.jsonl

Python API
----------

.. code-block:: python

   import asyncio
   from sigil_pipeline.config import PipelineConfig
   from sigil_pipeline.main import run_pipeline

   async def main():
       config = PipelineConfig(
           crates=["serde", "tokio"],
           output_path="output/dataset.jsonl",
       )
       await run_pipeline(config)

   if __name__ == "__main__":
       asyncio.run(main())

Output Format
-------------

The pipeline generates JSONL files with the following structure:

.. code-block:: json

   {"prompt": "Write a Rust function that...", "gen": "pub fn example() {...}"}
   {"prompt": "Implement a struct with...", "gen": "struct Config {...}"}

Next Steps
----------

* :doc:`configuration` - Learn about all configuration options
* :doc:`filtering` - Understand quality filtering criteria
* :doc:`dataset-format` - Detailed dataset schema documentation



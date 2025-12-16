Command Line Interface
======================

The Sigil Pipeline provides a comprehensive command-line interface for running the
pipeline and managing datasets.

Basic Usage
-----------

.. code-block:: bash

   python -m sigil_pipeline.main [OPTIONS]

Options
-------

Crate Selection
~~~~~~~~~~~~~~~

``--crates CRATE [CRATE ...]``
    Specific crate names to process.

``--crate-list PATH``
    Path to a file containing crate names (one per line).

``--limit N``
    Maximum number of crates to process.

Output Options
~~~~~~~~~~~~~~

``--output PATH``
    Output JSONL file path (default: output/sigil_phase2_dataset.jsonl).

``--log-level LEVEL``
    Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO).

Dataset Generation
~~~~~~~~~~~~~~~~~~

``--max-sft-lines N``
    Maximum lines per snippet (default: 200).

``--max-sft-chars N``
    Maximum characters per snippet (default: 8000).

``--task-mix JSON``
    Task type distribution as JSON string.

Train/Val Split
~~~~~~~~~~~~~~~

``--create-train-val-split``
    Create train/val split by source.

``--val-ratio RATIO``
    Ratio of sources for validation set (default: 0.1).

Checkpointing
~~~~~~~~~~~~~

``--checkpoint-path PATH``
    Path to checkpoint file for resuming.

``--no-checkpointing``
    Disable automatic checkpointing.

``--checkpoint-interval N``
    Save checkpoint every N crates (default: 10).

Examples
--------

Basic Analysis
~~~~~~~~~~~~~~

.. code-block:: bash

   python -m sigil_pipeline.main --crates serde tokio

Generate Dataset
~~~~~~~~~~~~~~~~

.. code-block:: bash

   python -m sigil_pipeline.main \
       --crate-list data/crate_list.txt \
       --max-sft-lines 200 \
       --max-sft-chars 8000 \
       --output datasets/phase2_full.jsonl






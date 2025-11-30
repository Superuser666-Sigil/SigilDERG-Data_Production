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

Phase-2 Options
~~~~~~~~~~~~~~~

``--prompt-mode MODE``
    Prompt generation mode: "phase1_compat" or "instruct" (default: phase1_compat).

``--max-sft-lines N``
    Maximum lines per snippet for Phase-2 (default: 200).

``--max-sft-chars N``
    Maximum characters per snippet for Phase-2 (default: 8000).

``--task-mix JSON``
    Task type distribution as JSON string.

Dataset Merging
~~~~~~~~~~~~~~~

``--merge-with-phase1``
    Merge Phase 2 output with Phase 1 dataset.

``--phase1-dataset-path PATH``
    Path to Phase 1 dataset file.

``--shuffle-merged``
    Shuffle the merged dataset (default: True).

``--phase1-phase2-ratio RATIO``
    Target ratio of Phase-1:Phase-2 samples (e.g., 10.0 = 10:1).

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

Phase-2 Instruct Mode
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python -m sigil_pipeline.main \
       --crate-list data/crate_list.txt \
       --prompt-mode instruct \
       --max-sft-lines 200 \
       --max-sft-chars 8000 \
       --output datasets/phase2_full.jsonl

Merge with Phase 1
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   python -m sigil_pipeline.main \
       --merge-with-phase1 \
       --phase1-dataset-path data/phase1.jsonl \
       --phase1-phase2-ratio 10.0 \
       --create-train-val-split \
       --output output/merged.jsonl






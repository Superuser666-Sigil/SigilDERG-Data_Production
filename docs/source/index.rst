Sigil Pipeline Documentation
============================

**Sigil Pipeline** is a static analysis pipeline for generating high-quality Rust code 
datasets for model fine-tuning. It analyzes Rust crates using static analysis tools 
and generates training datasets in JSONL format.

Version: |release|

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   configuration
   cli
   filtering
   dataset-format

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/modules

.. toctree::
   :maxdepth: 2
   :caption: Development

   contributing
   security
   architecture

.. toctree::
   :maxdepth: 1
   :caption: Appendix

   changelog
   license


Features
--------

* **Static Code Analysis** - Clippy, Geiger, Outdated, License, and Deny checks
* **Quality Filtering** - Modern Rust (2021+), documentation, unsafe code limits
* **Semantic Chunking** - Tree-sitter based code parsing
* **Multiple Task Types** - Code generation, transformations, error fixing, explanations
* **Checkpoint/Resume** - Automatic progress saving for long-running pipelines
* **Streaming Architecture** - Memory-efficient processing of large datasets


Quick Example
-------------

.. code-block:: bash

   # Analyze crates and generate dataset
   python -m sigil_pipeline.main \
       --crate-list data/crate_list.txt \
       --prompt-mode instruct \
       --output datasets/phase2_full.jsonl


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`



Quality Filtering
=================

The Sigil Pipeline applies multiple quality filters to ensure high-quality training data.
This document explains each filter and how to configure them.

Crate-Level Filters
-------------------

These filters determine whether an entire crate should be included or excluded.

Rust Edition
~~~~~~~~~~~~

By default, only Rust 2021+ edition crates are included.

.. code-block:: python

   config = PipelineConfig(
       allow_edition_2018=False,  # Default: only 2021+
   )

**Rationale**: Modern Rust editions have cleaner syntax and better defaults,
making them more suitable for training code generation models.

Clippy Warnings
~~~~~~~~~~~~~~~

The pipeline uses category-based Clippy filtering:

* **bad_code**: Unsafe code, memory safety, logic errors → **causes rejection**
* **safe_to_ignore**: Style/documentation warnings → **ignored**
* **questionable**: May indicate issues but often false positives → **ignored**

.. code-block:: python

   config = PipelineConfig(
       max_bad_code_warnings=0,  # Reject crates with any bad_code warnings
   )

Documentation
~~~~~~~~~~~~~

Crates must have documentation comments:

.. code-block:: python

   config = PipelineConfig(
       require_docs=True,
       min_doc_coverage=0.0,  # Any docs is sufficient
   )

License Filtering
~~~~~~~~~~~~~~~~~

Only permissively licensed code is included:

.. code-block:: python

   config = PipelineConfig(
       enable_license_scan=True,
       allowed_licenses=["MIT", "Apache-2.0", "BSD", "ISC"],
   )

The pipeline handles SPDX expressions like "MIT OR Apache-2.0" correctly.

Unsafe Code Filtering
~~~~~~~~~~~~~~~~~~~~~

Optional threshold for unsafe code items (from cargo-geiger):

.. code-block:: python

   config = PipelineConfig(
       max_unsafe_items=0,  # No unsafe code allowed
   )

Outdated Dependencies
~~~~~~~~~~~~~~~~~~~~~

Optional threshold for outdated dependencies:

.. code-block:: python

   config = PipelineConfig(
       max_outdated_ratio=0.5,  # Max 50% outdated deps
   )

Platform Compatibility
~~~~~~~~~~~~~~~~~~~~~~

Automatically detects and skips platform-specific crates that won't compile
on the current platform (e.g., Windows-only crates on Linux).

File-Level Filters
------------------

These filters apply to individual code files within accepted crates.

Test/Benchmark Exclusion
~~~~~~~~~~~~~~~~~~~~~~~~

Test and benchmark files are automatically excluded:

* Files in ``tests/``, ``benches/``, or ``test/`` directories
* Files ending in ``_test.rs`` or ``_tests.rs``
* Files containing ``#[cfg(test)]``

Size Sanity Filters
~~~~~~~~~~~~~~~~~~~

Based on Stack dataset criteria:

.. code-block:: python

   config = PipelineConfig(
       max_line_length=100,        # Maximum average line length
       min_alphabetic_ratio=0.3,   # Minimum alphabetic character ratio
       max_line_length_hard_cap=500,  # No single line > 500 chars
   )

These filter out:

* Minified code
* Generated code
* Code with excessively long lines

Filter Metrics
--------------

The pipeline provides detailed metrics on filter outcomes:

.. code-block:: json

   {
     "filter_breakdown": {
       "edition": 5,
       "clippy": 12,
       "docs": 3,
       "license": 8,
       "unsafe": 2,
       "platform": 4
     }
   }

This helps identify which filters are most active and tune thresholds accordingly.


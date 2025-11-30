Installation
============

Requirements
------------

* **Python 3.12+** (required - we use modern syntax)
* **Rust toolchain** (1.72+ for 2024 edition, 1.56+ for 2021 edition)
* **Cargo subcommands**:

  * ``cargo clippy`` (included with rustup)
  * ``cargo geiger``
  * ``cargo outdated``
  * ``cargo license``
  * ``cargo deny``

Installation via pip
--------------------

Basic Installation
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install sigil-pipeline

With Optional Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # For HuggingFace dataset integration
   pip install sigil-pipeline[datasets]

   # For full ecosystem integration
   pip install sigil-pipeline[ecosystem]

   # All optional dependencies
   pip install sigil-pipeline[all]

Development Installation
------------------------

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/Superuser666-Sigil/SigilDERG-Data_Production.git
   cd SigilDERG-Data_Production

   # Create virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   # Install in development mode
   pip install -e ".[dev,datasets]"

   # Install pre-commit hooks
   pre-commit install

Installing Cargo Subcommands
----------------------------

.. code-block:: bash

   # Install required cargo subcommands
   cargo install cargo-geiger cargo-outdated cargo-license cargo-deny

   # Add clippy component
   rustup component add clippy

Verifying Installation
----------------------

.. code-block:: bash

   # Check Python installation
   python -c "from sigil_pipeline import config; print('Python OK')"

   # Check Rust toolchain
   cargo --version
   rustup --version

   # Check cargo subcommands
   cargo clippy --version
   cargo geiger --version






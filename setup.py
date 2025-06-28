from typing import Dict, List, Tuple, Optional, Any
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="rust-crate-pipeline",
    version="1.3.3",
    author="SuperUser666-Sigil",
    author_email="miragemodularframework@gmail.com",
    description=(
        "A comprehensive system for gathering, enriching, and analyzing "
        "metadata for Rust crates using AI-powered insights"
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=("https://github.com/Superuser666-Sigil/SigilDERG-Data_Production"),
    project_urls={
        "PyPI": "https://pypi.org/project/rust-crate-pipeline/",
        "Bug Tracker": (
            "https://github.com/Superuser666-Sigil/" "SigilDERG-Data_Production/issues"
        ),
        "Documentation": (
            "https://github.com/Superuser666-Sigil/" "SigilDERG-Data_Production#readme"
        ),
        "Source Code": (
            "https://github.com/Superuser666-Sigil/SigilDERG-Data_Production"
        ),
        "System Audit": (
            "https://github.com/Superuser666-Sigil/"
            "SigilDERG-Data_Production/blob/main/SYSTEM_AUDIT_REPORT.md"
        ),
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "isort>=5.10.0",
        ],
        "advanced": [
            "radon>=6.0.0",
            "rustworkx>=0.13.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "rust-crate-pipeline=rust_crate_pipeline.main:main",
        ],
    },
    keywords="rust crates metadata ai analysis pipeline dependencies",
    include_package_data=True,
)

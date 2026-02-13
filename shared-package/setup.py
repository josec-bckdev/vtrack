"""
Setup configuration for vtrack-shared package.
Provides shared code for all vtrack microservices.
"""

from setuptools import setup, find_packages

setup(
    name="vtrack-shared",
    version="0.1.0",
    description="Shared utilities and models for vtrack microservices",
    author="Vtrack Team",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "redis>=5.0.0",
        "rq>=1.13.0",
        "geopy>=2.3.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0",
    ],
)

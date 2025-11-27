
from setuptools import setup, find_packages

setup(
    name="crypto_trading",
    version="0.1",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
)

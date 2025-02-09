from setuptools import setup, find_packages

setup(
    name="hantu_common",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.2.0",
        "numpy>=1.26.3",
        "ta>=0.11.0",
        "scipy>=1.12.0"
    ],
    author="Hantu Quant",
    author_email="your.email@example.com",
    description="Common library for Hantu Quant trading system",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
) 
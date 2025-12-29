from setuptools import setup, find_packages

setup(
    name="hantu_quant",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "requests>=2.31.0",
        "tenacity>=8.2.0",
        "pydantic>=2.0.0",
        "websockets>=12.0",
        "pandas>=2.2.0",
        "numpy>=1.26.3",
        "sqlalchemy>=2.0.25",
        "python-dotenv>=1.0.0",
        "schedule>=1.2.1",
        "ta>=0.11.0",
        "matplotlib>=3.8.2",
        "seaborn>=0.13.2",
        "plotly>=5.18.0",
        "scipy>=1.12.0",
        "pyarrow>=15.0.0",
        "psutil>=5.9.0",
        "aiohttp>=3.9.0",
    ],
    entry_points={
        "console_scripts": [
            "hantu=cli.main:main",
        ],
    },
    author="Hantu Quant",
    author_email="your.email@example.com",
    description="Quantitative trading system using Korea Investment & Securities API",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
) 
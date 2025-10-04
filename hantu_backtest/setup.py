from setuptools import setup, find_packages

setup(
    name="hantu_backtest",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pandas>=2.2.0",
        "numpy>=1.26.3",
        "matplotlib>=3.8.2",
        "seaborn>=0.13.2",
        "plotly>=5.18.0",
        "scipy>=1.12.0",
        "hantu_common @ file:///Users/grimm/Documents/Dev/hantu_quant/hantu_common"
    ],
    author="Hantu Quant",
    author_email="your.email@example.com",
    description="Backtesting system for Hantu Quant trading strategies",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
) 
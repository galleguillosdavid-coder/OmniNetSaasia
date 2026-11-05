from setuptools import setup, find_packages

setup(
    name="omninet-pro",
    version="1.0.0",
    description="Autonomous Cross-Platform Network Optimizer & Self-Healing Sentinel",
    author="OmniNet Technologies",
    packages=find_packages(),
    py_modules=["main", "mcp_server"],
    install_requires=[],
    entry_points={
        "console_scripts": [
            "omninet=main:main",
            "omninet-agent=main:main",
            "omninet-mcp=mcp_server:main"
        ]
    },
    python_requires=">=3.9",
)


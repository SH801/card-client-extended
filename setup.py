import os

from setuptools import find_packages, setup


def load_requirements(file: str):
    """
    Load requirements file and return non-empty, non-comment lines with leading and trailing
    whitespace stripped.
    """
    with open(os.path.join(os.path.dirname(__file__), file)) as f:
        return [
            line.strip()
            for line in f
            if (
                line.strip() != ""
                and not line.strip().startswith("#")
                and not line.strip().startswith("--")
            )
        ]


setup(
    name="cardclientplus",
    version="1.1.10",
    packages=find_packages(),
    install_requires=load_requirements("requirements.txt"),
    tests_require=load_requirements("requirements-tests.txt"),
    entry_points={
        "console_scripts": [
            "cardclientplus=cardclientplus:main",
        ]
    },
)

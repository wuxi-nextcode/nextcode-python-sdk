#!/usr/bin/env python
import os
import sys

from setuptools import setup, find_packages

if sys.version_info < (3, 6):
    raise NotImplementedError(
        """Genuity Science SDK does not support Python versions older than 3.6"""
    )
version_file = os.path.abspath(os.path.join("nextcode", "VERSION"))

def get_version():
    with open(version_file) as f:
        return f.readlines()[0].strip()

with open("README.md", "r") as fh:
    long_description = fh.read()

version = get_version()

setup(
    name="nextcode-sdk",
    python_requires=">=3.6",
    version=version,
    license="MIT",
    author="WUXI NextCODE",
    author_email="support@wuxinextcode.com",
    description="Python SDK for Genuity Science Services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://www.github.com/wuxi-nextcode/nextcode-python-sdk",
    packages=find_packages(exclude=["tests"]),
    package_data={"nextcode": ["VERSION"]},
    install_requires=[
        "python-dateutil",
        "PyYAML",
        "requests",
        "hjson",
        "PyJWT~=1.7.1",
        "boto3",
        "pytest",
    ],
    extras_require={
        "jupyter": ["pandas", "ipython", "termcolor", "tqdm", "ipywidgets", "plotly"]
    },
    include_package_data=True,
    entry_points={},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Framework :: Jupyter",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    test_suite="tests",
)

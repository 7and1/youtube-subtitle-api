"""
Setup configuration for youtube-subtitle-api-sdk package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="youtube-subtitle-api-sdk",
    version="1.0.0",
    author="YouTube Subtitle API Team",
    author_email="support@expertbeacon.com",
    description="Python SDK for the YouTube Subtitle API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/expertbeacon/youtube-subtitle-api",
    project_urls={
        "Bug Reports": "https://github.com/expertbeacon/youtube-subtitle-api/issues",
        "Source": "https://github.com/expertbeacon/youtube-subtitle-api",
        "Documentation": "https://docs.expertbeacon.com/youtube-subtitle-api",
    },
    package_dir={"": "."},
    packages=find_packages(where="."),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3 :: Only",
        "Typing :: Typed",
    ],
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.27.0,<1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "pytest-cov>=5.0.0",
            "black>=24.0.0",
            "ruff>=0.5.0",
            "mypy>=1.10.0",
        ],
        "fastapi": [
            "fastapi>=0.115.0",
        ],
    },
    keywords=[
        "youtube",
        "subtitles",
        "captions",
        "transcript",
        "api",
        "sdk",
        "async",
        "httpx",
    ],
    package_data={
        "youtube_subtitle_api": ["py.typed"],
    },
    include_package_data=True,
    zip_safe=False,
)

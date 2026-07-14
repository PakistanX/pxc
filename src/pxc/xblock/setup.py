"""setup.py shim for installing pxc-xblock on old toolchains.

pyproject.toml's ``[project]`` table (PEP 621) needs setuptools>=61, which
itself needs Python 3.7+ — unavailable on a real Python 3.5 install (the
target here, see README.md "Compatibility"). ``pip install -e .`` with an
old pip/setuptools also flatly refuses editable installs without a
setup.py. This file carries the actual package metadata so the ancient
setuptools resolved for a Python 3.5 interpreter can build/install this
package at all; pyproject.toml is kept only for its ``[build-system]``
table (and for modern tooling elsewhere in this monorepo that expects one).
"""

from setuptools import setup

setup(
    name="pxc-xblock",
    version="0.1.0",
    description=(
        "PXC XBlock: run PXC activities inside Open edX. Talks to a "
        "separately-deployed pxc-libserver over HTTP instead of embedding "
        "pxc-lib/wasmtime in-process, so it can run on an older Python than "
        "the runtime it delegates to."
    ),
    license="Apache-2.0",
    packages=[
        "pxc.xblock",
        "pxc.xblock.migrations",
        "pxc.xblock.management",
        "pxc.xblock.management.commands",
    ],
    package_dir={
        "pxc.xblock": ".",
        "pxc.xblock.migrations": "migrations",
        "pxc.xblock.management": "management",
        "pxc.xblock.management.commands": "management/commands",
    },
    package_data={
        "pxc.xblock": [
            "static/html/*.html",
            "static/js/*.js",
        ],
    },
    include_package_data=True,
    install_requires=[
        "xblock",
        "web-fragments",
        "Django",
        "requests",
    ],
    entry_points={
        "xblock.v1": [
            "pxc = pxc.xblock.pxc_xblock:PxcXBlock",
        ],
        # Open edX's plugin-app loader (openedx.core.djangoapps.plugins)
        # discovers candidate apps via these entry point groups, THEN reads
        # PxcXBlockConfig.plugin_app for the actual url_config (see apps.py).
        # Without these, the app's plugin_app dict is never inspected at all
        # regardless of INSTALLED_APPS membership — the loader doesn't scan
        # installed apps generically, only packages that declare themselves
        # here.
        "lms.djangoapp": [
            "pxc.xblock = pxc.xblock.apps:PxcXBlockConfig",
        ],
        "cms.djangoapp": [
            "pxc.xblock = pxc.xblock.apps:PxcXBlockConfig",
        ],
    },
)

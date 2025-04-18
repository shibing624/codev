# -*- coding: utf-8 -*-
import sys

from setuptools import setup, find_packages

# Avoids IDE errors, but actual version is read from version.py
__version__ = ""
exec(open('codev/version.py').read())

if sys.version_info < (3,):
    sys.exit('Sorry, Python3 is required.')

with open('README.md', 'r', encoding='utf-8') as f:
    readme = f.read()

setup(
    name='pycodev',
    version=__version__,
    description='codev: Code Agent for Python',
    long_description=readme,
    long_description_content_type='text/markdown',
    author='XuMing',
    author_email='xuming624@qq.com',
    url='https://github.com/shibing624/codev',
    license='Apache License 2.0',
    zip_safe=False,
    python_requires='>=3.8.0',
    entry_points={"console_scripts": ["codev = codev.cli:main"]},
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Natural Language :: Chinese (Simplified)',
        'Natural Language :: Chinese (Traditional)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Topic :: Text Processing',
        'Topic :: Text Processing :: Indexing',
        'Topic :: Text Processing :: Linguistic',
    ],
    keywords='codev,code-agent,code-completion,code-generation,code-assistant',
    install_requires=[
        "loguru",
        "openai",
    ],
    packages=find_packages(exclude=['tests']),
    package_dir={'codev': 'codev'},
    package_data={'codev': ['*.*']}
)

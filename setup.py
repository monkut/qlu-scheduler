from setuptools import setup
from qlu import __version__

setup(
    name='qlu',
    version=__version__,
    packages=['qlu'],
    url='https://github.com/monkut/qlu-scheduler',
    install_requires=['numpy',
                      'toposort',
                      'arrow'],
    license='MIT',
    author='Shane Cousins',
    author_email='shane.cousins@gmail.com',
    description='Project Schedule Estimator',
    classifiers = [
        "Environment :: Console",
        "License :: OSI Approved :: The MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ]

)

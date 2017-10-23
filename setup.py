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
    description='Project Schedule Estimator'
)

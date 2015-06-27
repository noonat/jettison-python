import os
from setuptools import setup


version_file_path = os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                'jettison', '_version.py')
with open(version_file_path, 'r') as version_file:
    exec(compile(version_file.read(), version_file_path, 'exec'))

setup(
    name='jettison',
    version=__version__,  # noqa -- flake8 should ignore this line
    description=('Encode binary data in a way compatible with the jettison '
                 'JavaScript library'),
    url='https://github.com/noonat/jettison-python',
    packages=['jettison'],
    install_requires=[
        'six',
    ],
    extras_require={
        'docs': [
            'sphinx',
        ],
        'tests': [
            'coverage',
            'flake8',
            'mock',
            'pytest',
        ],
    }
)

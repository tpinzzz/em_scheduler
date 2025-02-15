from setuptools import setup, find_packages

setup(
    name="em_scheduler",
    packages=find_packages(),
    version="0.1",
    install_requires=[
        'ortools',
        'pytest'
    ]
)
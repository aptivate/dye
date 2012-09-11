from distutils.core import setup

setup(
    name='DYE',
    version='0.1.0',
    author='Hamish Downer',
    author_email='hamish+dye@aptivate.org',
    packages=['dye', 'dye.test'],
    #scripts=['bin/stowe-towels.py','bin/wash-towels.py'],
    url='http://pypi.python.org/pypi/Dye/',
    license='LICENSE.txt',
    description='A set of functions to improve deploy scripts',
    long_description=open('README.txt').read(),
    install_requires=[
        "fabric >= 0.9",
    ],
)

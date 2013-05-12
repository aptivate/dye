from distutils.core import setup

setup(
    name='dye',
    version='0.1.0',
    author='Hamish Downer',
    author_email='hamish+dye@aptivate.org',
    packages=['dye', 'dye.test'],
    scripts=['dye/tasks.py'],
    url='http://pypi.python.org/pypi/Dye/',
    license='LICENSE.txt',
    description='A set of functions to improve deploy scripts',
    #long_description=open('README.md').read(),
    install_requires=[
        "fabric >= 0.9",
    ],
)

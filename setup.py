from setuptools import setup

setup(
    name='dye',
    version='0.2.0',
    author='Hamish Downer',
    author_email='hamish+dye@aptivate.org',
    packages=['dye', 'dye.test'],
    scripts=['dye/tasks.py'],
    url='http://pypi.python.org/pypi/Dye/',
    license='LICENSE.txt',
    description='A set of functions to improve deploy scripts',
    # long_description=open('README.md').read(),
    install_requires=[
        "fabric == 1.13.2",
        "docopt >= 0.6.1",
        "mysqlclient >= 1.3.10",
        "unittest2 >= 0.5.1",
    ],
    tests_require=[
    ],
    test_suite = "dye.test",
)

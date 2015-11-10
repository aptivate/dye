Installing for Development
==========================

This is how to get a new laptop to run this project.

The basics should be

.. code-block:: sh

   # clone the code - might be github.com
   git clone git@git.aptivate.org:{{cookiecutter.project_name}}.git

   # install the packages and get going
   cd {{cookiecutter.project_name}}/deploy
   ./bootstrap.py
   ./tasks.py deploy:dev

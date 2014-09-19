dye
===

A cookiecutter_ template for Aptivate Django projects.

.. _cookiecutter: https://github.com/audreyr/cookiecutter

Features
---------

Uses standard Aptivate stuff, including

- dye_ for deployment.
- apache/mod_wsgi for the webserver

.. _dye: https://github.com/aptivate/dye

Constraints
-----------


Usage
------

Let's pretend you want to create a Django project called "redditclone". Rather than using `startproject`
and then editing the results to include your name, email, and various configuration issues that always get forgotten until the worst possible moment, get cookiecutter_ to do all the work.

First, get cookiecutter. Trust me, it's awesome::

    $ pip install cookiecutter

Now run it against this repo::

    $ cookiecutter --checkout develop https://github.com/aptivate/dye.git

You'll be prompted for some questions, answer them, then it will create a Django project for you.

**Warning**: After this point, change 'Hamish Downer', 'foobacca', etc to your own information.

It prompts you for questions. Answer them::

    Cloning into 'cookiecutter-django'...
    remote: Counting objects: 49, done.
    remote: Compressing objects: 100% (33/33), done.
    remote: Total 49 (delta 6), reused 48 (delta 5)
    Unpacking objects: 100% (49/49), done.
    project_name (default is "dj-project")? redditclone
    domain_name: (default is "Domain name")?
    author_name: (default is "Your Name")?
    email: (default is "Your email")?
    description: (default is "A short description of the project.")?
    year: (default is "Current year")?
    django_type: (default is "normal")?
    use_pytest: (default is "no")?

Note that django_type can be normal, minimal or cms - this affects what packages
are added.

Enter the project and take a look around::

    $ cd redditclone/
    $ ls

Create a GitHub repo and push it there::

    $ git init
    $ git add .
    $ git commit -m "first awesome commit!"
    $ git remote add origin git@github.com:foobacca/redditclone.git
    $ git push -u origin master

Now take a look at your repo. Awesome, right?

It's time to write the code!!!


"Your Stuff"
-------------

Scattered throughout the Python and HTML of this project are places marked with "your stuff". This is where third-party libraries are to be integrated with your project.


Not Exactly What You Want?
---------------------------

This is what I want. *It might not be what you want.* Don't worry, you have options:

Fork This
~~~~~~~~~~

If you have differences in your preferred setup, I encourage you to fork this to create your own version.
Once you have your fork working, let me know and I'll add it to a '*Similar Cookiecutter Templates*' list here.
It's up to you whether or not to rename your fork.

If you do rename your fork, I encourage you to submit it to the following places:

* cookiecutter_ so it gets listed in the README as a template. 
* The cookiecutter grid_ on Django Packages.

.. _cookiecutter: https://github.com/audreyr/cookiecutter
.. _grid: https://www.djangopackages.com/grids/g/cookiecutter/

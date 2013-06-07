===
DYE
===

DYE is a bacronym for "Deploy Your Environment" - a set of scripts and
functions to deploy your web app along with the required python libraries in a
virtualenv, either locally or on a remote server.

It is built on fabric and was originally built for our technology stack, but is
intended to be able to support a number of different technologies, and to allow
projects to extend it as required.

The core technology stack it has been used with is:

- Django as the web framework of choice, PHP when appropriate
- subversion and git for version control
- MySQL as the database server
- Apache as the web server
- CentOS as the Linux platform for deploying, Ubuntu as the development platform

There is experimental support for Debian/Ubuntu as the Linux platform to deploy
to, and points to plug in support for other webservers.

Contents

.. toctree::
   :maxdepth: 2

   getting-started
   usage
   roadmap
   similar

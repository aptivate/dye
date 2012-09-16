===
DYE
===

DYE is a bacronym for "Deploy Your Environment" - a set of scripts
and functions to deploy your web app, either locally or on a remote
server. It is built on fabric. It is most well developed for Django
web apps, but we have used it for PHP projects aswell.

You should copy the example/ directory to a deploy/ directory in your
project and edit the project_settings.py file. You may also want to add
localtasks.py and/or localfab.py

Expected Project Structure
==========================

Tasks.py
========

tasks.py manages tasks on the local machine, while working in a similar
way to fabric. fabric will call a copy of tasks.py on the remote machine
meaning the code to do common tasks only exists in one place.

localtasks.py
-------------

This is a file where you can define your own functions to do stuff that
you need for your project. You can also override functions from tasklib.py

Fabric and DYE
==============

localfab.py
-----------

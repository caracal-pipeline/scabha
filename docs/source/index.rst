.. stimela documentation master file, created by
   sphinx-quickstart on Mon Oct 24 14:11:23 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Scabha 2.0
===========

Scabha is a configuration management and parameter validation tool for (not just) radio astronomy software applications and pipelines. It combines the flexibility of `OmegaConf <https://omegaconf.readthedocs.io/>`_ and the dynamism of `Click <https://click.palletsprojects.com/>`_ to provide an extensive, flexible and robust framework for createing well-defined configurarions for command-line tools.

Please refer to the `stimela 2.0 reference paper <https://doi.org/10.1016/j.ascom.2025.100959>`_ for an overview.


Getting Started
================

Installation
-----------------
The stable version of scabha can be install from the `Python Packaging Index (PyPI) <https://pypi.org/>`_ ::

   pip install 'scabha>=2.0'

The latest version (not recommended) can be installed from the GitHub *main* branch::

   pip install git+https://github.com/caracal-pipeline/scabha@main


Making a simple command-line app
----------------------------------





.. toctree::
   :maxdepth: 1
   :caption: Contents:

   installation
   reference/reference.rst
   authors
   

.. Indices and tables
.. ==================

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

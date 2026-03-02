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

   pip install git+https://github.com/caracal-pipeline/scabha


Making a simple command-line app
----------------------------------
First provide the app configurarion via a YaML file. In this example, the app takes in two parameters; a name and an integer.

   .. code-block:: yaml
      inputs:
        name: 
          dtype: str
            info: Name to greet
            required: true
            policies:
              positional: true
        count:
          info: Number of greetings
          dtype: int
          default: 1

This file can be converted into a CLI as follows:

.. code-block:: python

    import click
    from scabha.schema_utils import clickify_parameters

    @click.command()
    @clickify_parameters("/path/to/hello_schema.yml")
    def hello(count, name):
        """Simple program that greets NAME for a 
            total of COUNT times."""
        for x in range(count):
            print(f"Hello {name}!")

    if __name__ == '__main__':
        hello()

The ``clickify_paramerers()`` function converts the YaML app configurarion into a CLI using the `click <https://click.palletsprojects.com>`_ package. The resulting tool now has a fully-functional CLI:

.. code-block:: none

    $ python hello.py --help
    Usage: hello.py [OPTIONS] NAME

    Simple program that greets NAME for a total 
    of COUNT times.

    Options:
    --count INTEGER  Number of greetings
    --help           Show this message and exit.

In the example above, the help string app was specified via the docstring of the ``hello()`` function. But it can also be defined in the YaML config file as shown below. This example, also shows how to handle app output products.

.. code-block:: yaml
    info: A Scabha hello
    inputs:
        name: 
            dtype: str
            info: Your name
            required: true
            policies:
                positional: true
            
        language:
           info: Greet in this language
            dtype: str
            choices: [english, isizulu]
            default: english
    outputs:
        saveto:
            info: Save greet to text file
            dtype: File

The ``info`` parameter is not part of the app inputs/outputs and must treated differently. Therefore, instead of parsing the whole config file to ``clickify_parameters()`` we first open it with a YaML file reader, ``OmegaConf`` so it can be passed into the ``click.command()`` separately. 

.. code-block:: python

    import click
    from scabha.schema_utils import clickify_parameters
    from omegaconf import OmegaConf

    app_config = OmegaConf.load("/path/to/mypackage.yml")
   
    @click.command("hello-world", help=app_config.info)
    @clickify_parameters(app_config)
    def hello_world(name, language, saveto):
        greetings = {
        "english": f"Hello, world. My name is {name}.".,
        "isizulu": f"Sawubona, mhlaba. Ngingu {name}.",
        }
        if saveto:
            with open(saveto, "w") as stdw:
                stdw.write(greetings[language])
        else:
            print(greetings[language])
    
    if __name__ == __main__:
        hello_world()
            
Config File Inheritance (``_inlude``and ``_use``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Scabha configurarion file sections and parameters can be shared between apps using the ``_include`` and ``_use`` constructs. Say I wanted to create app that extends the previous app by adding the country of the person making the greeting. 

.. code-block:: yaml
   libs:
      _include: /path/to_old_hello_config.yaml
   
   inputs:
     _use: libs.inputs
     _use: libs.outputs
     country:
       info: Your country
       dtype: str
       default: South Africa

The ``libs`` in the first line is a built-in section set aside for config files meant for inheritance. Inherting parameters can lead to conflicts when inherting from multiple config files as the ``inputs`` sections of previous files will be overwriten by successive ones. For example, this will not work

.. code-block:: yaml
   libs:
     _include:
     - inherit_one.yaml
     - inherit_two.yaml

In such cases, the different files can be labelled:
.. code-block::
   libs:
     one:
       _include: inherit_one
     two:
       _include: inherit_two

Then the inputs from can accessed using ``_use: libs.one.inputs``. 


.. toctree::
   :maxdepth: 1
   :caption: Contents:

   reference/reference.rst
   authors
   

.. Indices and tables
.. ==================

.. * :ref:`genindex`
.. * :ref:`modindex`
.. * :ref:`search`

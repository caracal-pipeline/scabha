
===========
scabha 2.x
===========


|Pypi Version|
|Python Versions|

Scabha is an option parser and parameter validation tool built for (but not limited to) radio interferometry related software applications. The option parser is based on `Click <https://click.palletsprojects.com/>`_.

`Documentation page <https://stimela.readthedocs.io/>`_

`Reference paper <https://doi.org/10.1016/j.ascom.2025.100959/>`_


Installation - User
-------------------

Scabha can be installed using ``pip``. Simply run ``pip install scabha``.

Installation - Developer
------------------------

``uv`` - ``uv`` managed environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After cloning the repo, install with ``uv sync --group dev``. Then run ``uv run pre-commit install`` to set up the pre-commit hooks. By default, you should end up with a correctly configured environment in ``.venv``. ``ruff`` can be invoked manually with ``uv run ruff check`` and ``uv run ruff format``. 


``pip`` managed environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~

After cloning the repo, create a virtual environment with ``virtualenv -p {python_version} path/to/env``. Activate the environment and install with ``pip install -e . --group dev``. Then run ``pre-commit install`` inside the environment to set up the pre-commit hooks. ``ruff`` can be invoked manually with ``ruff check`` and ``ruff format``.

.. |Pypi Version| image:: https://img.shields.io/pypi/v/scabha.svg
                  :target: https://pypi.python.org/pypi/scabha
                  :alt:


.. |Python Versions| image:: https://img.shields.io/pypi/pyversions/scabha.svg
                     :target: https://pypi.python.org/pypi/scabha
                     :alt:

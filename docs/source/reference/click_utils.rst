.. highlight: yml
.. _command_line_apps:


Clickify parameters
===================


For any given command-line tool, most of the information in the cab schema (i.e. argument names and types, help strings) directly mirrors that already provided to the tool's command-line parser. When wrapping a third-party package in a cab, this leads to an unavoidable duplication of effort (with all the attendant potential for inconsistencies) -- after all, the package developer has already implemented their own command-line interface (CLI) parser, and this CLI needs to be described to Stimela. Note, however, that the schema itself provides all the information that would be needed to construct a CLI in the first place. For newly-developed packages, this provides a substantial labour-saving opportunity. Stimela includes a utility function that can convert a schema into a CLI using the `click <https://click.palletsprojects.com>`_ package. For a notional example, consider this 
``hello_schema.yml`` file defining a simple schema with two inputs::

    inputs:
        name: 
            dtype: str
            info: Your name
            required: true
            policies:
                positional: true
            
        count:
            dtype: int
            default: 1
            info: Number of greetings

This file can be instantly converted into a CLI as follows:

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

The resulting tool now has a fully-functional CLI:

.. code-block:: none

    $ python hello.py --help
    Usage: hello.py [OPTIONS] NAME

    Simple program that greets NAME for a total 
    of COUNT times.

    Options:
    --count INTEGER  Number of greetings
    --help           Show this message and exit.

Here is a more extensive, *hello world*, example.

.. code-block:: python

    import click
    from scabha.schema_utils import clickify_parameters
    from omegaconf import OmegaConf

    app_schema = OmegaConf.load("/path/to/mypackage.yml")
    all_params = dict(inputs=app_schema.inputs, outputs=app_schema.outputs)

    @click.command("hello-world", help="Scabha hello world app")
    @clickify_parameters(all_params)
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
            

where ``mypackage.yaml`` contains::
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

App from a stimela Cab
-----------------------
Creating an app from a stimela Cab is very similar to the last example. In fact,  


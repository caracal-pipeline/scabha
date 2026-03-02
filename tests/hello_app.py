import click


@click.command("hello-world", help="Scabha hello world app", no_args_is_help=True)
@click.option("--language", "-l", help="Language.")
@click.option("--saveto", "-s", help="Save message in this file.")
@click.argument("name")
def hello_world(name, language, saveto):
    greetings = {
        "english": f"Hello, world. My name is {name}.",
        "isizulu": f"Sawubona, mhlaba. Ngingu {name}.",
    }
    if saveto:
        with open(saveto, "w") as stdw:
            stdw.write(greetings[language])
    else:
        print(greetings[language])

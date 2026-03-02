#  Adapted  from: https://click.palletsprojects.com/en/stable/complex/#lazily-loading-subcommands
import importlib

import click


class LazyGroup(click.Group):
    def __init__(self, *args, lazy_subcommands=None, parent_module=None, **kwargs):
        super().__init__(*args, **kwargs)
        # lazy_subcommands is a map of the form:
        #
        #   {command-name} -> {module-name}.{command-object-name}
        #
        self.lazy_subcommands = lazy_subcommands or {}
        self.parent_module = parent_module

    def list_commands(self, ctx):
        base = super().list_commands(ctx)
        lazy = sorted(self.lazy_subcommands.keys())
        return base + lazy

    def get_command(self, ctx, cmd_name):
        if cmd_name in self.lazy_subcommands:
            return self._lazy_load(cmd_name)
        return super().get_command(ctx, cmd_name)

    def _lazy_load(self, cmd_name):
        # lazily loading a command, first get the module name and attribute name
        import_path = self.lazy_subcommands[cmd_name]
        if isinstance(import_path, click.Command):
            return import_path
        modname, cmd_object_name = import_path.rsplit(".", 1)
        # do the import
        import_prefix = f"{self.parent_module}." if self.parent_module else ""
        mod = importlib.import_module(import_prefix + modname)
        # get the Command object from that module
        cmd_object = getattr(mod, cmd_object_name)
        # check the result to make debugging easier
        if not isinstance(cmd_object, click.Command):
            raise ValueError(f"Lazy loading of {import_path} failed by returning a non-command object")
        return cmd_object

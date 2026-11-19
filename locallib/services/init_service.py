from pathlib import Path

from loguru import logger


class InitService:
    """Writes the sample ``.dbschemer.toml`` config file.

    The template text is injected by ``ServiceFactory``.
    """

    def __init__(self, template: str):
        self.template = template

    def run(self, path: Path, force: bool = False) -> Path:
        """Write the template to ``path`` and return it.

        Raises ``FileNotFoundError`` if the parent directory is missing (it is
        never created) and ``FileExistsError`` if ``path`` exists and ``force``
        is false.
        """
        parent = path.parent
        if not parent.is_dir():
            raise FileNotFoundError(f"Directory {parent} does not exist")
        # "x" fails atomically if the file exists: no exists()-then-write race.
        mode = "w" if force else "x"
        try:
            with path.open(mode, encoding="utf-8", newline="\n") as f:
                f.write(self.template)
        except FileExistsError:
            raise FileExistsError(
                f"{path} already exists; use --force to overwrite"
            ) from None
        logger.info(f"Wrote sample config to {path}")
        return path

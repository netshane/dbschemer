import re
import tomllib
from pathlib import Path

import pytest

from locallib.services.config_template import CONFIG_TEMPLATE
from locallib.services.init_service import InitService

README = Path(__file__).resolve().parents[2] / "README.md"


@pytest.fixture
def service() -> InitService:
    return InitService(template=CONFIG_TEMPLATE)


@pytest.mark.unit
def test_writes_template(service, tmp_path):
    path = tmp_path / ".dbschemer.toml"
    assert service.run(path) == path
    assert path.read_text(encoding="utf-8") == CONFIG_TEMPLATE


@pytest.mark.unit
def test_template_is_valid_config():
    data = tomllib.loads(CONFIG_TEMPLATE)
    assert set(data["databases"]) == {"sample", "sample2"}
    for name, db in data["databases"].items():
        assert set(db) == {
            "type",
            "server",
            "database",
            "user",
            "password_env_var",
            "output",
        }
        assert db["password_env_var"] == f"DBSCHEMER_PWD_{name}"
        assert db["output"] == f"./docs/db/{name}"


@pytest.mark.unit
def test_template_matches_readme_sample():
    match = re.search(r"```toml\n(.*?)```", README.read_text(encoding="utf-8"), re.S)
    assert match is not None
    assert match.group(1) == CONFIG_TEMPLATE


@pytest.mark.unit
def test_existing_file_is_not_overwritten(service, tmp_path):
    path = tmp_path / ".dbschemer.toml"
    path.write_text("keep me")
    with pytest.raises(FileExistsError, match="use --force"):
        service.run(path)
    assert path.read_text() == "keep me"


@pytest.mark.unit
def test_force_overwrites(service, tmp_path):
    path = tmp_path / ".dbschemer.toml"
    path.write_text("old")
    service.run(path, force=True)
    assert path.read_text(encoding="utf-8") == CONFIG_TEMPLATE


@pytest.mark.unit
def test_missing_parent_directory(service, tmp_path):
    path = tmp_path / "missing" / ".dbschemer.toml"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        service.run(path)
    assert not path.parent.exists()

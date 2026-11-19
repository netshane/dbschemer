# AGENTS.md

- spec and feature documents are stored in `docs/agent/specs/`
- implementation plans are stored in `docs/agent/plans/`
 - If a plan file is provided, write a summary of the implementation in the plan upon completion of implementation.

- repo is hosted on a local forgejo instance at nsforge.netshane.com
- use `fj -H nsforge.netshane.com` commands to interact with the forgejo instance.
    - use `fj -H nsforge.netshane.com pr review [PR_NUMBER] list -a -c` to list all review comments for a specific pull request.

## Coding Practices
- `locallib` - all application modules should be stored here
- `locallib\dependencies.py` - a service factory that should be used for generating all internal classes and modules
- prefer building classes for containting code
- use a dependency injection model where all required dependencies for a class are defined in the constructor. Classes should not construct other classes outside of factory classes and methods.

## Environment
- `uv` is used for dependency management and virtual environments.  Do not use `pip` or `venv`      directly.
- use `uv run python` to run python commands within the uv environment.
- use pytest for all unit tests
- use `uvx ruff format` to autoformat files
- use `uvx ruff check --fix` to lint all files
- use `mypy` to perform static type checking on the codebase and fix issues as needed

## Configuration
- `settings.toml` - Connection string and other settings are stored here
- `secrets.toml` - location for secrets that are excluded from source control

## Test Markers
Configured in `pyproject.toml`:
- `unit` - Standard unit tests
- `slow` - Long-running tests
- `unit_external` - Tests requiring external resources
- `integration` - Tests requiring full environment setup

 ## Memory
 - create notes and lessons learned in the `docs/agent/memory/` directory.  `Use MEMORY.md` as the main file.
 - notes in this file should be very short and concise, capturing only the essential information and key takeaways.
 - Larger notes or explanations should be stored in separate files within the `docs/agent/memory/` directory, and referenced from MEMORY.md as needed.

 - If a spec file is provided, write a summary of the implementation in the spec upon completion of implementation.

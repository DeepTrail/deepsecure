#!/usr/bin/env python3
"""Script to generate alembic.ini configuration file."""

import os
from pathlib import Path

def generate_alembic_ini(output_dir: str = "."):
    """
    Generate alembic.ini file in the specified directory.
    
    Args:
        output_dir: Directory where alembic.ini should be created
    """
    content = """[alembic]
script_location = alembic

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
"""
    
    output_path = Path(output_dir) / "alembic.ini"
    with open(output_path, "w") as f:
        f.write(content)
    
    print(f"✅ Generated alembic.ini at {output_path}")

if __name__ == "__main__":
    # Get the project root (assuming script is in scripts directory)
    project_root = Path(__file__).parent.parent
    generate_alembic_ini(str(project_root)) 
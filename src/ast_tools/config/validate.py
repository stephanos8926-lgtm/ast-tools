"""Config validation command."""

from pathlib import Path


def validate_config(path: Path | None = None) -> dict:
    """Validate all config files. Return list of errors/warnings.

    Args:
        path: Config directory path. Defaults to get_config_dir().

    Returns:
        {"valid": bool, "errors": list[dict]}
    """
    from .loader import get_config_dir

    config_dir = path or get_config_dir()
    errors: list[dict] = []

    # Validate tokens.yaml
    tokens_path = config_dir / "config" / "tokens.yaml"
    if tokens_path.exists():
        import jsonschema
        import yaml

        from .tokens_schema import TOKENS_SCHEMA

        try:
            data = yaml.safe_load(tokens_path.read_text()) or {}
            jsonschema.validate(instance=data, schema=TOKENS_SCHEMA)
        except (yaml.YAMLError, jsonschema.ValidationError) as e:
            errors.append({"file": str(tokens_path), "error": str(e)})
        except OSError as e:
            errors.append({"file": str(tokens_path), "error": f"Cannot read: {e}"})
    else:
        errors.append({"file": str(tokens_path), "warning": "Not found — using defaults"})

    return {"valid": len(errors) == 0, "errors": errors}

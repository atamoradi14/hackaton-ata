"""Names-only deployment checks must not leak configuration values."""
import runpy
from pathlib import Path


CHECK = runpy.run_path(str(Path(__file__).resolve().parents[1] / "deploy/check-env.py"))["check"]


def config(path, quote=True, postgis=False):
    hashed = "$2b$12$" + "a" * 53
    path.write_text("ACME_EMAIL=fixture@example.invalid\nLINZ_API_KEY=fixture-private-value\nCADDY_PASSWORD_HASH="
                    + (f"'{hashed}'" if quote else hashed) + "\n"
                    + ("POSTGIS_PASSWORD=fixture-database-value\n" if postgis else ""))


def test_required_settings_and_secret_values_not_printed(tmp_path, capsys):
    path = tmp_path / "test.env"
    config(path)
    assert CHECK(path)
    output = capsys.readouterr().out
    assert "fixture-private-value" not in output
    assert "fixture@example.invalid" not in output
    assert "$2b$" not in output


def test_empty_environment_is_not_valid(tmp_path):
    assert not CHECK(tmp_path / "missing.env")


def test_retired_login_settings_are_not_required(tmp_path):
    path = tmp_path / "test.env"
    config(path, quote=False)
    assert CHECK(path)


def test_postgis_requirement_is_opt_in(tmp_path):
    path = tmp_path / "test.env"
    config(path)
    assert CHECK(path)
    assert not CHECK(path, postgis=True)
    config(path, postgis=True)
    assert CHECK(path, postgis=True)

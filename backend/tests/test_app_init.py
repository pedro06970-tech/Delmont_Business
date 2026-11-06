from app.main import app


def test_app_title_is_configured() -> None:
    assert app.title == "Delmont Business"

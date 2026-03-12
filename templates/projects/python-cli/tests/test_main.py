from app.main import main


def test_main_runs(capsys):
    main()
    assert "Hello from __PROJECT_NAME__" in capsys.readouterr().out

from server.projects import Project, parse_projects


def test_parses_single_project():
    projects = parse_projects("ahorrapp:/home/ubuntu/AhorrApp")
    assert projects["ahorrapp"] == Project(
        id="ahorrapp", name="AhorrApp", path="/home/ubuntu/AhorrApp"
    )


def test_parses_several_projects():
    projects = parse_projects(
        "ahorrapp:/home/ubuntu/AhorrApp;petwatch:/home/ubuntu/PetWatch1"
    )
    assert list(projects) == ["ahorrapp", "petwatch"]
    assert projects["petwatch"].name == "PetWatch1"


def test_name_ignores_trailing_slash():
    projects = parse_projects("ahorrapp:/home/ubuntu/AhorrApp/")
    assert projects["ahorrapp"].name == "AhorrApp"


def test_ignores_empty_and_malformed_entries():
    projects = parse_projects("ahorrapp:/home/ubuntu/AhorrApp;;sinruta:;:/sin/id")
    assert list(projects) == ["ahorrapp"]


def test_empty_string_gives_no_projects():
    assert parse_projects("") == {}


def test_strips_whitespace():
    projects = parse_projects("  ahorrapp : /home/ubuntu/AhorrApp  ")
    assert projects["ahorrapp"].path == "/home/ubuntu/AhorrApp"

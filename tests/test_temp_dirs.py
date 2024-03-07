from radas import shared

def test_moddir_monkeypatch(monkeypatch, temp_module_directory):
    monkeypatch.setattr(shared, "module_directory", temp_module_directory)
    assert shared.module_directory.resolve() == temp_module_directory.resolve()
    assert (temp_module_directory / "config.yaml").exists()

def test_repdir_monkeypatch(monkeypatch, temp_repository_directory):
    monkeypatch.setattr(shared, "repository_directory", temp_repository_directory)
    assert shared.repository_directory.resolve() == temp_repository_directory.resolve()

def test_open_config_file(monkeypatch, temp_module_directory):
    monkeypatch.setattr(shared, "module_directory", temp_module_directory)
    configuration = shared.open_config_file()

    assert "globals" in configuration
    assert "data_file_config" in configuration
    assert "species" in configuration

def test_open_config_file_from_specified_path(temp_module_directory):
    configuration = shared.open_config_file(temp_module_directory / "config.yaml")

    assert "globals" in configuration
    assert "data_file_config" in configuration
    assert "species" in configuration


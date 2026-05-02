"""Unit tests for aureka.config — focuses on the [asr] section added in
the simplify-asr-backend change."""
import pytest

pytestmark = pytest.mark.unit


def test_asr_default_model_is_medium():
    from aureka.config import Config
    cfg = Config()
    assert cfg.asr.model == "medium"


def test_asr_model_loaded_from_toml(tmp_path):
    from aureka.config import load_config
    p = tmp_path / "test.toml"
    p.write_text('[asr]\nmodel = "large-v3"\n')
    cfg = load_config(p)
    assert cfg.asr.model == "large-v3"


def test_asr_section_optional(tmp_path):
    """Configs without [asr] keep the default."""
    from aureka.config import load_config
    p = tmp_path / "test.toml"
    p.write_text('[llm]\nbase_url = "http://x"\n')
    cfg = load_config(p)
    assert cfg.asr.model == "medium"


def test_asr_model_accepts_arbitrary_string(tmp_path):
    """We don't whitelist; any string is passed through to faster-whisper."""
    from aureka.config import load_config
    p = tmp_path / "test.toml"
    p.write_text('[asr]\nmodel = "Systran/faster-whisper-tiny"\n')
    cfg = load_config(p)
    assert cfg.asr.model == "Systran/faster-whisper-tiny"

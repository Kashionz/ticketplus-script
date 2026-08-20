from pathlib import Path

from src.utils.config import Config


def test_example_config_loads(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    cfg = Config("config/config.example.yaml")
    ticket = cfg.get_ticket_config()
    assert "ticketplus.com.tw" in ticket.activity_url
    assert ticket.quantity >= 1
    assert cfg.bot_refresh_interval >= 200
    assert ticket.country_code == "+886"
    assert ticket.require_exact_quantity is False
    example = Path("config/config.example.yaml").read_text(encoding="utf-8")
    assert "kktix.com/events/sbgr01" in example


def test_local_config_points_to_test_event():
    cfg = Config("config/config.yaml")
    ticket = cfg.get_ticket_config()
    assert "4b47b5360d42451f65704664c40b1c72" in ticket.activity_url
    assert "全區" in ticket.area_priorities

from src.models.ticket_config import TicketConfig


def test_kktix_url_validates():
    cfg = TicketConfig(activity_url="https://kktix.com/events/sbgr01/registrations/new", quantity=2)
    assert cfg.validate() == []
    assert cfg.get_kktix_slug() == "sbgr01"


def test_kktix_organizer_subdomain_validates():
    cfg = TicketConfig(activity_url="https://binliveco.kktix.cc/events/sbgr01", quantity=4)
    assert cfg.validate() == []


def test_kktix_mock_url_validates():
    cfg = TicketConfig(
        activity_url="http://127.0.0.1:8765/events/mock-kktix/registrations/new",
        quantity=2,
    )
    assert cfg.validate() == []
    assert cfg.get_kktix_slug() == "mock-kktix"


def test_kktix_url_without_slug_fails():
    cfg = TicketConfig(activity_url="https://kktix.com/events", quantity=1)
    errors = cfg.validate()
    assert errors


def test_unknown_host_still_fails():
    cfg = TicketConfig(activity_url="https://example.com/foo", quantity=1)
    assert any("ticketplus" in e or "kktix" in e for e in cfg.validate())


def test_ticketplus_still_requires_event_id():
    cfg = TicketConfig(activity_url="https://ticketplus.com.tw/activity/not-an-id", quantity=1)
    assert cfg.validate()


def test_kktix_config_str_uses_slug():
    cfg = TicketConfig(activity_url="https://kktix.com/events/sbgr01/registrations/new", quantity=2)
    assert "sbgr01" in str(cfg)

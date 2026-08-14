"""票券設定資料模型。"""

from dataclasses import dataclass, field
from typing import List, Optional
from ..utils.helpers import extract_event_id, is_mock_url


@dataclass
class TicketConfig:
    """票券購買設定。"""

    activity_url: str = ""
    target_session: str = ""
    quantity: int = 2
    area_priorities: List[str] = field(default_factory=list)
    session_exclude_keywords: List[str] = field(default_factory=list)
    exclusive_code: str = ""
    fallback_first_available: bool = False
    require_exact_quantity: bool = False
    account: str = ""
    password: str = ""
    country_code: str = "+886"

    def get_event_id(self) -> Optional[str]:
        return extract_event_id(self.activity_url)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.activity_url:
            errors.append("活動網址不能為空")
        elif is_mock_url(self.activity_url):
            if not self.get_event_id():
                errors.append("無法從模擬站網址解析 eventId")
        elif "ticketplus.com.tw" not in self.activity_url:
            errors.append("活動網址必須是 ticketplus.com.tw 或本機模擬站")
        elif not self.get_event_id():
            errors.append("無法從活動網址解析 eventId")

        if self.quantity < 1:
            errors.append("購票張數必須大於 0")
        elif self.quantity > 4:
            errors.append("購票張數不能超過 4 張（遠大單場次上限）")
        return errors

    def __str__(self) -> str:
        return (
            f"TicketConfig(event={self.get_event_id()}, "
            f"session={self.target_session!r}, qty={self.quantity}, "
            f"areas={self.area_priorities})"
        )

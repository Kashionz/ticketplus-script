"""票券設定資料模型。"""

from dataclasses import dataclass, field
from typing import List, Optional
from ..utils.helpers import detect_platform, extract_event_id, extract_kktix_slug, is_mock_url


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

    def get_kktix_slug(self) -> Optional[str]:
        return extract_kktix_slug(self.activity_url)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.activity_url:
            errors.append("活動網址不能為空")
        else:
            platform = detect_platform(self.activity_url)
            if platform == "kktix":
                if not self.get_kktix_slug():
                    errors.append("無法從 KKTIX 網址解析活動代碼")
            elif platform == "ticketplus":
                if is_mock_url(self.activity_url) and not self.get_event_id():
                    errors.append("無法從模擬站網址解析 eventId")
                elif not is_mock_url(self.activity_url) and not self.get_event_id():
                    errors.append("無法從活動網址解析 eventId")
            else:
                errors.append("活動網址必須是 ticketplus.com.tw、kktix.com 或本機模擬站")
        if self.quantity < 1:
            errors.append("購票張數必須大於 0")
        elif self.quantity > 4:
            errors.append("購票張數不能超過 4 張")
        return errors

    def __str__(self) -> str:
        event = self.get_kktix_slug() or self.get_event_id()
        return (
            f"TicketConfig(event={event}, "
            f"session={self.target_session!r}, qty={self.quantity}, "
            f"areas={self.area_priorities})"
        )

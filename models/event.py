from dataclasses import dataclass


@dataclass
class Event:
    event_id: str
    event_title: str
    event_summary: str
    category_id: str
    first_seen_at: str
    last_seen_at: str
    status: str

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_title": self.event_title,
            "event_summary": self.event_summary,
            "category_id": self.category_id,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "status": self.status,
        }

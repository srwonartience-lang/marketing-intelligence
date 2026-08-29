from dataclasses import dataclass


@dataclass
class Content:
    content_id: str
    source_id: str
    title: str
    url: str
    published_at: str
    collected_at: str
    author: str
    language: str
    content_type: str
    summary: str
    content_hash: str
    is_duplicate: bool

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "source_id": self.source_id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "author": self.author,
            "language": self.language,
            "content_type": self.content_type,
            "summary": self.summary,
            "content_hash": self.content_hash,
            "is_duplicate": "TRUE" if self.is_duplicate else "FALSE",
        }

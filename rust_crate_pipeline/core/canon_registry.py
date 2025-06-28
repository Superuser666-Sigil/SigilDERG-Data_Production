import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class CanonEntry:
    source: str
    version: str
    authority_level: int
    content_hash: str
    last_validated: str
    expiry: Optional[str] = None

    def is_valid(self) -> bool:
        if self.expiry:
            expiry_time = datetime.fromisoformat(self.expiry)
            return datetime.now(timezone.utc) < expiry_time
        return True


class CanonRegistry:
    
    def __init__(self) -> None:
        self.canon_entries: Dict[str, CanonEntry] = {}
        self.authority_chain: List[str] = []
        self.version = "1.4.0"
        self.logger = logging.getLogger(__name__)
        
        self._initialize_default_canon()
    
    def _initialize_default_canon(self) -> None:
        default_sources = {
            "crates.io": {
                "authority_level": 10,
                "base_url": "https://crates.io/api/v1/",
                "version": "1.4.0",
                "last_validated": datetime.now(timezone.utc).isoformat(),
            },
            "github.com": {
                "authority_level": 8,
                "base_url": "https://api.github.com/",
                "version": "3.0",
                "last_validated": datetime.now(timezone.utc).isoformat(),
            },
            "lib.rs": {
                "authority_level": 6,
                "base_url": "https://lib.rs/",
                "version": "1.3.0",
                "last_validated": datetime.now(timezone.utc).isoformat(),
            },
            "docs.rs": {
                "authority_level": 7,
                "base_url": "https://docs.rs/",
                "version": "1.3.0",
                "last_validated": datetime.now(timezone.utc).isoformat(),
            },
        }
        
        for key, source_info in default_sources.items():
            self.register_canon(
                key=key,
                source=source_info["base_url"],
                content=f"Default Canon source: {key}",
                authority_level=source_info["authority_level"]
            )
    
    def register_canon(
        self, key: str, source: str, content: str, authority_level: int = 5
    ) -> bool:
        try:
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            timestamp = datetime.now(timezone.utc).isoformat()

            canon_entry = CanonEntry(
                source=source,
                version=self.version,
                authority_level=authority_level,
                content_hash=content_hash,
                last_validated=timestamp,
            )

            self.canon_entries[key] = canon_entry
            self.authority_chain.append(f"{timestamp}:{key}:{authority_level}")

            self.logger.info(f"Canon registered: {key} with authority {authority_level}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register Canon {key}: {e}")
            return False

    def get_canon(self, key: str) -> Optional[CanonEntry]:
        if key in self.canon_entries:
            canon = self.canon_entries[key]
            if canon.is_valid():
                return canon
            else:
                self.logger.warning(f"Canon expired: {key}")
                del self.canon_entries[key]
        return None

    def get_valid_canon_sources(self) -> List[str]:
        valid_sources = []
        for key, entry in self.canon_entries.items():
            if entry.is_valid():
                valid_sources.append(key)
        return valid_sources

    def get_authority_level(self, source: str) -> int:
        canon = self.get_canon(source)
        return canon.authority_level if canon else 0

    def audit_trail(self) -> List[str]:
        return self.authority_chain.copy()
    
    def get_canon_summary(self) -> Dict[str, Any]:
        valid_count = len(self.get_valid_canon_sources())
        total_count = len(self.canon_entries)
        
        authority_levels = {}
        for key, entry in self.canon_entries.items():
            level = entry.authority_level
            authority_levels[level] = authority_levels.get(level, 0) + 1
        
        return {
            "total_canon_entries": total_count,
            "valid_canon_entries": valid_count,
            "authority_level_distribution": authority_levels,
            "version": self.version,
            "last_operation": self.authority_chain[-1] if self.authority_chain else None,
        } 
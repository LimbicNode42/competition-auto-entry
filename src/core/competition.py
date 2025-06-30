"""
Competition data models and database operations.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum


class CompetitionStatus(Enum):
    """Competition status enumeration."""
    DISCOVERED = "discovered"
    ELIGIBLE = "eligible"
    ENTERED = "entered"
    FAILED = "failed"
    EXPIRED = "expired"
    INELIGIBLE = "ineligible"


class EntryStatus(Enum):
    """Entry attempt status enumeration."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class Competition:
    """Competition data model."""
    url: str
    title: str
    source: str
    description: str = ""
    deadline: Optional[datetime] = None
    status: CompetitionStatus = CompetitionStatus.DISCOVERED
    terms_url: str = ""
    entry_url: str = ""
    requirements: List[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    hash_id: str = ""
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.requirements is None:
            self.requirements = []
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        if not self.hash_id:
            import hashlib
            content = f"{self.url}{self.title}{self.source}"
            self.hash_id = hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['status'] = self.status.value
        data['deadline'] = self.deadline.isoformat() if self.deadline else None
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        data['requirements'] = ','.join(self.requirements) if self.requirements else ""
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Competition':
        """Create Competition from dictionary."""
        # Convert datetime strings back to datetime objects
        if data.get('deadline'):
            data['deadline'] = datetime.fromisoformat(data['deadline'])
        if data.get('created_at'):
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('updated_at'):
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        
        # Convert status string back to enum
        if 'status' in data:
            data['status'] = CompetitionStatus(data['status'])
        
        # Convert requirements string back to list
        if data.get('requirements'):
            data['requirements'] = data['requirements'].split(',')
        else:
            data['requirements'] = []
        
        return cls(**data)
    
    def is_expired(self) -> bool:
        """Check if competition deadline has passed."""
        if not self.deadline:
            return False
        
        # Handle case where deadline might be a string
        if isinstance(self.deadline, str):
            try:
                # Try to parse string deadline
                from ..utils.helpers import parse_deadline
                deadline_dt = parse_deadline(self.deadline)
                if deadline_dt:
                    return datetime.now() > deadline_dt
                else:
                    return False  # Can't parse deadline, assume not expired
            except Exception:
                return False  # Can't parse deadline, assume not expired
        
        return datetime.now() > self.deadline
    
    def is_eligible(self) -> bool:
        """Check if competition is eligible for entry."""
        return (
            self.status in [CompetitionStatus.DISCOVERED, CompetitionStatus.ELIGIBLE] and
            not self.is_expired()
        )


@dataclass
class CompetitionEntry:
    """Competition entry attempt data model."""
    competition_id: str
    entry_date: datetime
    status: EntryStatus
    confirmation_data: Dict[str, Any] = None
    error_message: str = ""
    retry_count: int = 0
    entry_id: Optional[str] = None
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.confirmation_data is None:
            self.confirmation_data = {}
        if self.entry_date is None:
            self.entry_date = datetime.now()
        if not self.entry_id:
            import uuid
            self.entry_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        data['status'] = self.status.value
        data['entry_date'] = self.entry_date.isoformat()
        data['confirmation_data'] = str(self.confirmation_data) if self.confirmation_data else ""
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CompetitionEntry':
        """Create CompetitionEntry from dictionary."""
        if data.get('entry_date'):
            data['entry_date'] = datetime.fromisoformat(data['entry_date'])
        
        if 'status' in data:
            data['status'] = EntryStatus(data['status'])
        
        if data.get('confirmation_data'):
            import json
            try:
                data['confirmation_data'] = json.loads(data['confirmation_data'])
            except (json.JSONDecodeError, TypeError):
                data['confirmation_data'] = {}
        
        return cls(**data)


@dataclass
class FormField:
    """Form field data model for automated filling."""
    name: str
    field_type: str  # text, email, select, checkbox, radio, etc.
    label: str = ""
    required: bool = False
    value: str = ""
    options: List[str] = None
    placeholder: str = ""
    xpath: str = ""
    css_selector: str = ""
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.options is None:
            self.options = []


@dataclass
class CompetitionForm:
    """Competition entry form data model."""
    url: str
    fields: List[FormField]
    submit_button_selector: str = ""
    terms_checkbox_selector: str = ""
    captcha_present: bool = False
    requires_social_media: List[str] = None
    form_method: str = "POST"
    form_action: str = ""
    
    def __post_init__(self):
        """Initialize computed fields."""
        if self.requires_social_media is None:
            self.requires_social_media = []

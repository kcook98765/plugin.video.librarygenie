
from dataclasses import dataclass, field
from typing import Dict, List, Set, Any, Optional

@dataclass
class Actor:
    """Actor information for cast lists"""
    name: str = ""
    role: str = ""
    order: int = 0
    thumb: str = ""

@dataclass
class MediaItem:
    """Canonical media item representation for movies/episodes/folders"""
    # Core identification
    id: Optional[int] = None
    media_type: str = "movie"  # movie, episode, folder
    title: str = ""
    year: int = 0
    
    # External IDs
    imdb: str = ""
    tmdb: str = ""
    
    # Content info
    plot: str = ""
    genres: List[str] = field(default_factory=list)
    runtime: int = 0  # seconds
    rating: float = 0.0
    votes: int = 0
    studio: str = ""
    country: str = ""
    
    # Technical details
    stream_details: Dict[str, Any] = field(default_factory=dict)
    play_path: str = ""
    is_folder: bool = False
    
    # Visual assets
    art: Dict[str, str] = field(default_factory=dict)  # poster, fanart, thumb, banner, landscape
    
    # Cast and metadata
    cast: List[Actor] = field(default_factory=list)
    context_tags: Set[str] = field(default_factory=set)
    sort_keys: Dict[str, Any] = field(default_factory=dict)
    extras: Dict[str, Any] = field(default_factory=dict)  # for odd fields
    
    def __post_init__(self):
        """Ensure consistent defaults"""
        if not self.title:
            self.title = ""
        if not self.plot:
            self.plot = ""
        if not self.imdb:
            self.imdb = ""
        if not self.tmdb:
            self.tmdb = ""
        if not self.studio:
            self.studio = ""
        if not self.country:
            self.country = ""
        if not self.play_path:
            self.play_path = ""

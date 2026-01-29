"""
Enhanced TMDB API Service with full movie details.

Provides comprehensive movie data including runtime, genres, and more.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from .config import Settings, get_settings
from .utils.cache import PosterCache

logger = logging.getLogger(__name__)

# Template constants
DIVIDER = "━━━━━━━━━━━━━━━━━━━━"
CINEBRAIN_FOOTER = """<i>Powered by CineBrain Movie Bot 🤖</i>"""


@dataclass
class MovieInfo:
    """
    Enhanced movie information from TMDB.
    
    Attributes:
        id: TMDB movie ID.
        title: Movie title.
        year: Release year.
        rating: Vote average (0-10).
        overview: Movie overview/synopsis.
        poster_url: Full URL to the movie poster.
        original_title: Original title in original language.
        runtime: Runtime in minutes.
        genres: List of genre names.
        tagline: Movie tagline.
        release_date: Full release date.
        popularity: Popularity score.
        vote_count: Number of votes.
    """
    id: int
    title: str
    year: Optional[int] = None
    rating: float = 0.0
    overview: str = ""
    poster_url: Optional[str] = None
    original_title: Optional[str] = None
    runtime: Optional[int] = None
    genres: List[str] = field(default_factory=list)
    tagline: Optional[str] = None
    release_date: Optional[str] = None
    popularity: float = 0.0
    vote_count: int = 0
    
    def get_formatted_caption(self) -> str:
        """
        Generate professional formatted caption using template.
        
        Returns:
            HTML formatted caption string.
        """
        # Format year
        year_str = f" ({self.year})" if self.year else ""
        
        # Format rating with stars
        rating_stars = self._get_rating_stars()
        rating_display = f"{rating_stars} {self.rating:.1f}/10"
        if self.vote_count > 0:
            rating_display += f" ({self.vote_count:,} votes)"
        
        # Format runtime
        runtime_str = ""
        if self.runtime:
            hours = self.runtime // 60
            minutes = self.runtime % 60
            if hours > 0:
                runtime_str = f" | ⏱ {hours}h {minutes}m"
            else:
                runtime_str = f" | ⏱ {minutes}m"
        
        # Format genres
        genres_str = ", ".join(self.genres[:3]) if self.genres else "Unknown"
        
        # Format synopsis
        synopsis = self.overview or "No synopsis available."
        if len(synopsis) > 500:
            synopsis = synopsis[:497] + "..."
        
        # Build hashtags
        hashtags = self._generate_hashtags()
        
        # Build the message using template
        message = f"""<b>🎞️ MOVIE: {self.title}{year_str}</b>
<b>✨ Rating:</b> {rating_display}{runtime_str}
<b>🎭 Genre:</b> {genres_str}
{DIVIDER}
💬 <b>Synopsis</b>
<blockquote><i>{synopsis}</i></blockquote>
{DIVIDER}
<i>🍿 Smart recommendations • Upcoming updates • Latest releases • Trending movies</i>

{CINEBRAIN_FOOTER}

{hashtags}"""
        
        return message
    
    def _get_rating_stars(self) -> str:
        """Get star rating display."""
        if self.rating >= 8.0:
            return "⭐⭐⭐⭐⭐"
        elif self.rating >= 6.5:
            return "⭐⭐⭐⭐"
        elif self.rating >= 5.0:
            return "⭐⭐⭐"
        elif self.rating >= 3.5:
            return "⭐⭐"
        else:
            return "⭐"
    
    def _generate_hashtags(self) -> str:
        """Generate relevant hashtags."""
        tags = []
        
        # Title hashtag
        title_tag = self.title.replace(" ", "").replace(":", "").replace("-", "")
        title_tag = ''.join(c for c in title_tag if c.isalnum())
        if title_tag:
            tags.append(f"#{title_tag}")
        
        # Year tag
        if self.year:
            tags.append(f"#{self.year}")
        
        # Genre tags
        for genre in self.genres[:2]:
            genre_tag = genre.replace(" ", "").replace("-", "")
            tags.append(f"#{genre_tag}")
        
        # Quality tags based on rating
        if self.rating >= 8.0:
            tags.append("#MustWatch")
        elif self.rating >= 7.0:
            tags.append("#Recommended")
        
        # General tags
        tags.extend(["#Movies", "#CineBrain"])
        
        return " ".join(tags)
    
    def get_short_info(self) -> str:
        """Get short info for selection list."""
        year_str = f" ({self.year})" if self.year else ""
        return f"{self.title}{year_str} - ⭐ {self.rating:.1f}"


class TMDBError(Exception):
    """Base exception for TMDB-related errors."""
    pass


class TMDBApiError(TMDBError):
    """Exception raised when TMDB API returns an error."""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"TMDB API Error ({status_code}): {message}")


class TMDBRateLimitError(TMDBError):
    """Exception raised when TMDB rate limit is exceeded."""
    pass


class TMDBService:
    """
    Enhanced TMDB service with comprehensive movie data fetching.
    """
    
    def __init__(
        self,
        settings: Optional[Settings] = None,
        poster_cache: Optional[PosterCache] = None
    ) -> None:
        """Initialize the TMDB service."""
        self._settings = settings or get_settings()
        self._poster_cache = poster_cache or PosterCache(
            ttl=self._settings.poster_cache_ttl,
            max_size=self._settings.poster_cache_max_size
        )
        self._client: Optional[httpx.AsyncClient] = None
        
        # Genre ID to name mapping
        self._genre_map = {
            28: "Action", 12: "Adventure", 16: "Animation",
            35: "Comedy", 80: "Crime", 99: "Documentary",
            18: "Drama", 10751: "Family", 14: "Fantasy",
            36: "History", 27: "Horror", 10402: "Music",
            9648: "Mystery", 10749: "Romance", 878: "Science Fiction",
            10770: "TV Movie", 53: "Thriller", 10752: "War",
            37: "Western"
        }
    
    async def __aenter__(self) -> "TMDBService":
        """Async context manager entry."""
        await self._ensure_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def _ensure_client(self) -> None:
        """Ensure the HTTP client is initialized."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.request_timeout),
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def _make_request(
        self,
        endpoint: str,
        params: Optional[dict] = None
    ) -> dict:
        """Make an authenticated request to the TMDB API."""
        await self._ensure_client()
        
        url = f"{self._settings.tmdb_base_url}{endpoint}"
        
        request_params = {"api_key": self._settings.tmdb_api_key}
        if params:
            request_params.update(params)
        
        logger.debug(f"Making TMDB request: {endpoint}")
        
        response = await self._client.get(url, params=request_params)
        
        if response.status_code == 429:
            logger.warning("TMDB rate limit exceeded")
            raise TMDBRateLimitError("Rate limit exceeded")
        
        if response.status_code != 200:
            error_msg = response.json().get("status_message", "Unknown error")
            logger.error(f"TMDB API error: {response.status_code} - {error_msg}")
            raise TMDBApiError(response.status_code, error_msg)
        
        return response.json()
    
    async def search_movie(
        self,
        query: str,
        year: Optional[int] = None
    ) -> Optional[MovieInfo]:
        """
        Search for a movie on TMDB (returns first result).
        
        Args:
            query: Movie title to search for.
            year: Optional release year to narrow search.
            
        Returns:
            MovieInfo for the best matching movie, or None if not found.
        """
        results = await self.search_movies(query, year, limit=1)
        return results[0] if results else None
    
    async def search_movies(
        self,
        query: str,
        year: Optional[int] = None,
        limit: int = 5
    ) -> List[MovieInfo]:
        """
        Search for movies on TMDB (returns multiple results).
        
        Args:
            query: Movie title to search for.
            year: Optional release year to narrow search.
            limit: Maximum number of results to return.
            
        Returns:
            List of MovieInfo objects for matching movies.
        """
        logger.info(f"Searching TMDB for: '{query}' (year: {year})")
        
        params = {"query": query, "language": "en-US", "page": 1}
        if year:
            params["year"] = year
        
        try:
            data = await self._make_request("/search/movie", params)
        except Exception as e:
            logger.error(f"TMDB search failed: {e}")
            return []
        
        results = data.get("results", [])[:limit]
        
        if not results:
            logger.info(f"No results found for: '{query}'")
            return []
        
        movies = []
        for movie_data in results:
            # Get full details for each movie
            movie_id = movie_data.get("id")
            if movie_id:
                full_movie = await self.get_movie(movie_id)
                if full_movie:
                    movies.append(full_movie)
                    continue
            
            # Fallback to basic parsing if full details fail
            movie = self._parse_search_result(movie_data)
            movies.append(movie)
        
        logger.info(f"Found {len(movies)} movies for: '{query}'")
        return movies
    
    async def get_movie(self, movie_id: int) -> Optional[MovieInfo]:
        """
        Get detailed movie information by ID.
        
        Args:
            movie_id: TMDB movie ID.
            
        Returns:
            MovieInfo for the movie, or None if not found.
        """
        logger.debug(f"Fetching TMDB movie details for ID: {movie_id}")
        
        try:
            data = await self._make_request(f"/movie/{movie_id}")
        except Exception as e:
            logger.error(f"TMDB fetch failed: {e}")
            return None
        
        return await self._parse_movie_data(data)
    
    def _parse_search_result(self, data: dict) -> MovieInfo:
        """
        Parse search result into MovieInfo (basic info only).
        
        Args:
            data: Raw movie data from search results.
            
        Returns:
            Parsed MovieInfo object with basic info.
        """
        movie_id = data.get("id", 0)
        
        # Get poster URL
        poster_path = data.get("poster_path")
        poster_url = None
        if poster_path:
            poster_url = f"{self._settings.poster_base_url}{poster_path}"
        
        # Extract release year
        release_date = data.get("release_date", "")
        year = None
        if release_date:
            try:
                year = int(release_date.split("-")[0])
            except (ValueError, IndexError):
                pass
        
        # Extract genres from genre_ids
        genre_ids = data.get("genre_ids", [])
        genres = [self._genre_map.get(gid, "") for gid in genre_ids if gid in self._genre_map]
        
        return MovieInfo(
            id=movie_id,
            title=data.get("title", "Unknown Title"),
            year=year,
            rating=data.get("vote_average", 0.0),
            overview=data.get("overview", ""),
            poster_url=poster_url,
            original_title=data.get("original_title"),
            runtime=None,  # Not available in search results
            genres=genres,
            tagline=None,  # Not available in search results
            release_date=release_date,
            popularity=data.get("popularity", 0.0),
            vote_count=data.get("vote_count", 0)
        )
    
    async def _parse_movie_data(self, data: dict) -> MovieInfo:
        """
        Parse full TMDB movie data into MovieInfo.
        
        Args:
            data: Raw movie data from TMDB movie endpoint.
            
        Returns:
            Parsed MovieInfo object with full details.
        """
        movie_id = data.get("id", 0)
        
        # Try to get poster URL from cache first
        poster_url = await self._poster_cache.get_poster_url(movie_id)
        
        if poster_url is None:
            poster_path = data.get("poster_path")
            if poster_path:
                poster_url = f"{self._settings.poster_base_url}{poster_path}"
                await self._poster_cache.cache_poster_url(movie_id, poster_url)
                logger.debug(f"Cached poster URL for movie {movie_id}")
        
        # Extract release year
        release_date = data.get("release_date", "")
        year = None
        if release_date:
            try:
                year = int(release_date.split("-")[0])
            except (ValueError, IndexError):
                pass
        
        # Extract genres from full movie data
        genres = []
        if "genres" in data:
            genres = [g["name"] for g in data.get("genres", [])]
        
        return MovieInfo(
            id=movie_id,
            title=data.get("title", "Unknown Title"),
            year=year,
            rating=data.get("vote_average", 0.0),
            overview=data.get("overview", ""),
            poster_url=poster_url,
            original_title=data.get("original_title"),
            runtime=data.get("runtime"),  # Full runtime from movie details
            genres=genres,
            tagline=data.get("tagline"),
            release_date=release_date,
            popularity=data.get("popularity", 0.0),
            vote_count=data.get("vote_count", 0)
        )
    
    async def fetch_poster(self, poster_url: str) -> Optional[bytes]:
        """
        Fetch poster image bytes from URL.
        
        Args:
            poster_url: Full URL to the poster image.
            
        Returns:
            Image bytes or None if fetch failed.
        """
        await self._ensure_client()
        
        try:
            logger.debug(f"Fetching poster from: {poster_url}")
            response = await self._client.get(poster_url)
            
            if response.status_code == 200:
                return response.content
            else:
                logger.warning(f"Failed to fetch poster: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching poster: {e}")
            return None


# Singleton instance
_tmdb_service: Optional[TMDBService] = None


async def get_tmdb_service() -> TMDBService:
    """Get the singleton TMDB service instance."""
    global _tmdb_service
    if _tmdb_service is None:
        _tmdb_service = TMDBService()
    return _tmdb_service
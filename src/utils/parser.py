"""
Advanced filename parsing utilities for extracting movie information.

This module provides intelligent parsing of messy movie filenames to extract
clean movie titles suitable for TMDB searches.
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ParsedFilename:
    """
    Represents a parsed movie filename.
    
    Attributes:
        title: The extracted movie title.
        year: The extracted year (if found).
        original_filename: The original filename before parsing.
    """
    title: str
    year: Optional[int]
    original_filename: str


class FilenameParser:
    """
    Advanced parser for extracting movie information from filenames.
    """
    
    def __init__(self) -> None:
        """Initialize the parser with all patterns."""
        self._compile_all_patterns()
    
    def _compile_all_patterns(self) -> None:
        """Compile all regex patterns for efficient matching."""
        
        # ============================================
        # YEAR PATTERN - EXTRACT BEFORE ANYTHING ELSE!
        # ============================================
        self.year_pattern = re.compile(
            r'\b(19[0-9]{2}|20[0-3][0-9])\b'  # 1900-2039
        )
        
        # ============================================
        # FILE EXTENSION
        # ============================================
        self.extension_pattern = re.compile(
            r'\.(mkv|mp4|avi|mov|wmv|flv|webm|m4v|mpg|mpeg|m2ts|ts|vob|3gp|f4v|ogv)'
            r'(?:\.(zip|rar|7z|gz|bz2|xz|tar))?'
            r'(?:\.\d{3,4})?$',
            re.IGNORECASE
        )
        
        # ============================================
        # CHANNEL/GROUP TAGS
        # ============================================
        self.channel_tags = re.compile(
            r'^[@#!~][\w]*?(?:Official|Movies?|Films?|Entertainment|Media|Channel|TG|Bot|Mawa|Troller)[\w]*?[-_\s]+',
            re.IGNORECASE
        )
        
        # Build junk patterns list
        self._build_junk_patterns()
    
    def _build_junk_patterns(self) -> None:
        """Build comprehensive list of junk patterns to remove."""
        
        # ============================================
        # QUALITY/SOURCE PATTERNS - ORDER MATTERS!
        # ============================================
        quality_patterns = [
            # Compound patterns first
            r'\bWEB[-\s]?DL\b',
            r'\bWEB[-\s]?Rip\b',
            r'\bBlu[-\s]?Ray\b',
            r'\bHD[-\s]?Rip\b',
            r'\bDVD[-\s]?Rip\b',
            r'\bBD[-\s]?Rip\b',
            r'\bBR[-\s]?Rip\b',
            
            # Individual components
            r'\b(WEBRip|BluRay|BDRip|BRRip|DVDRip|HDRip)\b',
            r'\b(CAM|TS|TC|SCR|HDTV|PDTV|DSR|DTHRip)\b',
            r'\b(REMUX|PROPER|REPACK|INTERNAL|LIMITED)\b',
            r'\b(UNCUT|UNRATED|EXTENDED|THEATRICAL|REMASTERED)\b',
            r'\b(HYBRID|TRUE)\b',
            
            # Clean up fragments
            r'\b(WEB|DL|Rip|BD|BR|DVD|CD)\b',
            
            # Resolutions
            r'\b(144|240|360|480|576|720|1080|1440|2160)[pPiI]?\b',
            r'\b(4K|8K|2K|UHD|FHD|HD|SD|HQ|LQ)\b',
            
            # HDR
            r'\b(HDR10|HDR|SDR|DoVi|Dolby[-\s]?Vision|DV|HLG)\b',
            r'\b(3D|IMAX)\b',
        ]
        
        # ============================================
        # VIDEO CODECS
        # ============================================
        codec_patterns = [
            r'\b[xXhH]\.?26[45]\b',
            r'\b(HEVC|AVC|AV1|XviD|XVID|DivX|DIVX)\b',
            r'\b(10bit|10-bit|8bit|8-bit)\b',
        ]
        
        # ============================================
        # AUDIO PATTERNS
        # ============================================
        audio_patterns = [
            # Audio codecs
            r'\b(AAC|AC3|E-?AC3|DTS|FLAC|MP3|Opus)\b',
            r'\b(TrueHD|Atmos|ATMOS|DTS-?HD|DTS-?X)\b',
            
            # Dolby patterns
            r'\bDD\+?[0-9\.]*\b',
            
            # Channel patterns
            r'\b[257]\.1\.?[0-9]?\b',  # 5.1, 7.1, etc.
            r'\b\d+\.\d+\b',  # Any X.Y pattern (audio channels)
            
            # Bitrates
            r'\b[0-9]+[kK]bps?\b',
            
            # Audio types
            r'\b(Dual[-\s]?Audio|Multi[-\s]?Audio)\b',
            r'\b(Stereo|Mono)\b',
        ]
        
        # ============================================
        # STREAMING PLATFORMS
        # ============================================
        platforms = [
            'Netflix', 'NF', 'Amazon', 'AMZN', 'Prime', 'Hotstar', 'Disney',
            'DSNP', 'Hulu', 'HBO', 'Max', 'HMAX', 'Apple', 'ATVP',
            'Peacock', 'PCOK', 'Paramount', 'PMTP', 'Zee5', 'SonyLIV',
            'Voot', 'MX', 'Aha', 'AHA', 'SunNXT', 'Hoichoi', 'ALTBalaji',
            'ErosNow', 'JioCinema', 'iTunes', 'YouTube', 'YT'
        ]
        
        # ============================================
        # RELEASE GROUPS
        # ============================================
        groups = [
            'YIFY', 'YTS', 'RARBG', 'PSA', 'SPARKS', 'FGT', 'FLEET',
            'ESubs', 'mkvCinemas', 'TamilRockers', 'TamilBlasters',
            'MoviesVerse', 'HDHub4u', 'KatmovieHD', 'Vegamovies',
            'INFOTAINMENT', 'GalaxyRG', 'EVO', 'TOMMY', 'CMRG'
        ]
        
        # ============================================
        # LANGUAGES
        # ============================================
        languages = [
            'Hindi', 'Tamil', 'Telugu', 'Malayalam', 'Kannada', 'Bengali',
            'Marathi', 'Punjabi', 'Gujarati', 'English', 'Spanish', 'French',
            'German', 'Italian', 'Russian', 'Japanese', 'Korean', 'Chinese',
            'Proper'  # Often appears with language
        ]
        
        # ============================================
        # SUBTITLE PATTERNS
        # ============================================
        subtitle_patterns = [
            r'\b(ESubs?|Subs?|Subtitles?|HI|SDH|CC)\b',
        ]
        
        # ============================================
        # BUILD COMPLETE PATTERN
        # ============================================
        all_patterns = []
        all_patterns.extend(quality_patterns)
        all_patterns.extend(codec_patterns)
        all_patterns.extend(audio_patterns)
        all_patterns.extend([rf'\b{p}\b' for p in platforms])
        all_patterns.extend([rf'\b{g}\b' for g in groups])
        all_patterns.extend([rf'\b{l}\b' for l in languages])
        all_patterns.extend(subtitle_patterns)
        
        self.junk_pattern = re.compile(
            '|'.join(f'({p})' for p in all_patterns),
            re.IGNORECASE
        )
    
    def parse(self, filename: str) -> ParsedFilename:
        """
        Parse a movie filename to extract title and year.
        
        Args:
            filename: The original filename to parse.
            
        Returns:
            ParsedFilename: Parsed filename information.
        """
        logger.debug(f"Parsing filename: {filename}")
        original = filename
        
        # Step 1: Remove extension
        cleaned = self.extension_pattern.sub('', filename)
        logger.debug(f"After extension removal: {cleaned}")
        
        # Step 2: CRITICAL - Extract ALL years and pick the most likely one
        year = None
        year_matches = self.year_pattern.findall(cleaned)
        if year_matches:
            # Take the first valid year (usually the correct one)
            for year_str in year_matches:
                year_candidate = int(year_str)
                if 1900 <= year_candidate <= 2039:
                    year = year_candidate
                    logger.debug(f"Found year: {year}")
                    break
        
        # Step 3: Remove channel tags
        cleaned = self.channel_tags.sub('', cleaned)
        logger.debug(f"After channel removal: {cleaned}")
        
        # Step 4: Remove content in brackets/parentheses
        cleaned = re.sub(r'[\[\(\{][^\]\)\}]*[\]\)\}]', ' ', cleaned)
        
        # Step 5: Replace separators
        cleaned = re.sub(r'[._\-]+', ' ', cleaned)
        logger.debug(f"After separator replacement: {cleaned}")
        
        # Step 6: IMPORTANT - Remove ALL years from the title
        if year:
            cleaned = re.sub(rf'\b{year}\b', '', cleaned)
        # Also remove any other years that might be part of junk
        cleaned = self.year_pattern.sub('', cleaned)
        logger.debug(f"After year removal: {cleaned}")
        
        # Step 7: Remove all junk patterns (multiple aggressive passes)
        prev_cleaned = ""
        passes = 0
        while cleaned != prev_cleaned and passes < 5:
            prev_cleaned = cleaned
            cleaned = self.junk_pattern.sub(' ', cleaned)
            passes += 1
            logger.debug(f"After junk pass {passes}: {cleaned}")
        
        # Step 8: Remove @handles
        cleaned = re.sub(r'@\w+', ' ', cleaned)
        
        # Step 9: Remove unclosed brackets or special chars
        cleaned = re.sub(r'[\[\]\(\)\{\}]', ' ', cleaned)
        
        # Step 10: Remove standalone numbers (but preserve L2, T2, etc.)
        words = cleaned.split()
        filtered_words = []
        for word in words:
            # Skip pure numbers unless they're part of title
            if re.match(r'^[0-9]+$', word):
                # Keep single digit or two digits (could be part of title)
                if len(word) <= 2:
                    # Only keep if it seems like part of a title
                    if filtered_words:  # Has preceding words
                        filtered_words.append(word)
            elif re.match(r'^[A-Za-z][0-9]$', word):
                # Keep patterns like "L2", "T2"
                filtered_words.append(word)
            elif not re.match(r'^[0-9\.\-_]+$', word):
                # Keep if it's not just numbers and punctuation
                filtered_words.append(word)
        
        cleaned = ' '.join(filtered_words)
        
        # Step 11: Clean up whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        logger.debug(f"Final cleaned: {cleaned}")
        
        # Step 12: Fallback if needed
        if len(cleaned) < 2:
            cleaned = self._simple_extraction(original, year)
        
        # Step 13: Title case
        title = self._smart_title_case(cleaned)
        
        result = ParsedFilename(
            title=title,
            year=year,
            original_filename=original
        )
        
        logger.info(f"Parsed '{original}' -> Title: '{title}', Year: {year}")
        return result
    
    def _simple_extraction(self, filename: str, year: Optional[int]) -> str:
        """Simple fallback extraction."""
        cleaned = self.extension_pattern.sub('', filename)
        cleaned = self.channel_tags.sub('', cleaned)
        cleaned = re.sub(r'[._\-]', ' ', cleaned)
        
        words = []
        for word in cleaned.split()[:5]:
            if re.match(r'^\d{4}$', word):
                break
            if re.match(r'^(720|1080|2160)p?$', word, re.IGNORECASE):
                break
            if len(word) > 1:
                words.append(word)
        
        return ' '.join(words) if words else 'Unknown Movie'
    
    def _smart_title_case(self, text: str) -> str:
        """Apply smart title case."""
        if not text:
            return text
        
        lowercase_words = {
            'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor',
            'on', 'at', 'to', 'by', 'of', 'in', 'vs', 'with'
        }
        
        words = text.split()
        result = []
        
        for i, word in enumerate(words):
            # Preserve special patterns like "L2"
            if re.match(r'^[A-Z][0-9]$', word, re.IGNORECASE):
                result.append(word.upper())
            elif i == 0:
                result.append(word.capitalize())
            elif word.lower() in lowercase_words:
                result.append(word.lower())
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)


_parser: Optional[FilenameParser] = None

def get_parser() -> FilenameParser:
    """Get singleton parser."""
    global _parser
    if _parser is None:
        _parser = FilenameParser()
    return _parser

def parse_filename(filename: str) -> ParsedFilename:
    """Parse a filename."""
    return get_parser().parse(filename)
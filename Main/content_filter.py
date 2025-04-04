import re
import logging
import json
import os
import sqlite3
from typing import List, Tuple, Dict, Any, Optional, Set
import string
import unicodedata

logger = logging.getLogger(__name__)

# Constants
DB_NAME = 'image_history.db'
BANNED_WORDS_FILE = os.path.join(os.path.dirname(__file__), 'banned.json')
REGEX_PATTERNS_FILE = os.path.join(os.path.dirname(__file__), 'regex_patterns.json')
CONTEXT_RULES_FILE = os.path.join(os.path.dirname(__file__), 'context_rules.json')

class ContentFilter:
    """Enhanced content filter with regex patterns and context awareness"""
    
    def __init__(self):
        """Initialize the content filter"""
        self.banned_words = set()
        self.regex_patterns = []
        self.context_rules = []
        self.load_banned_words()
        self.load_regex_patterns()
        self.load_context_rules()
        
    def load_banned_words(self):
        """Load banned words from JSON file and database"""
        try:
            # Load from JSON file
            if os.path.exists(BANNED_WORDS_FILE):
                with open(BANNED_WORDS_FILE, 'r') as f:
                    words = json.load(f)
                    self.banned_words.update(self._normalize_words(words))
                    
            # Load from database
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT word FROM banned_words")
            db_words = [row[0] for row in c.fetchall()]
            conn.close()
            
            self.banned_words.update(self._normalize_words(db_words))
            
            logger.info(f"Loaded {len(self.banned_words)} banned words")
            
        except Exception as e:
            logger.error(f"Error loading banned words: {e}")
            
    def load_regex_patterns(self):
        """Load regex patterns from JSON file"""
        try:
            if os.path.exists(REGEX_PATTERNS_FILE):
                with open(REGEX_PATTERNS_FILE, 'r') as f:
                    patterns_data = json.load(f)
                    
                self.regex_patterns = []
                for pattern_data in patterns_data:
                    try:
                        pattern = re.compile(pattern_data['pattern'], re.IGNORECASE)
                        self.regex_patterns.append({
                            'pattern': pattern,
                            'name': pattern_data.get('name', 'Unnamed pattern'),
                            'description': pattern_data.get('description', ''),
                            'severity': pattern_data.get('severity', 'high')
                        })
                    except re.error as e:
                        logger.error(f"Invalid regex pattern '{pattern_data['pattern']}': {e}")
                        
                logger.info(f"Loaded {len(self.regex_patterns)} regex patterns")
            else:
                # Create default regex patterns file
                default_patterns = [
                    {
                        "name": "Email Pattern",
                        "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                        "description": "Matches email addresses",
                        "severity": "medium"
                    },
                    {
                        "name": "URL Pattern",
                        "pattern": r"https?://[^\s]+",
                        "description": "Matches URLs",
                        "severity": "low"
                    },
                    {
                        "name": "Age Pattern",
                        "pattern": r"\b(1[0-7]|[0-9])\s*(?:years?|yrs?|y/o)\s*(?:old|young|age)",
                        "description": "Matches references to underage individuals",
                        "severity": "high"
                    },
                    {
                        "name": "Obfuscated Slurs",
                        "pattern": r"\bn+[^a-zA-Z]*i+[^a-zA-Z]*g+[^a-zA-Z]*g+[^a-zA-Z]*[aeiou]+[^a-zA-Z]*r+\b",
                        "description": "Matches obfuscated racial slurs",
                        "severity": "high"
                    }
                ]
                
                with open(REGEX_PATTERNS_FILE, 'w') as f:
                    json.dump(default_patterns, f, indent=4)
                    
                logger.info(f"Created default regex patterns file with {len(default_patterns)} patterns")
                
                # Load the default patterns
                for pattern_data in default_patterns:
                    try:
                        pattern = re.compile(pattern_data['pattern'], re.IGNORECASE)
                        self.regex_patterns.append({
                            'pattern': pattern,
                            'name': pattern_data.get('name', 'Unnamed pattern'),
                            'description': pattern_data.get('description', ''),
                            'severity': pattern_data.get('severity', 'high')
                        })
                    except re.error as e:
                        logger.error(f"Invalid regex pattern '{pattern_data['pattern']}': {e}")
                
        except Exception as e:
            logger.error(f"Error loading regex patterns: {e}")
            
    def load_context_rules(self):
        """Load context rules from JSON file"""
        try:
            if os.path.exists(CONTEXT_RULES_FILE):
                with open(CONTEXT_RULES_FILE, 'r') as f:
                    self.context_rules = json.load(f)
                    
                logger.info(f"Loaded {len(self.context_rules)} context rules")
            else:
                # Create default context rules file
                default_rules = [
                    {
                        "trigger_word": "young",
                        "allowed_contexts": ["young adult", "young woman", "young man", "young professional"],
                        "disallowed_contexts": ["young girl", "young boy", "very young", "too young"],
                        "description": "Context rules for the word 'young'"
                    },
                    {
                        "trigger_word": "teen",
                        "allowed_contexts": ["nineteen", "eighteen"],
                        "disallowed_contexts": ["thirteen", "fourteen", "fifteen", "sixteen", "seventeen"],
                        "description": "Context rules for the word 'teen'"
                    },
                    {
                        "trigger_word": "small",
                        "allowed_contexts": ["small details", "small features", "small objects"],
                        "disallowed_contexts": ["small girl", "small boy", "small child"],
                        "description": "Context rules for the word 'small'"
                    }
                ]
                
                with open(CONTEXT_RULES_FILE, 'w') as f:
                    json.dump(default_rules, f, indent=4)
                    
                self.context_rules = default_rules
                logger.info(f"Created default context rules file with {len(default_rules)} rules")
                
        except Exception as e:
            logger.error(f"Error loading context rules: {e}")
            
    def _normalize_words(self, words: List[str]) -> Set[str]:
        """Normalize a list of words by removing accents, punctuation, etc."""
        normalized = set()
        for word in words:
            if not word:
                continue
                
            # Convert to lowercase
            word = word.lower()
            
            # Remove accents
            word = ''.join(c for c in unicodedata.normalize('NFD', word)
                          if not unicodedata.combining(c))
                          
            # Remove punctuation
            word = ''.join(c for c in word if c not in string.punctuation)
            
            normalized.add(word)
            
        return normalized
        
    def _normalize_text(self, text: str) -> str:
        """Normalize text for checking against banned words"""
        if not text:
            return ""
            
        # Convert to lowercase
        text = text.lower()
        
        # Remove accents
        text = ''.join(c for c in unicodedata.normalize('NFD', text)
                      if not unicodedata.combining(c))
                      
        # Replace punctuation with spaces
        for c in string.punctuation:
            text = text.replace(c, ' ')
            
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        
        return text
        
    def check_banned_words(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check if text contains any banned words
        
        Args:
            text: The text to check
            
        Returns:
            Tuple of (contains_banned_words, list_of_matched_words)
        """
        if not text:
            return False, []
            
        normalized_text = self._normalize_text(text)
        words = normalized_text.split()
        
        matched_words = []
        for word in words:
            if word in self.banned_words:
                matched_words.append(word)
                
        return bool(matched_words), matched_words
        
    def check_regex_patterns(self, text: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if text matches any regex patterns
        
        Args:
            text: The text to check
            
        Returns:
            Tuple of (has_matches, list_of_matches)
        """
        if not text:
            return False, []
            
        matches = []
        for pattern_data in self.regex_patterns:
            pattern = pattern_data['pattern']
            found_matches = pattern.findall(text)
            
            if found_matches:
                matches.append({
                    'name': pattern_data['name'],
                    'description': pattern_data['description'],
                    'severity': pattern_data['severity'],
                    'matches': found_matches
                })
                
        return bool(matches), matches
        
    def check_context_rules(self, text: str) -> Tuple[bool, List[Dict[str, Any]]]:
        """
        Check if text violates any context rules
        
        Args:
            text: The text to check
            
        Returns:
            Tuple of (has_violations, list_of_violations)
        """
        if not text:
            return False, []
            
        normalized_text = self._normalize_text(text)
        violations = []
        
        for rule in self.context_rules:
            trigger_word = rule['trigger_word'].lower()
            
            # Check if trigger word is in the text
            if trigger_word not in normalized_text:
                continue
                
            # Check for disallowed contexts
            for context in rule.get('disallowed_contexts', []):
                if context.lower() in normalized_text:
                    violations.append({
                        'trigger_word': trigger_word,
                        'disallowed_context': context,
                        'description': rule.get('description', '')
                    })
                    
            # Check if any allowed context is present
            if rule.get('allowed_contexts'):
                allowed_found = False
                for context in rule['allowed_contexts']:
                    if context.lower() in normalized_text:
                        allowed_found = True
                        break
                        
                # If trigger word is present but no allowed context is found, it's a violation
                if not allowed_found:
                    violations.append({
                        'trigger_word': trigger_word,
                        'missing_allowed_context': True,
                        'description': rule.get('description', '')
                    })
                    
        return bool(violations), violations
        
    def check_content(self, text: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if content violates any filtering rules
        
        Args:
            text: The text to check
            
        Returns:
            Tuple of (is_banned, details)
        """
        if not text:
            return False, {}
            
        # Check banned words
        has_banned_words, banned_words = self.check_banned_words(text)
        
        # Check regex patterns
        has_regex_matches, regex_matches = self.check_regex_patterns(text)
        
        # Check context rules
        has_context_violations, context_violations = self.check_context_rules(text)
        
        # Determine if content is banned
        is_banned = has_banned_words or has_regex_matches or has_context_violations
        
        # Compile details
        details = {
            'banned_words': banned_words,
            'regex_matches': regex_matches,
            'context_violations': context_violations,
            'is_banned': is_banned
        }
        
        return is_banned, details
        
    def add_banned_word(self, word: str) -> bool:
        """
        Add a word to the banned words list
        
        Args:
            word: The word to add
            
        Returns:
            True if the word was added, False otherwise
        """
        try:
            # Normalize the word
            normalized = list(self._normalize_words([word]))
            if not normalized:
                return False
                
            word = normalized[0]
            
            # Add to database
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO banned_words (word) VALUES (?)", (word,))
            conn.commit()
            conn.close()
            
            # Add to in-memory set
            self.banned_words.add(word)
            
            # Update JSON file
            self._save_banned_words_to_json()
            
            return True
            
        except Exception as e:
            logger.error(f"Error adding banned word: {e}")
            return False
            
    def remove_banned_word(self, word: str) -> bool:
        """
        Remove a word from the banned words list
        
        Args:
            word: The word to remove
            
        Returns:
            True if the word was removed, False otherwise
        """
        try:
            # Normalize the word
            normalized = list(self._normalize_words([word]))
            if not normalized:
                return False
                
            word = normalized[0]
            
            # Remove from database
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("DELETE FROM banned_words WHERE word = ?", (word,))
            conn.commit()
            conn.close()
            
            # Remove from in-memory set
            if word in self.banned_words:
                self.banned_words.remove(word)
                
            # Update JSON file
            self._save_banned_words_to_json()
            
            return True
            
        except Exception as e:
            logger.error(f"Error removing banned word: {e}")
            return False
            
    def _save_banned_words_to_json(self):
        """Save banned words to JSON file"""
        try:
            with open(BANNED_WORDS_FILE, 'w') as f:
                json.dump(sorted(list(self.banned_words)), f, indent=4)
                
        except Exception as e:
            logger.error(f"Error saving banned words to JSON: {e}")
            
    def add_regex_pattern(self, name: str, pattern: str, description: str = "", severity: str = "medium") -> bool:
        """
        Add a regex pattern to the filter
        
        Args:
            name: Name of the pattern
            pattern: Regex pattern string
            description: Description of the pattern
            severity: Severity level (low, medium, high)
            
        Returns:
            True if the pattern was added, False otherwise
        """
        try:
            # Validate the pattern
            try:
                compiled_pattern = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                logger.error(f"Invalid regex pattern '{pattern}': {e}")
                return False
                
            # Add to in-memory list
            self.regex_patterns.append({
                'pattern': compiled_pattern,
                'name': name,
                'description': description,
                'severity': severity
            })
            
            # Update JSON file
            patterns_data = []
            for p in self.regex_patterns:
                if hasattr(p['pattern'], 'pattern'):
                    pattern_str = p['pattern'].pattern
                else:
                    pattern_str = str(p['pattern'])
                    
                patterns_data.append({
                    'name': p['name'],
                    'pattern': pattern_str,
                    'description': p['description'],
                    'severity': p['severity']
                })
                
            with open(REGEX_PATTERNS_FILE, 'w') as f:
                json.dump(patterns_data, f, indent=4)
                
            return True
            
        except Exception as e:
            logger.error(f"Error adding regex pattern: {e}")
            return False
            
    def remove_regex_pattern(self, name: str) -> bool:
        """
        Remove a regex pattern from the filter
        
        Args:
            name: Name of the pattern to remove
            
        Returns:
            True if the pattern was removed, False otherwise
        """
        try:
            # Find the pattern
            for i, pattern_data in enumerate(self.regex_patterns):
                if pattern_data['name'] == name:
                    # Remove from in-memory list
                    del self.regex_patterns[i]
                    
                    # Update JSON file
                    patterns_data = []
                    for p in self.regex_patterns:
                        if hasattr(p['pattern'], 'pattern'):
                            pattern_str = p['pattern'].pattern
                        else:
                            pattern_str = str(p['pattern'])
                            
                        patterns_data.append({
                            'name': p['name'],
                            'pattern': pattern_str,
                            'description': p['description'],
                            'severity': p['severity']
                        })
                        
                    with open(REGEX_PATTERNS_FILE, 'w') as f:
                        json.dump(patterns_data, f, indent=4)
                        
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error removing regex pattern: {e}")
            return False
            
    def add_context_rule(self, trigger_word: str, allowed_contexts: List[str] = None, 
                        disallowed_contexts: List[str] = None, description: str = "") -> bool:
        """
        Add a context rule to the filter
        
        Args:
            trigger_word: The word that triggers the rule
            allowed_contexts: List of allowed contexts for the trigger word
            disallowed_contexts: List of disallowed contexts for the trigger word
            description: Description of the rule
            
        Returns:
            True if the rule was added, False otherwise
        """
        try:
            if not trigger_word:
                return False
                
            if not allowed_contexts and not disallowed_contexts:
                return False
                
            # Add to in-memory list
            self.context_rules.append({
                'trigger_word': trigger_word,
                'allowed_contexts': allowed_contexts or [],
                'disallowed_contexts': disallowed_contexts or [],
                'description': description
            })
            
            # Update JSON file
            with open(CONTEXT_RULES_FILE, 'w') as f:
                json.dump(self.context_rules, f, indent=4)
                
            return True
            
        except Exception as e:
            logger.error(f"Error adding context rule: {e}")
            return False
            
    def remove_context_rule(self, trigger_word: str) -> bool:
        """
        Remove a context rule from the filter
        
        Args:
            trigger_word: The trigger word of the rule to remove
            
        Returns:
            True if the rule was removed, False otherwise
        """
        try:
            # Find the rule
            for i, rule in enumerate(self.context_rules):
                if rule['trigger_word'] == trigger_word:
                    # Remove from in-memory list
                    del self.context_rules[i]
                    
                    # Update JSON file
                    with open(CONTEXT_RULES_FILE, 'w') as f:
                        json.dump(self.context_rules, f, indent=4)
                        
                    return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error removing context rule: {e}")
            return False

# Create a singleton instance
content_filter = ContentFilter()

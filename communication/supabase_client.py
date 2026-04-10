"""
Supabase client for fetching emergency contacts and safe locations.
Uses REST API directly via requests (no heavy supabase-py dependency).
"""

import requests
from typing import List, Dict, Optional, Tuple
import time


class SupabaseClient:
    """
    Lightweight Supabase REST client for the emergency system.
    Fetches family_members (contacts) and safe_locations from Supabase.
    """
    
    def __init__(self, url: str, key: str, logger):
        """
        Initialize Supabase client.
        
        Args:
            url: Supabase project URL
            key: Supabase anon key
            logger: Logger instance
        """
        self.url = url.rstrip('/')
        self.key = key
        self.logger = logger
        
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        
        # Cached data
        self._contacts: List[Dict] = []
        self._safe_location: Optional[Dict] = None
    
    def fetch_contacts(self) -> List[str]:
        """
        Fetch emergency contact phone numbers from family_members table.
        
        Returns:
            List of phone numbers
        """
        try:
            response = requests.get(
                f"{self.url}/rest/v1/family_members",
                headers=self.headers,
                params={
                    "select": "name,phone",
                },
                timeout=10
            )
            
            if response.status_code == 200:
                self._contacts = response.json()
                # Normalize phones (remove spaces) and deduplicate
                seen = set()
                phones = []
                for c in self._contacts:
                    phone = c.get("phone", "").replace(" ", "")
                    if phone and phone not in seen:
                        seen.add(phone)
                        phones.append(phone)
                        self.logger.info(f"  Contact: {c.get('name', 'Unknown')} - {phone}")
                
                self.logger.info(f"Loaded {len(phones)} unique emergency contacts from Supabase")
                return phones
            else:
                self.logger.error(f"Supabase contacts fetch failed: {response.status_code} - {response.text}")
                return []
                
        except requests.exceptions.Timeout:
            self.logger.error("Supabase contacts fetch timed out")
            return []
        except Exception as e:
            self.logger.error(f"Supabase contacts fetch error: {e}")
            return []
    
    def fetch_safe_location(self) -> Optional[Tuple[float, float]]:
        """
        Fetch safe location (home) coordinates from safe_locations table.
        Returns the most recently created safe location for the user.
        
        Returns:
            Tuple of (latitude, longitude) or None
        """
        try:
            response = requests.get(
                f"{self.url}/rest/v1/safe_locations",
                headers=self.headers,
                params={
                    "select": "name,latitude,longitude",
                    "order": "created_at.desc",
                    "limit": "1",
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    loc = data[0]
                    self._safe_location = loc
                    lat = loc["latitude"]
                    lon = loc["longitude"]
                    name = loc.get("name", "Home")
                    self.logger.info(f"Safe location loaded: {name} ({lat:.6f}, {lon:.6f})")
                    return (lat, lon)
                else:
                    self.logger.warning("No safe locations found in Supabase for this user")
                    return None
            else:
                self.logger.error(f"Supabase safe location fetch failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            self.logger.error("Supabase safe location fetch timed out")
            return None
        except Exception as e:
            self.logger.error(f"Supabase safe location fetch error: {e}")
            return None
    
    def fetch_all(self) -> Dict:
        """
        Fetch both contacts and safe location.
        
        Returns:
            Dict with 'contacts' (list of phone numbers) and 'safe_location' (lat, lon tuple or None)
        """
        contacts = self.fetch_contacts()
        safe_location = self.fetch_safe_location()
        
        return {
            "contacts": contacts,
            "safe_location": safe_location,
        }

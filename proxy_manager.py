"""
Webshare Proxy Rotation Manager.
Supports single rotating proxy endpoint (e.g. p.webshare.io:80) or list of rotating proxies.
"""

import os
import random
import itertools
from typing import Optional, List
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("proxy_manager")


class ProxyManager:
    def __init__(
        self,
        proxy_url: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
        proxy_file: Optional[str] = "proxies.txt"
    ):
        self.proxies: List[str] = []
        
        # 1. Direct Webshare rotating proxy URL (from env or argument)
        env_url = proxy_url or os.getenv("WEBSHARE_PROXY_URL")
        if env_url:
            self.proxies.append(env_url.strip())
            
        # 2. Comma-separated list from env
        env_list = os.getenv("WEBSHARE_PROXIES")
        if env_list:
            for p in env_list.split(","):
                p_clean = p.strip()
                if p_clean and p_clean not in self.proxies:
                    self.proxies.append(self._format_proxy(p_clean))

        # 3. Passed proxy list
        if proxy_list:
            for p in proxy_list:
                p_clean = self._format_proxy(p.strip())
                if p_clean and p_clean not in self.proxies:
                    self.proxies.append(p_clean)

        # 4. Proxy file if present
        if proxy_file and os.path.exists(proxy_file):
            with open(proxy_file, "r", encoding="utf-8") as f:
                for line in f:
                    p_clean = self._format_proxy(line.strip())
                    if p_clean and p_clean not in self.proxies:
                        self.proxies.append(p_clean)

        self._cycle = itertools.cycle(self.proxies) if self.proxies else None
        
        if self.proxies:
            logger.info(f"Initialized ProxyManager with {len(self.proxies)} proxy endpoints.")
        else:
            logger.info("No proxy configured. Running in direct connection mode.")

    def _format_proxy(self, raw_proxy: str) -> str:
        """Formats ip:port:user:pass or user:pass@ip:port into http://user:pass@ip:port"""
        if not raw_proxy:
            return ""
        if raw_proxy.startswith("http://") or raw_proxy.startswith("https://"):
            return raw_proxy
            
        # Check if ip:port:user:pass format
        parts = raw_proxy.split(":")
        if len(parts) == 4:
            ip, port, user, password = parts
            return f"http://{user}:{password}@{ip}:{port}"
        elif len(parts) == 2:
            ip, port = parts
            return f"http://{ip}:{port}"
        return f"http://{raw_proxy}"

    def is_enabled(self) -> bool:
        return bool(self.proxies)

    def get_proxy(self) -> Optional[str]:
        """Returns the next rotating proxy in cycle."""
        if not self.proxies:
            return None
        return next(self._cycle)

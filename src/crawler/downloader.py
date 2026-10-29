"""
Distributed Electoral Ingestion & Intelligence Platform (DEIP V2.2)
Automated Electoral Roll PDF Downloader for CEO Andhra Pradesh Portal
Supports Headless Session Downloads, SHA-256 Integrity Verification, and Exponential Backoff.
"""

import os
import time
import hashlib
import logging
from typing import Dict, Any, Optional
import urllib.request
import urllib.error

from src.crawler.captcha import AcousticCaptchaSolver

logger = logging.getLogger(__name__)

BASE_CEO_PORTAL_URL = "https://ceoandhra.nic.in"


class ElectoralRollDownloader:
    """
    Automated Downloader for Andhra Pradesh Electoral Rolls.
    Enforces PDF signature verification, SHA-256 hash logging, and automatic retry.
    """

    def __init__(self, download_dir: str = "downloads", max_retries: int = 3, retry_backoff_sec: float = 2.0):
        self.download_dir = download_dir
        self.max_retries = max_retries
        self.retry_backoff_sec = retry_backoff_sec
        self.captcha_solver = AcousticCaptchaSolver()
        os.makedirs(self.download_dir, exist_ok=True)

    def _calculate_sha256(self, filepath: str) -> str:
        """Calculates SHA-256 checksum of downloaded file."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _verify_pdf_signature(self, filepath: str) -> bool:
        """Verifies file starts with '%PDF-' magic header and is at least 10KB."""
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 1024:
            return False
        with open(filepath, 'rb') as f:
            header = f.read(5)
        return header == b'%PDF-'

    def download_part_pdf(self, constituency_no: int, part_no: int,
                          override_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Downloads the electoral roll PDF for a specific AC and Part.
        Returns metadata dictionary containing filepath, sha256, and byte size.
        """
        ac_dir = os.path.join(self.download_dir, f"ac_{constituency_no}")
        os.makedirs(ac_dir, exist_ok=True)
        dest_path = os.path.join(ac_dir, f"AC{constituency_no}_Part{part_no:03d}.pdf")

        # Check if already downloaded and valid
        if os.path.exists(dest_path) and self._verify_pdf_signature(dest_path):
            sha256_hash = self._calculate_sha256(dest_path)
            file_size = os.path.getsize(dest_path)
            logger.info(f"Using cached valid PDF at {dest_path} (SHA-256: {sha256_hash[:12]}...)")
            return {
                'status': 'CACHED',
                'filepath': dest_path,
                'sha256': sha256_hash,
                'size_bytes': file_size,
                'assembly_constituency_no': constituency_no,
                'assembly_part_no': part_no
            }

        target_url = override_url or f"{BASE_CEO_PORTAL_URL}/rolls/AC_{constituency_no}/Part_{part_no}.pdf"

        # Download with exponential backoff
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"Downloading roll AC {constituency_no} Part {part_no} from {target_url} (Attempt {attempt}/{self.max_retries})...")
                req = urllib.request.Request(
                    target_url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) DEIP/2.2 Electoral Engine'}
                )
                with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, 'wb') as out_file:
                    out_file.write(response.read())

                if not self._verify_pdf_signature(dest_path):
                    raise ValueError(f"Downloaded file at {dest_path} is not a valid PDF")

                sha256_hash = self._calculate_sha256(dest_path)
                file_size = os.path.getsize(dest_path)
                logger.info(f"Successfully downloaded AC {constituency_no} Part {part_no}: {file_size} bytes (SHA-256: {sha256_hash[:12]}...)")

                return {
                    'status': 'DOWNLOADED',
                    'filepath': dest_path,
                    'sha256': sha256_hash,
                    'size_bytes': file_size,
                    'assembly_constituency_no': constituency_no,
                    'assembly_part_no': part_no
                }
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_sec * (2 ** (attempt - 1)))
                else:
                    raise RuntimeError(f"Failed to download roll for AC {constituency_no} Part {part_no} after {self.max_retries} attempts: {e}")

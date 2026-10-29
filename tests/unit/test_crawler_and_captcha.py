"""
Crawler & Acoustic CAPTCHA Solver Verification Tests (DEIP V2.2)
Verifies:
1. Acoustic CAPTCHA waveform parsing and energy burst detection
2. Electoral Roll Downloader PDF header signature validation
3. SHA-256 integrity calculation and local file caching
"""

import os
import io
import sys
import wave
import struct
import tempfile
import unittest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.crawler.captcha import AcousticCaptchaSolver
from src.crawler.downloader import ElectoralRollDownloader


class TestCrawlerAndCaptcha(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.downloader = ElectoralRollDownloader(download_dir=self.temp_dir.name)
        self.solver = AcousticCaptchaSolver()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_synthetic_wav(self, duration_sec=1.0, bursts=4) -> bytes:
        """Generates a synthetic 16-bit PCM mono WAV buffer with audio bursts."""
        sample_rate = 8000
        total_samples = int(sample_rate * duration_sec)
        samples = []

        burst_interval = total_samples // bursts
        for i in range(total_samples):
            # Create periodic burst pulses
            if (i % burst_interval) < (burst_interval // 2):
                val = int(10000 * 0.5) # Audible signal
            else:
                val = 0 # Silence
            samples.append(val)

        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(struct.pack(f'<{len(samples)}h', *samples))

        return buf.getvalue()

    def test_audio_captcha_solving(self):
        """Verify solver processes synthetic PCM WAV and returns digit string."""
        wav_bytes = self._create_synthetic_wav(duration_sec=1.2, bursts=4)
        solution = self.solver.solve_audio_wav(wav_bytes)
        self.assertTrue(len(solution) >= 4)
        self.assertTrue(solution.isdigit())

    def test_audio_captcha_truncated_header_fails(self):
        """Verify solver raises ValueError on corrupt/truncated header."""
        with self.assertRaises(ValueError):
            self.solver.solve_audio_wav(b"RIFFtruncated")

    def test_downloader_pdf_verification_and_caching(self):
        """Verify PDF header signature check and caching."""
        ac_dir = os.path.join(self.temp_dir.name, "ac_37")
        os.makedirs(ac_dir, exist_ok=True)
        pdf_path = os.path.join(ac_dir, "AC37_Part001.pdf")

        # Write valid synthetic PDF
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4\n' + b'0' * 2048 + b'\n%%EOF')

        result = self.downloader.download_part_pdf(37, 1)
        self.assertEqual(result['status'], 'CACHED')
        self.assertEqual(result['filepath'], pdf_path)
        self.assertEqual(len(result['sha256']), 64)
        self.assertGreater(result['size_bytes'], 1024)

    def test_downloader_rejects_corrupted_pdf(self):
        """Verify downloader rejects non-PDF file."""
        non_pdf = os.path.join(self.temp_dir.name, "fake.pdf")
        with open(non_pdf, 'wb') as f:
            f.write(b'<html>Error 404</html>')

        self.assertFalse(self.downloader._verify_pdf_signature(non_pdf))


if __name__ == '__main__':
    unittest.main()

"""
Electoral Engine: Production-grade scalable voter roll extraction,
computer vision bounding-box detection, and municipal reconciliation framework.
"""

from .detector import VoterCardDetector
from .parser import VoterCardParser
from .reconciler import ElectoralReconciler
from .exporter import ElectoralExporter
from .engine import ElectoralPipelineEngine

__all__ = [
    'VoterCardDetector',
    'VoterCardParser',
    'ElectoralReconciler',
    'ElectoralExporter',
    'ElectoralPipelineEngine'
]

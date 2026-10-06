"""
Universal AI Application Agent — Frame Resolver
Discovers, inspects, and locates application forms inside standard and nested iframes.
"""

from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FrameInfo:
    frame_index: int
    name: str
    frame_id: str
    src: str
    input_count: int
    has_form: bool
    is_accessible: bool
    selector: str


class FrameResolver:
    """Detects, inspects, and maps application components situated within iframes."""

    @classmethod
    async def discover_frames(cls, agent: Any) -> List[FrameInfo]:
        """Discovers all iframes in the document and counts accessible inputs inside them."""
        js_probe = """(() => {
            const iframes = Array.from(document.querySelectorAll('iframe'));
            return iframes.map((ifr, idx) => {
                let accessible = false;
                let inputs = 0;
                let hasForm = false;
                try {
                    const doc = ifr.contentDocument || ifr.contentWindow.document;
                    if (doc) {
                        accessible = true;
                        inputs = doc.querySelectorAll('input:not([type="hidden"]), select, textarea').length;
                        hasForm = doc.querySelectorAll('form').length > 0;
                    }
                } catch (e) {
                    accessible = false;
                }
                return {
                    frame_index: idx,
                    name: ifr.name || '',
                    frame_id: ifr.id || '',
                    src: ifr.src || '',
                    input_count: inputs,
                    has_form: hasForm,
                    is_accessible: accessible,
                    selector: ifr.id ? `#${ifr.id}` : `iframe:nth-of-type(${idx + 1})`,
                };
            });
        })()"""

        try:
            res = agent.evaluate(js_probe)
            if asyncio.iscoroutine(res):
                frames_data = await res
            else:
                frames_data = res
        except Exception as e:
            logger.warning("Frame discovery evaluation failed: %s", e)
            return []

        results = []
        for d in frames_data:
            results.append(
                FrameInfo(
                    frame_index=d.get("frame_index", 0),
                    name=d.get("name", ""),
                    frame_id=d.get("frame_id", ""),
                    src=d.get("src", ""),
                    input_count=d.get("input_count", 0),
                    has_form=d.get("has_form", False),
                    is_accessible=d.get("is_accessible", False),
                    selector=d.get("selector", "iframe"),
                )
            )
        return results

    @classmethod
    async def find_application_frame(cls, agent: Any) -> Optional[FrameInfo]:
        """Locates the frame most likely containing the job application form."""
        frames = await cls.discover_frames(agent)
        if not frames:
            return None

        # Prioritize frame with highest input count
        form_frames = [f for f in frames if f.input_count >= 2]
        if form_frames:
            form_frames.sort(key=lambda f: f.input_count, reverse=True)
            return form_frames[0]

        # Prioritize ATS-branded iframes
        ats_keywords = ["greenhouse", "lever", "workday", "jobvite", "catsone", "smartrecruiters", "apply"]
        for f in frames:
            if any(k in f.src.lower() for k in ats_keywords) or any(k in f.name.lower() for k in ats_keywords):
                return f

        return None

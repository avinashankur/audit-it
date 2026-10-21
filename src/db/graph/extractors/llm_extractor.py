"""LLM-assisted extractor for narrative MD&A sections and footnote disclosures."""

from __future__ import annotations

import json
import re
from typing import Any, Sequence
import uuid

from src.core.logging import get_logger, profile_stage
from src.db.graph.extractors.base import BaseExtractor
from src.db.models.entities import (
    CausalDirection,
    CausalRelationshipEdge,
    CausalRelationType,
    DisclosureNode,
    TextChunk,
)
from src.reasoning.llm_client import LLMClient
from src.reasoning.prompts import EXTRACTION_SYSTEM_PROMPT, build_extraction_prompt

logger = get_logger(__name__)


class LLMExtractor(BaseExtractor):
    """Extracts causal triples and qualitative disclosures from narrative text using LLM reasoning."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.client = llm_client or LLMClient.create_mock(response="[]")

    @profile_stage("llm_extractor_extract_chunk")
    def extract_from_chunk(
        self,
        chunk: TextChunk,
        source_filename: str | None = None,
    ) -> tuple[DisclosureNode | None, list[CausalRelationshipEdge]]:
        """Extract disclosure node and causal relationship edges from a single text chunk."""
        prompt = build_extraction_prompt(chunk.text, page_number=chunk.page_number)
        try:
            raw_response = self.client.generate(
                prompt=prompt,
                system_prompt=EXTRACTION_SYSTEM_PROMPT,
            )
            parsed_items = self._parse_json_response(raw_response)
        except Exception as exc:
            logger.warning(f"Narrative causal extraction failed on page {chunk.page_number}: {exc}")
            return None, []

        if not parsed_items:
            return None, []

        filename = source_filename or chunk.metadata.get("filename", "")

        # Create a disclosure node summarizing the narrative excerpt
        first_quote = parsed_items[0].get("evidence_quote", chunk.text[:150])
        first_topic = f"{parsed_items[0].get('source_entity', 'Disclosure')} Analysis"
        disclosure = DisclosureNode(
            node_id=str(uuid.uuid4()),
            topic=first_topic,
            summary=first_quote,
            source_doc_id=chunk.doc_id,
            source_page=chunk.page_number,
            snippet=chunk.text[:300],
        )

        edges: list[CausalRelationshipEdge] = []
        for item in parsed_items:
            src = str(item.get("source_entity", "")).strip()
            tgt = str(item.get("target_entity", "")).strip()
            if not src or not tgt:
                continue

            rel_str = str(item.get("relationship_type", "IMPACTS")).upper()
            try:
                rel_type = CausalRelationType(rel_str)
            except ValueError:
                rel_type = CausalRelationType.IMPACTS

            dir_str = str(item.get("direction", "direct")).lower()
            if "inverse" in dir_str or "negative" in dir_str or "down" in dir_str:
                direction = CausalDirection.INVERSE
            elif "correlat" in dir_str:
                direction = CausalDirection.CORRELATED
            elif "neutral" in dir_str:
                direction = CausalDirection.NEUTRAL
            else:
                direction = CausalDirection.DIRECT

            conf = float(item.get("confidence", 0.8))
            conf = max(0.0, min(1.0, conf))
            quote = str(item.get("evidence_quote", "")).strip() or chunk.text[:200]

            edge = CausalRelationshipEdge(
                edge_id=str(uuid.uuid4()),
                source_node_id=src,
                target_node_id=tgt,
                relation_type=rel_type,
                direction=direction,
                confidence=conf,
                evidence_text=quote,
                source_page=chunk.page_number,
                source_doc_id=chunk.doc_id,
                source_filename=filename,
            )
            edges.append(edge)

        return disclosure, edges

    @profile_stage("llm_extractor_extract")
    def extract(
        self,
        data: Sequence[TextChunk] | TextChunk,
        source_filename: str | None = None,
        **kwargs: Any,
    ) -> list[tuple[DisclosureNode, list[CausalRelationshipEdge]]]:
        """Extract disclosures and causal edges across chunks."""
        chunks: Sequence[TextChunk] = [data] if isinstance(data, TextChunk) else data
        results: list[tuple[DisclosureNode, list[CausalRelationshipEdge]]] = []

        for chunk in chunks:
            disc, edges = self.extract_from_chunk(chunk, source_filename=source_filename)
            if disc is not None and edges:
                results.append((disc, edges))

        return results

    @staticmethod
    def _parse_json_response(raw_text: str) -> list[dict[str, Any]]:
        """Extract and parse JSON array from raw LLM output text."""
        cleaned = raw_text.strip()
        if "```" in cleaned:
            match = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", cleaned, re.DOTALL)
            if match:
                cleaned = match.group(1).strip()
            else:
                cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
                cleaned = re.sub(r"```$", "", cleaned).strip()

        # Find first '[' and last ']'
        start_idx = cleaned.find("[")
        end_idx = cleaned.rfind("]")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_substr = cleaned[start_idx : end_idx + 1]
            try:
                data = json.loads(json_substr)
                if isinstance(data, list):
                    return [item for item in data if isinstance(item, dict)]
            except json.JSONDecodeError:
                pass

        # Fallback to single object if array parsing didn't match
        start_obj = cleaned.find("{")
        end_obj = cleaned.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            obj_substr = cleaned[start_obj : end_obj + 1]
            try:
                data = json.loads(obj_substr)
                if isinstance(data, dict):
                    return [data]
            except json.JSONDecodeError:
                pass

        return []

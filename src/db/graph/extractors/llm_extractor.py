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

    @staticmethod
    def _is_quote_grounded(quote: str, source_text: str) -> bool:
        """Verify that the evidence quote is actually present in the source chunk text."""
        if not quote or not source_text:
            return False
        # Normalize whitespace and lowercase for comparison
        norm_quote = re.sub(r"\s+", " ", quote.strip().lower())
        norm_source = re.sub(r"\s+", " ", source_text.strip().lower())
        return norm_quote in norm_source

    @staticmethod
    def _parse_confidence(val: Any) -> float:
        """Safely parse confidence value from model JSON output."""
        if val is None:
            return 0.8
        if isinstance(val, (int, float)):
            return max(0.0, min(1.0, float(val)))
        if isinstance(val, str):
            val_clean = val.strip().lower()
            if val_clean in ("high", "very high"):
                return 0.9
            if val_clean in ("medium", "med", "moderate"):
                return 0.7
            if val_clean in ("low", "very low"):
                return 0.4
            try:
                parsed_num = float(val_clean.rstrip("%"))
                if parsed_num > 1.0:
                    parsed_num /= 100.0
                return max(0.0, min(1.0, parsed_num))
            except ValueError:
                return 0.8
        return 0.8

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
        edges: list[CausalRelationshipEdge] = []

        for item in parsed_items:
            try:
                if not isinstance(item, dict):
                    continue

                src = str(item.get("source_entity") or "").strip()
                tgt = str(item.get("target_entity") or "").strip()
                if not src or not tgt:
                    continue

                # Grounding check: verify quote exists in chunk text
                raw_quote = item.get("evidence_quote")
                if not raw_quote or not isinstance(raw_quote, str) or not raw_quote.strip():
                    logger.debug("Skipping relationship with missing or empty evidence quote.")
                    continue

                quote = raw_quote.strip()
                if not self._is_quote_grounded(quote, chunk.text):
                    logger.debug(f"Rejecting ungrounded causal quote: '{quote}'")
                    continue

                rel_str = str(item.get("relationship_type") or "IMPACTS").upper()
                try:
                    rel_type = CausalRelationType(rel_str)
                except ValueError:
                    rel_type = CausalRelationType.IMPACTS

                dir_str = str(item.get("direction") or "direct").lower()
                if "inverse" in dir_str or "negative" in dir_str or "down" in dir_str:
                    direction = CausalDirection.INVERSE
                elif "correlat" in dir_str:
                    direction = CausalDirection.CORRELATED
                elif "neutral" in dir_str:
                    direction = CausalDirection.NEUTRAL
                else:
                    direction = CausalDirection.DIRECT

                conf = self._parse_confidence(item.get("confidence"))

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
            except Exception as item_exc:
                logger.debug(f"Failed to process extraction item: {item_exc}")
                continue

        if not edges:
            return None, []

        first_edge = edges[0]
        topic = f"{first_edge.source_node_id} Analysis"
        summary = first_edge.evidence_text[:150]
        disclosure = DisclosureNode(
            node_id=str(uuid.uuid4()),
            topic=topic,
            summary=summary,
            source_doc_id=chunk.doc_id,
            source_page=chunk.page_number,
            snippet=chunk.text[:300],
        )

        return disclosure, edges

    @profile_stage("llm_extractor_extract")
    def extract(
        self,
        data: Sequence[TextChunk] | TextChunk,
        source_filename: str | None = None,
        **kwargs: Any,
    ) -> list[tuple[DisclosureNode, list[CausalRelationshipEdge]]]:
        """Extract disclosures and causal edges across chunks, isolating failures per chunk."""
        chunks: Sequence[TextChunk] = [data] if isinstance(data, TextChunk) else data
        results: list[tuple[DisclosureNode, list[CausalRelationshipEdge]]] = []

        for chunk in chunks:
            try:
                disc, edges = self.extract_from_chunk(chunk, source_filename=source_filename)
                if disc is not None and edges:
                    results.append((disc, edges))
            except Exception as exc:
                chunk_id = getattr(chunk, "chunk_id", "unknown")
                logger.warning(f"Error extracting from chunk {chunk_id}: {exc}")

        return results

    def apply(self, store: Any, ingest_result: Any) -> None:
        """Execute narrative causal extraction and persist disclosures and edges into the graph store."""
        filename = ingest_result.metadata.filename
        results = self.extract(ingest_result.chunks, source_filename=filename)
        for disc, edges in results:
            if disc is not None:
                store.add_disclosure_node(disc)
            for edge in edges:
                store.add_causal_edge(edge)

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

"""
Hallucination detection for LLM responses.

Compares LLM-generated responses against known facts and source
data to detect fabricated or incorrect information.
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

from config import get_logger
from llm.providers.provider_factory import ProviderFactory

logger = get_logger(__name__)


@dataclass
class Fact:
    """A known fact used for hallucination checking."""

    fact_id: str
    statement: str
    source: str = ""
    category: str = ""
    keywords: List[str] = field(default_factory=list)


@dataclass
class HallucinationFinding:
    """A single hallucination finding in a response."""

    claim: str
    verdict: str  # "supported", "contradicted", "unverifiable"
    confidence: float = 0.0
    supporting_fact: Optional[str] = None
    explanation: str = ""


@dataclass
class HallucinationReport:
    """Complete hallucination analysis report."""

    response_text: str
    findings: List[HallucinationFinding] = field(default_factory=list)
    hallucination_score: float = 0.0  # 0 = no hallucination, 1 = fully hallucinated
    supported_claims: int = 0
    contradicted_claims: int = 0
    unverifiable_claims: int = 0
    total_claims: int = 0
    timestamp: str = ""

    @property
    def is_reliable(self) -> bool:
        """Check if the response is considered reliable."""
        return self.hallucination_score < 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hallucination_score": round(self.hallucination_score, 4),
            "is_reliable": self.is_reliable,
            "total_claims": self.total_claims,
            "supported_claims": self.supported_claims,
            "contradicted_claims": self.contradicted_claims,
            "unverifiable_claims": self.unverifiable_claims,
            "findings": [
                {
                    "claim": f.claim,
                    "verdict": f.verdict,
                    "confidence": round(f.confidence, 3),
                    "supporting_fact": f.supporting_fact,
                    "explanation": f.explanation,
                }
                for f in self.findings
            ],
            "timestamp": self.timestamp,
        }


class HallucinationDetector:
    """
    Detects hallucinations in LLM responses by comparing against known facts.

    Uses a combination of keyword matching, fact comparison, and LLM-assisted
    verification to identify fabricated or incorrect claims.
    """

    VERIFICATION_PROMPT = (
        "You are a fact-checking assistant. Compare the following claim against "
        "the provided known facts and determine if the claim is:\n"
        "- SUPPORTED: Consistent with known facts\n"
        "- CONTRADICTED: Conflicts with known facts\n"
        "- UNVERIFIABLE: Cannot be confirmed or denied from available facts\n\n"
        "Respond in this format:\n"
        "VERDICT: <supported|contradicted|unverifiable>\n"
        "CONFIDENCE: <0.0-1.0>\n"
        "EXPLANATION: <brief explanation>\n"
    )

    def __init__(self):
        self._provider = ProviderFactory.get_default_provider()
        self._facts: List[Fact] = []
        self._fact_index: Dict[str, List[Fact]] = {}

    def add_facts(self, facts: List[Fact]) -> None:
        """
        Add known facts for hallucination checking.

        Args:
            facts: List of known facts to use as ground truth.
        """
        self._facts.extend(facts)
        # Index facts by keywords for fast lookup
        for fact in facts:
            for keyword in fact.keywords:
                kw_lower = keyword.lower()
                if kw_lower not in self._fact_index:
                    self._fact_index[kw_lower] = []
                self._fact_index[kw_lower].append(fact)

        logger.info(f"Added {len(facts)} facts (total: {len(self._facts)})")

    def add_fact(
        self,
        statement: str,
        source: str = "",
        category: str = "",
        keywords: Optional[List[str]] = None,
    ) -> None:
        """Add a single known fact."""
        fact = Fact(
            fact_id=f"fact_{len(self._facts) + 1}",
            statement=statement,
            source=source,
            category=category,
            keywords=keywords or self._extract_keywords(statement),
        )
        self.add_facts([fact])

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for indexing."""
        # Simple keyword extraction: words longer than 3 chars, lowercased
        words = text.lower().split()
        stopwords = {"the", "is", "are", "was", "were", "and", "or", "for", "in", "on", "at", "to", "of", "a", "an"}
        return [w.strip(".,;:!?()[]") for w in words if len(w) > 3 and w not in stopwords]

    def _find_relevant_facts(self, claim: str, max_facts: int = 5) -> List[Fact]:
        """Find facts relevant to a claim using keyword matching."""
        claim_keywords = self._extract_keywords(claim)
        fact_scores: Dict[str, float] = {}

        for keyword in claim_keywords:
            matching_facts = self._fact_index.get(keyword, [])
            for fact in matching_facts:
                if fact.fact_id not in fact_scores:
                    fact_scores[fact.fact_id] = 0.0
                fact_scores[fact.fact_id] += 1.0

        # Sort by relevance score
        sorted_facts = sorted(fact_scores.items(), key=lambda x: x[1], reverse=True)
        top_fact_ids = [fid for fid, _ in sorted_facts[:max_facts]]

        return [f for f in self._facts if f.fact_id in top_fact_ids]

    def _extract_claims(self, response_text: str) -> List[str]:
        """Extract individual claims from a response."""
        # Split by sentences
        sentences = response_text.replace("\n", " ").split(".")
        claims = []

        for sentence in sentences:
            sentence = sentence.strip()
            # Filter out very short or question sentences
            if len(sentence) > 15 and "?" not in sentence:
                claims.append(sentence)

        return claims

    async def check_response(
        self,
        response_text: str,
        context: Optional[str] = None,
        use_llm_verification: bool = True,
    ) -> HallucinationReport:
        """
        Check an LLM response for hallucinations.

        Args:
            response_text: The LLM-generated response to check.
            context: Optional context that was provided to the LLM.
            use_llm_verification: Whether to use LLM for claim verification.

        Returns:
            HallucinationReport with findings and hallucination score.
        """
        logger.info(f"Checking response for hallucinations ({len(response_text)} chars)")

        claims = self._extract_claims(response_text)
        findings: List[HallucinationFinding] = []

        for claim in claims:
            relevant_facts = self._find_relevant_facts(claim)

            if not relevant_facts:
                # No relevant facts found - mark as unverifiable
                findings.append(HallucinationFinding(
                    claim=claim,
                    verdict="unverifiable",
                    confidence=0.5,
                    explanation="No relevant facts available for verification.",
                ))
                continue

            if use_llm_verification:
                finding = await self._verify_claim_with_llm(claim, relevant_facts)
            else:
                finding = self._verify_claim_keyword_match(claim, relevant_facts)

            findings.append(finding)

        # Calculate hallucination score
        supported = sum(1 for f in findings if f.verdict == "supported")
        contradicted = sum(1 for f in findings if f.verdict == "contradicted")
        unverifiable = sum(1 for f in findings if f.verdict == "unverifiable")
        total = len(findings)

        # Score: contradicted claims are worst, unverifiable are moderate
        hallucination_score = 0.0
        if total > 0:
            hallucination_score = (contradicted * 1.0 + unverifiable * 0.3) / total

        report = HallucinationReport(
            response_text=response_text,
            findings=findings,
            hallucination_score=hallucination_score,
            supported_claims=supported,
            contradicted_claims=contradicted,
            unverifiable_claims=unverifiable,
            total_claims=total,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )

        logger.info(
            f"Hallucination check complete: score={hallucination_score:.3f}, "
            f"{supported} supported, {contradicted} contradicted, {unverifiable} unverifiable"
        )
        return report

    async def _verify_claim_with_llm(
        self, claim: str, relevant_facts: List[Fact]
    ) -> HallucinationFinding:
        """Verify a claim against facts using LLM."""
        facts_text = "\n".join(f"- {f.statement}" for f in relevant_facts)

        prompt = (
            f"Claim to verify: \"{claim}\"\n\n"
            f"Known facts:\n{facts_text}\n\n"
            "Is this claim supported, contradicted, or unverifiable based on the facts above?"
        )

        try:
            response = await self._provider.generate(
                prompt=prompt,
                system_prompt=self.VERIFICATION_PROMPT,
            )
            return self._parse_verification(claim, response, relevant_facts)

        except Exception as e:
            logger.error(f"LLM verification failed: {e}")
            return self._verify_claim_keyword_match(claim, relevant_facts)

    def _parse_verification(
        self, claim: str, response: str, facts: List[Fact]
    ) -> HallucinationFinding:
        """Parse LLM verification response."""
        verdict = "unverifiable"
        confidence = 0.5
        explanation = ""

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("VERDICT:"):
                v = line.replace("VERDICT:", "").strip().lower()
                if v in ("supported", "contradicted", "unverifiable"):
                    verdict = v
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                    confidence = max(0.0, min(1.0, confidence))
                except ValueError:
                    pass
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()

        supporting_fact = facts[0].statement if facts else None

        return HallucinationFinding(
            claim=claim,
            verdict=verdict,
            confidence=confidence,
            supporting_fact=supporting_fact,
            explanation=explanation,
        )

    def _verify_claim_keyword_match(
        self, claim: str, relevant_facts: List[Fact]
    ) -> HallucinationFinding:
        """Simple keyword-based verification without LLM."""
        claim_lower = claim.lower()
        best_match_score = 0.0
        best_fact: Optional[Fact] = None

        for fact in relevant_facts:
            fact_keywords = set(self._extract_keywords(fact.statement))
            claim_keywords = set(self._extract_keywords(claim))

            if not claim_keywords:
                continue

            overlap = len(fact_keywords & claim_keywords)
            score = overlap / len(claim_keywords)

            if score > best_match_score:
                best_match_score = score
                best_fact = fact

        # Determine verdict based on keyword overlap
        if best_match_score > 0.5:
            verdict = "supported"
        elif best_match_score > 0.2:
            verdict = "unverifiable"
        else:
            verdict = "unverifiable"

        return HallucinationFinding(
            claim=claim,
            verdict=verdict,
            confidence=best_match_score,
            supporting_fact=best_fact.statement if best_fact else None,
            explanation="Verified via keyword matching.",
        )

    def clear_facts(self) -> None:
        """Clear all registered facts."""
        self._facts.clear()
        self._fact_index.clear()
        logger.info("All facts cleared")

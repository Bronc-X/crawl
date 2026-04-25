from __future__ import annotations

from dataclasses import dataclass

from .models import Decision, DecisionKind, FAQRule, IncomingMessage


def _normalize(text: str) -> str:
    return text.casefold().strip()


@dataclass
class DecisionEngine:
    faq_rules: tuple[FAQRule, ...]
    redline_keywords: tuple[str, ...]
    manual_only_contacts: frozenset[str]

    def classify(self, message: IncomingMessage) -> Decision:
        contact_key = message.contact_name.casefold()
        if contact_key in {item.casefold() for item in self.manual_only_contacts}:
            return Decision(
                kind=DecisionKind.HANDOFF,
                reason="contact is marked manual-only",
            )

        normalized = _normalize(message.text)
        matched_redlines = tuple(
            keyword for keyword in self.redline_keywords if _normalize(keyword) in normalized
        )
        if matched_redlines:
            return Decision(
                kind=DecisionKind.HANDOFF,
                reason="message matched handoff redline keywords",
                matched_keywords=matched_redlines,
            )

        for rule in self.faq_rules:
            matched_keywords = tuple(
                keyword for keyword in rule.keywords if _normalize(keyword) in normalized
            )
            if not matched_keywords:
                continue

            if rule.material_id:
                return Decision(
                    kind=DecisionKind.SAFE_MATERIAL,
                    reason=f"matched FAQ rule: {rule.name}",
                    rule_id=rule.rule_id,
                    reply_text=rule.reply_text,
                    material_id=rule.material_id,
                    matched_keywords=matched_keywords,
                )

            return Decision(
                kind=DecisionKind.SAFE_REPLY,
                reason=f"matched FAQ rule: {rule.name}",
                rule_id=rule.rule_id,
                reply_text=rule.reply_text,
                matched_keywords=matched_keywords,
            )

        return Decision(
            kind=DecisionKind.HANDOFF,
            reason="message did not match an approved low-risk rule",
        )

"""Synthetic transcript display for legacy leads."""

from app.dashboard.transcript_display import synthetic_lead_history


class _Lead:
  def __init__(self, **kwargs):
    for k, v in kwargs.items():
      setattr(self, k, v)


def test_synthetic_lead_history_from_fields():
    lead = _Lead(
        business_name="Water Inn",
        business_type="Restaurant",
        locations="2",
        current_system="Manual",
        demo_slot="Kal 11am",
        ad_source="Bahi POS",
        entry_intent="",
    )
    msgs = synthetic_lead_history(lead, {})
    assert len(msgs) >= 4
    assert any("Water Inn" in m["content"] for m in msgs if m["role"] == "user")
    assert any(m["role"] == "assistant" for m in msgs)

from pathlib import Path

POLICY = Path("tailscale/policies/reviewed-policy.hujson")

def test_review_policy_is_placeholdered_and_deny_by_default():
    text = POLICY.read_text(encoding="utf-8")
    assert "REPLACE_T16" in text and "REPLACE_IPHONE" in text and "REPLACE_T480" in text
    assert '"ssh": []' in text
    assert '"exitNode": []' in text
    assert '"routes": {}' in text
    assert "autogroup:member" not in text
    assert "0.0.0.0/0" not in text

def test_review_policy_has_only_dashboard_as_the_iphone_example_port():
    text = POLICY.read_text(encoding="utf-8")
    iphone_line = next(line for line in text.splitlines() if "REPLACE_IPHONE" in line)
    assert ":8080" in iphone_line
    assert "REPLACE_T16_PORT" not in iphone_line

from src.utils.alerts import alert_rule_roas_drop


def test_alert_rule_roas_drop_triggers():
    metrics = {"validation_rate": 0.0, "num_creatives": 0, "roas_drop": 0.5}
    thresholds = {"roas_drop_threshold": 0.2}
    r = alert_rule_roas_drop(metrics, thresholds)
    assert r["alerted"] is True
    assert "no_creatives" in r["reason"] or "roas_drop_exceeded" in r["reason"]


def test_alert_rule_roas_drop_no_trigger():
    metrics = {"validation_rate": 0.5, "num_creatives": 2, "roas_drop": 0.05}
    thresholds = {"roas_drop_threshold": 0.2}
    r = alert_rule_roas_drop(metrics, thresholds)
    assert r["alerted"] is False

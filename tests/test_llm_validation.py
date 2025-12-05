"""
Tests for LLM output validation and retry utilities.
"""
import pytest
import time

from src.utils.llm_validation import (
    validate_hypothesis_output,
    validate_creative_output,
    repair_malformed_json,
    retry_with_backoff,
    sanitize_hypothesis_output,
    sanitize_creative_output,
    LLMOutputValidationError
)


class TestHypothesisValidation:
    """Test hypothesis output validation."""

    def test_valid_hypothesis_list(self):
        """Test validation of valid hypothesis list."""
        hypotheses = [
            {
                "id": "h1",
                "hypothesis": "CTR is declining",
                "initial_confidence": 0.8,
                "metrics_used": ["ctr"]
            },
            {
                "id": "h2",
                "hypothesis": "ROAS is below baseline",
                "initial_confidence": 0.7,
                "metrics_used": ["roas"]
            }
        ]

        is_valid, errors = validate_hypothesis_output(hypotheses)
        assert is_valid
        assert len(errors) == 0

    def test_missing_required_field(self):
        """Test validation detects missing required fields."""
        hypotheses = [
            {
                "id": "h1",
                "hypothesis": "Test",
                # Missing initial_confidence
                "metrics_used": ["ctr"]
            }
        ]

        is_valid, errors = validate_hypothesis_output(hypotheses)
        assert not is_valid
        assert any("initial_confidence" in str(e) for e in errors)

    def test_confidence_out_of_range(self):
        """Test validation detects confidence out of range."""
        hypotheses = [
            {
                "id": "h1",
                "hypothesis": "Test",
                "initial_confidence": 1.5,  # > 1.0
                "metrics_used": ["ctr"]
            },
            {
                "id": "h2",
                "hypothesis": "Test 2",
                "initial_confidence": -0.2,  # < 0.0
                "metrics_used": ["roas"]
            }
        ]

        is_valid, errors = validate_hypothesis_output(hypotheses)
        assert not is_valid
        assert len(errors) >= 2

    def test_empty_hypothesis_list(self):
        """Test validation of empty list."""
        is_valid, errors = validate_hypothesis_output([])
        assert is_valid  # Empty is technically valid
        assert "Empty" in str(errors)

    def test_not_a_list(self):
        """Test validation rejects non-list input."""
        is_valid, errors = validate_hypothesis_output({"not": "a list"})
        assert not is_valid
        assert any("list" in str(e).lower() for e in errors)


class TestCreativeValidation:
    """Test creative output validation."""

    def test_valid_creative_list(self):
        """Test validation of valid creative list."""
        creatives = [
            {
                "id": "c1",
                "creative_concept": "Test creative",
                "campaign": "Campaign A",
                "issue_diagnosed": "Low CTR"
            }
        ]

        is_valid, errors = validate_creative_output(creatives)
        assert is_valid
        assert len(errors) == 0

    def test_missing_required_field(self):
        """Test validation detects missing required fields."""
        creatives = [
            {
                "id": "c1",
                "creative_concept": "Test",
                # Missing campaign and issue_diagnosed
            }
        ]

        is_valid, errors = validate_creative_output(creatives)
        assert not is_valid
        assert len(errors) >= 2


class TestJSONRepair:
    """Test JSON repair functionality."""

    def test_repair_trailing_comma(self):
        """Test repair of trailing commas."""
        malformed = '{"key": "value",}'
        repaired = repair_malformed_json(malformed)
        assert repaired is not None
        assert repaired == {"key": "value"}

    def test_repair_missing_closing_bracket(self):
        """Test repair of missing closing brackets."""
        malformed = '{"key": "value"'
        repaired = repair_malformed_json(malformed)
        assert repaired is not None
        assert "key" in repaired

    def test_valid_json_unchanged(self):
        """Test that valid JSON is not modified."""
        valid = '{"key": "value", "num": 123}'
        repaired = repair_malformed_json(valid)
        assert repaired is not None
        assert repaired == {"key": "value", "num": 123}

    def test_completely_malformed_returns_none(self):
        """Test that completely malformed JSON returns None."""
        malformed = 'this is not json at all'
        repaired = repair_malformed_json(malformed)
        assert repaired is None


class TestRetryWithBackoff:
    """Test retry mechanism with backoff."""

    def test_successful_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = [0]

        def mock_func():
            call_count[0] += 1
            return {"result": "success"}

        result = retry_with_backoff(
            mock_func,
            max_retries=3,
            initial_delay=0.1,
            agent_name="test"
        )

        assert result == {"result": "success"}
        assert call_count[0] == 1

    def test_retry_on_validation_failure(self):
        """Test retry when validation fails."""
        call_count = [0]

        def mock_func():
            call_count[0] += 1
            if call_count[0] < 2:
                return []  # Empty list (will fail validation)
            return [{"id": "h1", "hypothesis": "Test", "initial_confidence": 0.8, "metrics_used": []}]

        def validation(result):
            if not result or len(result) == 0:
                return False, ["Empty result"]
            return True, []

        result = retry_with_backoff(
            mock_func,
            max_retries=3,
            initial_delay=0.1,
            validation_func=validation,
            agent_name="test"
        )

        assert len(result) == 1
        assert call_count[0] == 2

    def test_max_retries_exceeded(self):
        """Test error when max retries exceeded."""
        call_count = [0]

        def mock_func():
            call_count[0] += 1
            return []  # Always fails validation

        def validation(result):
            return False, ["Always fails"]

        with pytest.raises(LLMOutputValidationError):
            retry_with_backoff(
                mock_func,
                max_retries=2,
                initial_delay=0.05,
                validation_func=validation,
                agent_name="test"
            )

        assert call_count[0] == 2

    def test_exponential_backoff(self):
        """Test that backoff increases exponentially."""
        call_count = [0]
        times = []

        def mock_func():
            call_count[0] += 1
            times.append(time.time())
            raise ValueError("Always fails")

        try:
            retry_with_backoff(
                mock_func,
                max_retries=3,
                initial_delay=0.1,
                backoff_factor=2.0,
                agent_name="test"
            )
        except ValueError:
            pass

        # Should have 3 attempts
        assert call_count[0] == 3

        # Check that delays increase
        if len(times) >= 3:
            delay1 = times[1] - times[0]
            delay2 = times[2] - times[1]
            # Second delay should be roughly double first delay
            assert delay2 > delay1 * 1.5


class TestSanitization:
    """Test sanitization functions."""

    def test_sanitize_hypothesis_confidence(self):
        """Test sanitization clamps confidence to valid range."""
        hypotheses = [
            {
                "id": "h1",
                "hypothesis": "Test",
                "initial_confidence": 5.0,  # > 1.0
                "metrics_used": []
            },
            {
                "id": "h2",
                "hypothesis": "Test 2",
                "initial_confidence": -0.5,  # < 0.0
                "metrics_used": []
            }
        ]

        sanitized = sanitize_hypothesis_output(hypotheses, fix_confidence=True)

        assert 0.0 <= sanitized[0]["initial_confidence"] <= 1.0
        assert 0.0 <= sanitized[1]["initial_confidence"] <= 1.0

    def test_sanitize_hypothesis_missing_fields(self):
        """Test sanitization adds missing required fields."""
        hypotheses = [
            {"hypothesis": "Test"}  # Missing id, initial_confidence, metrics_used
        ]

        sanitized = sanitize_hypothesis_output(hypotheses, fix_missing_fields=True)

        assert "id" in sanitized[0]
        assert "initial_confidence" in sanitized[0]
        assert "metrics_used" in sanitized[0]
        assert "hypothesis" in sanitized[0]

    def test_sanitize_creative_missing_fields(self):
        """Test creative sanitization adds missing fields."""
        creatives = [
            {"creative_concept": "Test"}  # Missing other fields
        ]

        sanitized = sanitize_creative_output(creatives, fix_missing_fields=True)

        assert "id" in sanitized[0]
        assert "creative_concept" in sanitized[0]
        assert "campaign" in sanitized[0]
        assert "issue_diagnosed" in sanitized[0]

    def test_sanitize_skips_non_dict(self):
        """Test sanitization skips non-dict entries."""
        hypotheses = [
            {"id": "h1", "hypothesis": "Test", "initial_confidence": 0.8, "metrics_used": []},
            "not a dict",
            None,
            {"id": "h2", "hypothesis": "Test 2", "initial_confidence": 0.7, "metrics_used": []}
        ]

        sanitized = sanitize_hypothesis_output(hypotheses)

        # Should only include valid dicts
        assert len(sanitized) == 2
        assert all(isinstance(h, dict) for h in sanitized)

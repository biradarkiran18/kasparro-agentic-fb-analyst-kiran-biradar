"""
LLM output validation and retry utilities.

Provides:
- validate_hypothesis_output(): Validate structure of generated hypotheses
- validate_creative_output(): Validate structure of generated creatives
- retry_with_backoff(): Retry mechanism for LLM calls with exponential backoff
- repair_malformed_json(): Attempt to fix common JSON formatting issues
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import re

from src.utils.observability import log_event


class LLMOutputValidationError(Exception):
    """Raised when LLM output fails validation."""
    pass


def validate_hypothesis_output(
    hypotheses: Any,
    *,
    min_confidence: float = 0.0,
    max_confidence: float = 1.0,
    required_fields: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """
    Validate structure of hypothesis output from insight agent.

    Args:
        hypotheses: Output to validate (should be list of dicts)
        min_confidence: Minimum valid confidence value
        max_confidence: Maximum valid confidence value
        required_fields: List of required field names

    Returns:
        (is_valid, errors) tuple
    """
    if required_fields is None:
        required_fields = ["id", "hypothesis", "initial_confidence", "metrics_used"]

    errors = []

    # Check if it's a list
    if not isinstance(hypotheses, list):
        errors.append(f"Expected list, got {type(hypotheses).__name__}")
        return False, errors

    # Empty list is technically valid but should be noted
    if len(hypotheses) == 0:
        errors.append("Empty hypotheses list")
        return True, errors  # Valid but notable

    # Validate each hypothesis
    for idx, h in enumerate(hypotheses):
        if not isinstance(h, dict):
            errors.append(f"Hypothesis {idx}: Expected dict, got {type(h).__name__}")
            continue

        # Check required fields
        for field in required_fields:
            if field not in h:
                errors.append(f"Hypothesis {idx}: Missing required field '{field}'")

        # Validate confidence range
        if "initial_confidence" in h:
            conf = h["initial_confidence"]
            if not isinstance(conf, (int, float)):
                errors.append(f"Hypothesis {idx}: confidence must be numeric, got {type(conf).__name__}")
            elif conf < min_confidence or conf > max_confidence:
                errors.append(f"Hypothesis {idx}: confidence {conf} out of range [{min_confidence}, {max_confidence}]")

        # Validate metrics_used is a list
        if "metrics_used" in h:
            if not isinstance(h["metrics_used"], list):
                errors.append(f"Hypothesis {idx}: metrics_used must be list, got {type(h['metrics_used']).__name__}")

        # Check hypothesis text is non-empty string
        if "hypothesis" in h:
            if not isinstance(h["hypothesis"], str):
                errors.append(f"Hypothesis {idx}: hypothesis must be string, got {type(h['hypothesis']).__name__}")
            elif len(h["hypothesis"].strip()) == 0:
                errors.append(f"Hypothesis {idx}: hypothesis text is empty")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_creative_output(
    creatives: Any,
    required_fields: Optional[List[str]] = None
) -> Tuple[bool, List[str]]:
    """
    Validate structure of creative output from creative generator.

    Args:
        creatives: Output to validate (should be list of dicts)
        required_fields: List of required field names

    Returns:
        (is_valid, errors) tuple
    """
    if required_fields is None:
        required_fields = ["id", "creative_concept", "campaign", "issue_diagnosed"]

    errors = []

    if not isinstance(creatives, list):
        errors.append(f"Expected list, got {type(creatives).__name__}")
        return False, errors

    if len(creatives) == 0:
        errors.append("Empty creatives list")
        return True, errors  # Valid but notable

    for idx, c in enumerate(creatives):
        if not isinstance(c, dict):
            errors.append(f"Creative {idx}: Expected dict, got {type(c).__name__}")
            continue

        # Check required fields
        for field in required_fields:
            if field not in c:
                errors.append(f"Creative {idx}: Missing required field '{field}'")

        # Validate evidence structure if present
        if "evidence" in c:
            if not isinstance(c["evidence"], dict):
                errors.append(f"Creative {idx}: evidence must be dict, got {type(c['evidence']).__name__}")

    is_valid = len(errors) == 0
    return is_valid, errors


def repair_malformed_json(text: str) -> Optional[Any]:
    """
    Attempt to repair common JSON formatting issues.

    Handles:
    - Trailing commas
    - Single quotes instead of double quotes
    - Unescaped newlines in strings
    - Missing closing brackets

    Args:
        text: Potentially malformed JSON string

    Returns:
        Parsed JSON object or None if unrepairable
    """
    if not text or not isinstance(text, str):
        return None

    original = text.strip()

    # Try standard parse first
    try:
        return json.loads(original)
    except json.JSONDecodeError:
        pass

    # Attempt repairs
    repaired = original

    # 1. Remove trailing commas before closing brackets
    repaired = re.sub(r',(\s*[}\]])', r'\1', repaired)

    # 2. Replace single quotes with double quotes (careful with apostrophes)
    # Only replace single quotes that appear to be JSON delimiters
    repaired = re.sub(r"'(\w+)':", r'"\1":', repaired)  # Keys

    # 3. Remove unescaped newlines within strings
    repaired = repaired.replace('\n', '\\n')

    # 4. Try to add missing closing brackets (simple heuristic)
    open_braces = repaired.count('{')
    close_braces = repaired.count('}')
    open_brackets = repaired.count('[')
    close_brackets = repaired.count(']')

    if open_braces > close_braces:
        repaired += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        repaired += ']' * (open_brackets - close_brackets)

    # Try parsing repaired version
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    validation_func: Optional[Callable[[Any], Tuple[bool, List[str]]]] = None,
    agent_name: str = "unknown",
    base_dir: str = "logs/observability",
    **kwargs
) -> Any:
    """
    Execute function with retry logic and exponential backoff.

    Args:
        func: Function to call
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds between retries
        backoff_factor: Multiplier for delay after each retry
        validation_func: Optional validation function that returns (is_valid, errors)
        agent_name: Name of agent for logging
        base_dir: Base directory for logs
        **kwargs: Keyword arguments for func

    Returns:
        Function result if successful

    Raises:
        LLMOutputValidationError: If all retries fail validation
    """
    delay = initial_delay
    last_error = None

    for attempt in range(max_retries):
        try:
            # Call the function
            result = func(*args, **kwargs)

            # If validation function provided, validate result
            if validation_func:
                is_valid, errors = validation_func(result)

                if is_valid:
                    if attempt > 0:
                        log_event(
                            agent_name,
                            "retry_success",
                            {"attempt": attempt + 1, "max_retries": max_retries},
                            base_dir=base_dir
                        )
                    return result
                else:
                    # Validation failed
                    log_event(
                        agent_name,
                        "validation_failed",
                        {
                            "attempt": attempt + 1,
                            "errors": errors,
                            "result_type": type(result).__name__
                        },
                        base_dir=base_dir
                    )

                    if attempt < max_retries - 1:
                        # Try to repair if it's a string
                        if isinstance(result, str):
                            repaired = repair_malformed_json(result)
                            if repaired is not None:
                                is_valid, errors = validation_func(repaired)
                                if is_valid:
                                    log_event(
                                        agent_name,
                                        "json_repair_success",
                                        {"attempt": attempt + 1},
                                        base_dir=base_dir
                                    )
                                    return repaired

                        # Wait before retry
                        time.sleep(delay)
                        delay *= backoff_factor
                        continue
                    else:
                        # Last attempt failed
                        raise LLMOutputValidationError(
                            f"Validation failed after {max_retries} attempts: {errors}"
                        )
            else:
                # No validation, just return result
                return result

        except Exception as e:
            last_error = e
            log_event(
                agent_name,
                "execution_error",
                {
                    "attempt": attempt + 1,
                    "error": str(e),
                    "error_type": type(e).__name__
                },
                base_dir=base_dir
            )

            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= backoff_factor
            else:
                raise

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    else:
        raise LLMOutputValidationError("All retry attempts failed")


def sanitize_hypothesis_output(
    hypotheses: List[Dict[str, Any]],
    *,
    fix_confidence: bool = True,
    fix_missing_fields: bool = True,
    default_confidence: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Sanitize hypothesis output by fixing common issues.

    Args:
        hypotheses: List of hypothesis dicts to sanitize
        fix_confidence: Clamp confidence values to [0, 1] range
        fix_missing_fields: Add default values for missing required fields
        default_confidence: Default confidence value for missing field

    Returns:
        Sanitized list of hypotheses
    """
    sanitized = []

    for idx, h in enumerate(hypotheses):
        if not isinstance(h, dict):
            continue  # Skip non-dict entries

        clean_h = dict(h)

        # Fix confidence
        if fix_confidence and "initial_confidence" in clean_h:
            conf = clean_h["initial_confidence"]
            if isinstance(conf, (int, float)):
                clean_h["initial_confidence"] = max(0.0, min(1.0, float(conf)))
            else:
                clean_h["initial_confidence"] = default_confidence

        # Add missing fields
        if fix_missing_fields:
            if "id" not in clean_h:
                clean_h["id"] = f"h{idx}"
            if "initial_confidence" not in clean_h:
                clean_h["initial_confidence"] = default_confidence
            if "metrics_used" not in clean_h:
                clean_h["metrics_used"] = []
            if "hypothesis" not in clean_h or not clean_h["hypothesis"]:
                clean_h["hypothesis"] = f"Hypothesis {idx}"

        sanitized.append(clean_h)

    return sanitized


def sanitize_creative_output(
    creatives: List[Dict[str, Any]],
    *,
    fix_missing_fields: bool = True
) -> List[Dict[str, Any]]:
    """
    Sanitize creative output by fixing common issues.

    Args:
        creatives: List of creative dicts to sanitize
        fix_missing_fields: Add default values for missing required fields

    Returns:
        Sanitized list of creatives
    """
    sanitized = []

    for idx, c in enumerate(creatives):
        if not isinstance(c, dict):
            continue

        clean_c = dict(c)

        if fix_missing_fields:
            if "id" not in clean_c:
                clean_c["id"] = f"c{idx}"
            if "creative_concept" not in clean_c:
                clean_c["creative_concept"] = f"Creative {idx}"
            if "campaign" not in clean_c:
                clean_c["campaign"] = "unknown"
            if "issue_diagnosed" not in clean_c:
                clean_c["issue_diagnosed"] = "unspecified"

        sanitized.append(clean_c)

    return sanitized

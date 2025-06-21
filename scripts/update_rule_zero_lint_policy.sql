-- Add or update the canonical lint policy in the Rule Zero rigor DB
INSERT OR REPLACE INTO rule_zero_policies (
    policy_name,
    policy_type,
    description,
    policy_json,
    enforcement_rank,
    last_updated
) VALUES (
    'Rule Zero Canonical Lint Policy',
    'lint',
    'Only E501 (line too long) warnings are permitted to remain if they are the sole remaining flake8 errors after autopep8 (max-line-length=88) and do not affect runtime or maintainability. All other flake8 and all dmypy errors must be resolved.',
    '{"flake8": {"allow_only": ["E501"], "max_line_length": 88, "autopep8_required": true}, "dmypy": {"allow_only": [], "all_errors_must_be_resolved": true}}',
    100,
    '2025-06-21T00:00:00Z'
);

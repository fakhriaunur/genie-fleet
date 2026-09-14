"""Unit tests for the default AWS region (user-required ap-southeast-3)."""

from __future__ import annotations

from genie_fleet.settings import Settings, load_settings


def test_default_aws_region_is_ap_southeast_3() -> None:
    assert Settings().aws_region == "ap-southeast-3"


def test_load_settings_without_aws_region_env_reports_default() -> None:
    assert load_settings({}).aws_region == "ap-southeast-3"


def test_explicit_aws_region_env_overrides_default() -> None:
    settings = load_settings({"AWS_REGION": "eu-west-1"})
    assert settings.aws_region == "eu-west-1"

"""
Unit tests for JobParser service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.job_parser import (
    JobParser,
    JOB_PLATFORMS,
    get_job_platform,
    extract_company_from_platform_url,
)


class TestJobParserDomainExtraction:
    """Tests for domain extraction functionality."""

    @pytest.fixture
    def parser(self):
        """Create a JobParser instance."""
        return JobParser()

    def test_extract_domain_simple(self, parser):
        """Test extracting domain from simple URL."""
        assert parser.extract_domain("https://linkedin.com/jobs/123") == "linkedin.com"
        assert parser.extract_domain("https://indeed.com/job/456") == "indeed.com"
        assert parser.extract_domain("https://glassdoor.com/job/789") == "glassdoor.com"

    def test_extract_domain_with_www(self, parser):
        """Test extracting domain removes www prefix."""
        assert parser.extract_domain("https://www.linkedin.com/jobs/123") == "linkedin.com"
        assert parser.extract_domain("http://www.indeed.com/job/456") == "indeed.com"

    def test_extract_domain_with_subdomain(self, parser):
        """Test extracting domain preserves other subdomains."""
        assert parser.extract_domain("https://jobs.linkedin.com/view/123") == "jobs.linkedin.com"
        assert parser.extract_domain("https://m.indeed.com/job/456") == "m.indeed.com"

    def test_extract_domain_with_port(self, parser):
        """Test extracting domain with port number."""
        result = parser.extract_domain("http://localhost:8000/jobs/123")
        assert "localhost" in result

    def test_extract_domain_with_path(self, parser):
        """Test that path is not included in domain."""
        result = parser.extract_domain("https://example.com/long/path/to/job")
        assert result == "example.com"
        assert "path" not in result

    def test_extract_domain_with_query_params(self, parser):
        """Test that query params don't affect domain."""
        result = parser.extract_domain("https://example.com/job?id=123&source=google")
        assert result == "example.com"
        assert "?" not in result

    def test_extract_domain_case_insensitive(self, parser):
        """Test that domain extraction is case-insensitive."""
        assert parser.extract_domain("https://LINKEDIN.COM/jobs") == "linkedin.com"
        assert parser.extract_domain("https://Indeed.Com/job") == "indeed.com"

    def test_extract_domain_invalid_url(self, parser):
        """Test extracting domain from invalid URL."""
        assert parser.extract_domain("not a url") == ""
        assert parser.extract_domain("") == ""

    def test_extract_domain_special_tlds(self, parser):
        """Test extracting domains with special TLDs."""
        assert parser.extract_domain("https://drushim.co.il/job/123") == "drushim.co.il"
        assert parser.extract_domain("https://jobs.gov.uk/view/456") == "jobs.gov.uk"


class TestJobParserEdgeCases:
    """Edge case tests for JobParser."""

    @pytest.fixture
    def parser(self):
        return JobParser()

    def test_extract_domain_with_fragment(self, parser):
        """Test URL with fragment identifier."""
        result = parser.extract_domain("https://example.com/job#apply-section")
        assert result == "example.com"

    def test_extract_domain_international(self, parser):
        """Test international domain names."""
        result = parser.extract_domain("https://例え.jp/job")
        # Should handle or return empty for invalid
        assert isinstance(result, str)

    def test_extract_domain_ip_address(self, parser):
        """Test URL with IP address."""
        result = parser.extract_domain("http://192.168.1.1/jobs")
        assert result == "192.168.1.1"


class TestJobPlatforms:
    """Tests for job platform detection and extraction."""

    @pytest.fixture
    def parser(self):
        return JobParser()

    def test_greenhouse_is_platform(self, parser):
        """Test that greenhouse.io is detected as a platform."""
        is_platform, config = parser.is_job_platform("https://boards.greenhouse.io/stripe/jobs/123")
        assert is_platform is True
        assert config is not None
        assert "company_from_url" in config

    def test_lever_is_platform(self, parser):
        """Test that lever.co is detected as a platform."""
        is_platform, config = parser.is_job_platform("https://jobs.lever.co/openai/123")
        assert is_platform is True
        assert config is not None

    def test_workday_is_platform(self, parser):
        """Test that myworkdayjobs.com is detected as a platform."""
        is_platform, config = parser.is_job_platform("https://google.wd5.myworkdayjobs.com/job/123")
        assert is_platform is True

    def test_ashby_is_platform(self, parser):
        """Test that ashbyhq.com is detected as a platform."""
        is_platform, config = parser.is_job_platform("https://jobs.ashbyhq.com/company/job/123")
        assert is_platform is True

    def test_smartrecruiters_is_platform(self, parser):
        """Test that smartrecruiters.com is detected as a platform."""
        is_platform, config = parser.is_job_platform("https://jobs.smartrecruiters.com/company/job")
        assert is_platform is True

    def test_breezy_is_platform(self, parser):
        """Test that breezy.hr is detected as a platform."""
        is_platform, config = parser.is_job_platform("https://company.breezy.hr/job/123")
        assert is_platform is True

    def test_unknown_site_is_not_platform(self, parser):
        """Test that unknown sites are not platforms."""
        is_platform, config = parser.is_job_platform("https://random-company.com/careers")
        assert is_platform is False

    def test_extract_company_from_greenhouse_url(self, parser):
        """Test extracting company from Greenhouse URL."""
        company = parser.extract_company_from_url(
            "https://boards.greenhouse.io/stripe/jobs/123456",
            r"boards\.greenhouse\.io/([^/]+)"
        )
        assert company == "Stripe"

    def test_extract_company_from_lever_url(self, parser):
        """Test extracting company from Lever URL."""
        company = parser.extract_company_from_url(
            "https://jobs.lever.co/openai/123456",
            r"jobs\.lever\.co/([^/]+)"
        )
        assert company == "Openai"

    def test_extract_company_handles_hyphens(self, parser):
        """Test that hyphens in company names are converted to spaces."""
        company = parser.extract_company_from_url(
            "https://boards.greenhouse.io/my-awesome-startup/jobs/123",
            r"boards\.greenhouse\.io/([^/]+)"
        )
        assert company == "My Awesome Startup"

    def test_extract_company_handles_underscores(self, parser):
        """Test that underscores in company names are converted to spaces."""
        company = parser.extract_company_from_url(
            "https://boards.greenhouse.io/some_company/jobs/123",
            r"boards\.greenhouse\.io/([^/]+)"
        )
        assert company == "Some Company"

    def test_extract_company_returns_none_for_invalid(self, parser):
        """Test that invalid URLs return None."""
        company = parser.extract_company_from_url(
            "https://totally-different.com/jobs/123",
            r"boards\.greenhouse\.io/([^/]+)"
        )
        assert company is None

    def test_extract_company_from_workday_subdomain(self, parser):
        """Test extracting company from Workday subdomain."""
        company = parser.extract_company_from_url(
            "https://google.wd5.myworkdayjobs.com/en-US/careers/job/123",
            r"://([^.]+)\.wd\d*\.myworkdayjobs\.com"
        )
        assert company == "Google"

    def test_extract_company_from_ashby_path(self, parser):
        """Test extracting company from Ashby path."""
        company = parser.extract_company_from_url(
            "https://jobs.ashbyhq.com/notion/job/123",
            r"jobs\.ashbyhq\.com/([^/]+)"
        )
        assert company == "Notion"

    def test_job_platforms_dict_has_entries(self):
        """Test that JOB_PLATFORMS has expected entries."""
        assert "greenhouse.io" in JOB_PLATFORMS
        assert "lever.co" in JOB_PLATFORMS
        assert "myworkdayjobs.com" in JOB_PLATFORMS
        assert "ashbyhq.com" in JOB_PLATFORMS

    def test_job_platforms_only_have_url_patterns(self):
        """Test that platforms only have URL patterns, no CSS selectors."""
        for domain, config in JOB_PLATFORMS.items():
            assert "company_from_url" in config, f"{domain} missing company_from_url"
            # CSS selectors should be removed
            assert "company_selector" not in config, f"{domain} should not have company_selector"
            assert "title_selector" not in config, f"{domain} should not have title_selector"

    def test_get_job_platform_helper(self):
        """Test the get_job_platform helper function."""
        is_platform, config = get_job_platform("https://boards.greenhouse.io/company/jobs/1")
        assert is_platform is True

    def test_extract_company_from_platform_url_helper(self):
        """Test the extract_company_from_platform_url helper function."""
        company = extract_company_from_platform_url("https://boards.greenhouse.io/stripe/jobs/1")
        assert company == "Stripe"

    def test_extract_company_from_platform_url_unknown(self):
        """Test helper returns None for non-platform URLs."""
        company = extract_company_from_platform_url("https://random-site.com/job")
        assert company is None


class TestJobPlatformPatterns:
    """Tests for URL patterns in job platforms."""

    @pytest.fixture
    def parser(self):
        return JobParser()

    def test_greenhouse_pattern_variations(self, parser):
        """Test Greenhouse URL pattern with various formats."""
        # Standard format
        _, config = parser.is_job_platform("https://boards.greenhouse.io/stripe/jobs/1")
        company = parser.extract_company_from_url(
            "https://boards.greenhouse.io/stripe/jobs/123",
            config["company_from_url"]
        )
        assert company == "Stripe"

        # With hyphenated company name
        company = parser.extract_company_from_url(
            "https://boards.greenhouse.io/my-company/jobs/456",
            config["company_from_url"]
        )
        assert company == "My Company"

    def test_lever_pattern_variations(self, parser):
        """Test Lever URL pattern with various formats."""
        _, config = parser.is_job_platform("https://jobs.lever.co/company/job")

        company = parser.extract_company_from_url(
            "https://jobs.lever.co/openai/abc123",
            config["company_from_url"]
        )
        assert company == "Openai"

        company = parser.extract_company_from_url(
            "https://jobs.lever.co/anthropic/position/xyz",
            config["company_from_url"]
        )
        assert company == "Anthropic"

    def test_workday_pattern_with_different_wd_numbers(self, parser):
        """Test Workday URL pattern with different wd numbers."""
        _, config = parser.is_job_platform("https://company.wd1.myworkdayjobs.com/job")

        # wd1 - note the pattern now includes "://" to anchor subdomain
        company = parser.extract_company_from_url(
            "https://amazon.wd1.myworkdayjobs.com/en-US/Amazon_Talent/job/123",
            config["company_from_url"]
        )
        assert company == "Amazon"

        # wd5
        company = parser.extract_company_from_url(
            "https://google.wd5.myworkdayjobs.com/Google_Careers/job/456",
            config["company_from_url"]
        )
        assert company == "Google"

        # wd12
        company = parser.extract_company_from_url(
            "https://meta.wd12.myworkdayjobs.com/Meta/job/789",
            config["company_from_url"]
        )
        assert company == "Meta"

    def test_breezy_subdomain_pattern(self, parser):
        """Test Breezy subdomain-based URL pattern."""
        _, config = parser.is_job_platform("https://startup.breezy.hr/job")

        company = parser.extract_company_from_url(
            "https://cool-startup.breezy.hr/p/some-job",
            config["company_from_url"]
        )
        assert company == "Cool Startup"

    def test_bamboohr_subdomain_pattern(self, parser):
        """Test BambooHR subdomain-based URL pattern."""
        _, config = parser.is_job_platform("https://company.bamboohr.com/job")

        company = parser.extract_company_from_url(
            "https://acme-corp.bamboohr.com/careers/123",
            config["company_from_url"]
        )
        assert company == "Acme Corp"

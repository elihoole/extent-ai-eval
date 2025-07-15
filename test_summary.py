"""
Comprehensive test suite for Financial Highlights Extraction Pipeline
Tests various components including PDF processing, LLM extraction, validation, and edge cases.
"""

import json
import logging
import os
import tempfile
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

# Import your modules
from scripts.extract_with_llm import (
    FinancialHighlights,
    FinancialMetric,
    extract_from_image,
)
from scripts.file_handler import read_pdf
from scripts.pipeline import get_company_name_from_pdf, run_pdf_extraction
from scripts.utils import get_file_path_to_save, pil_image_to_base64, write_output_json


class TestFinancialMetric(unittest.TestCase):
    """Test the FinancialMetric Pydantic model"""

    def test_financial_metric_creation(self):
        """Test basic creation of FinancialMetric"""
        metric = FinancialMetric(
            metric="Revenue", change_percent=-5.8, value_2024=171170, value_2023=181722
        )

        self.assertEqual(metric.metric, "Revenue")
        self.assertEqual(metric.change_percent, -5.8)
        self.assertEqual(metric.get_year_value(2024), 171170)
        self.assertEqual(metric.get_year_value(2023), 181722)

    def test_dynamic_year_values(self):
        """Test dynamic year field handling"""
        metric = FinancialMetric(metric="Net Income")

        # Test setting values dynamically
        metric.set_year_value(2025, 1000000)
        metric.set_year_value(2024, 900000)

        self.assertEqual(metric.get_year_value(2025), 1000000)
        self.assertEqual(metric.get_year_value(2024), 900000)
        self.assertIsNone(metric.get_year_value(2022))

    def test_optional_change_percent(self):
        """Test that change_percent can be None"""
        metric = FinancialMetric(metric="Test Metric", value_2024=100)
        self.assertIsNone(metric.change_percent)

        metric_with_change = FinancialMetric(
            metric="Test Metric", value_2024=100, change_percent=10.5
        )
        self.assertEqual(metric_with_change.change_percent, 10.5)


class TestFinancialHighlights(unittest.TestCase):
    """Test the FinancialHighlights response schema"""

    def test_financial_highlights_creation(self):
        """Test creation with sample data"""
        metrics = [
            FinancialMetric(
                metric="Revenue",
                change_percent=-5.8,
                value_2024=171170,
                value_2023=181722,
            )
        ]

        highlights = FinancialHighlights(
            report_year=2024,
            metrics=metrics,
            metadata={
                "currency": "Sri Lankan Rupees",
                "year_end_date": "December 31, 2024",
            },
        )

        self.assertEqual(highlights.report_year, 2024)
        self.assertEqual(len(highlights.metrics), 1)
        self.assertEqual(highlights.metadata["currency"], "Sri Lankan Rupees")

    def test_empty_metrics_list(self):
        """Test with empty metrics list"""
        highlights = FinancialHighlights(report_year=2024, metrics=[], metadata={})

        self.assertEqual(len(highlights.metrics), 0)


class TestDataValidation(unittest.TestCase):
    """Test data validation and business logic"""

    def test_percentage_change_calculation(self):
        """Test percentage change calculation accuracy"""

        def calculate_percentage_change(current: float, previous: float) -> float:
            """Helper function to calculate percentage change"""
            if previous == 0:
                return 0.0
            return round(((current - previous) / previous) * 100, 1)

        # Test cases based on actual data from Dialog output
        test_cases = [
            (171170, 181722, -5.8),  # Revenue
            (72695, 65759, 10.5),  # Gross profit
            (12435, 20113, -38.2),  # Profit for the year
        ]

        for current, previous, expected in test_cases:
            calculated = calculate_percentage_change(current, previous)
            self.assertAlmostEqual(calculated, expected, places=1)

    def test_metric_validation_rules(self):
        """Test business rules for financial metrics"""

        def validate_financial_metric(metric_data: Dict[str, Any]) -> bool:
            """Validate financial metric data"""
            # Check required fields
            if not metric_data.get("metric"):
                return False

            # Check that at least one year value exists
            year_values = [k for k in metric_data.keys() if k.startswith("value_")]
            if not year_values:
                return False

            # Check that percentage changes are reasonable (-100% to +1000%)
            change_percent = metric_data.get("change_percent")
            if change_percent is not None:
                if change_percent < -100 or change_percent > 1000:
                    return False

            return True

        # Valid metric
        valid_metric = {
            "metric": "Revenue",
            "value_2024": 171170,
            "value_2023": 181722,
            "change_percent": -5.8,
        }
        self.assertTrue(validate_financial_metric(valid_metric))

        # Invalid - no metric name
        invalid_metric = {"value_2024": 171170, "change_percent": -5.8}
        self.assertFalse(validate_financial_metric(invalid_metric))

        # Invalid - no year values
        invalid_metric2 = {"metric": "Revenue", "change_percent": -5.8}
        self.assertFalse(validate_financial_metric(invalid_metric2))


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions"""

    def test_get_file_path_to_save(self):
        """Test filename generation"""
        test_path = "/path/to/financial_statement (1).pdf"
        result = get_file_path_to_save(test_path)

        # Should contain sanitized name and UUID
        self.assertTrue(result.startswith("financial_statement"))
        self.assertTrue(result.endswith(".pdf"))
        # After sanitization: "financial_statement_1_" + 8-char-uuid + ".pdf"
        # This creates: financial_statement_1_{uuid}.pdf
        parts = result.replace(".pdf", "").split("_")
        self.assertGreaterEqual(
            len(parts), 3
        )  # At least: financial, statement, 1, uuid

        # Verify UUID part is 8 characters
        uuid_part = parts[-1]
        self.assertEqual(len(uuid_part), 8)

    def test_write_output_json(self):
        """Test JSON output writing"""
        test_data = {
            "report_year": 2024,
            "metrics": [{"metric": "Test", "value_2024": 100}],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            # Temporarily override OUTPUT_DIR
            with patch.dict(os.environ, {"OUTPUT_DIR": temp_dir}):
                write_output_json("test_output.json", test_data)

                output_path = os.path.join(temp_dir, "test_output.json")
                self.assertTrue(os.path.exists(output_path))

                # Verify content
                with open(output_path, "r") as f:
                    loaded_data = json.load(f)
                    self.assertEqual(loaded_data["report_year"], 2024)


class TestPDFProcessing(unittest.TestCase):
    """Test PDF processing functionality"""

    @patch("scripts.file_handler.pdf2image.convert_from_path")
    def test_read_pdf_success(self, mock_convert):
        """Test successful PDF reading"""
        # Mock PIL images
        mock_images = [Mock(), Mock(), Mock()]
        mock_convert.return_value = mock_images

        result = read_pdf("test.pdf")

        self.assertEqual(len(result), 3)
        mock_convert.assert_called_once_with("test.pdf")

    def test_read_pdf_invalid_path(self):
        """Test PDF reading with invalid paths"""
        test_cases = [
            None,
            "",
            "not_a_pdf.txt",
            123,  # Non-string
        ]

        for invalid_path in test_cases:
            result = read_pdf(invalid_path)
            self.assertIsNone(result)

    @patch("scripts.pipeline.PyPDF2.PdfReader")
    @patch("builtins.open")
    def test_company_name_extraction(self, mock_open, mock_pdf_reader):
        """Test company name extraction from PDF"""
        # Mock PDF content
        mock_page = Mock()
        mock_page.extract_text.return_value = (
            "Ceylon Investment PLC\nAnnual Report 2024"
        )

        mock_reader = Mock()
        mock_reader.pages = [mock_page]
        mock_pdf_reader.return_value = mock_reader

        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file

        result = get_company_name_from_pdf("test.pdf", 0)

        self.assertEqual(result, "Ceylon Investment PLC\nAnnual Report 2024")


class TestLLMIntegration(unittest.TestCase):
    """Test LLM integration and mocking"""

    @patch("scripts.extract_with_llm.genai.Client")
    def test_extract_from_image_mock(self, mock_client_class):
        """Test LLM extraction with mocked response"""
        # Mock the response
        mock_response = Mock()
        mock_response.text = json.dumps(
            {
                "report_year": 2024,
                "metrics": [
                    {
                        "metric": "Revenue",
                        "value_2024": 171170,
                        "value_2023": 181722,
                        "change_percent": -5.8,
                    }
                ],
                "metadata": {
                    "currency": "Sri Lankan Rupees",
                    "year_end_date": "December 31, 2024",
                },
            }
        )

        # Mock usage metadata
        mock_usage = Mock()
        mock_usage.prompt_token_count = 666
        mock_usage.candidates_token_count = 2008
        mock_usage.total_token_count = 6078
        mock_response.usage_metadata = mock_usage

        # Setup mock client
        mock_client = Mock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        # Test extraction
        test_image = b"fake_image_data"
        result = extract_from_image(test_image)

        # Assertions
        self.assertIsInstance(result, FinancialHighlights)
        self.assertEqual(result.report_year, 2024)
        self.assertEqual(len(result.metrics), 1)
        self.assertEqual(result.metrics[0].metric, "Revenue")
        self.assertIn("token_usage", result.metadata)


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    def test_invalid_json_response(self):
        """Test handling of invalid JSON responses"""
        with patch("scripts.extract_with_llm.genai.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.text = "Invalid JSON content"

            mock_client = Mock()
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client

            test_image = b"fake_image_data"

            with self.assertRaises(Exception):
                extract_from_image(test_image, max_tries=1)

    def test_missing_required_fields(self):
        """Test validation with missing required fields"""
        invalid_data = {
            "metrics": [],  # Missing report_year
            "metadata": {},
        }

        with self.assertRaises(Exception):
            FinancialHighlights.model_validate(invalid_data)


class TestRealDataValidation(unittest.TestCase):
    """Test with real extracted data samples"""

    def test_dialog_axiata_sample(self):
        """Test with actual Dialog Axiata extracted data"""
        sample_data = {
            "report_year": 2024,
            "metrics": [
                {
                    "metric": "Revenue",
                    "change_percent": -5.8,
                    "value_2024": 171170,
                    "value_2023": 181722,
                },
                {
                    "metric": "Gross profit",
                    "change_percent": 10.5,
                    "value_2024": 72695,
                    "value_2023": 65759,
                },
            ],
            "metadata": {
                "currency": "Sri Lankan Rupees",
                "year_end_date": "December 31, 2024",
            },
        }

        # Should validate successfully
        highlights = FinancialHighlights.model_validate(sample_data)
        self.assertEqual(highlights.report_year, 2024)
        self.assertEqual(len(highlights.metrics), 2)

        # Test specific metric values
        revenue = highlights.metrics[0]
        self.assertEqual(revenue.metric, "Revenue")
        self.assertEqual(revenue.get_year_value(2024), 171170)
        self.assertEqual(revenue.change_percent, -5.8)

    def test_percentage_change_hallucination_detection(self):
        """Test detection of hallucinated percentage changes"""

        def detect_hallucinated_change(metric_data: Dict[str, Any]) -> bool:
            """Detect if change_percent is hallucinated by calculating actual change"""
            change_percent = metric_data.get("change_percent")
            if change_percent is None or change_percent == -0.0:
                return False  # Explicitly marked as no change data

            # Find year values
            year_values = {}
            for key, value in metric_data.items():
                if key.startswith("value_") and value is not None:
                    year = int(key.split("_")[1])
                    year_values[year] = value

            if len(year_values) < 2:
                return False  # Can't validate with less than 2 years

            # Calculate actual change
            years = sorted(year_values.keys())
            current_year = years[-1]
            previous_year = years[-2]

            current_value = year_values[current_year]
            previous_value = year_values[previous_year]

            if previous_value == 0:
                return False  # Can't calculate meaningful change

            actual_change = ((current_value - previous_value) / previous_value) * 100
            tolerance = 1.0  # Allow 1% tolerance for rounding

            return abs(actual_change - change_percent) > tolerance

        # Test with correct data (should not be flagged as hallucination)
        correct_metric = {
            "metric": "Revenue",
            "value_2024": 171170,
            "value_2023": 181722,
            "change_percent": -5.8,
        }
        self.assertFalse(detect_hallucinated_change(correct_metric))

        # Test with incorrect data (should be flagged as hallucination)
        incorrect_metric = {
            "metric": "Revenue",
            "value_2024": 171170,
            "value_2023": 181722,
            "change_percent": 25.0,  # Clearly wrong
        }
        self.assertTrue(detect_hallucinated_change(incorrect_metric))


class TestPerformanceOptimization(unittest.TestCase):
    """Test performance optimization scenarios"""

    def test_batch_processing_simulation(self):
        """Simulate batch processing of multiple PDFs"""
        # Mock scenario for processing multiple files
        file_count = 10
        processing_times = []

        for i in range(file_count):
            # Simulate processing time
            import time

            start_time = time.time()

            # Mock some processing work
            time.sleep(0.01)  # Simulate 10ms processing

            end_time = time.time()
            processing_times.append(end_time - start_time)

        avg_time = sum(processing_times) / len(processing_times)

        # Performance assertions
        self.assertLess(avg_time, 0.1)  # Should be under 100ms per file for mock
        self.assertEqual(len(processing_times), file_count)

    def test_memory_efficiency(self):
        """Test memory usage patterns"""
        # Create a large dataset to test memory handling
        large_metrics = []
        for i in range(1000):
            metric = FinancialMetric(
                metric=f"Metric_{i}",
                change_percent=i * 0.1,
                value_2024=i * 1000,
                value_2023=i * 900,
            )
            large_metrics.append(metric)

        highlights = FinancialHighlights(
            report_year=2024, metrics=large_metrics, metadata={"test": "memory_test"}
        )

        # Verify we can handle large datasets
        self.assertEqual(len(highlights.metrics), 1000)

        # Cleanup
        del highlights
        del large_metrics


def run_specific_test(test_class_name: str = None):
    """Run a specific test class or all tests"""
    if test_class_name:
        suite = unittest.TestLoader().loadTestsFromName(f"__main__.{test_class_name}")
    else:
        suite = unittest.TestLoader().loadTestsFromModule(__import__("__main__"))

    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


if __name__ == "__main__":
    # Setup logging for tests
    logging.basicConfig(level=logging.WARNING)  # Reduce noise during tests

    print("=" * 80)
    print("FINANCIAL HIGHLIGHTS EXTRACTION - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    # Run all tests
    result = run_specific_test()

    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")

    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")

    success_rate = (
        (result.testsRun - len(result.failures) - len(result.errors))
        / result.testsRun
        * 100
    )
    print(f"\nSuccess Rate: {success_rate:.1f}%")

    if result.wasSuccessful():
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed. Review the output above.")

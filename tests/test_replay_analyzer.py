import unittest
import logging
import sys
import os

# Adjust path to import from src
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from src.replay_analyzer import ReplayAnalyzer
    from src.iracing_manager import PlaceholderIRacingManager # Analyzer depends on a manager
    from src.app_settings import AppSettings # For manager and analyzer settings
except ModuleNotFoundError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.replay_analyzer import ReplayAnalyzer
    from src.iracing_manager import PlaceholderIRacingManager
    from src.app_settings import AppSettings


logger = logging.getLogger(__name__)

class TestReplayAnalyzer(unittest.TestCase):
    """Tests for the ReplayAnalyzer class."""

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up TestReplayAnalyzer class.")
        # Create shared settings and manager for analyzer tests
        cls.test_settings_file = "test_analyzer_settings.ini"
        cls.app_settings = AppSettings(settings_file_path=cls.test_settings_file)
        # Customize settings if needed for analyzer tests
        # cls.app_settings.update_setting("ReplayAnalysis", "event_detection_sensitivity", "high")
        # cls.app_settings.save_settings()

        cls.iracing_manager = PlaceholderIRacingManager(settings=cls.app_settings)
        # It's good practice for the manager to be "connected" if the analyzer expects live data
        # or data that would normally come from a connected manager.
        cls.iracing_manager.connect()


    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down TestReplayAnalyzer class.")
        if cls.iracing_manager.is_connected:
            cls.iracing_manager.disconnect()
        if os.path.exists(cls.test_settings_file):
            os.remove(cls.test_settings_file)

    def setUp(self):
        logger.debug(f"Setting up test: {self._testMethodName}")
        # Create a new analyzer for each test, using the shared manager and settings
        self.analyzer = ReplayAnalyzer(iracing_manager=self.iracing_manager, settings=self.app_settings)

    def tearDown(self):
        logger.debug(f"Tearing down test: {self._testMethodName}")
        self.analyzer = None # Release instance

    def test_01_instantiation(self):
        """Test that ReplayAnalyzer can be instantiated."""
        logger.info("Running test_01_instantiation")
        self.assertIsInstance(self.analyzer, ReplayAnalyzer)
        self.assertIsNotNone(self.analyzer.iracing_manager)
        # self.assertIsNotNone(self.analyzer.settings) # If settings are stored

    def test_02_instantiation_with_none_manager(self):
        """Test that ReplayAnalyzer raises error if manager is None."""
        logger.info("Running test_02_instantiation_with_none_manager")
        with self.assertRaisesRegex(ValueError, "IRacingManager instance cannot be None."):
            ReplayAnalyzer(iracing_manager=None, settings=self.app_settings)


    def test_03_load_replay_data_placeholder(self):
        """Test the placeholder load_replay_data method."""
        logger.info("Running test_03_load_replay_data_placeholder")
        # Ensure manager is connected for "live" source, which it should be from setUpClass
        self.assertTrue(self.iracing_manager.is_connected, "Manager should be connected for this test.")

        # Test "live" source (placeholder)
        self.analyzer.load_replay_data(source="live")
        self.assertIn("TrackName", self.analyzer.session_details, "Session details should be populated.")
        self.assertEqual(len(self.analyzer.raw_telemetry_data), 0,
                         "Raw telemetry should be empty initially for 'live' before processing any frames.")

        # Test "file" source (placeholder) - manager simulates data loading
        self.analyzer.load_replay_data(source="file", replay_file_path="dummy.ibt")
        self.assertTrue(len(self.analyzer.raw_telemetry_data) > 0,
                        "Raw telemetry should be populated by placeholder file load.")
        # Check if some telemetry detail is present (depends on PlaceholderIRacingManager's mock data)
        if self.analyzer.raw_telemetry_data:
            self.assertIn("Speed", self.analyzer.raw_telemetry_data[0])


    def test_04_process_telemetry_placeholder(self):
        """Test the placeholder process_telemetry method."""
        logger.info("Running test_04_process_telemetry_placeholder")
        # Load some data first (simulated)
        self.analyzer.load_replay_data(source="file", replay_file_path="dummy.ibt")
        self.assertTrue(len(self.analyzer.raw_telemetry_data) > 0, "Need data to process.")

        results = self.analyzer.process_telemetry()
        self.assertIsInstance(results, dict, "Processing should return a dictionary of results.")
        self.assertIn("total_incidents", results, "Results should include total_incidents.")
        self.assertIn("laps_completed", results, "Results should include laps_completed.")
        self.assertIn("fastest_lap_time", results, "Results should include fastest_lap_time.")

        # Placeholder logic in ReplayAnalyzer might produce specific values based on PlaceholderIRacingManager
        # For now, just checking existence is fine for a placeholder test.
        # Example: if PlaceholderIRacingManager mock data is consistent:
        # self.assertEqual(results["total_incidents"], 0) # If mock data has no incidents


    def test_05_get_analysis_summary_placeholder(self):
        """Test the placeholder get_analysis_summary method."""
        logger.info("Running test_05_get_analysis_summary_placeholder")
        # Before processing
        summary_before = self.analyzer.get_analysis_summary()
        self.assertIn("No analysis summary available", summary_before)

        # After processing
        self.analyzer.load_replay_data(source="file", replay_file_path="dummy.ibt")
        self.analyzer.process_telemetry()
        summary_after = self.analyzer.get_analysis_summary()
        self.assertNotIn("No analysis summary available", summary_after)
        self.assertIn("Total Incidents", summary_after)
        self.assertIn("Laps Completed", summary_after)


    def test_06_generate_event_timeline_placeholder(self):
        """Test the placeholder generate_event_timeline method."""
        logger.info("Running test_06_generate_event_timeline_placeholder")
        timeline = self.analyzer.generate_event_timeline()
        self.assertIsInstance(timeline, list, "Timeline should be a list.")
        if timeline: # If placeholder returns non-empty
            self.assertIsInstance(timeline[0], dict, "Timeline events should be dictionaries.")
            self.assertIn("time", timeline[0])
            self.assertIn("event_type", timeline[0])
        # For current placeholder, it returns a fixed list
        self.assertEqual(len(timeline), 3)


if __name__ == "__main__":
    if not logging.getLoggerClass().root.hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    unittest.main()

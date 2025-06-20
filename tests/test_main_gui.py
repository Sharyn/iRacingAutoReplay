import unittest
import sys
import os
import logging

# Adjust path to import from src
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Attempt to import PyQt6 for GUI tests. If not available, tests might be skipped or limited.
HAS_PYQT6 = False
try:
    from PyQt6.QtWidgets import QApplication
    # from PyQt6.QtTest import QTest # For more advanced GUI testing
    HAS_PYQT6 = True
except ImportError:
    logging.warning("PyQt6 not found. GUI tests will be limited or skipped.")
    # Define a dummy QApplication if needed for basic structure testing without full GUI
    class QApplication:
        _instance = None
        def __init__(self, args):
            if QApplication._instance is None:
                QApplication._instance = self
        @classmethod
        def instance(cls):
            return cls._instance
        def exec(self): pass
        def quit(self): pass


try:
    from src.main_gui import MainWindow, start_app # Assuming start_app can be tested or components thereof
    from src.app_settings import AppSettings
    from src.iracing_manager import PlaceholderIRacingManager
    from src.replay_analyzer import ReplayAnalyzer
except ModuleNotFoundError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from src.main_gui import MainWindow, start_app
    from src.app_settings import AppSettings
    from src.iracing_manager import PlaceholderIRacingManager
    from src.replay_analyzer import ReplayAnalyzer


logger = logging.getLogger(__name__)

# Keep track of QApplication instance to avoid creating multiple
# This is important for PyQt applications.
q_app_instance = None

def get_qapp_instance():
    """Gets or creates a QApplication instance for testing."""
    global q_app_instance
    if HAS_PYQT6:
        q_app_instance = QApplication.instance() # Check if already exists
        if q_app_instance is None:
            # sys.argv is needed by QApplication.
            # If not running from a context where sys.argv is populated, provide a default.
            if not hasattr(sys, 'argv'):
                sys.argv = ['test_program']
            q_app_instance = QApplication(sys.argv)
    else: # Fallback for no PyQt6
        if q_app_instance is None:
            q_app_instance = QApplication(sys.argv if hasattr(sys, 'argv') else [''])
    return q_app_instance


class TestMainWindow(unittest.TestCase):
    """Basic tests for the MainWindow GUI class."""

    @classmethod
    def setUpClass(cls):
        logger.info("Setting up TestMainWindow class.")
        cls.app = get_qapp_instance() # Ensure QApplication exists for tests

        # Setup common resources needed by MainWindow
        cls.test_settings_file_gui = "test_gui_settings.ini"
        cls.app_settings = AppSettings(settings_file_path=cls.test_settings_file_gui)
        cls.iracing_manager = PlaceholderIRacingManager(settings=cls.app_settings)
        # Connect manager as GUI might expect it to be usable
        if hasattr(cls.iracing_manager, 'connect'): # Check if it's the real manager
             cls.iracing_manager.connect()
        cls.replay_analyzer = ReplayAnalyzer(iracing_manager=cls.iracing_manager, settings=cls.app_settings)


    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down TestMainWindow class.")
        if hasattr(cls.iracing_manager, 'is_connected') and cls.iracing_manager.is_connected:
            cls.iracing_manager.disconnect()
        if os.path.exists(cls.test_settings_file_gui):
            os.remove(cls.test_settings_file_gui)

        # Important: Clean up QApplication if we created it and no other tests need it.
        # However, q_app_instance.quit() or similar might be needed if exec was called.
        # For simple instantiation tests, this might not be strictly necessary.
        # global q_app_instance
        # if q_app_instance and HAS_PYQT6:
        #     # q_app_instance.quit() # This can cause issues if exec() wasn't called
        #     pass
        # q_app_instance = None


    def setUp(self):
        logger.debug(f"Setting up test: {self._testMethodName}")
        # Create a new MainWindow instance for each test
        # This ensures that each test starts with a fresh UI state.
        self.window = MainWindow(
            app_settings=self.app_settings,
            iracing_manager=self.iracing_manager,
            replay_analyzer=self.replay_analyzer
        )

    def tearDown(self):
        logger.debug(f"Tearing down test: {self._testMethodName}")
        # Close the window after each test if it was shown.
        # If window.show() was called, window.close() should be called.
        # For tests that don't show the window, this might not be needed.
        if hasattr(self.window, 'close') and callable(self.window.close):
             self.window.close() # Ensure it's closed, good practice
        self.window = None


    @unittest.skipUnless(HAS_PYQT6, "PyQt6 not installed, skipping full GUI instantiation tests.")
    def test_01_main_window_instantiation(self):
        """Test if MainWindow can be instantiated without errors."""
        logger.info("Running test_01_main_window_instantiation (Full PyQt6)")
        self.assertIsNotNone(self.window)
        self.assertEqual(self.window.windowTitle(), "iRacing Telemetry Analyzer & Replay Director")
        # Check if placeholder label is there
        self.assertIsNotNone(self.window.status_label)
        self.assertIn("Welcome!", self.window.status_label.text())


    def test_01a_main_window_instantiation_dummy(self):
        """Test if MainWindow can be instantiated (using dummy UI if PyQt6 is missing)."""
        logger.info("Running test_01a_main_window_instantiation_dummy (May use dummy UI)")
        # This test runs regardless of HAS_PYQT6 to ensure basic class structure is okay.
        # The MainWindow uses dummy classes if PyQt6 is not found.
        local_window = MainWindow( # Create with potentially dummy components
            app_settings=self.app_settings,
            iracing_manager=self.iracing_manager,
            replay_analyzer=self.replay_analyzer
        )
        self.assertIsNotNone(local_window)
        # If dummy, setWindowTitle might not exist or do anything.
        # So, we only check this if we are sure it's a QMainWindow.
        if HAS_PYQT6:
             self.assertEqual(local_window.windowTitle(), "iRacing Telemetry Analyzer & Replay Director")


    @unittest.skipUnless(HAS_PYQT6, "PyQt6 not installed, skipping GUI interaction tests.")
    def test_02_connect_button_click_placeholder(self):
        """Test connect button click behavior (placeholder functionality)."""
        logger.info("Running test_02_connect_button_click_placeholder (Full PyQt6)")
        self.assertTrue(self.iracing_manager.is_connected, "Manager should be connected from setUpClass.")

        # Simulate disconnect via button
        initial_button_text = self.window.connect_button.text()
        self.window.toggle_connection() # Should disconnect

        self.assertFalse(self.iracing_manager.is_connected, "Manager should be disconnected after toggle.")
        self.assertNotEqual(self.window.connect_button.text(), initial_button_text)
        self.assertIn("Connect to iRacing", self.window.connect_button.text())

        # Simulate connect via button
        self.window.toggle_connection() # Should connect
        self.assertTrue(self.iracing_manager.is_connected, "Manager should be re-connected.")
        self.assertIn("Disconnect from iRacing", self.window.connect_button.text())


    @unittest.skipUnless(HAS_PYQT6, "PyQt6 not installed, skipping GUI interaction tests.")
    def test_03_analyze_button_click_placeholder(self):
        """Test analyze button click behavior (placeholder functionality)."""
        logger.info("Running test_03_analyze_button_click_placeholder (Full PyQt6)")
        # Ensure manager is connected, as run_analysis might expect it
        if not self.iracing_manager.is_connected:
            self.iracing_manager.connect()

        initial_log_content = self.window.log_output_area.toPlainText()
        self.window.run_analysis() # Placeholder analysis

        # Check if log output area received messages related to analysis
        final_log_content = self.window.log_output_area.toPlainText()
        self.assertNotEqual(final_log_content, initial_log_content, "Log should have new messages.")
        self.assertIn("Starting analysis", final_log_content)
        self.assertIn("Analysis complete", final_log_content)
        self.assertIn("Total Incidents", final_log_content) # From summary

    # Test for start_app might be more of an integration test
    # and could be tricky if it calls sys.exit().
    # For now, focusing on MainWindow unit tests.
    # def test_start_app_basic_run(self):
    #     """Very basic test for start_app function, ensuring it runs without immediate error."""
    #     # This is a very superficial test. start_app() creates its own components.
    #     # It also calls app.exec() which would block if not handled.
    #     # Consider mocking sys.exit and QApplication.exec for a more robust test.
    #     logger.info("Attempting a limited run of start_app()")
    #     try:
    #         # TODO: Need a way to prevent start_app from blocking or exiting the test runner.
    #         # This might involve monkeypatching QApplication.exec and sys.exit.
    #         # For now, this test is more of a placeholder for future integration testing.
    #         pass # Placeholder for a more complex test setup
    #     except SystemExit:
    #         logger.info("start_app called sys.exit() as expected in some setups.")
    #     except Exception as e:
    #         self.fail(f"start_app raised an unexpected exception: {e}")


if __name__ == "__main__":
    # Ensure logging is available for test output
    if not logging.getLoggerClass().root.hasHandlers():
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Need to manage QApplication instance for GUI tests
    # This setup is basic; a dedicated test runner like pytest with pytest-qt plugin
    # would handle QApplication lifecycle more robustly.
    app = get_qapp_instance() # Ensure one is created before tests run

    unittest.main()

    # If we created q_app_instance and it's the main controller of an event loop,
    # it might need to be explicitly closed or quit, but unittest.main() might handle this.
    # if q_app_instance and HAS_PYQT6 and not QApplication.instance().closingDown():
    #    q_app_instance.quit() # Or exit(), depending on context.
    # This part is tricky without a full test runner setup like pytest-qt.

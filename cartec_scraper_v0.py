import os
import json
import logging
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit, QProgressBar, QTextEdit, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import pandas as pd
from playwright.sync_api import Playwright, sync_playwright
from parsel import Selector

class ScraperThread(QThread):
    progress_update = pyqtSignal(int, str)
    log_update = pyqtSignal(str)
    scraping_complete = pyqtSignal(str, int)
    scraping_error = pyqtSignal(str)

    def __init__(self, app, output_path):
        super().__init__()
        self.app = app
        self.output_path = output_path

    def run(self):
        try:
            with sync_playwright() as playwright:
                self.app.run_scraper(playwright)
        except Exception as e:
            self.scraping_error.emit(str(e))

class CartecScraperApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cartec Web Scraper")
        self.setGeometry(100, 100, 600, 500)

        # Setup logging
        logging.basicConfig(
            filename='scraper.log', 
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

        # State tracking file
        self.state_file = 'scraper_state.json'
        self.state = self.load_state()

        # UI Setup
        self.create_ui()

    def create_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        # Output File Path
        file_layout = QHBoxLayout()
        self.output_path = QLineEdit(self.state.get('output_path', 'cartec_data.xlsx'))
        file_layout.addWidget(QLabel("Output Excel File:"))
        file_layout.addWidget(self.output_path)
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.choose_output_file)
        file_layout.addWidget(browse_button)
        layout.addLayout(file_layout)

        # Progress Tracking
        self.progress_label = QLabel("Scraping Progress: Not Started")
        layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Control Buttons
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start/Continue Scraping")
        self.start_button.clicked.connect(self.start_scraping)
        button_layout.addWidget(self.start_button)

        reset_button = QPushButton("Reset Progress")
        reset_button.clicked.connect(self.reset_progress)
        button_layout.addWidget(reset_button)
        layout.addLayout(button_layout)

        # Log Display
        layout.addWidget(QLabel("Recent Logs:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        central_widget.setLayout(layout)

    def choose_output_file(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "", "Excel files (*.xlsx)")
        if filename:
            self.output_path.setText(filename)

    def log_message(self, message):
        self.logger.info(message)
        self.log_text.append(message)

    def load_state(self):
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log_message(f"Error loading state: {e}")
        return {}

    def save_state(self, state):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.log_message(f"Error saving state: {e}")

    def reset_progress(self):
        reply = QMessageBox.question(self, "Reset Progress", "Are you sure you want to reset all progress?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
            self.progress_label.setText("Scraping Progress: Not Started")
            self.progress_bar.setValue(0)
            self.log_text.clear()
            self.state = {}

    def start_scraping(self):
        self.start_button.setEnabled(False)
        self.scraper_thread = ScraperThread(self, self.output_path.text())
        self.scraper_thread.progress_update.connect(self.update_progress)
        self.scraper_thread.log_update.connect(self.log_message)
        self.scraper_thread.scraping_complete.connect(self.scraping_complete)
        self.scraper_thread.scraping_error.connect(self.scraping_error)
        self.scraper_thread.start()

    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.progress_label.setText(f"Scraping Progress: {message}")

    def scraping_complete(self, output_path, duplicates_removed):
        QMessageBox.information(self, "Scraping Complete", 
                                f"Data saved to {output_path}\n{duplicates_removed} duplicate rows removed.")
        self.progress_label.setText("Scraping Complete")
        self.progress_bar.setValue(100)
        self.start_button.setEnabled(True)

    def scraping_error(self, error_message):
        QMessageBox.critical(self, "Scraping Error", error_message)
        self.start_button.setEnabled(True)

    def remove_duplicate_rows(self, file_path):
        try:
            df = pd.read_excel(file_path)
            initial_rows = len(df)
            df_unique = df.drop_duplicates(subset=['MARQUE', 'MODELE', 'MOTORISATION'], keep='first')
            duplicates_removed = initial_rows - len(df_unique)
            df_unique.to_excel(file_path, index=False)
            if duplicates_removed > 0:
                self.log_message(f"Removed {duplicates_removed} duplicate rows from {file_path}")
            return duplicates_removed
        except Exception as e:
            self.log_message(f"Error removing duplicates: {e}")
            return 0

    def run_scraper(self, playwright: Playwright) -> None:
        output_path = self.output_path.text()
        
        if os.path.exists(output_path):
            existing_df = pd.read_excel(output_path)
            self.log_message(f"Loaded existing data: {len(existing_df)} rows")
        else:
            existing_df = pd.DataFrame(columns=['MARQUE', 'MODELE', 'MOTORISATION'])

        total_marques_names = existing_df['MARQUE'].tolist()
        total_modeles_names = existing_df['MODELE'].tolist()
        motorisation_true_names = existing_df['MOTORISATION'].tolist()
        
        processed_combinations = set(zip(total_marques_names, total_modeles_names, motorisation_true_names))

        last_marque = existing_df['MARQUE'].iloc[-1] if len(existing_df) > 0 else None
        
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        
        try:
            page = context.new_page()
            page.goto("https://www.cartec.ma/")
            page.wait_for_load_state("domcontentloaded")
            
            page_source = page.locator("html").inner_html()
            selector = Selector(page_source)
            
            marques = [marqua.attrib['value'] for marqua in selector.css("#manufacturer-select > option")]
            marques_names = selector.css("#manufacturer-select > option ::text").getall()
            
            marques_true_names = []
            for marque in marques_names[1:]:
                marques_true_names.append(
                    str(marque).replace("\n","").replace("            ","").replace("    ","")
                )

            start_index = 1
            if last_marque:
                try:
                    start_index = marques_true_names.index(last_marque) + 1
                    self.log_message(f"Resuming from last marque: {last_marque}")
                except ValueError:
                    self.log_message(f"Last marque {last_marque} not found. Starting from the beginning.")
                    start_index = 1

            for marque_index, marque in enumerate(marques[start_index:], start_index):
                self.log_message(f"Processing Marque: {marques_true_names[marque_index-1]}")
                page.locator("#manufacturer-select").select_option(str(marque))
                page.wait_for_timeout(200)
                
                page_source = page.locator("html").inner_html()
                selector = Selector(page_source)
                
                modeles = [modele.attrib['value'] for modele in selector.css("#model-select > option")]
                modeles_names = selector.css("#model-select > option ::text").getall()[1:]
                
                for modele_index, modele in enumerate(modeles[1:], 1):
                    try:
                        modele_name = str(modeles_names[modele_index-1]).replace("\n","").replace("            ","").replace("    ","")
                        
                        page.locator("#model-select").select_option(str(modele))
                        page.wait_for_timeout(200)
                        
                        page_source = page.locator("html").inner_html()
                        selector = Selector(page_source)
                        
                        motorisation_names = selector.css("#vehicle-select  option ::text").getall()[1:]
                        
                        model_additions = 0
                        
                        for motorisation_index, motorisation in enumerate(motorisation_names[1:], 1):
                            current_marque = marques_true_names[marque_index-1]
                            clean_motorisation = str(motorisation).replace("\n","").replace("            ","").replace("    ","")
                            
                            if (current_marque, modele_name, clean_motorisation) not in processed_combinations:
                                total_marques_names.append(current_marque)
                                total_modeles_names.append(modele_name)
                                motorisation_true_names.append(clean_motorisation)
                                
                                processed_combinations.add((current_marque, modele_name, clean_motorisation))
                                model_additions += 1
                        
                        self.log_message(f"Model {modele_name}: Added {model_additions} new entries")
                        
                        temp_df = pd.DataFrame({
                            'MARQUE': total_marques_names,
                            'MODELE': total_modeles_names,
                            'MOTORISATION': motorisation_true_names
                        })
                        temp_df.to_excel(output_path, index=False)
                        
                        progress_percentage = int((marque_index / len(marques[1:])) * 100)
                        self.scraper_thread.progress_update.emit(
                            progress_percentage,
                            f"Processing {marques_true_names[marque_index-1]} - {modele_name}"
                        )

                    except Exception as model_error:
                        self.log_message(f"Error processing model {modele_name}: {model_error}")
                        continue

                self.log_message(f"Current data lengths - Marques: {len(total_marques_names)}, Modeles: {len(total_modeles_names)}, Motorisations: {len(motorisation_true_names)}")

            df = pd.DataFrame({
                'MARQUE': total_marques_names,
                'MODELE': total_modeles_names,
                'MOTORISATION': motorisation_true_names
            })
            
            df.to_excel(output_path, index=False)
            
            duplicates_removed = self.remove_duplicate_rows(output_path)
            
            self.scraper_thread.scraping_complete.emit(output_path, duplicates_removed)

        except Exception as e:
            self.log_message(f"Scraping Error: {e}")
            self.scraper_thread.scraping_error.emit(str(e))
        finally:
            context.close()
            browser.close()

def main():
    app = QApplication(sys.argv)
    window = CartecScraperApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()


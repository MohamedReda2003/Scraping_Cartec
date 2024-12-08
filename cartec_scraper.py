import os
import json
import logging
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from playwright.sync_api import Playwright, sync_playwright
from parsel import Selector

class CartecScraperApp:
    def __init__(self, master):
        self.master = master
        master.title("Cartec Web Scraper")
        master.geometry("600x500")

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
        # Output File Path
        tk.Label(self.master, text="Output Excel File:").pack(pady=(10,0))
        self.output_path = tk.StringVar(value=self.state.get('output_path', 'cartec_data.xlsx'))
        output_frame = tk.Frame(self.master)
        output_frame.pack(fill='x', padx=20)
        
        tk.Entry(output_frame, textvariable=self.output_path, width=50).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0,10))
        tk.Button(output_frame, text="Browse", command=self.choose_output_file).pack(side=tk.RIGHT)

        # Progress Tracking
        tk.Label(self.master, text="Scraping Progress:").pack(pady=(10,0))
        self.progress_var = tk.StringVar(value="Not Started")
        tk.Label(self.master, textvariable=self.progress_var).pack()

        self.progress_bar = ttk.Progressbar(
            self.master, 
            orient='horizontal', 
            length=500, 
            mode='determinate'
        )
        self.progress_bar.pack(pady=10)

        # Control Buttons
        button_frame = tk.Frame(self.master)
        button_frame.pack(pady=10)
        
        self.start_button = tk.Button(
            button_frame, 
            text="Start/Continue Scraping", 
            command=self.start_scraping
        )
        self.start_button.pack(side=tk.LEFT, padx=10)
        
        tk.Button(
            button_frame, 
            text="Reset Progress", 
            command=self.reset_progress
        ).pack(side=tk.LEFT, padx=10)

        # Log Display
        tk.Label(self.master, text="Recent Logs:").pack()
        self.log_text = tk.Text(
            self.master, 
            height=10, 
            width=70, 
            state=tk.DISABLED
        )
        self.log_text.pack(pady=10)

    def choose_output_file(self):
        """Allow user to choose output Excel file."""
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")]
        )
        if filename:
            self.output_path.set(filename)

    def log_message(self, message):
        """Log message to both text widget and log file."""
        self.logger.info(message)
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.config(state=tk.DISABLED)
        self.log_text.see(tk.END)

    def load_state(self):
        """Load previous scraping state."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.log_message(f"Error loading state: {e}")
        return {}

    def save_state(self, state):
        """Save current scraping state."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.log_message(f"Error saving state: {e}")

    def reset_progress(self):
        """Reset scraping progress."""
        if messagebox.askyesno("Reset Progress", "Are you sure you want to reset all progress?"):
            # Remove state file
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
            
            # Reset UI elements
            self.progress_var.set("Not Started")
            self.progress_bar['value'] = 0
            
            # Clear log text
            self.log_text.config(state=tk.NORMAL)
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state=tk.DISABLED)

            # Reset state
            self.state = {}

    def start_scraping(self):
        """Start or continue scraping process."""
        # Disable start button during scraping
        self.start_button.config(state=tk.DISABLED)
        
        try:
            # Run scraping in playwright context
            with sync_playwright() as playwright:
                self.run_scraper(playwright)
        except Exception as e:
            messagebox.showerror("Scraping Error", str(e))
            self.log_message(f"Scraping Error: {e}")
        finally:
            # Re-enable start button
            self.start_button.config(state=tk.NORMAL)

    def run_scraper(self, playwright: Playwright) -> None:
        """Main scraping logic with state management."""
        # Prepare output file
        output_path = self.output_path.get()
        
        # Load existing data if file exists
        if os.path.exists(output_path):
            existing_df = pd.read_excel(output_path)
            self.log_message(f"Loaded existing data: {len(existing_df)} rows")
        else:
            existing_df = pd.DataFrame(columns=['MARQUE', 'MODELE', 'MOTORISATION'])

        # Initialize lists to collect data
        total_marques_names = existing_df['MARQUE'].tolist()
        total_modeles_names = existing_df['MODELE'].tolist()
        motorisation_true_names = existing_df['MOTORISATION'].tolist()
        
        # Track processed combinations to avoid duplicates
        processed_combinations = set(zip(total_marques_names, total_modeles_names, motorisation_true_names))

        # Browser and context setup
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        
        try:
            page = context.new_page()
            page.goto("https://www.cartec.ma/")
            page.wait_for_load_state("domcontentloaded")
            
            page_source = page.locator("html").inner_html()
            selector = Selector(page_source)
            
            # Get all marques (manufacturers)
            marques = [marqua.attrib['value'] for marqua in selector.css("#manufacturer-select > option")]
            marques_names = selector.css("#manufacturer-select > option ::text").getall()
            
            # Clean marque names
            marques_true_names = []
            for marque in marques_names[1:]:
                marques_true_names.append(
                    str(marque).replace("\n","").replace("            ","").replace("    ","")
                )

            # Iterate through marques
            for marque_index, marque in enumerate(marques[1:], 1):
                # Skip already processed marques if resuming
                if self.state.get('last_marque_index', 0) >= marque_index:
                    continue

                self.log_message(f"Processing Marque: {marques_true_names[marque_index-1]}")
                page.locator("#manufacturer-select").select_option(str(marque))
                page.wait_for_timeout(200)
                
                page_source = page.locator("html").inner_html()
                selector = Selector(page_source)
                
                # Get models for this marque
                modeles = [modele.attrib['value'] for modele in selector.css("#model-select > option")]
                modeles_names = selector.css("#model-select > option ::text").getall()[1:]
                
                # Get last processed model for this marque if resuming
                last_processed_modele_index = self.state.get(f'last_modele_index_{marque}', 0)
                
                # Iterate through models
                for modele_index, modele in enumerate(modeles[1:], 1):
                    # Skip already processed models for this marque
                    if last_processed_modele_index >= modele_index:
                        continue

                    try:
                        modele_name = str(modeles_names[modele_index-1]).replace("\n","").replace("            ","").replace("    ","")
                        
                        page.locator("#model-select").select_option(str(modele))
                        page.wait_for_timeout(200)
                        
                        page_source = page.locator("html").inner_html()
                        selector = Selector(page_source)
                        
                        # Get motorisations
                        motorisation_names = selector.css("#vehicle-select  option ::text").getall()[1:]
                        
                        # Track motorisation additions for this model
                        model_additions = 0
                        
                        # Collect data for this model's motorisations
                        for motorisation_index, motorisation in enumerate(motorisation_names[1:], 1):
                            current_marque = marques_true_names[marque_index-1]
                            clean_motorisation = str(motorisation).replace("\n","").replace("            ","").replace("    ","")
                            
                            # Check if this combination already exists
                            if (current_marque, modele_name, clean_motorisation) not in processed_combinations:
                                total_marques_names.append(current_marque)
                                total_modeles_names.append(modele_name)
                                motorisation_true_names.append(clean_motorisation)
                                
                                # Add to processed combinations
                                processed_combinations.add((current_marque, modele_name, clean_motorisation))
                                model_additions += 1
                        
                        # Log model-specific information
                        self.log_message(f"Model {modele_name}: Added {model_additions} new entries")
                        
                        # Create temporary DataFrame to save progress incrementally
                        temp_df = pd.DataFrame({
                            'MARQUE': total_marques_names,
                            'MODELE': total_modeles_names,
                            'MOTORISATION': motorisation_true_names
                        })
                        temp_df.to_excel(output_path, index=False)
                        
                        # Update progress
                        progress_percentage = (marque_index / len(marques[1:])) * 100
                        self.progress_bar['value'] = progress_percentage
                        self.progress_var.set(
                            f"Processing {marques_true_names[marque_index-1]} - {modele_name}"
                        )
                        self.master.update_idletasks()

                        # Update state after successful model processing
                        self.state[f'last_modele_index_{marque}'] = modele_index
                        self.save_state(self.state)

                    except Exception as model_error:
                        self.log_message(f"Error processing model {modele_name}: {model_error}")
                        continue

                # Save state after each marque
                self.state['last_marque_index'] = marque_index
                self.save_state(self.state)
                
                # Log column lengths
                self.log_message(f"Current data lengths - Marques: {len(total_marques_names)}, Modeles: {len(total_modeles_names)}, Motorisations: {len(motorisation_true_names)}")

            # Final DataFrame and save
            df = pd.DataFrame({
                'MARQUE': total_marques_names,
                'MODELE': total_modeles_names,
                'MOTORISATION': motorisation_true_names
            })
            
            df.to_excel(output_path, index=False)
            
            messagebox.showinfo("Scraping Complete", f"Data saved to {output_path}")
            self.progress_var.set("Scraping Complete")
            self.progress_bar['value'] = 100

        except Exception as e:
            self.log_message(f"Scraping Error: {e}")
            messagebox.showerror("Scraping Error", str(e))
        finally:
            context.close()
            browser.close()

def main():
    root = tk.Tk()
    app = CartecScraperApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
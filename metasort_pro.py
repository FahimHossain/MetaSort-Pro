import os
import re
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime
from PIL import Image, ExifTags

# Set default CustomTkinter appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PhotoOrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Main window setup
        self.title("EXIF Photo Organizer")
        self.geometry("600x650") # Made slightly taller for new options
        self.resizable(False, False)

        # Variables
        self.folder_path = ctk.StringVar()
        self.backup_var = ctk.BooleanVar(value=True)
        self.full_year_var = ctk.BooleanVar(value=False)
        self.maker_var = ctk.BooleanVar(value=False)
        self.model_var = ctk.BooleanVar(value=False)
        
        self.supported_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')
        self.is_dark_mode = True

        self.setup_ui()

    def setup_ui(self):
        # Top Bar: Theme Toggle
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=(15, 5))
        
        self.title_label = ctk.CTkLabel(self.top_bar, text="Photo Organizer", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(side="left")

        self.theme_btn = ctk.CTkButton(
            self.top_bar, 
            text="☀️ Light Mode", 
            width=120, 
            command=self.toggle_theme,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90")
        )
        self.theme_btn.pack(side="right")

        # Frame 1: Select Target Folder
        self.folder_frame = ctk.CTkFrame(self)
        self.folder_frame.pack(fill="x", padx=20, pady=10)
        
        self.folder_label = ctk.CTkLabel(self.folder_frame, text="Step 1: Select Target Folder", font=ctk.CTkFont(weight="bold"))
        self.folder_label.pack(anchor="w", padx=15, pady=(10, 0))

        self.path_container = ctk.CTkFrame(self.folder_frame, fg_color="transparent")
        self.path_container.pack(fill="x", padx=15, pady=10)

        self.path_entry = ctk.CTkEntry(self.path_container, textvariable=self.folder_path, state='readonly', width=350)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browse_btn = ctk.CTkButton(self.path_container, text="Browse...", width=100, command=self.browse_folder)
        self.browse_btn.pack(side="left")

        # Frame 2: Options
        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.pack(fill="x", padx=20, pady=5)

        self.options_label = ctk.CTkLabel(self.options_frame, text="Step 2: Options", font=ctk.CTkFont(weight="bold"))
        self.options_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.backup_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Copy existing photos to '.backup' folder before renaming", 
            variable=self.backup_var
        )
        self.backup_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.full_year_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Use Full Year (YYYY instead of YY)", 
            variable=self.full_year_var
        )
        self.full_year_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.maker_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Append Camera Maker (e.g., _Google)", 
            variable=self.maker_var
        )
        self.maker_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.model_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Append Camera Model (e.g., _Pixel 10 Pro)", 
            variable=self.model_var
        )
        self.model_check.pack(anchor="w", padx=15, pady=(0, 15))

        # Action Button
        self.run_btn = ctk.CTkButton(
            self, 
            text="Organize Photos", 
            height=40, 
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_processing, 
            state="disabled"
        )
        self.run_btn.pack(fill="x", padx=20, pady=15)

        # Log Console
        self.log_label = ctk.CTkLabel(self, text="Activity Log", font=ctk.CTkFont(weight="bold"))
        self.log_label.pack(anchor="w", padx=20, pady=(0, 5))

        self.log_text = ctk.CTkTextbox(self, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def toggle_theme(self):
        if self.is_dark_mode:
            ctk.set_appearance_mode("Light")
            self.theme_btn.configure(text="🌙 Dark Mode")
            self.is_dark_mode = False
        else:
            ctk.set_appearance_mode("Dark")
            self.theme_btn.configure(text="☀️ Light Mode")
            self.is_dark_mode = True

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self.folder_path.set(folder)
            self.run_btn.configure(state="normal")
            self.log_message(f"Selected folder: {folder}")

    def log_message(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clean_filename_string(self, text):
        """Removes null bytes and illegal Windows filename characters."""
        if not text:
            return ""
        # Remove null bytes often left by camera firmware
        text = str(text).replace('\x00', '').strip()
        # Remove illegal Windows characters: < > : " / \ | ? *
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        return text

    def get_exif_data(self, file_path):
        """Extracts Date Taken, Make, and Model from EXIF data."""
        data = {'date': None, 'make': None, 'model': None}
        try:
            image = Image.open(file_path)
            exif = image._getexif()
            if not exif:
                return data
            
            for tag, value in exif.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                if decoded == "DateTimeOriginal":
                    data['date'] = value
                elif decoded == "Make":
                    data['make'] = self.clean_filename_string(value)
                elif decoded == "Model":
                    data['model'] = self.clean_filename_string(value)
        except Exception:
            pass
        return data

    def generate_new_name(self, exif_data, original_extension, use_full_year, use_maker, use_model):
        """Formats the new filename based on selected options."""
        date_string = exif_data.get('date')
        if not date_string:
            return None
            
        try:
            date_obj = datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")
            
            # Determine Date Format
            if use_full_year:
                base_name = date_obj.strftime("%Y%m%d %H%M %S")
            else:
                base_name = date_obj.strftime("%y%m%d %H%M %S")
            
            # Build the suffix
            suffix = ""
            make = exif_data.get('make')
            model = exif_data.get('model')

            if use_maker and make:
                # Remove spaces from the maker name (e.g., "Google" instead of "Google ")
                suffix += f"_{make.replace(' ', '')}"
                
            if use_model and model:
                suffix += f"_{model}"

            return f"{base_name}{suffix}{original_extension.lower()}"
        except ValueError:
            return None

    def start_processing(self):
        folder = self.folder_path.get()
        if not folder:
            return
            
        # Capture settings from UI before passing to the background thread
        settings = {
            'folder': folder,
            'backup': self.backup_var.get(),
            'full_year': self.full_year_var.get(),
            'maker': self.maker_var.get(),
            'model': self.model_var.get()
        }
            
        # Disable UI
        self.browse_btn.configure(state="disabled")
        self.run_btn.configure(state="disabled")
        self.backup_check.configure(state="disabled")
        self.full_year_check.configure(state="disabled")
        self.maker_check.configure(state="disabled")
        self.model_check.configure(state="disabled")
        self.theme_btn.configure(state="disabled")
        
        self.log_message("\n--- Starting Process ---")
        threading.Thread(target=self.process_photos, args=(settings,), daemon=True).start()

    def process_photos(self, settings):
        folder_path = settings['folder']
        do_backup = settings['backup']
        processed_count = 0
        skipped_count = 0
        ignored_count = 0
        
        if do_backup:
            backup_dir = os.path.join(folder_path, ".backup")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                self.log_message("Created .backup folder.")
            
            self.log_message("Copying image files to backup folder... (This may take a moment)")
            
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                
                if os.path.isdir(file_path): 
                    continue
                if not filename.lower().endswith(self.supported_extensions):
                    continue
                
                try:
                    shutil.copy2(file_path, os.path.join(backup_dir, filename))
                except Exception as e:
                    self.log_message(f"Error backing up {filename}: {e}")
            
            self.log_message("Backup complete.")

        self.log_message("Scanning for EXIF data and renaming...")
        
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            
            if os.path.isdir(file_path):
                continue
            if not filename.lower().endswith(self.supported_extensions):
                ignored_count += 1
                continue
                
            _, ext = os.path.splitext(filename)
            
            # Extract Data
            exif_data = self.get_exif_data(file_path)
            
            if exif_data.get('date'):
                new_filename = self.generate_new_name(
                    exif_data, ext, 
                    settings['full_year'], settings['maker'], settings['model']
                )
                
                if new_filename:
                    new_file_path = os.path.join(folder_path, new_filename)
                    
                    # Handle duplicate names
                    counter = 1
                    while os.path.exists(new_file_path):
                        if new_file_path.lower() == file_path.lower():
                            break 
                        
                        name_without_ext = os.path.splitext(new_filename)[0]
                        new_file_path = os.path.join(folder_path, f"{name_without_ext}_{counter}{ext.lower()}")
                        counter += 1
                    
                    if new_file_path.lower() != file_path.lower():
                        try:
                            os.rename(file_path, new_file_path)
                            self.log_message(f"Renamed: {filename} -> {os.path.basename(new_file_path)}")
                            processed_count += 1
                        except Exception as e:
                            self.log_message(f"Error renaming {filename}: {e}")
                            skipped_count += 1
            else:
                self.log_message(f"Skipped: {filename} (No EXIF date data)")
                skipped_count += 1

        self.log_message(f"\n--- Done! ---")
        self.log_message(f"Successfully renamed: {processed_count}")
        self.log_message(f"Skipped (no EXIF): {skipped_count}")
        if ignored_count > 0:
            self.log_message(f"Ignored (non-image files): {ignored_count}")

        # Re-enable UI from the main thread
        self.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        self.browse_btn.configure(state="normal")
        self.run_btn.configure(state="normal")
        self.backup_check.configure(state="normal")
        self.full_year_check.configure(state="normal")
        self.maker_check.configure(state="normal")
        self.model_check.configure(state="normal")
        self.theme_btn.configure(state="normal")
        messagebox.showinfo("Complete", "Photo organization is finished!\nCheck the log for details.")

if __name__ == "__main__":
    app = PhotoOrganizerApp()
    app.mainloop()
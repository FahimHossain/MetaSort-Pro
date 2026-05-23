import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime
from PIL import Image, ExifTags

# Set default CustomTkinter appearance
ctk.set_appearance_mode("Dark")  # Modes: "System" (standard), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (standard), "green", "dark-blue"

class PhotoOrganizerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Main window setup
        self.title("EXIF Photo Organizer")
        self.geometry("600x550")
        self.resizable(False, False)

        # Variables
        self.folder_path = ctk.StringVar()
        self.backup_var = ctk.BooleanVar(value=True)
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
        self.backup_check.pack(anchor="w", padx=15, pady=(0, 15))

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
        """Toggles between Light and Dark mode using CTk built-ins."""
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
        """Helper to print messages to the GUI log safely."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def get_date_taken(self, file_path):
        try:
            image = Image.open(file_path)
            exif = image._getexif()
            if not exif:
                return None
            
            for tag, value in exif.items():
                decoded = ExifTags.TAGS.get(tag, tag)
                if decoded == "DateTimeOriginal":
                    return value
        except Exception:
            return None
        return None

    def generate_new_name(self, date_string, original_extension):
        try:
            date_obj = datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")
            new_name = date_obj.strftime("%y%m%d %H%M %S")
            return f"{new_name}{original_extension.lower()}"
        except ValueError:
            return None

    def start_processing(self):
        folder = self.folder_path.get()
        if not folder:
            return
            
        # Disable UI during processing
        self.browse_btn.configure(state="disabled")
        self.run_btn.configure(state="disabled")
        self.backup_check.configure(state="disabled")
        self.theme_btn.configure(state="disabled")
        
        self.log_message("\n--- Starting Process ---")
        
        # Run heavy work on background thread
        threading.Thread(target=self.process_photos, args=(folder,), daemon=True).start()

    def process_photos(self, folder_path):
        do_backup = self.backup_var.get()
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
            date_taken = self.get_date_taken(file_path)
            
            if date_taken:
                new_filename = self.generate_new_name(date_taken, ext)
                
                if new_filename:
                    new_file_path = os.path.join(folder_path, new_filename)
                    
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
                self.log_message(f"Skipped: {filename} (No EXIF data)")
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
        self.theme_btn.configure(state="normal")
        messagebox.showinfo("Complete", "Photo organization is finished!\nCheck the log for details.")

if __name__ == "__main__":
    app = PhotoOrganizerApp()
    app.mainloop()
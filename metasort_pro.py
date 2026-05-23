import os
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
from PIL import Image, ExifTags

class PhotoOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EXIF Photo Organizer")
        self.root.geometry("550x450")
        self.root.resizable(False, False)
        
        self.folder_path = tk.StringVar()
        self.backup_var = tk.BooleanVar(value=True) # Default to true for safety
        
        # Define which file types the program should touch
        self.supported_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')
        
        self.setup_ui()

    def setup_ui(self):
        # Frame for folder selection
        folder_frame = ttk.LabelFrame(self.root, text="Step 1: Select Target Folder", padding=(10, 10))
        folder_frame.pack(fill="x", padx=15, pady=10)

        self.path_entry = ttk.Entry(folder_frame, textvariable=self.folder_path, state='readonly', width=50)
        self.path_entry.pack(side="left", padx=(0, 10))

        self.browse_btn = ttk.Button(folder_frame, text="Browse...", command=self.browse_folder)
        self.browse_btn.pack(side="left")

        # Frame for options
        options_frame = ttk.LabelFrame(self.root, text="Step 2: Options", padding=(10, 10))
        options_frame.pack(fill="x", padx=15, pady=5)

        self.backup_check = ttk.Checkbutton(
            options_frame, 
            text="Copy existing photos to '.backup' folder before renaming", 
            variable=self.backup_var
        )
        self.backup_check.pack(anchor="w")

        # Frame for execution
        action_frame = ttk.Frame(self.root, padding=(0, 10))
        action_frame.pack(fill="x", padx=15)

        self.run_btn = ttk.Button(action_frame, text="Organize Photos", command=self.start_processing, state="disabled")
        self.run_btn.pack(fill="x", ipady=5)

        # Frame for logs
        log_frame = ttk.LabelFrame(self.root, text="Log", padding=(10, 10))
        log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_text = ScrolledText(log_frame, wrap=tk.WORD, height=10, state="disabled")
        self.log_text.pack(fill="both", expand=True)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self.folder_path.set(folder)
            self.run_btn.config(state="normal")
            self.log_message(f"Selected folder: {folder}")

    def log_message(self, message):
        """Helper to print messages to the GUI log safely."""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def get_date_taken(self, file_path):
        """Extracts the 'Date Taken' (DateTimeOriginal) from EXIF data."""
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
        """Formats the EXIF date string to YYMMDD HHMM SS."""
        try:
            date_obj = datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")
            new_name = date_obj.strftime("%y%m%d %H%M %S")
            return f"{new_name}{original_extension.lower()}"
        except ValueError:
            return None

    def start_processing(self):
        """Disables buttons and starts the worker thread to keep GUI responsive."""
        folder = self.folder_path.get()
        if not folder:
            return
            
        self.browse_btn.config(state="disabled")
        self.run_btn.config(state="disabled")
        self.backup_check.config(state="disabled")
        
        self.log_message("\n--- Starting Process ---")
        
        # Run the heavy work on a background thread
        threading.Thread(target=self.process_photos, args=(folder,), daemon=True).start()

    def process_photos(self, folder_path):
        do_backup = self.backup_var.get()
        processed_count = 0
        skipped_count = 0
        ignored_count = 0
        
        # 1. Handle Backup if requested
        if do_backup:
            backup_dir = os.path.join(folder_path, ".backup")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
                self.log_message("Created .backup folder.")
            
            self.log_message("Copying image files to backup folder... (This may take a moment)")
            
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                
                # Skip folders and non-image files
                if os.path.isdir(file_path): 
                    continue
                if not filename.lower().endswith(self.supported_extensions):
                    continue
                
                try:
                    shutil.copy2(file_path, os.path.join(backup_dir, filename))
                except Exception as e:
                    self.log_message(f"Error backing up {filename}: {e}")
            
            self.log_message("Backup complete.")

        # 2. Process and Rename Files
        self.log_message("Scanning for EXIF data and renaming...")
        
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            
            # Skip directories
            if os.path.isdir(file_path):
                continue
            
            # Skip non-image files
            if not filename.lower().endswith(self.supported_extensions):
                ignored_count += 1
                continue
                
            _, ext = os.path.splitext(filename)
            date_taken = self.get_date_taken(file_path)
            
            if date_taken:
                new_filename = self.generate_new_name(date_taken, ext)
                
                if new_filename:
                    new_file_path = os.path.join(folder_path, new_filename)
                    
                    # Handle duplicate names
                    counter = 1
                    while os.path.exists(new_file_path):
                        if new_file_path.lower() == file_path.lower():
                            break # File already named correctly
                        
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
        self.root.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        """Re-enables the buttons after processing finishes."""
        self.browse_btn.config(state="normal")
        self.run_btn.config(state="normal")
        self.backup_check.config(state="normal")
        messagebox.showinfo("Complete", "Photo organization is finished!\nCheck the log for details.")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoOrganizerApp(root)
    root.mainloop()
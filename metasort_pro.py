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
        self.root.geometry("550x490") # Slightly taller to fit the top bar
        self.root.resizable(False, False)
        
        self.folder_path = tk.StringVar()
        self.backup_var = tk.BooleanVar(value=True)
        self.supported_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')
        
        # Setup styling engine
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam' allows us to freely change background colors
        self.is_dark_mode = True
        
        self.setup_ui()
        self.apply_theme() # Apply the default dark theme on startup

    def setup_ui(self):
        # Top Bar for Theme Toggle
        top_bar = tk.Frame(self.root, bg=self.root['bg'])
        top_bar.pack(fill="x", padx=15, pady=(10, 0))
        
        self.theme_btn = ttk.Button(top_bar, text="☀️ Light Mode", command=self.toggle_theme, width=15)
        self.theme_btn.pack(side="right")

        # Frame for folder selection
        self.folder_frame = ttk.LabelFrame(self.root, text="Step 1: Select Target Folder", padding=(10, 10))
        self.folder_frame.pack(fill="x", padx=15, pady=10)

        self.path_entry = ttk.Entry(self.folder_frame, textvariable=self.folder_path, state='readonly', width=50)
        self.path_entry.pack(side="left", padx=(0, 10))

        self.browse_btn = ttk.Button(self.folder_frame, text="Browse...", command=self.browse_folder)
        self.browse_btn.pack(side="left")

        # Frame for options
        self.options_frame = ttk.LabelFrame(self.root, text="Step 2: Options", padding=(10, 10))
        self.options_frame.pack(fill="x", padx=15, pady=5)

        self.backup_check = ttk.Checkbutton(
            self.options_frame, 
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
        self.log_frame = ttk.LabelFrame(self.root, text="Log", padding=(10, 10))
        self.log_frame.pack(fill="both", expand=True, padx=15, pady=10)

        self.log_text = ScrolledText(self.log_frame, wrap=tk.WORD, height=10, state="disabled", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)

    def toggle_theme(self):
        """Flips the boolean and applies the new theme."""
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        """Applies color pallets based on the current mode."""
        if self.is_dark_mode:
            bg_main = "#2b2b2b"
            bg_frame = "#3c3f41"
            fg_text = "#ffffff"
            bg_input = "#1e1e1e"
            btn_bg = "#555555"
            btn_hover = "#777777"
            self.theme_btn.config(text="☀️ Light Mode")
        else:
            bg_main = "#f0f0f0"
            bg_frame = "#ffffff"
            fg_text = "#000000"
            bg_input = "#ffffff"
            btn_bg = "#e0e0e0"
            btn_hover = "#d0d0d0"
            self.theme_btn.config(text="🌙 Dark Mode")

        # Apply to main window
        self.root.configure(bg=bg_main)
        
        # Apply to ttk widgets
        self.style.configure(".", background=bg_main, foreground=fg_text)
        self.style.configure("TLabelframe", background=bg_main, bordercolor=btn_bg)
        self.style.configure("TLabelframe.Label", background=bg_main, foreground=fg_text)
        self.style.configure("TCheckbutton", background=bg_frame, foreground=fg_text)
        self.style.configure("TEntry", fieldbackground=bg_input, foreground=fg_text)
        
        # Button styling
        self.style.configure("TButton", background=btn_bg, foreground=fg_text, bordercolor=bg_main)
        self.style.map("TButton", background=[('active', btn_hover)])
        
        # ScrolledText (Standard tk widget, needs direct config)
        self.log_text.config(bg=bg_input, fg=fg_text, insertbackground=fg_text)
        
        # Update specific frame backgrounds
        self.folder_frame.configure(style="TLabelframe")
        self.options_frame.configure(style="TLabelframe")
        self.log_frame.configure(style="TLabelframe")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Images")
        if folder:
            self.folder_path.set(folder)
            self.run_btn.config(state="normal")
            self.log_message(f"Selected folder: {folder}")

    def log_message(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

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
            
        self.browse_btn.config(state="disabled")
        self.run_btn.config(state="disabled")
        self.backup_check.config(state="disabled")
        self.theme_btn.config(state="disabled") # Disable theme switching during process
        
        self.log_message("\n--- Starting Process ---")
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

        self.root.after(0, self.reset_ui_state)

    def reset_ui_state(self):
        self.browse_btn.config(state="normal")
        self.run_btn.config(state="normal")
        self.backup_check.config(state="normal")
        self.theme_btn.config(state="normal")
        messagebox.showinfo("Complete", "Photo organization is finished!\nCheck the log for details.")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoOrganizerApp(root)
    root.mainloop()
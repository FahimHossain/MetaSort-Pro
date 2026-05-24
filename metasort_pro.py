import os
import re
import json
import threading
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime
from PIL import Image, ImageTk, ExifTags

# Set default CustomTkinter appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MetaSortProApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Main window setup
        self.title("MetaSort Pro v2.0")
        
        # --- ICON FIX ---
        # 1. Tell Windows this is a unique app (forces Taskbar icon to update)
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('fahim.metasort.pro.2.0')
        except Exception:
            pass
            
        # 2. Find the icon exactly where the script lives
        icon_path = os.path.join(os.path.dirname(__file__), "MetaSort Pro.ico")
        
        # 3. Apply the CustomTkinter Workaround
        if os.path.exists(icon_path):
            try:
                self.app_icon = ImageTk.PhotoImage(Image.open(icon_path))
                self.wm_iconbitmap() # Clear CTk's default internal icon buffer
                self.after(200, lambda: self.iconphoto(False, self.app_icon)) # Apply after CTk draws the dark title bar
            except Exception as e:
                print(f"Warning: Failed to load icon: {e}")
        else:
            print(f"Warning: Icon not found at {icon_path}")
        # ----------------

        self.geometry("680x820") 
        self.minsize(600, 750)   
        self.resizable(True, True) 

        # Variables
        self.folder_path = ctk.StringVar()
        self.enable_undo_var = ctk.BooleanVar(value=True)
        self.full_year_var = ctk.BooleanVar(value=False)
        self.maker_var = ctk.BooleanVar(value=False)
        self.model_var = ctk.BooleanVar(value=False)
        self.preserve_modes_var = ctk.BooleanVar(value=False)
        
        # Added video formats
        self.image_extensions = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.dng')
        self.video_extensions = ('.mp4', '.mov', '.avi', '.mkv')
        self.supported_extensions = self.image_extensions + self.video_extensions
        
        self.is_dark_mode = True

        self.setup_ui()

    def setup_ui(self):
        # Top Bar: Theme Toggle
        self.top_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.top_bar.pack(fill="x", padx=20, pady=(15, 5))
        
        self.title_label = ctk.CTkLabel(self.top_bar, text="MetaSort Pro", font=ctk.CTkFont(size=22, weight="bold"))
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

        self.path_entry = ctk.CTkEntry(self.path_container, textvariable=self.folder_path, state='readonly')
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browse_btn = ctk.CTkButton(self.path_container, text="Browse...", width=100, command=self.browse_folder)
        self.browse_btn.pack(side="right")

        # Frame 2: Options
        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.pack(fill="x", padx=20, pady=5)

        self.options_label = ctk.CTkLabel(self.options_frame, text="Step 2: Options", font=ctk.CTkFont(weight="bold"))
        self.options_label.pack(anchor="w", padx=15, pady=(10, 5))

        # Updated Checkbox for Undo Log
        self.undo_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Enable Undo Log (Creates .metasort_undo.json to track changes)", 
            variable=self.enable_undo_var
        )
        self.undo_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.full_year_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Use Full Year (YYYY instead of YY)", 
            variable=self.full_year_var
        )
        self.full_year_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.maker_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Append Camera Maker (e.g., _Google) [Images Only]", 
            variable=self.maker_var
        )
        self.maker_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.model_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Append Camera Model (e.g., _Pixel 10 Pro) [Images Only]", 
            variable=self.model_var
        )
        self.model_check.pack(anchor="w", padx=15, pady=(0, 10))

        self.preserve_modes_check = ctk.CTkCheckBox(
            self.options_frame, 
            text="Preserve Camera Modes (e.g., .MP, .NIGHT, .PORTRAIT)", 
            variable=self.preserve_modes_var
        )
        self.preserve_modes_check.pack(anchor="w", padx=15, pady=(0, 15))

        # Frame 3: Action Buttons (Side by Side)
        self.action_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.action_frame.pack(fill="x", padx=20, pady=10)

        self.preview_btn = ctk.CTkButton(
            self.action_frame, 
            text="Preview Changes", 
            height=40,
            fg_color="#4B5563", hover_color="#374151",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_preview, 
            state="disabled"
        )
        self.preview_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.run_btn = ctk.CTkButton(
            self.action_frame, 
            text="Apply Changes", 
            height=40, 
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_processing, 
            state="disabled"
        )
        self.run_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Frame 4: Undo Controls
        self.undo_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.undo_frame.pack(fill="x", padx=20, pady=(0, 10))

        self.undo_last_btn = ctk.CTkButton(
            self.undo_frame,
            text="↩ Undo Last Session",
            height=30,
            fg_color="#991B1B", hover_color="#7F1D1D",
            command=self.undo_last_session,
            state="disabled"
        )
        self.undo_last_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.undo_history_btn = ctk.CTkButton(
            self.undo_frame,
            text="📋 Undo History...",
            height=30,
            fg_color="#854D0E", hover_color="#713F12",
            command=self.open_undo_history,
            state="disabled"
        )
        self.undo_history_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Log Console
        self.log_label = ctk.CTkLabel(self, text="Activity Log", font=ctk.CTkFont(weight="bold"))
        self.log_label.pack(anchor="w", padx=20, pady=(0, 5))

        self.log_text = ctk.CTkTextbox(self, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Footer
        self.footer_label = ctk.CTkLabel(
            self, 
            text="Developed by Fahim Hossain", 
            font=ctk.CTkFont(size=11), 
            text_color=("gray60", "gray40")
        )
        self.footer_label.pack(side="bottom", pady=(0, 10))

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
        folder = filedialog.askdirectory(title="Select Folder with Media")
        if folder:
            self.folder_path.set(folder)
            self.preview_btn.configure(state="normal")
            self.run_btn.configure(state="normal")
            self.undo_last_btn.configure(state="normal")
            self.undo_history_btn.configure(state="normal")
            self.log_message(f"Selected folder: {folder}")

    def log_message(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clean_filename_string(self, text):
        if not text:
            return ""
        text = str(text).replace('\x00', '').strip()
        text = re.sub(r'[<>:"/\\|?*]', '', text)
        return text

    def get_media_data(self, file_path):
        """Extracts date/metadata. Uses EXIF for images, OS creation time for videos."""
        data = {'date': None, 'make': None, 'model': None}
        ext = os.path.splitext(file_path)[1].lower()

        if ext in self.image_extensions:
            try:
                image = Image.open(file_path)
                exif = image._getexif()
                if exif:
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
        
        elif ext in self.video_extensions:
            # Fallback to OS creation/modification time for video files
            try:
                stat = os.stat(file_path)
                # Use the older of creation time (ctime on Windows) or modification time
                timestamp = min(stat.st_ctime, stat.st_mtime)
                dt = datetime.fromtimestamp(timestamp)
                data['date'] = dt.strftime("%Y:%m:%d %H:%M:%S")
            except Exception:
                pass
                
        return data

    def extract_mode_identifier(self, filename):
        base_name, _ = os.path.splitext(filename)
        match = re.search(r'[\._](MP|PORTRAIT|PHOTOSPHERE|NIGHT|PANO|VR|BURST|COVER|MOTION)(~[0-9]+)?$', base_name, re.IGNORECASE)
        if match:
            return match.group(0) 
        return ""

    def generate_new_name(self, media_data, original_extension, use_full_year, use_maker, use_model, mode_identifier=""):
        date_string = media_data.get('date')
        if not date_string:
            return None
            
        try:
            date_obj = datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")
            
            if use_full_year:
                base_name = date_obj.strftime("%Y%m%d %H%M %S")
            else:
                base_name = date_obj.strftime("%y%m%d %H%M %S")
            
            suffix = ""
            make = media_data.get('make')
            model = media_data.get('model')

            if use_maker and make:
                suffix += f"_{make.replace(' ', '')}"
                
            if use_model and model:
                suffix += f"_{model}"

            return f"{base_name}{suffix}{mode_identifier}{original_extension.lower()}"
        except ValueError:
            return None

    def save_undo_log(self, folder_path, session_changes):
        """Appends the renaming session to the JSON log file."""
        if not session_changes:
            return
            
        log_path = os.path.join(folder_path, ".metasort_undo.json")
        data = []
        
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                self.log_message(f"Warning: Could not read existing undo log: {e}")
                
        session = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "changes": session_changes
        }
        
        data.append(session)
        
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log_message(f"Error saving undo log: {e}")

    def execute_undo(self, session_index=-1):
        """Executes the undo logic on a specific session index."""
        folder = self.folder_path.get()
        log_path = os.path.join(folder, ".metasort_undo.json")
        
        if not os.path.exists(log_path):
            self.log_message("No undo log found (.metasort_undo.json).")
            return
            
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self.log_message(f"Error reading undo log: {e}")
            return
            
        if not data:
            self.log_message("Undo log is empty.")
            return
            
        try:
            target_session = data.pop(session_index)
        except IndexError:
            self.log_message("Invalid session index for undo.")
            return

        self.log_message(f"\n--- Undoing Session: {target_session['timestamp']} ---")
        
        success_count = 0
        fail_count = 0
        
        # Loop backwards through changes in case of chains
        for change in reversed(target_session["changes"]):
            old_name = change["old"]
            new_name = change["new"]
            
            old_path = os.path.join(folder, old_name)
            new_path = os.path.join(folder, new_name)
            
            if os.path.exists(new_path):
                try:
                    os.rename(new_path, old_path)
                    self.log_message(f"Reverted: {new_name} -> {old_name}")
                    success_count += 1
                except Exception as e:
                    self.log_message(f"Error reverting {new_name}: {e}")
                    fail_count += 1
            else:
                self.log_message(f"File missing, cannot revert: {new_name}")
                fail_count += 1
                
        # Save the log back without the undone session
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            self.log_message(f"Error updating log after undo: {e}")

        self.log_message(f">>> Undo Complete: {success_count} reverted, {fail_count} failed. <<<")

    def undo_last_session(self):
        """Triggered by the Undo Last Session button."""
        folder = self.folder_path.get()
        if not folder:
            return
        if messagebox.askyesno("Confirm Undo", "Are you sure you want to revert the most recent renaming session?"):
            threading.Thread(target=self.execute_undo, args=(-1,), daemon=True).start()

    def open_undo_history(self):
        """Opens a Toplevel window to view and select previous sessions to undo."""
        folder = self.folder_path.get()
        if not folder:
            return
            
        log_path = os.path.join(folder, ".metasort_undo.json")
        if not os.path.exists(log_path):
            messagebox.showinfo("Undo History", "No undo log found in this directory.")
            return
            
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read log: {e}")
            return
            
        if not data:
            messagebox.showinfo("Undo History", "Undo log is empty.")
            return

        history_win = ctk.CTkToplevel(self)
        history_win.title("Undo History")
        history_win.geometry("400x500")
        history_win.transient(self) # Keep on top of main window
        
        ctk.CTkLabel(history_win, text="Select a Session to Revert", font=ctk.CTkFont(weight="bold", size=16)).pack(pady=15)
        
        scroll_frame = ctk.CTkScrollableFrame(history_win)
        scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        def trigger_specific_undo(index, window):
            if messagebox.askyesno("Confirm Undo", "Are you sure you want to revert this specific session?"):
                window.destroy()
                threading.Thread(target=self.execute_undo, args=(index,), daemon=True).start()

        # Build list backwards so newest is at the top
        for idx, session in reversed(list(enumerate(data))):
            frame = ctk.CTkFrame(scroll_frame)
            frame.pack(fill="x", pady=5)
            
            time_str = session.get("timestamp", "Unknown Time")
            file_count = len(session.get("changes", []))
            
            info_label = ctk.CTkLabel(frame, text=f"{time_str}\n{file_count} files altered", justify="left")
            info_label.pack(side="left", padx=10, pady=10)
            
            btn = ctk.CTkButton(
                frame, 
                text="Revert", 
                width=80, 
                fg_color="#991B1B", hover_color="#7F1D1D",
                command=lambda i=idx, w=history_win: trigger_specific_undo(i, w)
            )
            btn.pack(side="right", padx=10)

    def start_preview(self):
        self._start_thread(dry_run=True)

    def start_processing(self):
        self._start_thread(dry_run=False)

    def _start_thread(self, dry_run):
        folder = self.folder_path.get()
        if not folder:
            return
            
        settings = {
            'folder': folder,
            'enable_undo': self.enable_undo_var.get(),
            'full_year': self.full_year_var.get(),
            'maker': self.maker_var.get(),
            'model': self.model_var.get(),
            'preserve_modes': self.preserve_modes_var.get(),
            'dry_run': dry_run
        }
            
        self.browse_btn.configure(state="disabled")
        self.preview_btn.configure(state="disabled")
        self.run_btn.configure(state="disabled")
        self.undo_check.configure(state="disabled")
        self.full_year_check.configure(state="disabled")
        self.maker_check.configure(state="disabled")
        self.model_check.configure(state="disabled")
        self.preserve_modes_check.configure(state="disabled")
        self.theme_btn.configure(state="disabled")
        self.undo_last_btn.configure(state="disabled")
        self.undo_history_btn.configure(state="disabled")
        
        mode_text = "PREVIEW MODE" if dry_run else "LIVE PROCESS"
        self.log_message(f"\n--- Starting Process ({mode_text}) ---")
        
        threading.Thread(target=self.process_media, args=(settings,), daemon=True).start()

    def process_media(self, settings):
        folder_path = settings['folder']
        dry_run = settings['dry_run']
        
        processed_count = 0
        skipped_count = 0
        ignored_count = 0
        
        projected_names = set() 
        session_changes = [] # Stores dicts: {"old": "original.jpg", "new": "renamed.jpg"}
        
        self.log_message("Scanning for metadata...")
        
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)
            
            if os.path.isdir(file_path):
                continue
            if not filename.lower().endswith(self.supported_extensions):
                ignored_count += 1
                continue
                
            _, ext = os.path.splitext(filename)
            media_data = self.get_media_data(file_path)
            
            mode_id = ""
            if settings['preserve_modes']:
                mode_id = self.extract_mode_identifier(filename)
            
            if media_data.get('date'):
                new_filename = self.generate_new_name(
                    media_data, ext, 
                    settings['full_year'], settings['maker'], settings['model'], mode_id
                )
                
                if new_filename:
                    new_file_path = os.path.join(folder_path, new_filename)
                    
                    counter = 1
                    while os.path.exists(new_file_path) or new_file_path.lower() in projected_names:
                        if new_file_path.lower() == file_path.lower():
                            break 
                        
                        name_without_ext = os.path.splitext(new_filename)[0]
                        new_file_path = os.path.join(folder_path, f"{name_without_ext}_{counter}{ext.lower()}")
                        counter += 1
                    
                    if new_file_path.lower() != file_path.lower():
                        projected_names.add(new_file_path.lower())
                        
                        if dry_run:
                            self.log_message(f"Preview: {filename} -> {os.path.basename(new_file_path)}")
                            processed_count += 1
                        else:
                            try:
                                os.rename(file_path, new_file_path)
                                self.log_message(f"Renamed: {filename} -> {os.path.basename(new_file_path)}")
                                processed_count += 1
                                # Log the change for undo
                                session_changes.append({
                                    "old": filename,
                                    "new": os.path.basename(new_file_path)
                                })
                            except Exception as e:
                                self.log_message(f"Error renaming {filename}: {e}")
                                skipped_count += 1
                    else:
                        if dry_run:
                            self.log_message(f"Unchanged (Already Correct): {filename}")
            else:
                self.log_message(f"Skipped: {filename} (No metadata date found)")
                skipped_count += 1

        # Handle Undo Logging
        if not dry_run and settings['enable_undo'] and session_changes:
            self.save_undo_log(folder_path, session_changes)

        self.log_message(f"\n--- Done! ---")
        if dry_run:
            self.log_message(f"Files to rename: {processed_count}")
        else:
            self.log_message(f"Successfully renamed: {processed_count}")
            
        self.log_message(f"Skipped (no date data): {skipped_count}")
        if ignored_count > 0:
            self.log_message(f"Ignored (unsupported files): {ignored_count}")

        self.after(0, lambda: self.reset_ui_state(dry_run))

    def reset_ui_state(self, is_preview):
        self.browse_btn.configure(state="normal")
        self.preview_btn.configure(state="normal")
        self.run_btn.configure(state="normal")
        self.undo_check.configure(state="normal")
        self.full_year_check.configure(state="normal")
        self.maker_check.configure(state="normal")
        self.model_check.configure(state="normal")
        self.preserve_modes_check.configure(state="normal")
        self.theme_btn.configure(state="normal")
        self.undo_last_btn.configure(state="normal")
        self.undo_history_btn.configure(state="normal")
        
        if is_preview:
            self.log_message("\n>>> Preview generation complete! Review the log above. <<<")
        else:
            self.log_message("\n>>> Media organization complete! <<<")

if __name__ == "__main__":
    app = MetaSortProApp()
    app.mainloop()
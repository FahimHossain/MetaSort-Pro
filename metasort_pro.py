import os
import re
import sys
import json
import threading
import ctypes
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime
from PIL import Image, ImageTk, ExifTags

# ==========================================
# BACKEND: Media Processing Engine
# ==========================================
class MediaEngine:
    """Handles all file metadata extraction and pure logic, isolated from the GUI."""
    IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.dng')
    VIDEO_EXTS = ('.mp4', '.mov', '.avi', '.mkv')
    SUPPORTED_EXTS = IMAGE_EXTS + VIDEO_EXTS

    @staticmethod
    def clean_string(text):
        if not text: return ""
        text = str(text).replace('\x00', '').strip()
        return re.sub(r'[<>:"/\\|?*]', '', text)

    @classmethod
    def get_metadata(cls, file_path):
        data = {'date': None, 'make': None, 'model': None}
        ext = os.path.splitext(file_path)[1].lower()

        if ext in cls.IMAGE_EXTS:
            try:
                image = Image.open(file_path)
                exif = image._getexif()
                if exif:
                    for tag, value in exif.items():
                        decoded = ExifTags.TAGS.get(tag, tag)
                        if decoded == "DateTimeOriginal":
                            data['date'] = value
                        elif decoded == "Make":
                            data['make'] = cls.clean_string(value)
                        elif decoded == "Model":
                            data['model'] = cls.clean_string(value)
            except Exception:
                pass
        
        elif ext in cls.VIDEO_EXTS:
            try:
                stat = os.stat(file_path)
                timestamp = min(stat.st_ctime, stat.st_mtime)
                data['date'] = datetime.fromtimestamp(timestamp).strftime("%Y:%m:%d %H:%M:%S")
            except Exception:
                pass
                
        return data, ext

    @staticmethod
    def extract_mode(filename):
        base_name = os.path.splitext(filename)[0]
        match = re.search(r'[\._](MP|PORTRAIT|PHOTOSPHERE|NIGHT|PANO|VR|BURST|COVER|MOTION)(~[0-9]+)?$', base_name, re.IGNORECASE)
        return match.group(0) if match else ""

    @staticmethod
    def generate_name(media_data, ext, settings, mode_identifier=""):
        date_str = media_data.get('date')
        if not date_str: return None
            
        try:
            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            year_format = "%Y%m%d %H%M %S" if settings['full_year'] else "%y%m%d %H%M %S"
            base_name = date_obj.strftime(year_format)
            
            suffix = ""
            if settings['maker'] and media_data.get('make'):
                suffix += f"_{media_data['make'].replace(' ', '')}"
            if settings['model'] and media_data.get('model'):
                suffix += f"_{media_data['model']}"

            return f"{base_name}{suffix}{mode_identifier}{ext.lower()}"
        except ValueError:
            return None


# ==========================================
# BACKEND: Undo Log Manager
# ==========================================
class UndoManager:
    """Handles reading, writing, and applying the JSON undo log."""
    
    @staticmethod
    def get_log_path(folder_path):
        return os.path.join(folder_path, ".metasort_undo.json")

    @classmethod
    def save_session(cls, folder_path, session_changes):
        if not session_changes: return
        log_path = cls.get_log_path(folder_path)
        data = cls.load_history(folder_path) or []
        
        data.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "changes": session_changes
        })
        
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

    @classmethod
    def load_history(cls, folder_path):
        log_path = cls.get_log_path(folder_path)
        if not os.path.exists(log_path): return None
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def update_history(cls, folder_path, new_data):
        with open(cls.get_log_path(folder_path), "w", encoding="utf-8") as f:
            json.dump(new_data, f, indent=4)


# ==========================================
# FRONTEND: GUI Application
# ==========================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class MetaSortProApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("MetaSort Pro v2.0")
        self.geometry("680x820") 
        self.minsize(600, 750)
        self._setup_window_icon()

        # Variables
        self.folder_path = ctk.StringVar()
        
        # --- NEW LOGIC: Set Default Target Folder to Execution Directory ---
        if getattr(sys, 'frozen', False):
            # If running as a compiled .exe
            default_folder = os.path.dirname(sys.executable)
        else:
            # If running as a standard python script
            default_folder = os.path.dirname(os.path.abspath(__file__))
            
        self.folder_path.set(default_folder)
        # -------------------------------------------------------------------

        self.settings = {
            'enable_undo': ctk.BooleanVar(value=True),
            'full_year': ctk.BooleanVar(value=False),
            'maker': ctk.BooleanVar(value=False),
            'model': ctk.BooleanVar(value=False),
            'preserve_modes': ctk.BooleanVar(value=True)
        }
        self.is_dark_mode = True

        self._build_ui()

    def _setup_window_icon(self):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('fahim.metasort.pro.2.0')
        except Exception: pass
            
        icon_path = os.path.join(os.path.dirname(__file__), "MetaSort Pro.ico")
        if os.path.exists(icon_path):
            self.app_icon = ImageTk.PhotoImage(Image.open(icon_path))
            self.wm_iconbitmap() 
            self.after(200, lambda: self.iconphoto(False, self.app_icon)) 

    # --- UI Builders ---
    
    def _build_ui(self):
        self._build_top_bar()
        self._build_folder_selector()
        self._build_options()
        self._build_action_buttons()
        self._build_undo_controls()
        self._build_console()

    def _build_top_bar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=20, pady=(15, 5))
        ctk.CTkLabel(bar, text="MetaSort Pro", font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
        self.theme_btn = ctk.CTkButton(bar, text="☀️ Light Mode", width=120, fg_color="transparent", 
                                       border_width=1, text_color=("gray10", "gray90"), command=self.toggle_theme)
        self.theme_btn.pack(side="right")

    def _build_folder_selector(self):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(frame, text="Step 1: Select Target Folder", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 0))
        
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="x", padx=15, pady=10)
        ctk.CTkEntry(container, textvariable=self.folder_path, state='readonly').pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.browse_btn = ctk.CTkButton(container, text="Browse...", width=100, command=self.browse_folder)
        self.browse_btn.pack(side="right")

    def _build_options(self):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame, text="Step 2: Options", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        options = [
            ("Enable Undo Log (Creates .metasort_undo.json)", self.settings['enable_undo']),
            ("Use Full Year (YYYY instead of YY)", self.settings['full_year']),
            ("Append Camera Maker (e.g., _Google) [Images Only]", self.settings['maker']),
            ("Append Camera Model (e.g., _Pixel) [Images Only]", self.settings['model']),
            ("Preserve Camera Modes (e.g., .MP, .NIGHT)", self.settings['preserve_modes'])
        ]
        
        self.option_widgets = []
        for text, var in options:
            chk = ctk.CTkCheckBox(frame, text=text, variable=var)
            chk.pack(anchor="w", padx=15, pady=(0, 10))
            self.option_widgets.append(chk)

    def _build_action_buttons(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=10)
        
        # Changed state from "disabled" to "normal" since we have a default folder now
        self.preview_btn = ctk.CTkButton(frame, text="Preview Changes", height=40, fg_color="#4B5563", hover_color="#374151", 
                                         font=ctk.CTkFont(size=14, weight="bold"), state="normal", command=lambda: self._start_thread(True))
        self.preview_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.run_btn = ctk.CTkButton(frame, text="Apply Changes", height=40, font=ctk.CTkFont(size=14, weight="bold"), 
                                     state="normal", command=lambda: self._start_thread(False))
        self.run_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _build_undo_controls(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(0, 10))
        
        # Changed state from "disabled" to "normal" since we have a default folder now
        self.undo_last_btn = ctk.CTkButton(frame, text="↩ Undo Last Session", height=30, fg_color="#991B1B", 
                                           hover_color="#7F1D1D", state="normal", command=self.undo_last_session)
        self.undo_last_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.undo_hist_btn = ctk.CTkButton(frame, text="📋 Undo History...", height=30, fg_color="#854D0E", 
                                           hover_color="#713F12", state="normal", command=self.open_undo_history)
        self.undo_hist_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _build_console(self):
        ctk.CTkLabel(self, text="Activity Log", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=20, pady=(0, 5))
        self.log_text = ctk.CTkTextbox(self, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        ctk.CTkLabel(self, text="Developed by Fahim Hossain", font=ctk.CTkFont(size=11), text_color=("gray60", "gray40")).pack(side="bottom", pady=(0, 10))

    # --- Interaction Logic ---

    def log(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def toggle_theme(self):
        ctk.set_appearance_mode("Light" if self.is_dark_mode else "Dark")
        self.theme_btn.configure(text="🌙 Dark Mode" if self.is_dark_mode else "☀️ Light Mode")
        self.is_dark_mode = not self.is_dark_mode

    def browse_folder(self):
        if folder := filedialog.askdirectory(title="Select Folder with Media"):
            self.folder_path.set(folder)
            self.toggle_ui_state("normal")
            self.log(f"Selected folder: {folder}")

    def toggle_ui_state(self, state):
        for widget in [self.browse_btn, self.preview_btn, self.run_btn, self.undo_last_btn, self.undo_hist_btn, self.theme_btn] + self.option_widgets:
            widget.configure(state=state)

    def _start_thread(self, dry_run):
        if not self.folder_path.get(): return
        
        current_settings = {k: v.get() for k, v in self.settings.items()}
        current_settings['dry_run'] = dry_run
        
        self.toggle_ui_state("disabled")
        self.log(f"\n--- Starting Process ({'PREVIEW' if dry_run else 'LIVE'}) ---")
        threading.Thread(target=self.process_media, args=(current_settings,), daemon=True).start()

    # --- Processing Core ---

    def process_media(self, run_settings):
        folder = self.folder_path.get()
        dry_run = run_settings['dry_run']
        stats = {'processed': 0, 'skipped': 0, 'ignored': 0, 'already_correct': 0}
        
        projected_names = set() 
        session_changes = [] 
        
        self.log(f"Target Directory: {folder}")
        self.log("Scanning for metadata...")
        
        for filename in os.listdir(folder):
            path = os.path.join(folder, filename)
            if os.path.isdir(path): continue
            
            if not filename.lower().endswith(MediaEngine.SUPPORTED_EXTS):
                stats['ignored'] += 1
                continue
                
            media_data, ext = MediaEngine.get_metadata(path)
            mode_id = MediaEngine.extract_mode(filename) if run_settings['preserve_modes'] else ""
            
            if not media_data.get('date'):
                self.log(f"Skipped: {filename} (No date found)")
                stats['skipped'] += 1
                continue

            new_filename = MediaEngine.generate_name(media_data, ext, run_settings, mode_id)
            if not new_filename: continue

            new_path = self._resolve_duplicate_name(folder, new_filename, path, projected_names, ext)
            
            if new_path.lower() != path.lower():
                projected_names.add(new_path.lower())
                self._apply_rename(path, new_path, filename, dry_run, session_changes, stats)
            else:
                stats['already_correct'] += 1
                if dry_run:
                    self.log(f"Unchanged (Already Correct): {filename}")

        if not dry_run and run_settings['enable_undo'] and session_changes:
            UndoManager.save_session(folder, session_changes)

        self._finalize_run(dry_run, stats)

    def _resolve_duplicate_name(self, folder, target_name, original_path, projected_set, ext):
        new_path = os.path.join(folder, target_name)
        counter = 1
        while os.path.exists(new_path) or new_path.lower() in projected_set:
            if new_path.lower() == original_path.lower(): break 
            base_no_ext = os.path.splitext(target_name)[0]
            new_path = os.path.join(folder, f"{base_no_ext}_{counter}{ext.lower()}")
            counter += 1
        return new_path

    def _apply_rename(self, old_path, new_path, old_name, dry_run, session_changes, stats):
        new_name = os.path.basename(new_path)
        if dry_run:
            self.log(f"Preview: {old_name} -> {new_name}")
            stats['processed'] += 1
        else:
            try:
                os.rename(old_path, new_path)
                self.log(f"Renamed: {old_name} -> {new_name}")
                session_changes.append({"old": old_name, "new": new_name})
                stats['processed'] += 1
            except Exception as e:
                self.log(f"Error renaming {old_name}: {e}")
                stats['skipped'] += 1

    def _finalize_run(self, dry_run, stats):
        self.log("\n--- Done! ---")
        self.log(f"{'Files to rename' if dry_run else 'Successfully renamed'}: {stats['processed']}")
        self.log(f"Skipped (already correct): {stats['already_correct']}")
        self.log(f"Skipped (no date data): {stats['skipped']}")
        if stats['ignored']: self.log(f"Ignored (unsupported files): {stats['ignored']}")
        
        self.after(0, lambda: self.toggle_ui_state("normal"))
        self.after(0, lambda: self.log("\n>>> Process Complete <<<"))

    # --- Undo Logic ---

    def undo_last_session(self):
        if messagebox.askyesno("Confirm Undo", "Are you sure you want to revert the most recent renaming session?"):
            threading.Thread(target=self._execute_undo, args=(-1,), daemon=True).start()

    def open_undo_history(self):
        data = UndoManager.load_history(self.folder_path.get())
        if not data:
            messagebox.showinfo("Undo History", "No undo history found.")
            return

        win = ctk.CTkToplevel(self)
        win.title("Undo History")
        win.geometry("400x500")
        win.transient(self) 
        
        ctk.CTkLabel(win, text="Select a Session to Revert", font=ctk.CTkFont(weight="bold", size=16)).pack(pady=15)
        scroll = ctk.CTkScrollableFrame(win)
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        def trigger_undo(index):
            if messagebox.askyesno("Confirm", "Revert this session?"):
                win.destroy()
                threading.Thread(target=self._execute_undo, args=(index,), daemon=True).start()

        for idx, session in reversed(list(enumerate(data))):
            frame = ctk.CTkFrame(scroll)
            frame.pack(fill="x", pady=5)
            ctk.CTkLabel(frame, text=f"{session.get('timestamp', 'Unknown')}\n{len(session.get('changes', []))} files", justify="left").pack(side="left", padx=10, pady=10)
            ctk.CTkButton(frame, text="Revert", width=80, fg_color="#991B1B", hover_color="#7F1D1D", 
                          command=lambda i=idx: trigger_undo(i)).pack(side="right", padx=10)

    def _execute_undo(self, session_index):
        folder = self.folder_path.get()
        data = UndoManager.load_history(folder)
        if not data: return self.log("Error: Undo log missing or corrupted.")
            
        try: target_session = data.pop(session_index)
        except IndexError: return self.log("Invalid session index.")

        self.log(f"\n--- Undoing Session: {target_session['timestamp']} ---")
        
        success, fail = 0, 0
        for change in reversed(target_session["changes"]):
            old_path = os.path.join(folder, change["old"])
            new_path = os.path.join(folder, change["new"])
            
            if os.path.exists(new_path):
                try:
                    os.rename(new_path, old_path)
                    self.log(f"Reverted: {change['new']} -> {change['old']}")
                    success += 1
                except Exception as e:
                    self.log(f"Error reverting {change['new']}: {e}")
                    fail += 1
            else:
                self.log(f"File missing, cannot revert: {change['new']}")
                fail += 1
                
        UndoManager.update_history(folder, data)
        self.log(f">>> Undo Complete: {success} reverted, {fail} failed. <<<")


if __name__ == "__main__":
    app = MetaSortProApp()
    app.mainloop()
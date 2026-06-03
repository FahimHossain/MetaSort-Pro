import os
import re
import sys
import json
import time
import threading
import ctypes
import hashlib
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from tkinterdnd2 import TkinterDnD, DND_FILES
from datetime import datetime
from PIL import Image, ImageTk, ExifTags
import reverse_geocoder as rg

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

    @staticmethod
    def get_lat_lon(exif_data):
        """Extracts latitude and longitude from EXIF GPSInfo (tag 34853)."""
        gps_info = exif_data.get(34853)
        if not gps_info: return None
        
        def convert_to_degrees(value):
            d = float(value[0])
            m = float(value[1])
            s = float(value[2])
            return d + (m / 60.0) + (s / 3600.0)

        try:
            lat = convert_to_degrees(gps_info[2])
            if gps_info[1] != 'N': lat = -lat
            lon = convert_to_degrees(gps_info[4])
            if gps_info[3] != 'E': lon = -lon
            return lat, lon
        except Exception:
            return None

    @classmethod
    def get_metadata(cls, file_path, needs_geo=False):
        data = {'date': None, 'make': '', 'model': '', 'city': '', 'country': ''}
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
                    
                    if needs_geo:
                        coords = cls.get_lat_lon(exif)
                        if coords:
                            results = rg.search(coords, verbose=False)
                            if results:
                                data['city'] = cls.clean_string(results[0].get('name', ''))
                                data['country'] = cls.clean_string(results[0].get('cc', ''))
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
    def generate_name(media_data, ext, settings, mode_identifier="", custom_template=""):
        date_str = media_data.get('date')
        if not date_str: return None
            
        try:
            date_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            
            # If the template exists, it dictates the format.
            if custom_template:
                mappings = {
                    'YYYY': date_obj.strftime('%Y'),
                    'YY': date_obj.strftime('%y'),
                    'MM': date_obj.strftime('%m'),
                    'DD': date_obj.strftime('%d'),
                    'hh': date_obj.strftime('%H'),
                    'mm': date_obj.strftime('%M'),
                    'ss': date_obj.strftime('%S'),
                    'MAKER': media_data.get('make', '').replace(' ', ''),
                    'MODEL': media_data.get('model', ''),
                    'CITY': media_data.get('city', '').replace(' ', ''),
                    'COUNTRY': media_data.get('country', '').replace(' ', ''),
                    'MODE': mode_identifier
                }

                new_name = custom_template
                for key, val in mappings.items():
                    new_name = new_name.replace(f"{{{key}}}", val)

                # Cleanup artifacts from empty tags (e.g., if CITY is blank, '__' becomes '_')
                new_name = re.sub(r'[_ \-\.]+((?=[_ \-\.]))', '', new_name) 
                new_name = re.sub(r'^[_ \-\.]+|[_ \-\.]+$', '', new_name)   
                return f"{new_name}{ext.lower()}"
            
            # Fallback STANDARD LOGIC if template is wiped completely empty manually
            else:
                year_format = "%Y%m%d %H%M %S" if settings.get('full_year') else "%y%m%d %H%M %S"
                base_name = date_obj.strftime(year_format)
                
                suffix = ""
                if settings.get('maker') and media_data.get('make'):
                    suffix += f"_{media_data['make'].replace(' ', '')}"
                if settings.get('model') and media_data.get('model'):
                    suffix += f"_{media_data['model']}"
                if settings.get('geotag'):
                    geo_parts = []
                    if media_data.get('city'): geo_parts.append(media_data['city'].replace(' ', ''))
                    if media_data.get('country'): geo_parts.append(media_data['country'].replace(' ', ''))
                    if geo_parts:
                        suffix += f"_{'_'.join(geo_parts)}"

                return f"{base_name}{suffix}{mode_identifier}{ext.lower()}"
                
        except ValueError:
            return None

    @staticmethod
    def get_partial_hash(file_path, chunk_size=1024*1024):
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(chunk_size)
                hasher.update(chunk)
            return hasher.hexdigest()
        except Exception:
            return None


# ==========================================
# BACKEND: Undo Log Manager
# ==========================================
class UndoManager:
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

class MetaSortProApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("MetaSort Pro v4.2")
        self.geometry("740x940") 
        self.minsize(680, 880)
        self._setup_window_icon()

        self.folder_path = ctk.StringVar()
        self.specific_files = [] 
        
        if getattr(sys, 'frozen', False):
            default_folder = os.path.dirname(sys.executable)
        else:
            default_folder = os.path.dirname(os.path.abspath(__file__))
        self.folder_path.set(default_folder)

        # Settings
        self.settings = {
            'enable_undo': ctk.BooleanVar(value=True),
            'full_year': ctk.BooleanVar(value=False),
            'maker': ctk.BooleanVar(value=False),
            'model': ctk.BooleanVar(value=False),
            'geotag': ctk.BooleanVar(value=False), 
            'preserve_modes': ctk.BooleanVar(value=True)
        }
        
        self.filename_template = ctk.StringVar() 
        self._update_template_string() # Auto-populate the initial string based on default checkboxes
        
        self.is_dark_mode = True
        self._build_ui()
        
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_drop)

    def _setup_window_icon(self):
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('fahim.metasort.pro.4.2')
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
        self._build_syntax_builder()
        self._build_action_buttons()
        self._build_progress_bar()
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
        ctk.CTkLabel(frame, text="Step 1: Select Folder (Or Drag & Drop Files/Folders anywhere)", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 0))
        
        container = ctk.CTkFrame(frame, fg_color="transparent")
        container.pack(fill="x", padx=15, pady=10)
        ctk.CTkEntry(container, textvariable=self.folder_path, state='readonly').pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.browse_btn = ctk.CTkButton(container, text="Browse...", width=100, command=self.browse_folder)
        self.browse_btn.pack(side="right")

    def _build_options(self):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(frame, text="Step 2: Naming Options", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(10, 5))

        # Each visual option runs _update_template_string when clicked
        options = [
            ("Enable Undo Log (Creates .metasort_undo.json)", self.settings['enable_undo'], None),
            ("Use Full Year (YYYY instead of YY)", self.settings['full_year'], self._update_template_string),
            ("Append Camera Maker (e.g., _Google) [Images Only]", self.settings['maker'], self._update_template_string),
            ("Append Camera Model (e.g., _Pixel) [Images Only]", self.settings['model'], self._update_template_string),
            ("Append Geo-Location (City_Country) [Images Only]", self.settings['geotag'], self._update_template_string),
            ("Preserve Camera Modes (e.g., .MP, .NIGHT)", self.settings['preserve_modes'], self._update_template_string)
        ]
        
        self.option_widgets = []
        for text, var, cmd in options:
            if cmd:
                chk = ctk.CTkCheckBox(frame, text=text, variable=var, command=cmd)
            else:
                chk = ctk.CTkCheckBox(frame, text=text, variable=var)
            chk.pack(anchor="w", padx=15, pady=(0, 10))
            self.option_widgets.append(chk)

    def _build_syntax_builder(self):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", padx=20, pady=5)
        
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(header, text="Step 3: Custom Format Builder", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        ctk.CTkLabel(frame, text="Updates automatically via checkboxes. You can also manually type your own format.", font=ctk.CTkFont(size=12, slant="italic"), text_color=("gray60", "gray40")).pack(anchor="w", padx=15, pady=(0, 5))

        self.template_entry = ctk.CTkEntry(frame, textvariable=self.filename_template, font=ctk.CTkFont(family="Consolas", size=14), placeholder_text="e.g. {YYYY}-{MM}-{DD}_{CITY}")
        self.template_entry.pack(fill="x", padx=15, pady=(0, 5))
        
        tags_text = "Available Tags: {YYYY}, {YY}, {MM}, {DD}, {hh}, {mm}, {ss}, {MAKER}, {MODEL}, {CITY}, {COUNTRY}, {MODE}"
        ctk.CTkLabel(frame, text=tags_text, font=ctk.CTkFont(size=11), text_color=("gray60", "gray40")).pack(anchor="w", padx=15, pady=(0, 10))

    def _build_action_buttons(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(10, 5))
        
        self.preview_btn = ctk.CTkButton(frame, text="Preview Changes", height=40, fg_color="#4B5563", hover_color="#374151", 
                                         font=ctk.CTkFont(size=14, weight="bold"), state="normal", command=lambda: self._start_thread(True))
        self.preview_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        self.run_btn = ctk.CTkButton(frame, text="Apply Changes", height=40, font=ctk.CTkFont(size=14, weight="bold"), 
                                     state="normal", command=lambda: self._start_thread(False))
        self.run_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

    def _build_progress_bar(self):
        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent", height=20)
        self.progress_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, mode="determinate")
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="0% | Idle", width=120, anchor="e")
        self.progress_label.pack(side="right")

    def _build_undo_controls(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=20, pady=(0, 10))
        
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
    
    def _update_template_string(self):
        """Constructs the format string automatically based on the current state of the checkboxes."""
        if self.settings['full_year'].get():
            template = "{YYYY}{MM}{DD} {hh}{mm} {ss}"
        else:
            template = "{YY}{MM}{DD} {hh}{mm} {ss}"
            
        if self.settings['maker'].get():
            template += "_{MAKER}"
        if self.settings['model'].get():
            template += "_{MODEL}"
        if self.settings['geotag'].get():
            template += "_{CITY}_{COUNTRY}"
            
        if self.settings['preserve_modes'].get():
            template += "{MODE}"
            
        self.filename_template.set(template)

    def handle_drop(self, event):
        raw_paths = self.tk.splitlist(event.data)
        paths = [os.path.normpath(p) for p in raw_paths]
        
        if not paths: return
        
        if len(paths) == 1 and os.path.isdir(paths[0]):
            self.folder_path.set(paths[0])
            self.specific_files = [] 
            self.log(f"Dropped folder: {paths[0]}")
        else:
            valid_files = [p for p in paths if os.path.isfile(p) and p.lower().endswith(MediaEngine.SUPPORTED_EXTS)]
            if not valid_files:
                self.log("No supported files dropped.")
                return
            
            self.specific_files = valid_files
            parent_dir = os.path.dirname(valid_files[0])
            self.folder_path.set(parent_dir) 
            self.log(f"Dropped {len(valid_files)} specific file(s) for processing.")
            
        self.toggle_ui_state("normal")

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
            self.specific_files = [] 
            self.toggle_ui_state("normal")
            self.log(f"Selected folder: {folder}")

    def toggle_ui_state(self, state):
        for widget in [self.browse_btn, self.preview_btn, self.run_btn, self.undo_last_btn, self.undo_hist_btn, self.theme_btn, self.template_entry] + self.option_widgets:
            widget.configure(state=state)

    def update_progress(self, val, text_val):
        self.progress_bar.set(val)
        self.progress_label.configure(text=text_val)

    def _start_thread(self, dry_run):
        if not self.folder_path.get(): return

        run_settings = {k: v.get() for k, v in self.settings.items()}
        run_settings['dry_run'] = dry_run
        run_settings['template'] = self.filename_template.get().strip()
        
        self.toggle_ui_state("disabled")
        self.update_progress(0, "0% | Calculating...")
        self.log(f"\n--- Starting Process ({'PREVIEW' if dry_run else 'LIVE'}) ---")
        threading.Thread(target=self.process_media, args=(run_settings,), daemon=True).start()

    # --- Processing Core ---

    def process_media(self, run_settings):
        folder = self.folder_path.get()
        dry_run = run_settings['dry_run']
        template = run_settings['template']
        stats = {'processed': 0, 'skipped': 0, 'ignored': 0, 'already_correct': 0, 'duplicates': 0}
        
        projected_paths = {} 
        session_changes = [] 
        
        if self.specific_files:
            target_paths = self.specific_files
            self.log(f"Processing {len(target_paths)} individually selected file(s)...")
        else:
            target_paths = [os.path.join(folder, f) for f in os.listdir(folder)]
            self.log(f"Target Directory: {folder}")
            self.log("Scanning for metadata...")
        
        total_files = len(target_paths)
        start_time = time.time()
        
        # Determine if we need to spend time doing reverse geocoding
        needs_geo = run_settings['geotag'] or '{CITY}' in template or '{COUNTRY}' in template

        for i, path in enumerate(target_paths):
            if os.path.isdir(path): 
                self._update_progress_ui(i, total_files, start_time)
                continue
            
            filename = os.path.basename(path)
            file_dir = os.path.dirname(path) 
            
            if not filename.lower().endswith(MediaEngine.SUPPORTED_EXTS):
                stats['ignored'] += 1
                self._update_progress_ui(i, total_files, start_time)
                continue
                
            media_data, ext = MediaEngine.get_metadata(path, needs_geo)
            
            if not media_data.get('date'):
                self.log(f"Skipped: {filename} (No date found)")
                stats['skipped'] += 1
                self._update_progress_ui(i, total_files, start_time)
                continue

            mode_id = MediaEngine.extract_mode(filename) if run_settings['preserve_modes'] else ""
            
            new_filename = MediaEngine.generate_name(media_data, ext, run_settings, mode_id, template)
            if not new_filename: 
                self._update_progress_ui(i, total_files, start_time)
                continue

            new_path, is_duplicate = self._resolve_path_and_duplicates(file_dir, new_filename, path, projected_paths, ext)
            
            if is_duplicate:
                stats['duplicates'] += 1
                if dry_run:
                    self.log(f"Preview: True Duplicate -> {filename} will be moved to /Duplicates")
                else:
                    dup_folder = os.path.join(file_dir, "Duplicates")
                    os.makedirs(dup_folder, exist_ok=True)
                    
                    base, ex = os.path.splitext(filename)
                    dup_target = os.path.join(dup_folder, filename)
                    c = 1
                    while os.path.exists(dup_target):
                        dup_target = os.path.join(dup_folder, f"{base}_{c}{ex}")
                        c += 1
                        
                    try:
                        shutil.move(path, dup_target)
                        self.log(f"Moved Duplicate: {filename} -> Duplicates/{os.path.basename(dup_target)}")
                        session_changes.append({"old_path": path, "new_path": dup_target, "old": filename, "new": f"Duplicates/{os.path.basename(dup_target)}"})
                    except Exception as e:
                        self.log(f"Error moving duplicate {filename}: {e}")
                        
                self._update_progress_ui(i, total_files, start_time)
                continue

            if new_path.lower() != path.lower():
                projected_paths[new_path.lower()] = path
                self._apply_rename(path, new_path, filename, dry_run, session_changes, stats)
            else:
                stats['already_correct'] += 1
                if dry_run:
                    self.log(f"Unchanged (Already Correct): {filename}")

            self._update_progress_ui(i, total_files, start_time)

        if not dry_run and run_settings['enable_undo'] and session_changes:
            UndoManager.save_session(folder, session_changes)

        self._finalize_run(dry_run, stats)

    def _update_progress_ui(self, current_index, total_files, start_time):
        progress_val = (current_index + 1) / total_files if total_files > 0 else 1
        percentage = int(progress_val * 100)
        
        elapsed = time.time() - start_time
        if current_index > 0:
            eta_seconds = (elapsed / current_index) * (total_files - current_index)
            eta_str = f"ETA: {int(eta_seconds)}s"
        else:
            eta_str = "Calculating..."

        self.after(0, lambda: self.update_progress(progress_val, f"{percentage}% | {eta_str}"))

    def _resolve_path_and_duplicates(self, file_dir, target_name, original_path, projected_paths, ext):
        new_path = os.path.join(file_dir, target_name)

        if new_path.lower() == original_path.lower():
            return new_path, False

        current_size = None
        current_hash = None
        counter = 1
        base_no_ext = os.path.splitext(target_name)[0]

        while True:
            conflict_path = None
            if os.path.exists(new_path):
                conflict_path = new_path
            elif new_path.lower() in projected_paths:
                conflict_path = projected_paths[new_path.lower()]

            if not conflict_path:
                break 

            if conflict_path.lower() == original_path.lower():
                break

            try:
                if current_size is None:
                    current_size = os.path.getsize(original_path)
                conflict_size = os.path.getsize(conflict_path)

                if current_size == conflict_size:
                    if current_hash is None:
                        current_hash = MediaEngine.get_partial_hash(original_path)
                    conflict_hash = MediaEngine.get_partial_hash(conflict_path)

                    if current_hash and conflict_hash and current_hash == conflict_hash:
                        return None, True 
            except Exception:
                pass 

            new_path = os.path.join(file_dir, f"{base_no_ext}_{counter}{ext.lower()}")
            counter += 1

        return new_path, False

    def _apply_rename(self, old_path, new_path, old_name, dry_run, session_changes, stats):
        new_name = os.path.basename(new_path)
        if dry_run:
            self.log(f"Preview: {old_name} -> {new_name}")
            stats['processed'] += 1
        else:
            try:
                os.rename(old_path, new_path)
                self.log(f"Renamed: {old_name} -> {new_name}")
                session_changes.append({"old_path": old_path, "new_path": new_path, "old": old_name, "new": new_name})
                stats['processed'] += 1
            except Exception as e:
                self.log(f"Error renaming {old_name}: {e}")
                stats['skipped'] += 1

    def _finalize_run(self, dry_run, stats):
        self.log("\n--- Done! ---")
        self.log(f"{'Files to rename' if dry_run else 'Successfully renamed'}: {stats['processed']}")
        if stats['duplicates']: self.log(f"{'Duplicates found' if dry_run else 'Duplicates moved to /Duplicates'}: {stats['duplicates']}")
        self.log(f"Skipped (already correct): {stats['already_correct']}")
        self.log(f"Skipped (no date data): {stats['skipped']}")
        if stats['ignored']: self.log(f"Ignored (unsupported files): {stats['ignored']}")
        
        self.after(0, lambda: self.update_progress(1.0, "100% | Done"))
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
            old_path = change.get("old_path", os.path.join(folder, change.get("old", ""))) 
            new_path = change.get("new_path", os.path.join(folder, change.get("new", "")))
            
            if os.path.exists(new_path):
                try:
                    shutil.move(new_path, old_path)
                    self.log(f"Reverted: {os.path.basename(new_path)} -> {os.path.basename(old_path)}")
                    success += 1
                except Exception as e:
                    self.log(f"Error reverting {os.path.basename(new_path)}: {e}")
                    fail += 1
            else:
                self.log(f"File missing, cannot revert: {os.path.basename(new_path)}")
                fail += 1
                
        UndoManager.update_history(folder, data)
        self.log(f">>> Undo Complete: {success} reverted, {fail} failed. <<<")


if __name__ == "__main__":
    app = MetaSortProApp()
    app.mainloop()
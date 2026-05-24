# MetaSort Pro v2.0

MetaSort Pro is a modern, responsive Windows GUI application built with Python that automatically organizes and renames your image and video files based on their metadata.

Say goodbye to cluttered media directories, MetaSort Pro standardizes your file names into a clean, chronological format while preserving critical device contexts like camera maker, model, and special photography modes (e.g., Portrait or Night mode). It intelligently extracts EXIF "Date Taken" data for images and falls back to OS creation/modification timestamps for video files.

---

# 🌟 Key Features

## Intelligent File Renaming

Automatically standardizes disorganized media names into:

```text
YYMMDD HHMM SS
```

Or optionally:

```text
YYYYMMDD HHMM SS
```

based on the true creation date of the file.

---

## Device Context Preservation

Optionally appends sanitized camera maker and model strings to filenames.

Example:

```text
240512 1430 55_Google_Pixel 10 Pro.jpg
```

---

## Smart Camera Mode Retention

Detects and preserves standard smartphone camera modes so native gallery app features continue functioning correctly.

Supported examples include:

- `.MP`
- `.MOTION`
- `.PORTRAIT`
- `.NIGHT`
- `.PANO`
- `.BURST`

---

## JSON-Based Undo Engine

Provides a fully non-destructive workflow using a lightweight:

```text
.metasort_undo.json
```

log file instead of space-consuming file duplication.

Features include:

- One-click **Undo Last Session**
- Full **Undo History** manager
- Session-based rollback tracking

---

## Preview Mode (Dry Run)

Features a virtual filesystem simulation that:

- Predicts naming collisions
- Displays projected filename changes
- Prevents accidental overwrites

No files are modified during preview mode.

---

## Modern UI

Built using `CustomTkinter` with:

- Responsive layout
- Native Light/Dark mode toggle
- Real-time activity log console

---

## Thread-Safe Processing

Heavy file operations run on a background daemon thread to keep the UI smooth and responsive, even while processing thousands of files.

---

# ⚙️ Prerequisites & Installation

To run MetaSort Pro from source, you must have **Python 3** installed on your system.

---

## 1. Clone or Download the Repository

Download or clone the project files to your local machine.

---

## 2. Install Dependencies

MetaSort Pro relies on:

- `Pillow` for EXIF extraction
- `CustomTkinter` for the GUI

Install them using:

```bash
pip install Pillow customtkinter
```

> Note: Standard Python libraries such as `os`, `shutil`, `threading`, `re`, `json`, and `datetime` are used internally and do not require separate installation.

---

# 🚀 Usage Guide (GUI)

## Run the Application

Open your terminal or command prompt and execute:

```bash
python metasort_pro.py
```

---

## Select Target Folder

Click the **Browse...** button and choose the directory containing your media files.

---

## Configure Options

Enable or disable desired formatting features:

- Enable Undo Log
- Use Full Year
- Append Camera Maker/Model
- Preserve Camera Modes

---

## Preview Changes (Recommended)

Click:

```text
Preview Changes
```

The application will:

- Scan all supported media files
- Simulate rename operations
- Display projected filenames in the Activity Log

No actual file modifications occur during this step.

---

## Apply Changes

Click:

```text
Apply Changes
```

MetaSort Pro will:

- Lock the UI during processing
- Execute all rename operations
- Update the JSON undo log
- Print real-time progress updates

---

# 📦 Building the Standalone `.exe`

You can compile MetaSort Pro into a standalone Windows executable using `PyInstaller`.

This allows the application to run on systems without Python installed.

---

## 1. Install PyInstaller

```bash
pip install pyinstaller
```

---

## 2. Build the Full GUI Application

```bash
pyinstaller --noconsole --onefile --icon="MetaSort Pro.ico" --add-data "MetaSort Pro.ico;." --collect-all customtkinter metasort_pro.py
```

---


# 📂 Supported File Formats

MetaSort Pro strictly filters supported formats to prevent accidental modification of unrelated files.

---

## Images

- `.jpg`
- `.jpeg`
- `.png`
- `.tif`
- `.tiff`
- `.dng` *(RAW image format)*

---

## Videos

- `.mp4`
- `.mov`
- `.avi`
- `.mkv`

---

# 📸 Supported Camera Mode Identifiers

If **Preserve Camera Modes** is enabled, MetaSort Pro uses Regular Expressions to detect and retain common smartphone camera identifiers.

| Identifier | Common Use Case |
|---|---|
| `.MP` / `.MOTION` | Google Pixel / Samsung Motion Photos |
| `.PORTRAIT` | Depth-mapped portrait photography |
| `.NIGHT` | Long-exposure night photography |
| `.PHOTOSPHERE` / `.PANO` / `.VR` | Panoramic and 360° captures |
| `.BURST` / `~[0-9]+` / `.COVER` | Burst shot sequences and top picks |

---

# 👨‍💻 Author

Developed by Fahim Hossain

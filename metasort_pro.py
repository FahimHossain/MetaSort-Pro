import os
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from PIL import Image, ExifTags

def get_date_taken(file_path):
    """Extracts the 'Date Taken' (DateTimeOriginal) from EXIF data."""
    try:
        # Open the image
        image = Image.open(file_path)
        
        # Get EXIF data
        exif = image._getexif()
        if not exif:
            return None
        
        # Find the specific DateTimeOriginal tag
        for tag, value in exif.items():
            decoded = ExifTags.TAGS.get(tag, tag)
            if decoded == "DateTimeOriginal":
                return value
    except Exception:
        # Fails silently for non-images or corrupted files
        return None
    return None

def generate_new_name(date_string, original_extension):
    """Formats the EXIF date string to YYMMDD HHMM SS."""
    try:
        # EXIF dates are typically formatted as "YYYY:MM:DD HH:MM:SS"
        date_obj = datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")
        # Format to user requirement: YYMMDD HHMM SS
        new_name = date_obj.strftime("%y%m%d %H%M %S")
        return f"{new_name}{original_extension.lower()}"
    except ValueError:
        return None

def rename_photos_in_folder():
    """Main function to select folder and process images."""
    # Hide the main tkinter window
    root = tk.Tk()
    root.withdraw()
    
    # Open folder selection dialog
    folder_path = filedialog.askdirectory(title="Select Folder with Images")
    
    if not folder_path:
        print("No folder selected. Exiting.")
        return

    print(f"Processing folder: {folder_path}\n")
    
    processed_count = 0
    skipped_count = 0

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        
        # Skip directories
        if os.path.isdir(file_path):
            continue
            
        _, ext = os.path.splitext(filename)
        
        # Extract date taken
        date_taken = get_date_taken(file_path)
        
        if date_taken:
            new_filename = generate_new_name(date_taken, ext)
            
            if new_filename:
                new_file_path = os.path.join(folder_path, new_filename)
                
                # Handle duplicate names (e.g., burst photos taken in the exact same second)
                counter = 1
                while os.path.exists(new_file_path):
                    if new_file_path.lower() == file_path.lower():
                        break # The file is already named correctly
                    
                    name_without_ext = os.path.splitext(new_filename)[0]
                    new_file_path = os.path.join(folder_path, f"{name_without_ext}_{counter}{ext.lower()}")
                    counter += 1
                
                # Rename the file if it's not already correct
                if new_file_path.lower() != file_path.lower():
                    try:
                        os.rename(file_path, new_file_path)
                        print(f"Renamed: {filename} -> {os.path.basename(new_file_path)}")
                        processed_count += 1
                    except Exception as e:
                        print(f"Error renaming {filename}: {e}")
                        skipped_count += 1
        else:
            print(f"Skipped: {filename} (No EXIF 'Date Taken' found)")
            skipped_count += 1

    print(f"\nDone! Successfully renamed {processed_count} files. Skipped {skipped_count} files.")
    
    # Show completion pop-up
    messagebox.showinfo("Complete", f"Successfully renamed {processed_count} files.\nSkipped {skipped_count} files.")

if __name__ == "__main__":
    rename_photos_in_folder()
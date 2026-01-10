"""
This module will contain all the low-level functions for UI automation and OCR.
This includes functions for:
- Finding elements on the screen (e.g., buttons, text fields)
- Clicking, typing, and other mouse/keyboard interactions
- Capturing screenshots
- Scraping text from images using OCR
"""
import pyautogui
import pytesseract
from PIL import Image
import cv2
import numpy as np

def list_granola_notes():
    """
    Finds the Granola application, takes a screenshot of the notes list,
    and returns a list of note titles.
    """
    granola_window = _find_and_focus_window("Granola")
    if not granola_window:
        print("Granola window not found.")
        return []

    # Take a screenshot of the window's region
    screenshot_path = "notes_list.png"
    pyautogui.screenshot(screenshot_path, region=(
        granola_window['left'], 
        granola_window['top'], 
        granola_window['width'], 
        granola_window['height']
    ))
    
    print(f"Screenshot saved to {screenshot_path}")

    # Use OCR to extract text from the screenshot
    try:
        image = Image.open(screenshot_path)
        extracted_text = pytesseract.image_to_string(image)
        print("\\n--- Extracted Text ---\\n")
        print(extracted_text)
        print("\\n----------------------\\n")
    except Exception as e:
        print(f"Error during OCR processing: {e}")
        return []

    # Parse the extracted text to get a list of note titles.
    # This logic can be refined based on the actual output of the Granola app.
    # For now, we'll filter out very short strings and potential OCR noise.
    lines = extracted_text.strip().split('\\n')
    note_titles = [
        line.strip() 
        for line in lines 
        if line.strip() and len(line.strip()) > 3 # Basic noise filtering
    ]

    print("--- Parsed Note Titles ---")
    print(note_titles)
    print("--------------------------")
    
    return note_titles


import subprocess

def _get_window_by_title(app_name):
    """
    Uses a more explicit AppleScript to get the window of a specific application.
    Returns the process name and window title if a match is found, otherwise None.
    """
    script = f"""
    tell application "{app_name}"
        if it is running then
            try
                set window_name to name of front window
                return "{app_name}|||" & window_name
            on error
                return ""
            end try
        end if
    end tell
    return ""
    """
    try:
        proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=True)
        result = proc.stdout.strip()
        if result:
            parts = result.split('|||')
            if len(parts) == 2:
                return parts
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error executing AppleScript to get window by app name: {e}")
        return None
    return None

def _focus_window(process_name, window_title):
    """
    Uses AppleScript to bring a specific window to the foreground.
    """
    script = f'''
    tell application "System Events"
        tell process "{process_name}"
            set frontmost to true
            perform action "AXRaise" of window "{window_title}"
        end tell
    end tell
    '''
    try:
        subprocess.run(['osascript', '-e', script], check=True)
        pyautogui.sleep(0.5) # Pause to allow window to focus
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error focusing window with AppleScript: {e}")
        return False
        
def _get_window_geometry(process_name, window_title):
    """
    Uses AppleScript to get the geometry (x, y, width, height) of a window.
    """
    script = f'''
    tell application "System Events"
        tell process "{process_name}"
            set {{x, y}} to position of window "{window_title}"
            set {{w, h}} to size of window "{window_title}"
            return x & "," & y & "," & w & "," & h
        end tell
    end tell
    '''
    try:
        proc = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, check=True)
        parts = proc.stdout.strip().split(',')
        if len(parts) == 4:
            return {
                "left": int(parts[0]),
                "top": int(parts[1]),
                "width": int(parts[2]),
                "height": int(parts[3]),
                "title": window_title
            }
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        print(f"Error getting window geometry with AppleScript: {e}")
    return None

def _find_and_focus_window(title_substring):
    """
    Finds a window with a title containing the given substring and brings it to focus.
    Returns a dictionary with the window's geometry if found, otherwise None.
    """
    window_info = _get_window_by_title(title_substring)
    if not window_info:
        return None
    
    process_name, window_title = window_info
    
    if _focus_window(process_name, window_title):
        # Now, get the precise geometry of the focused window
        return _get_window_geometry(process_name, window_title)
        
    return None

# The original function for reference, now replaced.
# def _find_and_focus_window_old(title_substring):
#     """
#     Finds a window with a title containing the given substring and brings it to focus.
#     Returns the window object if found, otherwise None.
#     """
#     windows = pyautogui.getWindowsWithTitle(title_substring)
#     if not windows:
#         return None
    
#     # Get the first matching window
#     window = windows[0]
    
#     # On macOS, activation might be needed.
#     # On Windows/Linux, this might bring the window to the front.
#     try:
#         if window.isActive == False:
#             window.activate()
#     except Exception as e:
#         # Some platforms might not support activate()
#         print(f"Could not activate window: {e}")

#     # A short pause to allow the window to come to the front
#     pyautogui.sleep(0.5)

#     return window



def read_granola_note(note_title: str):
    """
    Finds and clicks on a note with the given title, then extracts and returns its content.
    """
    granola_window = _find_and_focus_window("Granola")
    if not granola_window:
        print("Granola window not found.")
        return None

    # Find and click the note title within the window's region
    clicked = _find_and_click_text(note_title, region=granola_window)
    
    if not clicked:
        print(f"Could not find or click on note titled: {note_title}")
        return None

    # Placeholder for a future step: wait for the note to load
    pyautogui.sleep(1) 

    # Take a screenshot of the note content
    screenshot_path = "note_content.png"
    pyautogui.screenshot(screenshot_path, region=(
        granola_window.left, 
        granola_window.top, 
        granola_window.width, 
        granola_window.height
    ))
    print(f"Screenshot of note content saved to {screenshot_path}")

    # Use OCR to extract text from the screenshot
    try:
        image = Image.open(screenshot_path)
        extracted_text = pytesseract.image_to_string(image)
        print("\\n--- Extracted Note Content ---\\n")
        print(extracted_text)
        print("\\n----------------------------\\n")
        
        # Clean and return the final text
        cleaned_text = extracted_text.strip()
        return cleaned_text
    except Exception as e:
        print(f"Error during OCR processing of the note content: {e}")
        return None


def _find_and_click_text(text_to_find, region):
    """
    Finds a string of text within a given region of the screen using OCR and clicks on it.
    
    Args:
        text_to_find (str): The text to search for.
        region (dict): A dictionary with keys 'left', 'top', 'width', 'height'.

    Returns:
        bool: True if the text was found and clicked, False otherwise.
    """
    # 1. Take a screenshot of the specified region
    screenshot_path = "region_to_search.png"
    pyautogui.screenshot(screenshot_path, region=(
        region['left'], 
        region['top'], 
        region['width'], 
        region['height']
    ))
    
    image = cv2.imread(screenshot_path)
    
    # 2. Use Tesseract to get detailed OCR data, including bounding boxes
    ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    
    n_boxes = len(ocr_data['text'])
    for i in range(n_boxes):
        # Use 'in' for partial matches, which can be more robust
        if text_to_find.lower() in ocr_data['text'][i].lower():
            # Check for a reasonable confidence level
            if int(ocr_data['conf'][i]) > 50: # Confidence threshold
                # 4. If it matches, calculate the coordinates to click
                (x, y, w, h) = (ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i])
                
                # Calculate the center of the bounding box
                center_x = x + w // 2
                center_y = y + h // 2
                
                # Convert to absolute screen coordinates by adding the region's top-left corner
                absolute_x = region['left'] + center_x
                absolute_y = region['top'] + center_y
                
                # 5. Click on the found text
                print(f"Found '{text_to_find}' at ({absolute_x}, {absolute_y}). Clicking now.")
                pyautogui.click(absolute_x, absolute_y)
                return True
                
    return False

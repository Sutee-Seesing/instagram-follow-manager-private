import json
import time
import random
import os
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# --- Configuration ---
CHROME_PROFILE_PATH = "chrome_session_profile"  # Folder to save login session
PROCESSED_FILE = "processed_users.json"

def load_processed_users():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    try:
        with open(PROCESSED_FILE, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (OSError, json.JSONDecodeError):
        return set()

def save_processed_users(users_set):
    with open(PROCESSED_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(users_set), f)

def choose_instagram_zip_file():
    picker = tk.Tk()
    picker.withdraw()
    picker.attributes("-topmost", True)
    zip_path = filedialog.askopenfilename(
        title="Select Instagram data ZIP",
        filetypes=[("ZIP files", "*.zip")]
    )
    picker.destroy()
    return zip_path

def read_json_from_zip(zip_file, internal_path):
    with zip_file.open(internal_path) as f:
        raw_bytes = f.read()
        try:
            return json.loads(raw_bytes.decode('utf-8'))
        except UnicodeDecodeError:
            return json.loads(raw_bytes.decode('utf-8-sig'))

def load_instagram_data_from_zip(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zf:
        files = [name for name in zf.namelist() if not name.endswith('/')]

        followers_files = [
            name for name in files
            if name.lower().endswith('.json') and os.path.basename(name).lower().startswith('followers_')
        ]
        following_file = next(
            (name for name in files if os.path.basename(name).lower() == 'following.json'),
            None
        )

        if not followers_files or not following_file:
            raise ValueError("Could not find followers_*.json or following.json in ZIP.")

        followers_data = []
        for path in sorted(followers_files):
            chunk = read_json_from_zip(zf, path)
            if isinstance(chunk, list):
                followers_data.extend(chunk)

        following_data = read_json_from_zip(zf, following_file)

        return followers_data, following_data, followers_files, following_file

def extract_followers_set(followers_data):
    followers_set = set()
    for item in followers_data:
        if isinstance(item, dict) and 'string_list_data' in item:
            for data in item['string_list_data']:
                value = data.get('value') if isinstance(data, dict) else None
                if value:
                    followers_set.add(value)
    return followers_set

def get_following_items(following_data):
    if isinstance(following_data, dict) and 'relationships_following' in following_data:
        return following_data['relationships_following']
    if isinstance(following_data, list):
        return following_data
    return []

def extract_following_set(following_data):
    following_set = set()
    for item in get_following_items(following_data):
        title = item.get('title') if isinstance(item, dict) else None
        if title:
            following_set.add(title)
    return following_set

def compare_follow_data(followers_data, following_data):
    followers_set = extract_followers_set(followers_data)
    following_set = extract_following_set(following_data)

    unfollowers = sorted(following_set - followers_set)
    fans = sorted(followers_set - following_set)

    return followers_set, following_set, unfollowers, fans

def get_instagram_data():
    """
    Compares following and followers to find:
    1. Users who don't follow back (Unfollowers)
    2. Users you don't follow back (Fans)
    """
    zip_path = choose_instagram_zip_file()
    if not zip_path:
        print("No ZIP selected.")
        return [], []

    print(f"Loading data from ZIP: {zip_path}")
    try:
        followers_data, following_data, followers_paths, following_path = load_instagram_data_from_zip(zip_path)
        print(f"Detected followers files: {len(followers_paths)} file(s)")
        print(f"Detected following file: {following_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Could not load Instagram ZIP data.\n\n{e}")
        return [], []

    followers_set, following_set, unfollowers, fans = compare_follow_data(followers_data, following_data)
    
    print(f"Debug: Followers count: {len(followers_set)}")
    print(f"Debug: Following count: {len(following_set)}")
    print(f"Found {len(unfollowers)} users who don't follow you back.")
    print(f"Found {len(fans)} users you don't follow back.")
    
    return unfollowers, fans

class UserSelectionApp:
    """GUI for selecting users to unfollow."""
    def __init__(self, unfollowers, fans):
        self.unfollowers = unfollowers
        self.fans = fans
        self.processed_users = load_processed_users()
        self.selected_users = []
        
        self.root = tk.Tk()
        self.root.title("Instagram Bot Manager")
        self.root.geometry("450x650")

        # Toggle Buttons Frame
        toggle_frame = tk.Frame(self.root)
        toggle_frame.pack(fill="x", pady=10, padx=10)
        
        self.btn_unfollowers = tk.Button(toggle_frame, text=f"Not Following Back ({len(unfollowers)})", command=lambda: self.show_list("unfollowers"))
        self.btn_unfollowers.pack(side="left", expand=True, fill="x", padx=2)
        
        self.btn_fans = tk.Button(toggle_frame, text=f"I Don't Follow Back ({len(fans)})", command=lambda: self.show_list("fans"))
        self.btn_fans.pack(side="left", expand=True, fill="x", padx=2)

        # Instructions
        self.lbl_info = tk.Label(self.root, text="", font=("Arial", 10))
        self.lbl_info.pack(pady=5)

        # Select All / Deselect All Frame
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(fill="x", padx=20)
        tk.Button(btn_frame, text="Select All", command=self.select_all).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Deselect All", command=self.deselect_all).pack(side="left", padx=5)

        # Scrollable Frame for Checkboxes
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(container)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.check_vars = {}
        
        # Buttons
        self.btn_auto = tk.Button(self.root, text="START AUTO UNFOLLOW", bg="red", fg="white", font=("Arial", 12, "bold"), command=self.on_start_auto)
        self.btn_auto.pack(pady=5, fill="x", padx=20)
        
        self.btn_manual = tk.Button(self.root, text="MANUAL MODE (Open Links)", bg="blue", fg="white", font=("Arial", 12, "bold"), command=self.on_start_manual)
        self.btn_manual.pack(pady=5, fill="x", padx=20)

        # Initial Show
        self.show_list("unfollowers")

    def show_list(self, list_type):
        # Clear existing checkboxes
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.check_vars = {}
        
        if list_type == "unfollowers":
            users = self.unfollowers
            self.btn_unfollowers.config(relief="sunken", bg="#ddd")
            self.btn_fans.config(relief="raised", bg="#f0f0f0")
            self.lbl_info.config(text="Select users to Unfollow:")
            self.btn_auto.config(state="normal", bg="red") # Enable Auto Unfollow
        else:
            users = self.fans
            self.btn_unfollowers.config(relief="raised", bg="#f0f0f0")
            self.btn_fans.config(relief="sunken", bg="#ddd")
            self.lbl_info.config(text="Select users (Manual Mode recommended):")
            self.btn_auto.config(state="disabled", bg="gray") # Disable Auto Unfollow for Fans (Safety)

        for user in users:
            var = tk.BooleanVar()
            
            display_text = user
            is_processed = user in self.processed_users
            
            if is_processed:
                display_text += " (Opened)"
            
            chk = tk.Checkbutton(self.scrollable_frame, text=display_text, variable=var)
            if is_processed:
                chk.config(fg="gray")
                
            chk.pack(anchor="w")
            self.check_vars[user] = var

    def select_all(self):
        for var in self.check_vars.values():
            var.set(True)

    def deselect_all(self):
        for var in self.check_vars.values():
            var.set(False)

    def get_selected(self):
        return [user for user, var in self.check_vars.items() if var.get()]

    def on_start_auto(self):
        self.selected_users = self.get_selected()
        if not self.selected_users:
            messagebox.showwarning("Warning", "No users selected!")
            return
        
        confirm = messagebox.askyesno("Confirm", f"Are you sure you want to AUTO unfollow {len(self.selected_users)} users?")
        if confirm:
            self.mode = "auto"
            self.root.destroy()

    def on_start_manual(self):
        self.selected_users = self.get_selected()
        if not self.selected_users:
            messagebox.showwarning("Warning", "No users selected!")
            return
        
        self.mode = "manual"
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.selected_users, getattr(self, 'mode', None)

class InstagramBot:
    def __init__(self):
        print("Initializing Chrome with persistent profile...")
        service = Service(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        
        # Use a persistent profile to save login session
        profile_dir = os.path.abspath(CHROME_PROFILE_PATH)
        options.add_argument(f"user-data-dir={profile_dir}")
        
        # Stability options to prevent "DevToolsActivePort file doesn't exist" error
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--disable-gpu")
        
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def _log(self, message, logger=None):
        print(message)
        if logger:
            logger(message)

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass

    def _is_stop_requested(self, should_stop):
        return bool(should_stop and should_stop())

    def _wait_between_users(self, wait_time, should_stop, logger=None):
        self._log(f"Waiting {wait_time} seconds before next user...", logger)
        for _ in range(wait_time):
            if self._is_stop_requested(should_stop):
                self._log("Stop requested during wait. Ending auto run.", logger)
                return True
            time.sleep(1)
        return False

    def check_login(self, logger=None):
        self._log("Checking login status...", logger)
        self.driver.get("https://www.instagram.com/")
        time.sleep(5)

        # Check if we are on the login page or logged in
        try:
            # If we see the "Search" or "Profile" icon, we are logged in.
            # Or check if "Log In" button exists.
            if "login" in self.driver.current_url:
                self._log("Not logged in.", logger)
                messagebox.showinfo("Login Required", "Please log in to Instagram in the opened browser.\n\nOnce logged in, click OK to continue.")
            else:
                self._log("Already logged in!", logger)
        except Exception as e:
            self._log(f"Login check warning: {e}", logger)

    def unfollow_user(self, user, logger=None):
        self._log(f"Navigating to profile: {user}", logger)
        self.driver.get(f"https://www.instagram.com/{user}/")
        
        try:
            # Wait for "Following" button
            # The button text might be "Following" or "Requested"
            # We look for a button that indicates we are following them.
            # Instagram classes are obfuscated, so XPATH with text is often more reliable but language dependent.
            # Assuming English interface.
            
            time.sleep(random.randint(3, 6)) # Human-like delay before action

            following_btn = None
            possible_texts = ["Following", "Requested"]
            
            for text in possible_texts:
                try:
                    following_btn = self.driver.find_element(By.XPATH, f"//button[div/div[text()='{text}']]")
                    break
                except Exception:
                    try:
                        # Try simpler structure
                        following_btn = self.driver.find_element(By.XPATH, f"//button[text()='{text}']")
                        break
                    except Exception:
                        continue
            
            if following_btn:
                following_btn.click()
                time.sleep(2) # Wait for modal

                # Confirm Unfollow
                unfollow_confirm = self.driver.find_element(By.XPATH, "//button[text()='Unfollow']")
                unfollow_confirm.click()
                self._log(f"Successfully unfollowed {user}", logger)
                return True
            else:
                self._log(f"Could not find Following button for {user}. Maybe already unfollowed?", logger)
                return False

        except Exception as e:
            self._log(f"Error unfollowing {user}: {e}", logger)
            return False

    def run(self, users_to_unfollow, min_wait=30, max_wait=60, logger=None, should_stop=None, show_dialog=True):
        self.check_login(logger=logger)
        
        count = 0
        total = len(users_to_unfollow)
        
        self._log(f"Starting automation for {total} users...", logger)

        for i, user in enumerate(users_to_unfollow):
            if self._is_stop_requested(should_stop):
                self._log("Stop requested. Ending auto run.", logger)
                break

            self._log(f"[{i+1}/{total}] Processing {user}...", logger)
            success = self.unfollow_user(user, logger=logger)
            
            if success:
                count += 1
                
            # --- THE MAGIC WAIT ---
            # Random sleep between min_wait and max_wait seconds
            if i < total - 1: # Don't wait after the last one
                wait_time = random.randint(min_wait, max_wait)
                interrupted = self._wait_between_users(wait_time, should_stop, logger=logger)
                if interrupted:
                    break

        self._log(f"Finished. Unfollowed {count} users.", logger)
        if show_dialog:
            messagebox.showinfo("Done", f"Finished! Unfollowed {count} users.")
        self.close()

    def run_manual(self, users_to_process, batch_size=20, logger=None):
        self.check_login(logger=logger)
        self.processed_users = load_processed_users()
        
        # Simple GUI for Manual Control
        control_root = tk.Tk()
        control_root.title("Manual Mode Controller")
        control_root.geometry("300x250")
        control_root.attributes('-topmost', True) # Keep on top

        self.current_index = 0
        self.batch_size = batch_size
        
        lbl_count = tk.Label(control_root, text=f"Total Selected: {len(users_to_process)}", font=("Arial", 12))
        lbl_count.pack(pady=10)
        
        lbl_status = tk.Label(control_root, text="Ready to start.", fg="blue")
        lbl_status.pack(pady=5)

        def open_next_batch():
            start = self.current_index
            end = min(start + self.batch_size, len(users_to_process))
            
            if start >= len(users_to_process):
                messagebox.showinfo("Done", "All users processed.")
                return

            current_batch = users_to_process[start:end]
            self._log(f"Opening batch: {current_batch}", logger)
            
            for user in current_batch:
                # Open new tab
                self.driver.execute_script(f"window.open('https://www.instagram.com/{user}/', '_blank');")
                self.processed_users.add(user)
                time.sleep(0.5) # Small delay to prevent browser choking
            
            save_processed_users(self.processed_users)
            self.current_index = end
            lbl_status.config(text=f"Opened {start+1} - {end}")
            
            if self.current_index >= len(users_to_process):
                btn_next.config(state="disabled", text="All Done")

        btn_next = tk.Button(control_root, text=f"Open Next {self.batch_size} Profiles", bg="green", fg="white", font=("Arial", 12, "bold"), command=open_next_batch)
        btn_next.pack(pady=20, fill="x", padx=20)
        
        tk.Label(control_root, text="(Clicking this will open 20 tabs)").pack()

        control_root.mainloop()

if __name__ == "__main__":
    # 1. Get Instagram Data
    unfollowers, fans = get_instagram_data()

    if unfollowers or fans:
        # 2. Open GUI to Select Users
        app = UserSelectionApp(unfollowers, fans)
        selected_users, mode = app.run()

        # 3. Run Bot if users selected
        if selected_users and mode:
            bot = InstagramBot()
            if mode == "auto":
                bot.run(selected_users)
            elif mode == "manual":
                bot.run_manual(selected_users)
        else:
            print("No users selected or cancelled.")
    else:
        print("No data found or error loading files.")

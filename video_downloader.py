import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from yt_dlp import YoutubeDL
import os
import threading
from datetime import datetime
import time
import json
import sqlite3
import tempfile
import shutil

class VideoDownloader:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Advanced Video Downloader")
        self.setup_variables()
        self.create_gui()
        self.available_formats = {}
        # Try sqlite first, then json if not found
        self.cookies_file = 'cookies.sqlite' if os.path.exists('cookies.sqlite') else 'cookies.json'
        self.load_cookies()
        
    def setup_variables(self):
        self.url_var = tk.StringVar()
        self.output_dir_var = tk.StringVar()
        self.output_dir_var.set(os.path.join(os.path.expanduser("~"), "Downloads"))
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.progress_var = tk.DoubleVar()
    
    def clean_url(self, url):
        """Remove playlist parameters from YouTube URLs"""
        if 'youtube.com' in url or 'youtu.be' in url:
            # Remove list parameter and everything after it
            if '&list=' in url:
                url = url.split('&list=')[0]
            elif '?list=' in url and '?v=' not in url:
                # If it's ONLY a playlist URL, keep it
                pass
            self.status_var.set("Cleaned playlist parameters from URL")
        return url
        
    def load_cookies(self):
        """Load cookies from file, supporting both JSON and SQLite formats"""
        self.cookies_loaded = False
        if not os.path.exists(self.cookies_file):
            self.cookies = None
            self.status_var.set("No cookies file found")
            return

        try:
            # First try JSON format
            try:
                with open(self.cookies_file, 'r') as f:
                    self.cookies = json.load(f)
                    self.cookies_loaded = True
                    self.status_var.set("JSON Cookies loaded successfully")
                    return
            except json.JSONDecodeError:
                pass  # Not a JSON file, try SQLite

            # Try SQLite format
            if self.cookies_file.endswith('.sqlite'):
                try:
                    # Create a temporary copy of the SQLite file
                    temp_cookie_file = os.path.join(tempfile.gettempdir(), 'cookies_temp.sqlite')
                    shutil.copy2(self.cookies_file, temp_cookie_file)

                    # Connect to the temporary SQLite database
                    conn = sqlite3.connect(temp_cookie_file)
                    cursor = conn.cursor()
                    
                    # Extract YouTube cookies
                    cursor.execute("""
                        SELECT name, value, host
                        FROM moz_cookies
                        WHERE host LIKE '%youtube.com'
                    """)
                    
                    cookies_data = cursor.fetchall()
                    conn.close()
                    
                    # Convert to format yt-dlp expects
                    if cookies_data:
                        cookie_txt = os.path.join(tempfile.gettempdir(), 'cookies.txt')
                        with open(cookie_txt, 'w') as f:
                            for name, value, host in cookies_data:
                                f.write(f"{host}\tTRUE\t/\tFALSE\t2597573456\t{name}\t{value}\n")
                        
                        self.cookies_file = cookie_txt
                        self.cookies_loaded = True
                        self.status_var.set("SQLite Cookies loaded successfully")
                    else:
                        self.status_var.set("No YouTube cookies found in SQLite file")
                    
                    # Clean up temporary SQLite copy
                    try:
                        os.remove(temp_cookie_file)
                    except:
                        pass

                except sqlite3.Error as e:
                    self.status_var.set(f"SQLite error: {str(e)}")
                    self.cookies = None
            
        except Exception as e:
            self.status_var.set(f"Error loading cookies: {str(e)}")
            self.cookies = None

    def create_gui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # URL Entry
        ttk.Label(main_frame, text="Enter Video URL:").grid(row=0, column=0, sticky=tk.W)
        url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=50)
        url_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        # Format List
        ttk.Label(main_frame, text="Available Formats:").grid(row=1, column=0, sticky=tk.W)
        self.formats_listbox = tk.Listbox(main_frame, height=15, width=80)
        self.formats_listbox.grid(row=2, column=0, columnspan=3, padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.formats_listbox.yview)
        scrollbar.grid(row=2, column=3, sticky=(tk.N, tk.S))
        self.formats_listbox.configure(yscrollcommand=scrollbar.set)
        
        # Output Directory
        ttk.Label(main_frame, text="Output Directory:").grid(row=3, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.output_dir_var, width=50).grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(main_frame, text="Browse", command=self.choose_directory).grid(row=3, column=2, padx=5, pady=5)
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, mode='determinate', variable=self.progress_var)
        self.progress_bar.grid(row=4, column=0, columnspan=3, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        # Status label
        ttk.Label(main_frame, textvariable=self.status_var).grid(row=5, column=0, columnspan=3, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        ttk.Button(button_frame, text="Fetch Formats", command=self.fetch_formats_thread).grid(row=0, column=0, padx=5)
        ttk.Button(button_frame, text="Download", command=self.download_video_thread).grid(row=0, column=1, padx=5)
        ttk.Button(button_frame, text="Load Cookies", command=self.select_cookies).grid(row=0, column=2, padx=5)
        ttk.Button(button_frame, text="Exit", command=self.root.quit).grid(row=0, column=3, padx=5)

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    progress = (downloaded / total) * 100
                    self.progress_var.set(progress)
                    self.status_var.set(f"Downloading: {progress:.1f}%")
            except Exception:
                pass
        elif d['status'] == 'finished':
            self.status_var.set("Download completed! Processing video...")
            self.progress_var.set(100)
        elif d['status'] == 'error':
            self.status_var.set("Error occurred during download")

    def format_display_string(self, fmt):
        resolution = fmt.get('resolution', 'Unknown')
        filesize = fmt.get('filesize', 0)
        format_id = fmt.get('format_id', 'Unknown')
        ext = fmt.get('ext', 'Unknown')
        vcodec = fmt.get('vcodec', 'Unknown')
        acodec = fmt.get('acodec', 'Unknown')
        
        if filesize:
            if filesize < 1024:
                filesize_str = f"{filesize}B"
            elif filesize < 1024*1024:
                filesize_str = f"{filesize/1024:.1f}KB"
            elif filesize < 1024*1024*1024:
                filesize_str = f"{filesize/(1024*1024):.1f}MB"
            else:
                filesize_str = f"{filesize/(1024*1024*1024):.1f}GB"
        else:
            filesize_str = "Unknown"
            
        return f"ID: {format_id} | Resolution: {resolution} | Size: {filesize_str} | Format: {ext} | Video: {vcodec} | Audio: {acodec}"

    def get_ydl_opts(self, download=False):
        opts = {
            'verbose': True,
            'ignoreerrors': True,
            'no_warnings': False,
            'extract_flat': False,
            'quiet': False,
            'socket_timeout': 30,
            'retries': 5,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            # KEY FIXES for the 366 parts issue:
            'concurrent_fragments': 1,  # Download fragments sequentially
            'noprogress': False,
            'http_chunk_size': 10485760,  # 10MB chunks
        }
        
        if self.cookies_loaded:
            opts['cookiefile'] = self.cookies_file
        
        if download:
            opts['progress_hooks'] = [self.progress_hook]
        
        if not download:
            opts.update({
                'dump_single_json': True,
                'format': None,
            })
            
        return opts

    def fetch_formats(self):
        self.formats_listbox.delete(0, tk.END)
        url = self.url_var.get()
        
        if not url:
            messagebox.showerror("Error", "Please enter a video URL")
            return

        # Clean the URL to remove playlist parameters
        url = self.clean_url(url)
        self.url_var.set(url)  # Update the display with cleaned URL

        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                self.status_var.set(f"Fetching available formats (Attempt {retry_count + 1}/{max_retries})...")
                
                ydl_opts = self.get_ydl_opts(download=False)
                
                with YoutubeDL(ydl_opts) as ydl:
                    try:
                        info = ydl.extract_info(url, download=False)
                    except Exception as e:
                        self.status_var.set(f"First attempt failed, trying alternate method...")
                        ydl_opts.update({
                            'extract_flat': True,
                            'force_generic_extractor': True
                        })
                        info = ydl.extract_info(url, download=False)

                if info is None:
                    raise Exception("Could not fetch video information - video might be private or unavailable")

                formats = info.get('formats', [])
                if not formats:
                    formats = info.get('requested_formats', [])
                    
                if not formats:
                    raise Exception("No formats available for this video")

                common_resolutions = ["144p", "240p", "360p", "480p", "720p", "1080p", "1440p", "2160p"]
                filtered_formats = []
                
                for fmt in formats:
                    if fmt.get('vcodec') != 'none':
                        filtered_formats.append(fmt)
                
                if not filtered_formats:
                    filtered_formats = formats
                
                filtered_formats.sort(
                    key=lambda x: (
                        common_resolutions.index(x.get('resolution', '0p')) if x.get('resolution', '0p') in common_resolutions else -1,
                        x.get('filesize', 0) if x.get('filesize') is not None else 0
                    ),
                    reverse=True
                )
                
                self.formats_listbox.delete(0, tk.END)
                self.available_formats.clear()
                
                for fmt in filtered_formats:
                    display_string = self.format_display_string(fmt)
                    self.formats_listbox.insert(tk.END, display_string)
                    self.available_formats[display_string] = fmt
                
                self.status_var.set(f"Found {len(filtered_formats)} formats")
                return True
                
            except Exception as e:
                retry_count += 1
                error_msg = str(e)
                self.status_var.set(f"Attempt {retry_count} failed: {error_msg}")
                
                if retry_count < max_retries:
                    time.sleep(2)
                    continue
                else:
                    self.status_var.set("Failed to fetch formats after all attempts")
                    detailed_error = (
                        f"Error Details:\n"
                        f"- URL: {url}\n"
                        f"- Error: {error_msg}\n"
                        f"- Attempts made: {retry_count}\n\n"
                        f"Possible solutions:\n"
                        f"1. Check if the video is private or age-restricted\n"
                        f"2. Verify the URL is correct\n"
                        f"3. Check your internet connection\n"
                        f"4. Try updating yt-dlp using 'pip install --upgrade yt-dlp'\n"
                        f"5. Wait a few minutes and try again"
                    )
                    messagebox.showerror("Error", detailed_error)
                    return False

    def download_video(self):
        selected = self.formats_listbox.curselection()
        if not selected:
            messagebox.showerror("Error", "Please select a format before downloading.")
            return
            
        selected_format = self.formats_listbox.get(selected[0])
        format_data = self.available_formats.get(selected_format)
        if not format_data:
            messagebox.showerror("Error", "Invalid format selected")
            return
        
        format_id = format_data.get('format_id')
        url = self.url_var.get()
        
        # Clean the URL again just in case
        url = self.clean_url(url)
        
        output_dir = self.output_dir_var.get()
        
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ydl_opts = self.get_ydl_opts(download=True)
            ydl_opts.update({
                # FIXED: Better format selection to avoid fragmented streams
                'format': f"{format_id}+bestaudio[ext=m4a]/best[ext=mp4]/{format_id}/best",
                'outtmpl': os.path.join(output_dir, f'%(title)s_{timestamp}.%(ext)s'),
                'merge_output_format': 'mp4',  # Ensure final output is mp4
            })

            with YoutubeDL(ydl_opts) as ydl:
                self.status_var.set("Starting download...")
                self.progress_var.set(0)
                ydl.download([url])
                self.status_var.set("Download and processing completed!")
                messagebox.showinfo("Success", "Download completed successfully!")

        except Exception as e:
            self.status_var.set(f"Download failed: {e}")
            messagebox.showerror("Error", f"An error occurred during download: {e}")

    def choose_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir_var.set(directory)

    def select_cookies(self):
        file_path = filedialog.askopenfilename(filetypes=[("Cookie files", "*.json *.sqlite")])
        if file_path:
            self.cookies_file = file_path
            self.load_cookies()

    def fetch_formats_thread(self):
        threading.Thread(target=self.fetch_formats, daemon=True).start()

    def download_video_thread(self):
        threading.Thread(target=self.download_video, daemon=True).start()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    downloader = VideoDownloader()
    downloader.run()
=========================================
      DIY PHOTOBOOTH SOFTWARE
=========================================

This software runs a kiosk-style photobooth using a Canon camera connected to a Windows PC via digiCamControl.
NOTE: This project was built specifically for the author's Canon + Windows + digiCamControl combo.
If you use another camera brand or OS, see README.md for hardware alternatives and where to adapt the code.

-----------------------------------------
1. PREREQUISITES & INSTALLATION
-----------------------------------------

1. Install Python 3.10+
   Download from python.org and check "Add Python to PATH" during installation.

2. Install digiCamControl
   Download and install from digicamcontrol.com (handles USB camera control & Live View).
   Make sure Canon EOS Utility is closed so it does not conflict over USB.

3. Install Required Python Libraries
   Open PowerShell or Command Prompt in this folder and run:
   pip install -r requirements.txt

4. Configure Environment Variables (.env)
   Copy ".env.example" to ".env" and fill in your Cloudinary credentials
   (CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET).
   NOTE: If your Windows username contains spaces, set TEMP_CAPTURE_PATH in .env
   to a writable path without spaces (e.g., D:\photobooth_temp\temp_capture.jpg).

-----------------------------------------
2. SETUP & CONFIGURATION
-----------------------------------------

1. Connect Your Camera
   Connect your Canon camera to your PC using a USB cable and turn it ON.
   (Recommended: set camera to Manual Focus or use capturenoaf, shoot JPEG, disable auto-power-off.)

2. Configure digiCamControl
   - Open digiCamControl and wait for it to detect your camera.
   - Go to File -> Settings -> Webserver.
   - Check "Use web server", set Port to 5513, and check "Allow interaction via webserver".
   - Click OK, then restart digiCamControl and leave it running in the background.

3. Customize Your Frames
   - Place transparent RGBA PNG frames in static\assets\ named:
     * frame_2cut.png
     * frame_3cut.png
     * frame_4cut.png
   - Photo windows MUST be truly transparent (alpha = 0), not white-filled.

-----------------------------------------
3. HOW TO USE
-----------------------------------------

1. Start the Server:
   python app.py

2. Open Browser Kiosk:
   Open Chrome/Edge -> go to http://127.0.0.1:5000 -> press F11 for Full Screen.

3. Take Photos:
   - Tap "Start" -> choose 2, 3, or 4 Photos -> tap "Start" on the instructions card.
   - Wait for the 10-second countdown per shot, then scan the QR code to download!
   - Local backups are also saved in the processed\ folder.

For full architecture notes, API docs, and non-Canon camera alternatives, read README.md.

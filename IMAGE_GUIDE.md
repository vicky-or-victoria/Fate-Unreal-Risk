# 🖼️ Servant Image Guide

This guide explains how to add images to your Fate servants in the bot.

## How It Works

Each servant in `servants_data.py` now has an `image_url` field. When set to a valid URL, the bot will display the image in embeds when:
- A servant is summoned
- Viewing servants with `/servants`
- Admin assigns a servant

## Adding Images

### Step 1: Find Images

You can find Fate servant images from:
- **Fate/Grand Order Wiki**: https://fategrandorder.fandom.com
- **Type-Moon Wiki**: https://typemoon.fandom.com
- **Official artwork** from Type-Moon
- **Fan art** (with proper permissions)

### Step 2: Host Images

You need to host images at a publicly accessible URL. Options include:

#### Option A: Imgur (Recommended)
1. Go to https://imgur.com
2. Upload your image
3. Right-click the image → "Copy image address"
4. Use this URL

#### Option B: Discord CDN
1. Upload image to any Discord channel
2. Right-click the image → "Copy link"
3. Use this URL (starts with `https://cdn.discordapp.com/`)

#### Option C: GitHub
1. Upload to a GitHub repository
2. Use the raw image URL
3. Format: `https://raw.githubusercontent.com/username/repo/main/image.png`

#### Option D: Cloud Storage
- Google Drive (must set to public)
- Dropbox (must generate public link)
- AWS S3 (must set bucket to public)

### Step 3: Update servants_data.py

Open `servants_data.py` and find the servant you want to add an image to:

**Before:**
```python
{"name": "Gilgamesh", "class": "Archer", "description": "...", "noble_phantasm": "Gate of Babylon", "image_url": None},
```

**After:**
```python
{"name": "Gilgamesh", "class": "Archer", "description": "...", "noble_phantasm": "Gate of Babylon", "image_url": "https://i.imgur.com/example.png"},
```

### Step 4: Restart the Bot

After adding URLs, restart the bot:
```bash
python bot.py
```

## Example Setup

Here's an example with images added for some servants:

```python
"EX": [
    {
        "name": "Gilgamesh", 
        "class": "Archer", 
        "description": "The King of Heroes, possessor of all the world's treasures", 
        "noble_phantasm": "Gate of Babylon", 
        "image_url": "https://i.imgur.com/gilgamesh.png"
    },
    {
        "name": "Karna", 
        "class": "Lancer", 
        "description": "Son of the Sun God, Hero of Charity", 
        "noble_phantasm": "Vasavi Shakti", 
        "image_url": "https://cdn.discordapp.com/attachments/123/456/karna.png"
    },
],
"S": [
    {
        "name": "Artoria Pendragon", 
        "class": "Saber", 
        "description": "The Once and Future King", 
        "noble_phantasm": "Excalibur", 
        "image_url": "https://i.imgur.com/saber.png"
    },
    {
        "name": "Richard I", 
        "class": "Saber", 
        "description": "Richard the Lionheart", 
        "noble_phantasm": "Excalibur", 
        "image_url": "https://i.imgur.com/richard.png"
    },
],
```

## Tips

### Image Requirements
- **Format**: PNG, JPG, JPEG, GIF, WEBP
- **Size**: Discord recommends under 8MB
- **Dimensions**: 400x400 to 1000x1000 works well for embeds
- **Aspect Ratio**: Square or portrait works best

### Best Practices
1. **Use consistent image sizes** across all servants for a uniform look
2. **Test URLs** before adding them (paste in browser to verify)
3. **Use HTTPS URLs** (required by Discord)
4. **Backup your images** in case the hosting service changes
5. **Credit artists** if using fan art

### Finding Official Art

For official Fate/Grand Order character art:
1. Go to https://fategrandorder.fandom.com
2. Search for the servant
3. Look for "Ascension" images
4. Right-click → "Open image in new tab"
5. Copy the URL from the address bar

### Troubleshooting

**Image not showing:**
- Verify the URL works (paste in browser)
- Ensure URL starts with `https://`
- Check if the image host requires authentication
- Try re-uploading to Imgur

**Image too large:**
- Discord embeds might not display very large images
- Resize to 800x800 or smaller
- Compress using tools like TinyPNG

**URL broken:**
- Image hosts might delete old images
- Re-upload and update the URL
- Consider using multiple backup URLs

## Quick Reference Card Format

When adding images, you can organize them by creating a separate file:

Create `image_urls.py`:
```python
IMAGE_URLS = {
    "Gilgamesh": "https://i.imgur.com/gilgamesh.png",
    "Artoria Pendragon": "https://i.imgur.com/saber.png",
    "Richard I": "https://i.imgur.com/richard.png",
    # ... more servants
}
```

Then in `servants_data.py`:
```python
from image_urls import IMAGE_URLS

# In your servant definitions:
{"name": "Gilgamesh", ..., "image_url": IMAGE_URLS.get("Gilgamesh")},
```

This keeps your image URLs organized and easy to update!

## Copyright Notice

⚠️ **Important**: Make sure you have the right to use any images you add:
- Official Type-Moon artwork is copyrighted
- Fan art requires artist permission
- Consider using official sources or creating your own
- Give credit where appropriate

## Need Help?

If you have issues adding images:
1. Check that your URL is valid and publicly accessible
2. Verify the image format is supported
3. Ensure you've saved `servants_data.py` after editing
4. Restart the bot completely
5. Check the bot console for any error messages

---

Happy summoning! ✨

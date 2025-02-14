# Return Dislikes to my YT Channel

### Recommended Python Version
Python 3.7 or later.

Steps to Use the Script:
-------------------
1. **Set Up Google Cloud Project**:
   - Go to the [Google Cloud Console](https://console.cloud.google.com/).
   - Enable the "YouTube Data API v3" for your project.
   - Create OAuth 2.0 credentials and download the `client_secrets.json` file.

2. **Install Dependencies**:
   - Install the required Python libraries: `pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client`
   
4. **Prepare the Script**:
   - Save the script in a file, e.g., `update_youtube_descriptions.py`.
   - Rename and place your `client_secrets.json` file in the same directory as the script.

What does this script do?
-------------------
This script automates the process of tracking and updating YouTube video dislikes by:
   - Fetching all videos from your YouTube channel (excluding private ones)
   - Retrieving the dislike count for each video
   - Finding (or creating) a comment on each video that displays the dislike count
   - Updating the comment only if the dislike count has changed
   - Caching videos to reduce API usage (efficient quota management)
   - Saving progress to prevent unnecessary reprocessing

Who Is This Script For?
-------------------
If you:
   - Own a YouTube channel
   - Want to display dislike counts in a pinned comment
   - Want a semi-automatic solution (you must run the script manually)

Then this script could be your solution.

How It Works (Step by Step)
-------------------
1. **Authentication:**
   - The script logs into your YouTube account using OAuth 2.0.
   - If it’s the first time running, a browser window opens to grant permissions.
   - Credentials are saved for future runs (no need to log in every time).

2. **Fetching Videos:**
   - It checks your channel for videos where **comments are enabled.**
   - Uses **cached data** if available to save API quota.

3. **Retrieving Dislikes:**
   - For each video, it retrieves the current **dislike count** from YouTube’s API.

4. **Updating or Creating a Comment:**
   - The script looks for an existing comment **made by you.**
   - If found:
      - If the dislike count has changed (or has not yet been published), it **updates the comment** with:
        ```
        Dislikes: 120  
        Updated (YY-MM-DD): 2024-02-14
        ```
      - Previous content should be present below the comment **update date.**
      - Otherwise, it **leaves the comment unchanged** to avoid unnecessary edits.
   - If no comment exists, it **creates a new one.**

5. **Progress Tracking & Error Handling:**
   - The script **saves progress** after each video, so if it’s interrupted, it resumes where it left off.
   - If **quota is exceeded,** it **exits gracefully** and lets you continue the next day.
   - **Errors are handled interactively** (retry, skip, or exit).
  
Important Notes
-------------------
   - YouTube dislikes are private – only you (the channel owner) can see them.
   - The script does not modify video titles, descriptions, or settings – it only updates comments.
   - Google API quotas apply – if you run into quota limits, wait 24 hours before trying again.
   - Videos where comments are disabled are skipped automatically.
   - This script was mostly made written with immense help from AI. Tested for a couple of weeks, inspected and slightly modified code manually, some formatting has been done manually.

### How Many Videos Can This Script Process in a Day?
YouTube’s API **quota limit** is **10,000 units per day**, and each API request **costs a certain amount of quota**. 

---

### API Costs  
| **Action** | **API Request Type** | **Quota Cost per Request** |  
|------------|----------------------|---------------------------|  
| Fetch videos from your channel | `search.list` | **100** |  
| Get video details (status, stats) | `videos.list` | **1** per video |  
| Retrieve existing comments | `commentThreads.list` | **1** per video |  
| Update an existing comment | `comments.update` | **50** |  
| Create a new comment | `commentThreads.insert` | **50** |  

---

### Estimated Video Processing Capacity  

#### Case 1: Updating an existing comment  
If the script **only updates existing comments** (no new comments needed), for each video it makes:  
1. `search.list` (100) → **Once for all videos**  
2. `videos.list` (1)  
3. `commentThreads.list` (1)  
4. `comments.update` (50)  

**Total cost per video:** `1 + 1 + 50 = 52`  

**Videos processed per day:**  
```
10,000 ÷ 52 ≈ 192 videos/day
```

---

#### Case 2: Creating a new comment  
If the script **creates a new comment instead of updating**, for each video it makes:  
1. `search.list` (100) → **Once for all videos**  
2. `videos.list` (1)  
3. `commentThreads.list` (1)  
4. `commentThreads.insert` (50)  

**Total cost per video:** `1 + 1 + 50 = 52`  

**Videos processed per day:**  
```
10,000 ÷ 52 ≈ 192 videos/day
```

---

#### Case 3: Checking videos, but not updating anything  
If the script **only fetches videos and checks dislikes** but **does NOT update or create comments**, it makes:  
1. `search.list` (100) → **Once for all videos**  
2. `videos.list` (1)  
3. `commentThreads.list` (1)  

**Total cost per video:** `1 + 1 = 2`  

**Videos processed per day:**  
```
10,000 ÷ 2 = 5,000 videos/day
```
**However, this does NOT include comment updates!**  

---
  
| **Scenario** | **Videos Processed Per Day (10,000 Quota)** |  
|-------------|--------------------------------|  
| **Only checking dislikes, no updates** | **Up to 5,000** |  
| **Updating existing comments** | **~192** |  
| **Creating new comments** | **~192** |  

If **some videos do not need updates**, you may process **more than 192 videos** per day.

Known issues:
-------------------
   - Does not pin comments (yet!)
   - You must use `Task Scheduler` (in Windows), or some other 3rd party form of automation to start the script automatically.
   - You tell me

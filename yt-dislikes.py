from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
import json
import re
import os
import pickle
import sys
import ctypes
import subprocess

# Define the scopes required for YouTube Data API
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

def load_channel_owner_id():
    """Load the channel owner's ID from a file if it exists."""
    if os.path.exists('channel_owner_id.json'):
        with open('channel_owner_id.json', 'r') as file:
            return json.load(file).get('channel_owner_id')
    return None

def save_channel_owner_id(channel_owner_id):
    """Save the channel owner's ID to a file."""
    with open('channel_owner_id.json', 'w') as file:
        json.dump({'channel_owner_id': channel_owner_id}, file)

def load_channel_owner_id():
    """Load the channel owner's ID from a file if it exists."""
    if os.path.exists('channel_owner_id.json'):
        with open('channel_owner_id.json', 'r') as file:
            return json.load(file).get('channel_owner_id')
    return None

def save_channel_owner_id(channel_owner_id):
    """Save the channel owner's ID to a file."""
    with open('channel_owner_id.json', 'w') as file:
        json.dump({'channel_owner_id': channel_owner_id}, file)

# Function to load videos marked for removal from a file
def load_videos_to_remove():
    if os.path.exists('videos_to_remove.json'):
        with open('videos_to_remove.json', 'r') as file:
            return set(json.load(file))  # Convert the list back to a set
    return set()

# Function to save videos marked for removal to a file
def save_videos_to_remove(videos_to_remove):
    with open('videos_to_remove.json', 'w') as file:
        json.dump(list(videos_to_remove), file)

def load_progress():
    """Load the progress from a file. If the file is empty or contains invalid JSON, return an empty dict."""
    if os.path.exists('progress.json'):
        with open('progress.json', 'r') as file:
            content = file.read().strip()

        if not content:
            try:
                os.remove('progress.json')
            except Exception as e:
                print(f"Could not erase progress.json. Please attempt to do so manually.\n {e}")
            return {}

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                os.remove('progress.json')
            except Exception as e:
                print(f"Could not erase progress.json. Please attempt to do so manually.\n {e}")
            return {}
    return {}

def save_progress(last_video_id):
    """Save the progress to a file."""
    with open('progress.json', 'w') as file:
        json.dump({"last_video_id": last_video_id}, file)

def authenticate():
    """Authenticate and return a YouTube API client."""
    creds = None

    # Load existing credentials if available
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # Check if credentials are invalid or revoked
    if not creds or not creds.valid:
        try:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())  # Attempt to refresh token
            else:
                raise RefreshError  # Force re-authentication if no refresh token is available
        except RefreshError:  # Catches "invalid_grant" errors
            print("Token is expired or revoked. Removing old credentials and re-authenticating...")
            if os.path.exists('token.pickle'):
                os.remove('token.pickle')  # Delete corrupted token file
            creds = None  # Force re-authentication

        # If credentials are still invalid, prompt login
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=8080)

        # Save the new credentials
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('youtube', 'v3', credentials=creds)

def get_dislike_count(youtube, video_id):
    """Retrieve the dislike count for a video."""
    try:
        response = youtube.videos().list(
            part='statistics',
            id=video_id
        ).execute()

        stats = response['items'][0]['statistics']
        return int(stats.get('dislikeCount', 0))
    except HttpError as e:
        result = handle_http_error(e)
        if result == 'retry':
            return get_dislike_count(youtube, video_id)
        elif result == 'skip':
            return None
        else:
            raise e

def create_comment(youtube, video_id, text):
    """Create a new top-level comment."""
    try:
        response = youtube.commentThreads().insert(
            part='snippet',
            body={
                'snippet': {
                    'videoId': video_id,
                    'topLevelComment': {
                        'snippet': {
                            'textOriginal': text
                        }
                    }
                }
            }
        ).execute()
        print(f"Created new comment for video {video_id}.")
        return response['id']
    except HttpError as e:
        result = handle_http_error(e)
        if result == 'retry':
            return create_comment(youtube, video_id, text)
        elif result == 'skip':
            return None
        else:
            raise e

def update_comment(youtube, comment_id, text):
    """Update an existing comment."""
    try:
        youtube.comments().update(
            part='snippet',
            body={
                'id': comment_id,
                'snippet': {
                    'textOriginal': text
                }
            }
        ).execute()
        print(f"Updated comment {comment_id}.")
    except HttpError as e:
        result = handle_http_error(e)
        if result == 'retry':
            update_comment(youtube, comment_id, text)
        elif result == 'skip':
            print(f"Skipping update for comment {comment_id}.")
        else:
            raise e

def handle_http_error(error):
    """Handle HTTP errors with retry, skip, or exit options."""
    if error.resp.status == 403:
        if "quotaExceeded" in str(error):
            print("Quota exceeded. Stopping further updates for today.")
            sys.exit(0)  # Exits gracefully. Relies on `main()` to save progress
        else:
            raise error  # Raise error to `main()`
    
    while True:
        print(f"HTTP error occurred: {error}.")
        print("Options: [R]etry | [S]kip | [E]xit")
        choice = input("Enter your choice: ").strip().lower()
        if choice in ('r', 'retry'):
            return 'retry'
        elif choice in ('s', 'skip'):
            return 'skip'
        elif choice in ('e', 'exit'):
            print("Exiting program.")
            sys.exit(0)
        else:
            print("Invalid choice. Please try again.")

def find_or_create_comment(youtube, video_id, dislike_count):
    """Find an existing comment by the channel owner or create a new one."""
    # Intended comment text with the new "Dislikes:" line and today's update date.
    today_date = datetime.today().strftime("%Y-%m-%d")
    intended_dislike_line = f"Dislikes: {dislike_count}"
    intended_date_line = f"Updated (YY-MM-DD): {today_date}"

    # Try to load the stored channel owner's ID
    channel_owner_id = load_channel_owner_id()

    # If the channel owner's ID is not stored, ask the user for it
    if channel_owner_id is None:
        print("Channel owner's ID not found.")
        channel_owner_id = input("Please enter the channel owner's ID: ").strip()
        save_channel_owner_id(channel_owner_id)
        print(f"Channel owner's ID saved as: {channel_owner_id}")

    try:
        # Check for existing comments by the channel owner
        response = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            textFormat='plainText',
            maxResults=100
        ).execute()

        for item in response.get('items', []):
            comment = item['snippet']['topLevelComment']
            author_channel_id = comment['snippet']['authorChannelId']['value']
            if author_channel_id == channel_owner_id:
                comment_id = comment['id']
                existing_text = comment['snippet']['textOriginal']

                # Split comment into lines to check existing update info
                lines = existing_text.split("\n")
                new_lines = []
                existing_dislikes = None

                for line in lines:
                    if line.startswith("Dislikes:"):
                        existing_dislikes = line
                    elif not line.startswith("Updated (YY-MM-DD):"):
                        new_lines.append(line)  # Keep everything except old update date

                # If the dislike count is already correct, **do nothing**
                if existing_dislikes == intended_dislike_line:
                    print(f"Dislike count is already correct for video {video_id}. No update needed.")
                    return comment_id

                # If the dislike count is incorrect, update the comment and refresh the update date
                # Print previous and new dislike count for debugging
                print(f"Previous {existing_dislikes}")
                print(f"Current {intended_dislike_line}")
                updated_text = f"{intended_dislike_line}\n{intended_date_line}\n" + "\n".join(new_lines)
                updated_text = updated_text.rstrip("\n")  # Remove trailing newlines
                update_comment(youtube, comment_id, updated_text)
                return comment_id

        # If no matching comment, create a new one
        new_comment_text = f"{intended_dislike_line}\n{intended_date_line}"
        return create_comment(youtube, video_id, new_comment_text)

    except HttpError as e:
        result = handle_http_error(e)
        if result == 'retry':
            return find_or_create_comment(youtube, video_id, dislike_count)
        elif result == 'skip':
            return None
        else:
            raise e
            
def get_videos(youtube):
    """Retrieve the new videos since the last run, excluding private videos."""
    cache_file = 'videos_cache.json'
    current_videos = []

    # Load existing cache if it exists
    if os.path.exists(cache_file):
        print("Loading videos from cache...")
        with open(cache_file, 'r') as file:
            cached_videos = json.load(file)
    else:
        cached_videos = []

    print("Fetching videos from YouTube API...")

    # If the cache is empty, we know we haven't fetched any videos yet, so we proceed normally
    if cached_videos:
        # Make a 1-video request to check if there are new videos
        request = youtube.search().list(
            part='id,snippet',
            forMine=True,
            type='video',
            maxResults=1
        )

        response = request.execute()
        latest_video_id = response['items'][0]['id']['videoId']
        latest_video_title = response['items'][0]['snippet']['title']

        # Compare the most recent video with the one in the cache
        cached_video_ids = {video['id'] for video in cached_videos}

        if latest_video_id not in cached_video_ids:
            # Ask the user how many new videos have been uploaded since the last run
            print(f"A new video is available: {latest_video_title}")
            new_video_count = int(input("How many new videos have been uploaded since the last run? "))

            # Fetch only the new videos based on user input
            page_token = None  # Start with no page token
            while new_video_count > 0:
                # Fetch the next batch of videos (adjust maxResults based on new_video_count)
                request = youtube.search().list(
                    part='id,snippet',
                    forMine=True,
                    type='video',
                    maxResults=min(new_video_count, 50),
                    pageToken=page_token  # Use the correct pagination token
                )

                response = request.execute()

                # Process the response and add new videos
                for item in response.get('items', []):
                    video_id = item['id']['videoId']
                    video_details = youtube.videos().list(
                        part='status',
                        id=video_id
                    ).execute()
                    status = video_details['items'][0]['status']

                    # Only add public or unlisted videos whose comments are not disabled
                    if (
                        status.get('privacyStatus') in {'public', 'unlisted'} and
                        status.get('commentStatus') != 'disabled' and
                        video_id not in cached_video_ids
                    ):
                        current_videos.append({
                            'id': video_id,
                            'title': item['snippet']['title']
                        })
                        new_video_count -= 1

                        # Save progress immediately after processing each video
                        with open(cache_file, 'w') as file:
                            json.dump(current_videos + cached_videos, file)

                    # If we have reached the most recent cached video, stop fetching
                    elif video_id in cached_video_ids:
                        print("Encountered cached video. Stopping API requests.")
                        new_video_count = 0
                        break
                # Get the nextPageToken for pagination
                page_token = response.get("nextPageToken", None)
                if not page_token:
                    break  # Stop looping if there are no more pages

            # After fetching new videos, update the cache list to be new videos prepended to the old ones.
            current_videos = current_videos + cached_videos

        else:
            print("No new videos uploaded since the last run.")
            current_videos = cached_videos

    else:
        print("No cached videos found. Fetching all videos from scratch.")
        # Proceed normally if there was no cached list
        page_token = None
        while True:
            request = youtube.search().list(
                part='id,snippet',
                forMine=True,
                type='video',
                maxResults=50,
                pageToken=page_token
            )

            response = request.execute()
            for item in response.get('items', []):
                video_id = item['id']['videoId']
                video_details = youtube.videos().list(
                    part='status',
                    id=video_id
                ).execute()
                status = video_details['items'][0]['status']

                # Only add public or unlisted videos whose comments are not disabled
                if status.get('privacyStatus') in {'public', 'unlisted'} and status.get('commentStatus') != 'disabled':
                    current_videos.append({
                        'id': video_id,
                        'title': item['snippet']['title']
                    })

            # Save progress after each API request
            with open(cache_file, 'w') as file:
                json.dump(current_videos, file)

            # Get the nextPageToken for pagination
            page_token = response.get("nextPageToken", None)
            if not page_token:
                break  # Stop looping if there are no more pages

    # Save updated list of videos to cache if there are new ones
    if current_videos and current_videos != cached_videos:
        print(f"Saved {len(current_videos)} videos to cache.")
    else:
        print("No new videos to save to cache.")

    return current_videos

def main():
    """Main function to update dislike counts in comments."""
    try:
        youtube = authenticate()

        # Fetch videos (this also loads cached videos from get_videos)
        videos = get_videos(youtube)

        # Load progress
        progress = load_progress()
        last_video_id = progress.get("last_video_id")
        start_processing = last_video_id is None

        # Load the videos to remove set from the previous run
        videos_to_remove = load_videos_to_remove()

        # Track video indices to be removed from the list
        videos_to_remove = set()

        for index, video in enumerate(videos):
            video_id = video['id']
            title = video['title']

            if not start_processing:
                if video_id == last_video_id:
                    start_processing = True
                continue

            print(f"Processing video: {title}")

            # Get the dislike count for the video
            dislike_count = get_dislike_count(youtube, video_id)
            if dislike_count is None:
                print(f"Skipping video {title} due to error.")
                continue

            # Find or create a comment and pin it
            try:
                find_or_create_comment(youtube, video_id, dislike_count)
            except HttpError as e:
                if "commentsDisabled" in str(e):
                    print(f"Comments disabled. Marking video {video_id} for removal.")
                    # Mark this video for removal by its index
                    videos_to_remove.add(index)
                elif "videoNotFound" in str(e):
                    print(f"Video deleted. Marking video {video_id} for removal.")
                    videos_to_remove.add(index)
                else:
                    raise e

            # Save progress after processing each video
            save_progress(video_id)
        
            # Check if it's the last video in the list and reset progress
            if index == len(videos) - 1:
                if os.path.exists('progress.json'):
                    os.remove('progress.json')
                    print(f"\nAll videos have been processed! Progress has been reset.")

        # Remove marked videos from the videos list by iterating in reverse
        for index in range(len(videos) - 1, -1, -1):  # From len-1 to 0 (inclusive)
            if index in videos_to_remove:
                videos.pop(index)

        # Save updated cache
        cache_file = 'videos_cache.json'
        with open(cache_file, 'w') as file:
            json.dump(videos, file)

        print("Updated cache saved successfully.")

        # Save the videos marked for removal to the file
        save_videos_to_remove(videos_to_remove)

    except HttpError as e:
        result = handle_http_error(e)
        if result == 'retry':
            main()
        elif result == 'skip':
            print("Skipping current operation and continuing.")
        elif result == 'exit':
            print("Exiting program. Saving progress...")
            save_progress(video_id)
            sys.exit(0)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

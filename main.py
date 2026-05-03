import os
from dotenv import load_dotenv
load_dotenv()

import re
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from googleapiclient.discovery import build
import random

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    url: str
    yt_api_key: Optional[str] = None

def extract_youtube_id(url: str) -> Optional[str]:
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'shorts\/([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_instagram(url: str) -> bool:
    return "instagram.com" in url or "instagr.am" in url

def estimate_revenue(views: int) -> float:
    # Typical RPM $2 - $10
    rpm = random.uniform(2.0, 7.0)
    return (views / 1000) * rpm

def calculate_engagement(likes: int, views: int) -> float:
    if views == 0: return 0
    return (likes / views) * 100

def generate_mock_trends(total_views: int, published_at: str):
    # Simulate a growth curve over 6 months or since publish date
    pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
    now = datetime.now(pub_date.tzinfo)
    days_diff = (now - pub_date).days
    
    # We'll return 10 data points
    points = 10
    labels = []
    data = []
    
    current_views = 0
    step = total_views / points
    
    for i in range(points):
        # Add some randomness to growth
        current_views += step * random.uniform(0.5, 1.5)
        if current_views > total_views: current_views = total_views
        
        date_point = pub_date + timedelta(days=(days_diff / points) * i)
        labels.append(date_point.strftime('%b %d'))
        data.append(int(current_views))
        
    return {"labels": labels, "data": data}

@app.post("/analyze")
async def analyze_video(request: AnalyzeRequest):
    # Handle Instagram Mock
    if is_instagram(request.url):
        # Mock data for Instagram as Public API access is highly restricted
        return {
            "video": {
                "title": "Instagram Reel / Video",
                "thumbnail": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?w=800",
                "published_at": datetime.now().isoformat(),
                "views": 12500,
                "likes": 850,
                "revenue": estimate_revenue(12500),
                "engagement_rate": 6.8,
                "trends": generate_mock_trends(12500, datetime.now().isoformat())
            },
            "channel": {
                "name": "Instagram Creator",
                "avatar": "https://images.unsplash.com/photo-1511367461989-f85a21fda167?w=400",
                "owner": "Private (Policy Restricted)",
                "created_at": "2020-01-01T00:00:00Z",
                "subscribers": 54000,
                "monthly_revenue": 1200.0
            },
            "note": "Instagram data is currently simulated due to Meta API restrictions for public content."
        }

    yt_id = extract_youtube_id(request.url)
    
    if not yt_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    
    api_key = request.yt_api_key or os.getenv("YT_API_KEY")
    
    if not api_key:
        raise HTTPException(status_code=400, detail="YouTube API Key is required")

    try:
        youtube = build('youtube', 'v3', developerKey=api_key)
        
        # Get Video Details
        v_request = youtube.videos().list(
            part="snippet,statistics",
            id=yt_id
        )
        v_response = v_request.execute()
        
        if not v_response['items']:
            raise HTTPException(status_code=404, detail="Video not found")
            
        video = v_response['items'][0]
        snippet = video['snippet']
        stats = video['statistics']
        channel_id = snippet['channelId']
        
        # Get Channel Details
        c_request = youtube.channels().list(
            part="snippet,statistics",
            id=channel_id
        )
        c_response = c_request.execute()
        channel = c_response['items'][0]
        c_snippet = channel['snippet']
        c_stats = channel['statistics']
        
        views = int(stats.get('viewCount', 0))
        likes = int(stats.get('likeCount', 0))
        
        # Calculations
        revenue = estimate_revenue(views)
        eng_rate = calculate_engagement(likes, views)
        trends = generate_mock_trends(views, snippet['publishedAt'])
        
        # Channel revenue estimate (Average monthly based on total views and subs)
        chan_total_views = int(c_stats.get('viewCount', 0))
        chan_pub_date = datetime.fromisoformat(c_snippet['publishedAt'].replace('Z', '+00:00'))
        chan_age_days = (datetime.now(chan_pub_date.tzinfo) - chan_pub_date).days
        avg_monthly_views = (chan_total_views / max(chan_age_days, 1)) * 30
        chan_monthly_revenue = estimate_revenue(int(avg_monthly_views))

        return {
            "video": {
                "title": snippet['title'],
                "thumbnail": snippet['thumbnails']['high']['url'],
                "published_at": snippet['publishedAt'],
                "views": views,
                "likes": likes,
                "revenue": revenue,
                "engagement_rate": eng_rate,
                "trends": trends
            },
            "channel": {
                "name": c_snippet['title'],
                "avatar": c_snippet['thumbnails']['high']['url'],
                "owner": "Private (Policy Restricted)", # API doesn't expose real name/email
                "created_at": c_snippet['publishedAt'],
                "subscribers": int(c_stats.get('subscriberCount', 0)),
                "monthly_revenue": chan_monthly_revenue
            }
        }
        
    except Exception as e:
        print(f"API Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

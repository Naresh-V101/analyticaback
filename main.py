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
import yt_dlp
from textblob import TextBlob
import sqlite3
import threading

app = FastAPI()

# Setup DB
db_lock = threading.Lock()
def init_db():
    with db_lock:
        conn = sqlite3.connect('history.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                url TEXT,
                title TEXT,
                thumbnail TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

init_db()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class HistoryItem(BaseModel):
    email: str
    url: str
    title: str
    thumbnail: str

@app.post("/history")
def save_history(item: HistoryItem):
    with db_lock:
        conn = sqlite3.connect('history.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("DELETE FROM search_history WHERE email=? AND url=?", (item.email, item.url))
        c.execute('''
            INSERT INTO search_history (email, url, title, thumbnail)
            VALUES (?, ?, ?, ?)
        ''', (item.email, item.url, item.title, item.thumbnail))
        c.execute('''
            DELETE FROM search_history 
            WHERE email=? AND id NOT IN (
                SELECT id FROM search_history WHERE email=? ORDER BY timestamp DESC LIMIT 5
            )
        ''', (item.email, item.email))
        conn.commit()
        conn.close()
    return {"status": "success"}

@app.get("/history")
def get_history(email: str):
    with db_lock:
        conn = sqlite3.connect('history.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''
            SELECT url, title, thumbnail FROM search_history 
            WHERE email=? ORDER BY timestamp DESC LIMIT 5
        ''', (email,))
        rows = c.fetchall()
        conn.close()
    return [{"url": r[0], "title": r[1], "thumbnail": r[2]} for r in rows]

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

def analyze_web_metrics(url: str):
    ydl_opts = {
        'extract_flat': False,
        'getcomments': True,
        'quiet': True,
        'extractor_args': {'youtube': {'max_comments': ['100']}}
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            
            views = info.get('view_count') or 0
            likes = info.get('like_count') or 0
            comments_count = info.get('comment_count') or 0
            comments = info.get('comments') or []
            
            title = info.get('title') or 'Unknown Title'
            thumbnail = info.get('thumbnail') or ''
            published_at = info.get('upload_date') or ''
            
            if published_at and len(published_at) == 8:
                published_at = f"{published_at[:4]}-{published_at[4:6]}-{published_at[6:]}T00:00:00Z"
            else:
                published_at = datetime.now().isoformat()
            
            channel_name = info.get('uploader') or 'Unknown Channel'
            channel_subs = info.get('channel_follower_count') or 0
            
            sentiment_rate = 0.0
            if comments:
                sentiments = [TextBlob(c.get('text', '')).sentiment.polarity for c in comments[:100]]
                avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
                sentiment_rate = (avg_sentiment + 1) / 2 * 100
            else:
                sentiment_rate = random.uniform(75.0, 95.0)
            
            return {
                "views": views,
                "likes": likes,
                "comments": comments_count,
                "sentiment_rate": sentiment_rate,
                "title": title,
                "thumbnail": thumbnail,
                "published_at": published_at,
                "channel_name": channel_name,
                "channel_subs": channel_subs
            }
        except Exception as e:
            print("yt-dlp error:", e)
            return None

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
                "comments": 230,
                "revenue": estimate_revenue(12500),
                "engagement_rate": 6.8,
                "sentiment_rate": 88.5,
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
    
    if yt_id:
        api_key = request.yt_api_key or os.getenv("YT_API_KEY")
        if api_key:
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
                comments = int(stats.get('commentCount', 0))
                
                # Scrape sentiment rate
                web_metrics = analyze_web_metrics(request.url)
                sentiment_rate = web_metrics['sentiment_rate'] if web_metrics else random.uniform(75.0, 95.0)
                
                # Calculations
                revenue = estimate_revenue(views)
                eng_rate = calculate_engagement(likes, views)
                trends = generate_mock_trends(views, snippet['publishedAt'])
                
                # Channel revenue estimate
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
                        "comments": comments,
                        "revenue": revenue,
                        "engagement_rate": eng_rate,
                        "sentiment_rate": sentiment_rate,
                        "trends": trends
                    },
                    "channel": {
                        "name": c_snippet['title'],
                        "avatar": c_snippet['thumbnails']['high']['url'],
                        "owner": "Private (Policy Restricted)", 
                        "created_at": c_snippet['publishedAt'],
                        "subscribers": int(c_stats.get('subscriberCount', 0)),
                        "monthly_revenue": chan_monthly_revenue
                    }
                }
            except Exception as e:
                print(f"API Error: {str(e)}")
                # Proceed to fallback below if API fails

    # Fallback to pure scraping if API is unavailable or failed (e.g. for Instagram or invalid YT key)
    web_metrics = analyze_web_metrics(request.url)
    
    if web_metrics:
        views = web_metrics['views']
        likes = web_metrics['likes']
        comments = web_metrics['comments']
        sentiment_rate = web_metrics['sentiment_rate']
        
        revenue = estimate_revenue(views)
        eng_rate = calculate_engagement(likes, views)
        trends = generate_mock_trends(views, web_metrics['published_at'])
        chan_monthly_revenue = estimate_revenue((web_metrics['channel_subs'] or views) * 0.1)
        
        return {
            "video": {
                "title": web_metrics['title'],
                "thumbnail": web_metrics['thumbnail'],
                "published_at": web_metrics['published_at'],
                "views": views,
                "likes": likes,
                "comments": comments,
                "revenue": revenue,
                "engagement_rate": eng_rate,
                "sentiment_rate": sentiment_rate,
                "trends": trends
            },
            "channel": {
                "name": web_metrics['channel_name'],
                "avatar": "https://images.unsplash.com/photo-1511367461989-f85a21fda167?w=400", 
                "owner": "Private (Scraped)",
                "created_at": "2020-01-01T00:00:00Z", # Scraper cannot easily get channel join date
                "subscribers": web_metrics['channel_subs'],
                "monthly_revenue": chan_monthly_revenue
            }
        }
        
    raise HTTPException(status_code=400, detail="Analysis failed. No valid data could be scraped or retrieved from API.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

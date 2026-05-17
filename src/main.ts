import './style.css'
import { createIcons, BarChart3, Search, PlayCircle, Heart, User, LogOut } from 'lucide'
import Chart from 'chart.js/auto'

declare var google: any;

// Configuration
const GOOGLE_CLIENT_ID = "1023935688810-1oojb1r6joa572d6poh7rfvn6651pvo6.apps.googleusercontent.com";

// Initialize Lucide Icons
createIcons({
  icons: { BarChart3, Search, PlayCircle, Heart, User, LogOut }
})

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// DOM Elements
const loginContainer = document.getElementById('login-container') as HTMLDivElement
const appContainer = document.getElementById('app-container') as HTMLDivElement
const analyzeBtn = document.getElementById('analyze-trigger') as HTMLButtonElement
const urlInput = document.getElementById('video-url') as HTMLInputElement
const loader = document.getElementById('loader') as HTMLDivElement
const dashboard = document.getElementById('dashboard') as HTMLDivElement
const errorDiv = document.getElementById('error-msg') as HTMLDivElement
const logoutBtn = document.getElementById('logout-btn') as HTMLButtonElement
const userNameEl = document.getElementById('user-name') as HTMLElement
const logoUserAvatarEl = document.getElementById('logo-user-avatar') as HTMLImageElement
const logoIconEl = document.getElementById('logo-icon') as HTMLElement
const recentSearchesContainer = document.getElementById('recent-searches-container') as HTMLDivElement
const recentSearchesEl = document.getElementById('recent-searches') as HTMLDivElement

const tabSingle = document.getElementById('tab-single') as HTMLButtonElement
const tabCompare = document.getElementById('tab-compare') as HTMLButtonElement
const singleInputGroup = document.getElementById('single-input-group') as HTMLDivElement
const compareInputGroup = document.getElementById('compare-input-group') as HTMLDivElement
const videoUrl1 = document.getElementById('video-url-1') as HTMLInputElement
const videoUrl2 = document.getElementById('video-url-2') as HTMLInputElement
const analyzeCompareBtn = document.getElementById('analyze-compare-trigger') as HTMLButtonElement
const compareDashboard = document.getElementById('compare-dashboard') as HTMLDivElement
const searchTitle = document.getElementById('search-title') as HTMLHeadingElement
const searchDesc = document.getElementById('search-desc') as HTMLParagraphElement

let isCompareMode = false
let compareChartObj: Chart | null = null

interface SearchHistoryItem {
  url: string
  title: string
  thumbnail: string
}

let viewsChart: Chart | null = null

// --- Authentication Logic ---

function handleCredentialResponse(response: any) {
  // Decode JWT to get user info (basic way)
  const base64Url = response.credential.split('.')[1];
  const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
  const jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function (c) {
    return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
  }).join(''));

  const user = JSON.parse(jsonPayload);
  localStorage.setItem('user', JSON.stringify(user));
  showApp(user);
}

function initGoogleAuth() {
  google.accounts.id.initialize({
    client_id: GOOGLE_CLIENT_ID,
    callback: handleCredentialResponse
  });
  google.accounts.id.renderButton(
    document.getElementById("google-signin-btn"),
    { theme: "outline", size: "large", width: 280, shape: "pill" }
  );
}

function checkAuthState() {
  const savedUser = localStorage.getItem('user');
  if (savedUser) {
    showApp(JSON.parse(savedUser));
  } else {
    showLogin();
  }
}

function showLogin() {
  loginContainer.style.display = 'flex';
  appContainer.style.display = 'none';

  if (!document.getElementById('bg-video')) {
    const video = document.createElement('video');
    video.id = 'bg-video';
    video.autoplay = true;
    video.loop = true;
    video.muted = true;
    video.playsInline = true;
    video.style.position = 'absolute';
    video.style.top = '50%';
    video.style.left = '50%';
    video.style.minWidth = '100%';
    video.style.minHeight = '100%';
    video.style.width = 'auto';
    video.style.height = 'auto';
    video.style.zIndex = '-1';
    video.style.transform = 'translate(-50%, -50%)';
    video.style.objectFit = 'cover';
    video.style.filter = 'brightness(0.3) blur(2px)';
    
    const source = document.createElement('source');
    source.src = 'https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4';
    source.type = 'video/mp4';
    
    video.appendChild(source);
    loginContainer.insertBefore(video, loginContainer.firstChild);
    
    video.play().catch(error => {
      console.log('Video autoplay failed:', error);
    });
  } else {
    const video = document.getElementById('bg-video') as HTMLVideoElement;
    video.play().catch(error => {
      console.log('Video play failed:', error);
    });
  }

  initGoogleAuth();
}

function showApp(user: any) {
  loginContainer.style.display = 'none';
  appContainer.style.display = 'block';
  
  const video = document.getElementById('bg-video') as HTMLVideoElement;
  if (video) {
    video.pause();
  }

  userNameEl.innerText = user.name;
  logoUserAvatarEl.src = user.picture;
  logoUserAvatarEl.style.display = 'block';
  logoIconEl.style.display = 'none';
  fetchAndRenderHistory();
}

async function fetchAndRenderHistory() {
  const userStr = localStorage.getItem('user');
  if (!userStr) return;
  const user = JSON.parse(userStr);
  
  try {
    const res = await fetch(`${API_BASE_URL}/history?email=${encodeURIComponent(user.email)}`);
    if (!res.ok) return;
    const history: SearchHistoryItem[] = await res.json();
    
    if (history.length === 0) {
      recentSearchesContainer.style.display = 'none';
      return;
    }

    recentSearchesContainer.style.display = 'block';
    recentSearchesEl.innerHTML = '';

    history.forEach(item => {
    const el = document.createElement('div')
    el.className = 'recent-search-item'
    const shortTitle = item.title.length > 25 ? item.title.substring(0, 25) + '...' : item.title
    el.innerHTML = `
      <img src="${item.thumbnail}" class="recent-search-thumb" alt="thumb">
      <span>${shortTitle}</span>
    `
    el.addEventListener('click', () => {
      if (isCompareMode) {
        if (!videoUrl1.value) videoUrl1.value = item.url
        else if (!videoUrl2.value) videoUrl2.value = item.url
        else {
          videoUrl1.value = item.url
          videoUrl2.value = ''
        }
      } else {
        urlInput.value = item.url
        analyze()
      }
    })
    recentSearchesEl.appendChild(el)
  })
  } catch (err) {
    console.error("Failed to load history", err);
  }
}

async function saveToHistory(url: string, title: string, thumbnail: string) {
  const userStr = localStorage.getItem('user');
  if (!userStr) return;
  const user = JSON.parse(userStr);
  
  try {
    await fetch(`${API_BASE_URL}/history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: user.email, url, title, thumbnail })
    });
    fetchAndRenderHistory();
  } catch (err) {
    console.error("Failed to save history", err);
  }
}

function logout() {
  localStorage.removeItem('user');
  location.reload();
}

// --- App Logic ---

// Formatters
const formatNumber = (num: number) => new Intl.NumberFormat().format(num)
const formatCurrency = (num: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num)
const formatDate = (dateStr: string) => new Date(dateStr).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })

async function analyze() {
  const url = urlInput.value.trim()
  const apiKey = localStorage.getItem('yt_api_key') || ''

  if (!url) return alert('Please enter a URL')

  loader.style.display = 'block'
  dashboard.style.display = 'none'
  compareDashboard.style.display = 'none'
  errorDiv.style.display = 'none'

  try {
    const response = await fetch(`${API_BASE_URL}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, yt_api_key: apiKey })
    })

    if (!response.ok) {
      const err = await response.json()
      throw new Error(err.detail || 'Analysis failed')
    }

    const data = await response.json()
    renderData(data, url)
  } catch (error: any) {
    errorDiv.innerText = `Error: ${error.message}`
    errorDiv.style.display = 'block'
  } finally {
    loader.style.display = 'none'
  }
}

function renderData(data: any, originalUrl: string) {
  const { video, channel } = data
  
  saveToHistory(originalUrl, video.title, video.thumbnail)

    // Update Video Stats
    ; (document.getElementById('vid-title') as HTMLElement).innerText = video.title
    ; (document.getElementById('vid-thumb') as HTMLImageElement).src = video.thumbnail
    ; (document.getElementById('vid-date') as HTMLElement).innerText = `Posted on ${formatDate(video.published_at)}`
    ; (document.getElementById('vid-views') as HTMLElement).innerText = formatNumber(video.views)
    ; (document.getElementById('vid-likes') as HTMLElement).innerText = formatNumber(video.likes)
    ; (document.getElementById('vid-comments') as HTMLElement).innerText = formatNumber(video.comments || 0)
    ; (document.getElementById('vid-sentiment') as HTMLElement).innerText = `${(video.sentiment_rate || 0).toFixed(1)}%`
    ; (document.getElementById('vid-revenue') as HTMLElement).innerText = formatCurrency(video.revenue)
    ; (document.getElementById('vid-eng-rate') as HTMLElement).innerText = `${video.engagement_rate.toFixed(2)}%`

    // Update Channel Stats
    ; (document.getElementById('chan-name') as HTMLElement).innerText = channel.name
    ; (document.getElementById('chan-avatar') as HTMLImageElement).src = channel.avatar
    ; (document.getElementById('chan-owner') as HTMLElement).innerText = `Owner: ${channel.owner}`
    ; (document.getElementById('chan-date') as HTMLElement).innerText = `Joined: ${formatDate(channel.created_at)}`
    ; (document.getElementById('chan-subs') as HTMLElement).innerText = formatNumber(channel.subscribers)
    ; (document.getElementById('chan-revenue') as HTMLElement).innerText = formatCurrency(channel.monthly_revenue)

  dashboard.style.display = 'grid'

  // Render Chart
  renderChart(video.trends)
}

function renderChart(trends: any) {
  const ctx = (document.getElementById('views-chart') as HTMLCanvasElement).getContext('2d')
  if (!ctx) return

  if (viewsChart) viewsChart.destroy()

  viewsChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: trends.labels,
      datasets: [{
        label: 'Cumulative Views',
        data: trends.data,
        borderColor: '#8b5cf6',
        backgroundColor: 'rgba(139, 92, 246, 0.1)',
        fill: true,
        tension: 0.4,
        borderWidth: 3,
        pointRadius: 4,
        pointBackgroundColor: '#8b5cf6'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: '#94a3b8' }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#94a3b8' }
        }
      }
    }
  })
}

async function analyzeCompare() {
  const url1 = videoUrl1.value.trim()
  const url2 = videoUrl2.value.trim()
  const apiKey = localStorage.getItem('yt_api_key') || ''

  if (!url1 || !url2) return alert('Please enter both URLs')

  loader.style.display = 'block'
  dashboard.style.display = 'none'
  compareDashboard.style.display = 'none'
  errorDiv.style.display = 'none'

  try {
    const [res1, res2] = await Promise.all([
      fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url1, yt_api_key: apiKey })
      }),
      fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url2, yt_api_key: apiKey })
      })
    ])

    if (!res1.ok || !res2.ok) throw new Error('One or both analyses failed')

    const data1 = await res1.json()
    const data2 = await res2.json()

    renderCompareData(data1, data2, url1, url2)
  } catch (error: any) {
    errorDiv.innerText = `Error: ${error.message}`
    errorDiv.style.display = 'block'
  } finally {
    loader.style.display = 'none'
  }
}

function renderCompareData(data1: any, data2: any, url1: string, url2: string) {
  saveToHistory(url1, data1.video.title, data1.video.thumbnail)
  saveToHistory(url2, data2.video.title, data2.video.thumbnail)
  
  const setupVideo = (data: any, idx: number) => {
    const { video } = data;
    (document.getElementById(`comp-vid-title-${idx}`) as HTMLElement).innerText = video.title;
    (document.getElementById(`comp-vid-thumb-${idx}`) as HTMLImageElement).src = video.thumbnail;
    (document.getElementById(`comp-vid-date-${idx}`) as HTMLElement).innerText = `Posted on ${formatDate(video.published_at)}`;
    (document.getElementById(`comp-vid-views-${idx}`) as HTMLElement).innerText = formatNumber(video.views);
    (document.getElementById(`comp-vid-likes-${idx}`) as HTMLElement).innerText = formatNumber(video.likes);
    (document.getElementById(`comp-vid-comments-${idx}`) as HTMLElement).innerText = formatNumber(video.comments || 0);
    (document.getElementById(`comp-vid-revenue-${idx}`) as HTMLElement).innerText = formatCurrency(video.revenue);
    (document.getElementById(`comp-vid-eng-rate-${idx}`) as HTMLElement).innerText = `${video.engagement_rate.toFixed(2)}%`;
    (document.getElementById(`comp-vid-sentiment-${idx}`) as HTMLElement).innerText = `${(video.sentiment_rate || 0).toFixed(1)}%`;
  }

  setupVideo(data1, 1)
  setupVideo(data2, 2)
  
  compareDashboard.style.display = 'grid'
  
  // Render Compare Chart
  const ctx = (document.getElementById('compare-chart') as HTMLCanvasElement).getContext('2d')
  if (!ctx) return
  if (compareChartObj) compareChartObj.destroy()
  
  compareChartObj = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data1.video.trends.labels,
      datasets: [
        {
          label: 'Video 1 Views',
          data: data1.video.trends.data,
          borderColor: '#8b5cf6',
          tension: 0.4,
          borderWidth: 3
        },
        {
          label: 'Video 2 Views',
          data: data2.video.trends.data,
          borderColor: '#06b6d4',
          tension: 0.4,
          borderWidth: 3
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8' } },
        x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
      }
    }
  })
}

// Tab Switching
tabSingle.addEventListener('click', () => {
  isCompareMode = false
  tabSingle.classList.add('active')
  tabCompare.classList.remove('active')
  singleInputGroup.style.display = 'flex'
  compareInputGroup.style.display = 'none'
  dashboard.style.display = 'none'
  compareDashboard.style.display = 'none'
  searchTitle.innerText = 'Analyze any Video'
  searchDesc.innerText = 'Paste a YouTube link or Instagram Reel URL to get deep insights into performance, revenue, and channel stats.'
})

tabCompare.addEventListener('click', () => {
  isCompareMode = true
  tabCompare.classList.add('active')
  tabSingle.classList.remove('active')
  compareInputGroup.style.display = 'flex'
  singleInputGroup.style.display = 'none'
  dashboard.style.display = 'none'
  compareDashboard.style.display = 'none'
  searchTitle.innerText = 'Compare Videos'
  searchDesc.innerText = 'Compare performance metrics of two videos side-by-side.'
})

// Event Listeners
analyzeBtn.addEventListener('click', analyze)
urlInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') analyze()
})
analyzeCompareBtn.addEventListener('click', analyzeCompare)
videoUrl2.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') analyzeCompare()
})
logoutBtn.addEventListener('click', logout)

// Initialization
window.onload = checkAuthState;

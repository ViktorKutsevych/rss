from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import ClientSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import feedparser, asyncio, os

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["news"]
collection = db["articles"]

FEEDS = [
    ("BBC", "http://feeds.bbci.co.uk/news/rss.xml"),
    ("CNN", "http://rss.cnn.com/rss/edition.rss"),
    ("Reuters", "http://feeds.reuters.com/reuters/topNews"),
    ("NYTimes", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("DW", "https://rss.dw.com/rdf/rss-en-all")
]

async def fetch_and_store():
    async with ClientSession() as session:
        for name, url in FEEDS:
            try:
                async with session.get(url) as resp:
                    data = await resp.text()
            except Exception as e:
                print(f"❌ Error fetching {url}: {e}")
                continue

            parsed = feedparser.parse(data)

            for entry in parsed.entries:
                image_url = extract_image(entry)
                article = {
                    "title": entry.get("title", "Без заголовка"),
                    "link": entry.get("link"),
                    "source": name,
                    "published": entry.get("published", ""),
                    "image": image_url
                }
                if article["link"]:
                    await collection.update_one(
                        {"link": article["link"]},
                        {"$set": article},
                        upsert=True
                    )

async def fetch_and_store():
    async with ClientSession() as session:
        for name, url in FEEDS:
            try:
                async with session.get(url) as resp:
                    data = await resp.text()
            except Exception as e:
                print(f"❌ Error fetching {url}: {e}")
                continue

            parsed = feedparser.parse(data)

            for entry in parsed.entries:
                image_url = extract_image(entry)
                article = {
                    "title": entry.get("title", "Без заголовка"),
                    "link": entry.get("link"),
                    "source": name,
                    "published": entry.get("published", ""),
                    "image": image_url
                }
                if article["link"]:
                    await collection.update_one(
                        {"link": article["link"]},
                        {"$set": article},
                        upsert=True
                    )

def extract_image(entry):
    if "media_content" in entry and entry["media_content"]:
        return entry["media_content"][0].get("url")
    if "media_thumbnail" in entry and entry["media_thumbnail"]:
        return entry["media_thumbnail"][0].get("url")
    if "links" in entry:
        for link in entry["links"]:
            if link.get("type", "").startswith("image"):
                return link.get("href")
    return None

@app.on_event("startup")
async def startup_event():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(fetch_and_store, "interval", minutes=1)
    scheduler.start()
    await fetch_and_store()

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    grouped_articles = {}

    for source, _ in FEEDS:
        cursor = collection.find({
            "source": source,
            "image": {"$ne": None}
        }).sort("published", -1).limit(6)

        articles = await cursor.to_list(length=6)

        if articles:
            grouped_articles[source] = articles

    return templates.TemplateResponse("index.html", {"request": request, "grouped_articles": grouped_articles})
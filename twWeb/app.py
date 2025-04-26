from flask import Flask, render_template, request, send_file, session
import os
import requests
import pandas as pd
import time
import io

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Session için gizli anahtar


BEARER_TOKEN = "*"

def fetch_tweets(query, total_tweets):
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {
        "Authorization": f"Bearer {BEARER_TOKEN}"
    }

    tweets_collected = 0
    next_token = None
    all_tweets = []

    while tweets_collected < total_tweets:
        batch_size = min(100, total_tweets - tweets_collected)
        params = {
            "query": query,
            "tweet.fields": "author_id,created_at,lang,public_metrics",
            "max_results": batch_size
        }
        if next_token:
            params["next_token"] = next_token

        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 429:
            reset_timestamp = int(response.headers.get('x-rate-limit-reset', time.time() + 60))
            wait_seconds = reset_timestamp - int(time.time())
            wait_seconds = max(wait_seconds, 10)  # Minimum 10 saniye bekle ki emin olalım
            print(f"⚠️ API limiti aşıldı, {wait_seconds} saniye bekleniyor...")
            time.sleep(wait_seconds)
            continue

        if response.status_code != 200:
            raise Exception(f"Twitter API Hatası: {response.status_code} - {response.text}")

        data = response.json()
        tweets = data.get("data", [])
        all_tweets.extend(tweets)
        tweets_collected += len(tweets)

        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break

        time.sleep(1)  # Rate limit protection

    df = pd.DataFrame([{
        "Tweet ID": t["id"],
        "User ID": t["author_id"],
        "Text": t["text"],
        "Created At": t["created_at"],
        "Lang": t["lang"],
        "Likes": t["public_metrics"]["like_count"],
        "Replies": t["public_metrics"]["reply_count"],
        "Retweets": t["public_metrics"]["retweet_count"],
        "Quotes": t["public_metrics"]["quote_count"]
    } for t in all_tweets])

    return df


@app.route("/", methods=["GET", "POST"])
def index():
    error = None  # Başlangıçta hata yok

    if request.method == "POST":
        query = request.form["query"].strip()
        total = int(request.form["count"])

        if not query:
            error = "⚠️ Lütfen bir arama kelimesi giriniz."
            return render_template("index.html", preview=None, error=error, history=session.get("history", []))

        try:
            df = fetch_tweets(query, total)

            if df.empty:
                error = f"⚠️ '{query}' için tweet bulunamadı."
                return render_template("index.html", preview=None, error=error, history=session.get("history", []))

            # Bellekte CSV oluştur
            output = io.StringIO()
            df.to_csv(output, index=False)
            output.seek(0)

            # Önizleme verisi
            preview_data = df[[
                "Text", "Likes", "Retweets", "Replies", "Quotes", "Created At"
            ]].head(10).to_dict(orient="records")

            # Arama geçmişini güncelle
            if "history" not in session:
                session["history"] = []

            if query not in session["history"]:
                session["history"].insert(0, query)
                session["history"] = session["history"][:10]

            return render_template("index.html", preview=preview_data, csv_data=output.getvalue(), query=query, history=session["history"], error=None)

        except Exception as e:
            error = f"🚨 Bir hata oluştu: {str(e)}"
            return render_template("index.html", preview=None, error=error, history=session.get("history", []))

    return render_template("index.html", preview=None, error=None, history=session.get("history", []))



@app.route("/download", methods=["POST"])
def download():
    csv_data = request.form["csv"]
    return send_file(
        io.BytesIO(csv_data.encode("utf-8")),
        mimetype="text/csv",
        as_attachment=True,
        download_name="tweets.csv"
    )


if __name__ == "__main__":
    app.run(debug=True)

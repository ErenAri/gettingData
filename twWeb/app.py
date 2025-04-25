from flask import Flask, render_template, request, send_file
import requests
import pandas as pd
import time
import io

app = Flask(__name__)

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAK1w0wEAAAAA13hnq8DCNTntS4d4xvbLb0kgLLg%3D5HNaEgGylS119HXFnk3wPZPlXZOxqVOmfnZtZMbWXGIv3nNyAs"
#Bearer tokeni değiştirdim

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
            "query": f"{query} lang:en",
            "tweet.fields": "author_id,created_at,lang,public_metrics",
            "max_results": batch_size
        }
        if next_token:
            params["next_token"] = next_token

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            break

        data = response.json()
        tweets = data.get("data", [])
        all_tweets.extend(tweets)
        tweets_collected += len(tweets)

        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break

        time.sleep(1)  # Rate limit koruması

    # Verileri DataFrame'e çeviriyoruz
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
    if request.method == "POST":
        query = request.form["query"]
        total = int(request.form["count"])

        df = fetch_tweets(query, total)

        # CSV çıktısını bellekte tut
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)

        # İlk 5 tweeti sayfada göster
        preview = df.head(10).to_dict(orient="records")
        return render_template("index.html", preview=preview, csv_data=output.getvalue(), query=query)

    return render_template("index.html", preview=None)


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

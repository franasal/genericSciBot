
# [genericScienceBot](https://twitter.com/ViewsOnDrugsBot/)

A bot application sharing scientific publications and educated opinions on a given topic.


## What it does:

* Reads and parses a list of RSS feeds (i.e. PubMed)
 Tweets an article's title, link, abstract, and authors as a 5/5 thread :thread:.
* Retweets older RSS post after a given time.
* Retweets the most retweeted and up-voted post from:
  - a global search for specified keywords or hashtags defined on `keywords.txt`.
  - a search result from a given distribution Twitter list defined on `.env`.
* Interacts with users by liking posts from the above.
* Schedule jobs for any of the above.
* Send automated debug reports via Telegram.

All functions can be used independently.

## Install

0. Download or git clone Twitterbot:
    - `git clone https://github.com/franasal/genericsciencebot.git`
1. Run:
    - `cd scibot`
    - `pip install . --user`
2. Create a [Twitter application](https://apps.twitter.com/), and generate keys, tokens etc.
3. Create a [Telegram bot](https://python-telegram-bot.readthedocs.io/en/stable/) for post and debugging notifications.
4. Modify the settings in the `<project folder>` `.txt` files.
    - Modify `feed_urls` list to add the RSS feeds of your choice. [Here](https://github.com/roblanf/phypapers) you can find a description on how to set an RSS search.
    - Modify the variables in the `example.env` file and add keys, tokens etc. for connecting to your Twitter app and save it as `.env` in your home directory.
    - Modify `retweet_include_words` for keywords you want to search and retweet, and `retweet_exclude_words` for keywords you would like to exclude from retweeting. For example `retweet_include_words = ["foo"]` and `retweet_exclude_words = ["bar"]` will include any tweet with the word "foo", as long as the word "bar" is absent. This list can also be left empty, i.e. `retweet_exclude_words = []`.
    - Modify or add jobs to the `scheduled_job()` function.

## Requirements

* Python 3+
* Twitter account
* Telegram account

## Usage

Read the RSS feeds and post a thread to Twitter account:

```bash
$ scibot <project folder> rss
```

Search globally for tweets and retweet them:

```bash
$ scibot <project folder> rtg
```
Search for tweets within a Twitter list and retweet them:

```bash
$ scibot <project folder> rtl
```
Retweet last own tweet:

```bash
$ scibot <project folder> rto
```
### Deploy:

[Here](https://schedule.readthedocs.io/en/stable/) you can learn how set-up tasks for the the `scheduled_job()` function

There are some good free cloud solutions such as [pythonanywhere](https://www.pythonanywhere.com/), where you can deploy the bot,
to do that just run:

```bash
$ scibot <project folder> sch
```

:hibiscus:


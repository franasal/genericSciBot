import calendar
import tweepy
import logging
import json
import re
import time
import os
import random
import datetime
import feedparser
import dateutil.parser
from bs4 import BeautifulSoup
from twitterscibot.telebot import telegram_bot_sendtext
from schedule import Scheduler

def loggert(path_log):
    # logging parameters
    logger = logging.getLogger("bot logger")
    # handler determines where the logs go: stdout/file
    file_handler = logging.FileHandler(os.path.join(path_log, f"{datetime.date.today()}_scibot.log"))

    logger.setLevel(logging.DEBUG)
    file_handler.setLevel(logging.DEBUG)

    fmt_file = (
        "%(levelname)s %(asctime)s [%(filename)s: %(funcName)s:%(lineno)d] %(message)s"
    )

    file_formatter = logging.Formatter(fmt_file)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    return logger

def retrieve_rss_urls(url_paths):
    # read rss url file
    rss_len = random.randrange(10,150)
    with open(os.path.join(url_paths, "rss_urls.txt")) as file:
        lines = [line.rstrip().replace("limit=100", f"limit={rss_len}") for line in file]

    a = lines.index('>Alt_RSS')
    main_rss = lines[1:a]
    alt_rss = lines[a + 1:len(lines)]

    # RSS feeds to read and post tweets from.
    feed_urls = main_rss
    # rss best results no time harm reduction and psychedelics
    feed_older_literature = feedparser.parse(alt_rss[0])["entries"]

    pre_combined_feed = [feedparser.parse(url)["entries"] for url in feed_urls]

    # (combined_feed)
    combined_feed = [item for feed in pre_combined_feed for item in feed]
    combined_feed.sort(
        key=lambda x: dateutil.parser.parse(x["published"]), reverse=True
    )

    return {"feed_older_literature": feed_older_literature, "combined_feed": combined_feed}


def find_keyword_positions(key_sel, lines):
    for index, line in enumerate(lines):
        if line == key_sel:
            found_ix = index
    return found_ix


def retrieve_keywords(keys_path):
    # read keywords file
    with open(os.path.join(keys_path, "keywords.txt")) as file:
        lines = file.readlines()
    lines = [line.rstrip() for line in lines if not line.startswith("#")]

    include_pos = find_keyword_positions('>retweet_include_words', lines)
    exclude_pos = find_keyword_positions('>retweet_exclude_words', lines)
    hashtag_pos = find_keyword_positions('>add_hashtag', lines)
    watch_pos = find_keyword_positions('>watch_add_hashtag', lines)

    keywords_dict={
        # retweet_include_words Include tweets with these words when retweeting.
        "retweet_include_words": lines[include_pos + 1:exclude_pos],
        # retweet_exclude_words Do not include tweets with these words when retweeting.
        "retweet_exclude_words": lines[exclude_pos + 1:hashtag_pos],
        "add_hashtag": lines[hashtag_pos + 1:watch_pos],
        # watch_add_hashtag do not retweet if search results include one of these keywords withouth any of the hash list
        "watch_add_hashtag": lines[watch_pos + 1:]}

    return keywords_dict


def make_path_dict(base_path):
    path_dict = {
        # Log file to save all tweeted RSS links (one URL per line).
        "posted_urls_output_file": os.path.join(base_path, "publications.json"),
        # Log file to save all retweeted tweets (one tweetid per line).
        "posted_retweets_output_file": os.path.join(base_path, "posted-retweets.log"),
        # Log file to save all retweeted tweets (one tweetid per line).
        "faved_tweets_output_file": os.path.join(base_path, "faved-tweets.log"),
        # Log file to save followers list.
        "users_json_file": os.path.join(base_path, "users.json")
    }
    return path_dict


# Setup API:
def twitter_setup():
    """
    Setup Twitter connection for a developer account
    Returns: tweepy.API object

    """
    # Authenticate and access using keys:
    auth = tweepy.OAuthHandler(os.getenv("CONSUMER_KEY"), os.getenv("CONSUMER_SECRET"))
    auth.set_access_token(os.getenv("ACCESS_TOKEN"), os.getenv("ACCESS_SECRET"))

    # Return API access:
    api = tweepy.API(auth, wait_on_rate_limit=True)
    return api


def check_json_exists(file_path: os.path, init_dict: dict) -> None:
    """

    Create a folder and json file if does not exists

    Args:
        file_path: Log files file path
        init_dict: Dictionary to initiate a json file

    Returns: None

    """

    if not os.path.exists(os.path.dirname(os.path.abspath(file_path))):
        os.makedirs(file_path)

    if not os.path.isfile(file_path):
        with open(file_path, "w") as json_file:
            json.dump(init_dict, json_file, indent=4)

def retweet(logger, tweet: tweepy.Status):
    """
    re-tweet self last tweeted message.
    Args:
        tweet: tweet object

    Returns: None

    """

    try:
        twitter_api = twitter_setup()

        if not hasattr(tweet, 'retweeted'):
            print(tweet)
            twitter_api.retweet(id=tweet.id)
            logger.info(f"retweeted: twitter.com/i/status/{tweet.id}")
            telegram_bot_sendtext(f"Self retweeted: twitter.com/i/status/{tweet.id}")

        else:
            twitter_api.unretweet(tweet.id)
            twitter_api.retweet(tweet.id)
            telegram_bot_sendtext(f"Self re-retweeted: twitter.com/i/status/{tweet.id}")

    except tweepy.TweepError as e:
        logger.exception(e)
        telegram_bot_sendtext(f"ERROR:{e}")


def retweet_old_own(logger, project_path):
    """

    Returns: None

    """

    twitter_api = twitter_setup()
    paths_dict = make_path_dict(project_path)


    with open(paths_dict["posted_urls_output_file"], "r") as jsonFile:
        article_log = json.load(jsonFile)

    article_log_reversed = {article_log[x]['tweet_id']:{**article_log[x], **{'id':x}} for x in article_log}


    min_val = min(article_log[x]["count"] for x in article_log)

    for art in sorted(list(article_log_reversed), key=None, reverse=False):
        tweet = twitter_api.statuses_lookup([article_log_reversed[art]["tweet_id"]])
        if tweet and article_log_reversed[art]["count"] <= min_val:
            retweet(logger, tweet[0])
            article_log[article_log_reversed[art]['id']]["count"] += 1

            break

    with open(paths_dict["posted_urls_output_file"], "w") as fp:
        json.dump(article_log, fp, indent=4)


def get_followers_list(project_path) -> list:
    """
    Read json file of followers from Settings.users_json_file
    Returns: List of followers

    """

    paths_dict = make_path_dict(project_path)

    with open(paths_dict["users_json_file"], "r") as json_file:
        users_dic = json.load(json_file)
    return [x for x in users_dic if users_dic[x]["follower"] is True]

def update_thread(text: str, tweet: tweepy.Status, api: tweepy.API) -> tweepy.Status:
    """
    Add a tweet to a initiated thread
    Args:
        text: text to add to tweet as thread
        tweet: tweepy status to add reply to
        api: tweepy.API object

    Returns: post a reply to a tweet

    """
    return api.update_status(
        status=text, in_reply_to_status_id=tweet.id, auto_populate_reply_metadata=True
    )

class SafeScheduler(Scheduler):
    """
    An implementation of Scheduler that catches jobs that fail, logs their
    exception tracebacks as errors, optionally reschedules the jobs for their
    next run time, and keeps going.
    Use this to run jobs that may or may not crash without worrying about
    whether other jobs will run or if they'll crash the entire script.
    """

    def __init__(self, reschedule_on_failure=True):
        """

        Args:
            reschedule_on_failure: if is True, jobs will be rescheduled for their
        next run as if they had completed successfully. If False, they'll run
        on the next run_pending() tick.
        """
        self.reschedule_on_failure = reschedule_on_failure
        super().__init__()

    def _run_job(self, job):
        try:
            super()._run_job(job)

        except Exception as e:
            telegram_bot_sendtext(f"[Job Error] {e}")
            job.last_run = datetime.datetime.now()
            job._schedule_next_run()


def shorten_text(text: str, maxlength: int) -> str:
    """
    Truncate text and append three dots (...) at the end if length exceeds
    maxlength chars.

    Args:
        text: The to shorten.
        maxlength: The maximum character length of the text string.

    Returns: Shortened text string.

    """
    return (text[:maxlength] + "...") if len(text) > maxlength else text


def insert_hashtag(keys_path, title: str) -> str:
    """
    Add hashtag on title for keywords found on Settings.add_hashtag
    Args:
        title: Text to parse for inserting hash symbols

    Returns: Text with inserted hashtags

    """

    keywords_dict = retrieve_keywords(keys_path)

    for x in keywords_dict["add_hashtag"]:
        if re.search(fr"\b{x}", title.lower()):
            pos = (re.search(fr"\b{x}", title.lower())).start()
            if " " in x:
                title = title[:pos] + "#" + title[pos:].replace(" ", "", 1)
            elif "-" in x:
                title = title[:pos] + "#" + title[pos:].replace("-", "", 1)
            else:
                title = title[:pos] + "#" + title[pos:]
    return title


def compose_message(path_base, threadln, item: dict) -> str:
    """
    Compose a tweet from an RSS item (title, link, description)
    and return final tweet message.

    Args:
        item: feedparser.FeedParserDict
        An RSS item

    Returns: mMssage suited for a Twitter status update.
    :param path_base:

    """
    title = insert_hashtag(path_base, item["title"])

    message = "\U0001F9F5" + shorten_text(title, maxlength=240) + f" 1/{threadln+1}  " + item["link"]
    return message



def is_in_logfile(content: str, filename: str) -> bool:
    """
    Does the content exist on any line in the log file?

    Args:
        content: Content to search file for.
        filename: Full path to file to search.

    Returns: `True` if content is found in file, otherwise `False`.

    """
    if os.path.isfile(filename):
        with open(filename, "r") as jsonFile:
            article_log = json.load(jsonFile)
        if content in article_log:
            return True
    return False


def write_to_logfile(content: dict, filename: str) -> None:
    """
    Append content to json file.

    Args:
        content: Content to append to file
        filename: Full path to file that should be appended.

    Returns: None

    """
    try:
        with open(filename, "w") as fp:
            json.dump(content, fp, indent=4)
    except IOError as e:
        telegram_bot_sendtext(f"[Job Error] {e}")

def return_doi_str(article):
    """return doi link if exists"""
    title_search = re.search('(DOI:<a href=")(.*)(">)', str(article))
    if title_search:
        return title_search.group(2)
    else:
        return article.link
def make_literature_dict(feed: list) -> dict:
    """
    filter publications from an RSS feed having an abstract, parse html abstract as plane string
    Args:
        feed: list of RSS feed items

    Returns: dictionary of processed publications

    """

    dict_publications = {}

    for item in feed:
        if hasattr(item, "content") and not 'No abstract' in item.description:

            authors_list = [x["name"] for x in item.authors]

            abstract_pre= BeautifulSoup(item.content[0].value, "html.parser").get_text().split("ABSTRACT")[1]
            ixpmid = re.search("PMID:", abstract_pre).start()
            abstract_post= abstract_pre[:ixpmid]

            dict_publications[item.id] = {
                "title": item.title,
                "abstract":abstract_post,
                "link": return_doi_str(item),
                "description": item.description,
                "pub_date": f"Date: {calendar.month_name[item.published_parsed.tm_mon]} {item.published_parsed.tm_year}",
                "author-s": f"Authors:  {', '.join(authors_list)}" if len(authors_list) >1 else  f"Author:  {', '.join(authors_list)}",

            }
    return dict_publications

def json_add_new_friend(project_path, user_id: str) -> None:
    """
    add user friends to the interactions json file
    Args:
        user_id: user id to add to the interactions file

    Returns: None, updates interaction file

    """

    paths_dict = make_path_dict(project_path)

    with open(paths_dict["users_json_file"], "r") as json_file:
        users_dic = json.load(json_file)
    if user_id not in users_dic:
        users_dic[user_id] = {"follower": True, "interactions": 1}
    else:
        users_dic[user_id]["follower"] = True

    with open(paths_dict["users_json_file"], "w") as json_file:
        json.dump(users_dic, json_file, indent=4)

def get_longest_text(status: tweepy.Status) -> str:
    """
    Get the text of a quoted status
    Args:
        status: tweepy.Status object

    Returns: text of the quoted tweet

    """
    if hasattr(status, "retweeted_status"):
        return status.retweeted_status.full_text
    else:
        return status.full_text


def scheduled_job(read_rss_and_tweet, retweet_old_own, search_and_retweet, logger, project_path):

    # listen_stream_and_rt('#INSIGHT2021')

    schedule = SafeScheduler()
    # job 1
    schedule.every().day.at("22:20").do(read_rss_and_tweet, logger, project_path)
    schedule.every().day.at("06:20").do(read_rss_and_tweet, logger, project_path)
    schedule.every().day.at("14:20").do(read_rss_and_tweet, logger, project_path)
    # job 2
    schedule.every().day.at("01:10").do(retweet_old_own,logger, project_path)
    schedule.every().day.at("09:10").do(retweet_old_own,logger, project_path)
    schedule.every().day.at("17:10").do(retweet_old_own,logger, project_path)
    # job 3

    schedule.every().day.at("00:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("03:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("06:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("09:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("12:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("15:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("18:20").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("21:20").do(search_and_retweet, logger, project_path, "list_search")

    schedule.every().day.at("01:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("04:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("07:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("10:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("13:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("16:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("19:25").do(search_and_retweet, logger, project_path, "list_search")
    schedule.every().day.at("22:25").do(search_and_retweet, logger, project_path, "list_search")
    # job love
    schedule.every(5).minutes.do(search_and_retweet, logger, project_path,  "give_love")

    while 1:
        schedule.run_pending()
        time.sleep(1)

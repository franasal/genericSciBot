#!/usr/bin/python3.6
import sys
import textwrap
from os.path import expanduser
from random import randint
from dotenv import load_dotenv
from twitbot4.utils import *

IGNORE_ERRORS = [327, 139]

def main():
    """
    Main function of scibot

    """
    logger = loggert("./")
    if len(sys.argv) > 2:
        project_path = expanduser(sys.argv[1])
        env_path = os.path.join(project_path,".env")
        load_dotenv(dotenv_path=env_path, override=True)
        logger.info("\n### sciBot started ###\n\n")
        paths_dict=make_path_dict(project_path)

        try:
            check_json_exists(
                paths_dict["users_json_file"],
                {"test": {"follower": False, "interactions": 0}},
            )
            check_json_exists(paths_dict["faved_tweets_output_file"], {"test": {"count":0, "tweet_id":0}})
            check_json_exists(
                paths_dict["posted_retweets_output_file"],
                {"test":  {"count":0, "tweet_id":0}},
            )
            check_json_exists(
                paths_dict["posted_urls_output_file"],
                {"test": {"count":0, "tweet_id":0}},
            )

            if sys.argv[2].lower() == "rss":
                read_rss_and_tweet(logger, project_path)
            elif sys.argv[2].lower() == "str":
                if len(sys.argv) == 3:
                    listen_stream_and_rt()
                else:
                    print(sys.argv[3].split()[0], len(sys.argv))
                    raise Exception('add list of hashtags to retweet ie. "#GoVegan, #VegansRock"')
            elif sys.argv[2].lower() == "rtg":
                search_and_retweet(logger, project_path, "global_search")
            elif sys.argv[2].lower() == "glv":
                search_and_retweet(logger, project_path, "give_love")
            elif sys.argv[2].lower() == "glvn":
                search_and_retweet(logger, project_path, "give_love", now=True)
            elif sys.argv[2].lower() == "rtl":
                search_and_retweet(logger, project_path, "list_search")
            elif sys.argv[2].lower() == "rto":
                retweet_old_own(logger, project_path)
            elif sys.argv[2].lower() == "sch":
                scheduled_job(read_rss_and_tweet, retweet_old_own, search_and_retweet, logger, project_path)


        except Exception as e:
            logger.exception(e, exc_info=True)
            telegram_bot_sendtext(f"[Exception] {e}")

        except IOError as errno:
            logger.exception(f"[ERROR] IOError {errno}")
            telegram_bot_sendtext(f"[ERROR] IOError {errno}")

    else:
        display_help()
    logger.info("\n\n### sciBot finished ###")


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

def post_thread(project_path, dict_one_pub: dict) -> int:
    """
    Initiate and post a thread of tweets
    Args:
        dict_one_pub: dictionary object with processed publication item
        maxlength: length of the message to post (max tweet is 280 char)
        count: count of replies on the thread

    Returns: tweet id of the first tweet of thread

    """

    tw_handle = os.getenv("HANDLE")
    api = twitter_setup()


    long_string = dict_one_pub["abstract"]
    string_list = textwrap.wrap(long_string, 240, drop_whitespace=False)

    catch_dict = {}
    for i, c in enumerate(string_list):
        catch_dict[f"{i}"] = {"text": c}
    count=0

    try_list=["0",api.update_status(status=compose_message(project_path,len(catch_dict), dict_one_pub))
    ]
    telegram_bot_sendtext(f"Posting thread:, twitter.com/{tw_handle}/status/{try_list[1].id}")


    for i in catch_dict:
        count+=1
        if count < len(catch_dict):
            time.sleep(2)
            thread_message = (
                        insert_hashtag(project_path, catch_dict[i]["text"]) + f" ...{count+1}/{len(catch_dict)+1}"
                    )
            try_list.append(update_thread(thread_message, try_list[count], api))

        else:
            last_msg = shorten_text(dict_one_pub["pub_date"] + " " + dict_one_pub["author-s"], 250) + f" ...{count+1}/{len(catch_dict)+1} \n\U0001F331"

            update_thread(last_msg, try_list[count], api)

    return try_list[1].id


def read_rss_and_tweet(logger, project_path) -> None:
    """

    Read RSS objects and tweet one calling the post thread function
    Returns: None, updates log file with the posted article id

    """

    paths_dict = make_path_dict(project_path)
    rss_list = retrieve_rss_urls(project_path)
    dict_publications = make_literature_dict(rss_list["combined_feed"])

    with open(paths_dict["posted_urls_output_file"], "r") as jsonFile:
        article_log = json.load(jsonFile)

    if all(item in article_log.keys() for item in dict_publications.keys()):

        telegram_bot_sendtext("rss empty trying older articles")
        dict_publications = make_literature_dict(rss_list["feed_older_literature"])

    for article in sorted(dict_publications.keys(), reverse=True):

        if not is_in_logfile(article, paths_dict["posted_urls_output_file"]):
            try:
                article_log[article] = {
                    "count": 1,
                    "tweet_id": post_thread(project_path, dict_publications[article]),
                }

                write_to_logfile(article_log, paths_dict["posted_urls_output_file"])
                break
            except tweepy.TweepyException as e:
                logger.error(f"RSS error, possible duplicate {e}, {article}")
                write_to_logfile(article_log, paths_dict["posted_urls_output_file"])
                rss_list = retrieve_rss_urls(project_path)
                continue


def post_tweet(logger, message: str) -> None:
    """
    Post tweet message to account.
    Args:
        message: Message to post on Twitter

    Returns: None

    """
    try:
        twitter_api = twitter_setup()
        logger.info(f"post_tweet():{message}")
        twitter_api.update_status(status=message)
    except tweepy.TweepyException as e:
        logger.error(e)


def filter_repeated_tweets(project_path, result_search: list, flag: str) -> list:
    """

    Args:
        result_search:
        flag:

    Returns:

    """
    paths_dict = make_path_dict(project_path)


    if flag == "give_love":
        out_file = paths_dict["faved_tweets_output_file"]
    else:
        out_file = paths_dict["posted_retweets_output_file"]

    unique_results = {}

    for status in result_search:
        if hasattr(status, "retweeted_status"):
            check_id = status.retweeted_status.id_str
        else:
            check_id = status.id_str

        if not is_in_logfile(check_id, out_file):
            unique_results[status.full_text] = status

    return [unique_results[x] for x in unique_results]


def json_add_entry(project_path, object_id: str) -> None:
    """
    add user to the interactions json file
    Args:
        object_id: object id

    Returns: None

    """

    if "users.json" in project_path:

        with open(project_path, "r") as json_file:
            users_dic = json.load(json_file)
        if object_id not in users_dic:
            users_dic[object_id] = {"follower": False, "interactions": 1}
        else:
            users_dic[object_id]["interactions"] += 1
    
        with open(project_path, "w") as json_file:
            json.dump(users_dic, json_file, indent=4)
            
    elif "faved-tweets" in project_path:
        
        with open(project_path, "r") as json_file:
            favs_dic = json.load(json_file)
        if object_id not in favs_dic:
            favs_dic[object_id] = {"follower": False, "interactions": 1}
        else:
            favs_dic[object_id]["interactions"] += 1

        with open(project_path, "w") as json_file:
            json.dump(favs_dic, json_file, indent=4)
        
        


def get_query(project_path) -> str:
    """
    Create Twitter search query with included words minus the
    excluded words.

    Returns:  string with the Twitter search query

    """

    keywords_dict = retrieve_keywords(project_path)


    include = " OR ".join(keywords_dict["retweet_include_words"])
    exclude = " -".join(keywords_dict["retweet_exclude_words"])
    exclude = "-" + exclude if exclude else ""
    return include + " " + exclude


def check_interactions(project_path, tweet) -> None:
    """
    check if previously interacted with a user
    Args:
        tweet:

    Returns:

    """
    paths_dict = make_path_dict(project_path)

    if tweet.author.screen_name.lower() == os.getenv("HANDLE"):
        pass  # don't fav your self

    auth_id = tweet.author.id_str
    with open(paths_dict["users_json_file"], "r") as json_file:
        users_dic = json.load(json_file)

        user_list = [
            users_dic[x]["interactions"]
            for x in users_dic
            if users_dic[x]["follower"] == False
        ]

        down_limit = round(sum(user_list) / len(user_list))

        if auth_id in users_dic:
            if users_dic[auth_id]["interactions"] >= down_limit:
                return True
            else:
                return False
        else:
            return False


def try_retweet(project_path, logger,
    twitter_api: tweepy.API, tweet_text: str, in_tweet_id: str, self_followers: list
) -> None:
    """
    try to retweet, if already retweeted try next fom the list
    of recent tweets
    Args:
        twitter_api:
        tweet_text:
        in_tweet_id:
        self_followers:

    Returns:

    """

    tweet_id = find_simple_users(logger, project_path, twitter_api, in_tweet_id, self_followers)
    paths_dict = make_path_dict(project_path)

    if not is_in_logfile(in_tweet_id, paths_dict["posted_retweets_output_file"]):
        try:
            twitter_api.retweet(id=tweet_id)
            logger.info(f"Trying to rt {tweet_id}")
            write_to_logfile({in_tweet_id: {}}, paths_dict["posted_retweets_output_file"])
            _status = twitter_api.get_status(tweet_id)
            json_add_entry(project_path, _status.author.id_str)
            if tweet_id == in_tweet_id:
                id_mess = f"{tweet_id} original"
            else:
                id_mess = f"{tweet_id} from a nested profile"
            message_log = (
                "Retweeted and saved to file >  https://twitter.com/i/status/{}".format(
                    id_mess
                )
            )
            logger.info(message_log)
            telegram_bot_sendtext(message_log)
            return True
        except tweepy.TweepyException as e:
            if e.api_codes in IGNORE_ERRORS:
                write_to_logfile(
                    {in_tweet_id: {}}, paths_dict["posted_retweets_output_file"]
                )
                logger.exception(e)
                return False
            else:
                logger.error(e)
                return True
    else:
        logger.info(
            "Already retweeted {} (id {})".format(
                shorten_text(tweet_text, maxlength=140), tweet_id
            )
        )


def find_simple_users(logger, project_path,
    twitter_api: tweepy.API, tweet_id: str, followers_list: list
) -> int:
    """
    retweet/fav from users retweeting something interesting
    Args:
        twitter_api:
        tweet_id:
        followers_list:

    Returns: id of the retweeted/faved tweet

    """
    # get original retweeter:
    tweet_object = twitter_api.get_status(tweet_id, tweet_mode="extended")


    try:
        original_id = tweet_object.retweeted_status.id
        retweeters = twitter_api.get_retweets(original_id)
    except AttributeError:  # Not a Retweet
        retweeters = twitter_api.get_retweets(tweet_id)

    future_friends = []
    for retweet in retweeters:

        if check_interactions(project_path, retweet):
            continue
        try:
            follows_friends_ratio = (
                retweet.author.followers_count / retweet.author.friends_count
            )
        except ZeroDivisionError:
            follows_friends_ratio = 0

        future_friends_dic = {
            "id_str": retweet.author.id_str,
            "friends": retweet.author.friends_count,
            "followers": retweet.author.followers_count,
            "follows_friends_ratio": follows_friends_ratio,
        }
        if future_friends_dic["friends"] > future_friends_dic["followers"]:
            future_friends.append(
                (
                    future_friends_dic["follows_friends_ratio"],
                    retweet.id_str,
                    future_friends_dic,
                )
            )
        else:
            future_friends.append(
                (future_friends_dic["followers"], retweet.id_str, future_friends_dic)
            )
    if future_friends:
        try:  # give prioroty to non followers of self
            min_friend = min(
                [x for x in future_friends if x[2]["id_str"] not in followers_list]
            )
            logger.info(
                f"try retweeting/fav https://twitter.com/i/status/{min_friend[1]} from potential friend profile: {min_friend[2]['id_str']} friends= {min_friend[2]['friends']}, followrs={min_friend[2]['followers']}"
            )
            return min_friend[1]
        except:
            min_friend = min(future_friends)
            logger.info(
                f"try retweeting/fav https://twitter.com/i/status/{min_friend[1]} from potential friend profile: {min_friend[2]['id_str']} friends= {min_friend[2]['friends']}, followrs={min_friend[2]['followers']}"
            )
            return min_friend[1]
    else:
        logger.info(
            f"try retweeting from original post: https://twitter.com/i/status/{tweet_id}"
        )
        return tweet_id


def filter_tweet(logger, project_path, search_results: list, twitter_api):

    """
    function to ensure that retweets are on-topic
    by the hashtag list

    Args:
        search_results:
        twitter_api:

    Returns:

    """
    filtered_search_results = []

    keywords_dict = retrieve_keywords(project_path)
    paths_dict = make_path_dict(project_path)

    for status in search_results:

        faved_sum = (
            status.retweet_count,
            status.favorite_count,
            status.retweet_count + status.favorite_count,
        )

        if status.is_quote_status:
            try:
                quoted_tweet = twitter_api.get_status(
                    status.quoted_status_id, tweet_mode="extended"
                )

            except tweepy.TweepyException as e:
                telegram_bot_sendtext(f"ERROR {e}, twitter.com/anyuser/status/{status.id_str}")
                continue
            except AttributeError as a:
                telegram_bot_sendtext(f"ERROR {a}, twitter.com/anyuser/status/{status.id_str}")
                continue



            end_status = get_longest_text(status) + get_longest_text(quoted_tweet)
        else:
            end_status = get_longest_text(status)

        if len(end_status.split()) > 3 and faved_sum[2] > 1:

            joined_list = keywords_dict["add_hashtag"] + keywords_dict["retweet_include_words"]

            # remove elements from the exclude words list
            keyword_matches = [
                x
                for x in joined_list + keywords_dict["watch_add_hashtag"]
                if x in end_status.lower()
                and not any(
                    [
                        x
                        for x in keywords_dict["retweet_exclude_words"]
                        if x in end_status.lower()
                    ]
                )
            ]

            if keyword_matches:

                if any(
                    [x for x in keyword_matches if x not in keywords_dict["watch_add_hashtag"]]
                ) and not is_in_logfile(status.id_str, paths_dict["faved_tweets_output_file"]):

                    filtered_search_results.append(
                        (faved_sum, status.id_str, status.full_text)
                    )
                else:
                    logger.info(f">> skipped, {keyword_matches}, {end_status}")

    return sorted(filtered_search_results)


def try_give_love(logger, project_path, twitter_api, in_tweet_id, self_followers, now=False):
    """
    try to favorite a post from simple users
    Args:
        twitter_api:
        in_tweet_id:
        self_followers:

    Returns:

    """
    # todo add flag to use sleep or fav immediately

    paths_dict = make_path_dict(project_path)

    if not already_fav(in_tweet_id, twitter_api):

        tweet_id = find_simple_users(logger, project_path, twitter_api, in_tweet_id, self_followers)

        try:
            if not now:
                time.sleep(randint(0, 250))
            twitter_api.create_favorite(id=tweet_id)
            json_add_entry(paths_dict["faved_tweets_output_file"], in_tweet_id)

            # write_to_logfile({in_tweet_id: {}}, paths_dict["faved_tweets_output_file"])
            _status = twitter_api.get_status(tweet_id)
            json_add_entry(paths_dict["faved_tweets_output_file"], in_tweet_id)
            message_log = (
                "faved tweet succesful: https://twitter.com/i/status/{}".format(
                    tweet_id
                )
            )
            logger.info(message_log)
            telegram_bot_sendtext(message_log)

            return True

        except tweepy.TweepyException as e:
            if e.api_codes in IGNORE_ERRORS:
                logger.debug(f"throw a en error {e}")
                logger.exception(e)
                telegram_bot_sendtext(f"{e}")
                return False
            else:
                json_add_entry(paths_dict["faved_tweets_output_file"], in_tweet_id)
                logger.error(e)
                telegram_bot_sendtext(f"{e}")
                return True

    else:
        logger.info("Already faved (id {})".format(in_tweet_id))
        telegram_bot_sendtext("Already faved (id {})".format(in_tweet_id))


def fav_or_tweet(logger,project_path,  max_val, flag, twitter_api, now=False):
    """

    use a tweet or a fav function depending on the flag called
    Args:
        max_val:
        flag:
        twitter_api:

    Returns:

    """

    self_followers = get_followers_list(project_path)
    count = 0

    while count < len(max_val):

        tweet_id = max_val[-1 - count][1]
        tweet_text = max_val[-1 - count][2]
        logger.info(f"{len(tweet_text.split())}, {tweet_text}")

        if flag == "give_love":
            use_function = try_give_love(logger, project_path, twitter_api, tweet_id, self_followers, now)
            log_message = "fav"

        else:
            use_function = try_retweet(project_path, logger,
                twitter_api, tweet_text, tweet_id, self_followers
            )
            log_message = "retweet"

        if use_function:
            logger.info(f"{log_message}ed: id={tweet_id} text={tweet_text}")
            break
        else:
            count += 1
            time.sleep(2)
            if count >= len(max_val):
                logger.debug("no more tweets to post")
            continue


def search_and_retweet(logger, project_path, flag: str = "global_search", count: int = 100, now=False):
    """
    Search for a query in tweets, and retweet those tweets.

    Args:
        flag: A query to search for on Twitter. it can be `global_search` to search globally
              or `list_search` reduced to a list defined on mylist_id
        count: Number of tweets to search for. You should probably keep this low
               when you use search_and_retweet() on a schedule (e.g. cronjob)

    Returns: None

    """

    list_id = os.getenv("LIST_ID")
    list_id_alt = os.getenv("ALTLIST_ID")

    try:
        twitter_api = twitter_setup()
        if flag == "global_search":
            # search results retweets globally forgiven keywords
            search_results = twitter_api.search(
                q=get_query(project_path), count=count, tweet_mode="extended"
            )  # standard search results
        elif flag == "list_search":
            # search list retwwets most commented ad rt from the experts lists
            search_results = twitter_api.list_timeline(
                list_id=list_id, count=count, tweet_mode="extended"
            )  # list to tweet from


        elif flag == "give_love":
            search_results = twitter_api.list_timeline(
                list_id=list_id, count=count, tweet_mode="extended"
            ) + twitter_api.list_timeline(
                list_id=list_id_alt, count=count, tweet_mode="extended"
            )

    except tweepy.TweepyException as e:
        logger.exception(e)
        telegram_bot_sendtext(f"ERROR: {e}")
        return
    except Exception as e:
         telegram_bot_sendtext(f"ERROR: {e}")

    # get the most faved + rtweeted and retweet it
    max_val = filter_tweet(logger, project_path, filter_repeated_tweets(project_path, search_results, flag), twitter_api)
    fav_or_tweet(logger, project_path, max_val, flag, twitter_api, now)


banned_profiles = ['nydancesafe']

def vgnHeroCalc( name_, vgnbdays):
    return f"""#VgnHeroes @{name_}, since your #VgnBday you have saved:
💧 {int(vgnbdays*4.16)} L of water,
🌽 {vgnbdays*18} kg of grain,
🌲 {vgnbdays*3} Sq.m of 🌲 land,
☁️ {vgnbdays*9} kg CO2 &,
🐄 {vgnbdays*0.22} Animal lives!!
me & {vgnbdays*0.22} Animals thank you!

source: 5vegan.org"""

banned_profiles = ['nydancesafe']

pattern = r'\d{2} \d{2} \d{4}'
pattern2 = r'\d{4}'

date_wrong = True
today = datetime.datetime.now()


def listen_stream_and_rt():
    self_ids = os.getenv("TWT_ID"), os.getenv("TWT_ID")
    twitter_api = twitter_setup()
    keywords_list = ['vgnbday', 'veganbday', 'vegansince', '#vegansince', 'vegan since']

    class IDPrinter(tweepy.StreamingClient):

        def on_tweet(self, status):

            _status = twitter_api.get_status(status.id)
            answer_id = status.id

            tweet_ = status.text
            author_name = _status.author.screen_name.lower()
            vgndayrex = re.findall(pattern, tweet_)
            vgndayrex2 = re.findall(pattern2, tweet_)
            message_to_post = ""

            if hasattr(_status, "retweeted_status"):  # Check if Retweet
                pass

            elif status.author_id in self_ids or author_name.lower() == "vgnbot":
                pass

            elif not any(ext in tweet_.lower() for ext in keywords_list):
                pass

            else:
                ## catch nesting
                if author_name in banned_profiles:
                    pass
                elif hasattr(_status, "retweeted_status"):
                    if author_name in status.in_reply_to_screen_name:
                        pass

                elif vgndayrex2:
                    print(vgndayrex, vgndayrex2, author_name)

                    print(tweet_)

                    try:
                        vgnbday = datetime.datetime.strptime(vgndayrex[0], "%d %m %Y")
                        if vgnbday < today:
                            vgnbdays = today - vgnbday
                            message_to_post = vgnHeroCalc(author_name, vgnbdays.days)

                    except IndexError:
                        print("Wrong or inconplete format")
                        if vgndayrex2:
                            vgnbday = datetime.datetime.strptime(vgndayrex2[0], "%Y")
                            if vgnbday < today:
                                vgnbdays = today - vgnbday
                                message_to_post = vgnHeroCalc(author_name, vgnbdays.days)
                    except ValueError:
                        pass

                    except AttributeError as e:

                        answer_id = status.id

                        print(e)

                        # telegram_bot_sendtext(f"ATRIB ERROR: {replied_to}, 'nesting', {in_reply_to_user_id}, 'replied to', {replied_to}, 'message', {status.text}")

                    api = twitter_setup()

                    if message_to_post:
                        try:
                            update_status = f"""{message_to_post}

        https://twitter.com/{status.author_id}/status/{answer_id}
                     """
                            api.update_status(update_status, in_reply_to_status_id=answer_id,
                                              auto_populate_reply_metadata=True)
                        except tweepy.errors.Forbidden:
                            update_status = f"""{message_to_post[:-20]}

        https://twitter.com/{status.author_id}/status/{answer_id}
                     """
                            api.update_status(update_status[:-20], in_reply_to_status_id=answer_id,
                                              auto_populate_reply_metadata=True)

                        telegram_bot_sendtext(f"Quoting: https://twitter.com/{status.author_id}/status/{answer_id}")

            def on_error(self, status):
                telegram_bot_sendtext(f"ERROR with: {status}")

    streaming_client = IDPrinter(bearer_token=os.getenv("BEARER_TOKEN"), wait_on_rate_limit=True)

    try:
        streaming_client.add_rules(tweepy.StreamRule(" OR ".join(keywords_list)))
        streaming_client.filter()
    except Exception as ex:
        telegram_bot_sendtext(f"ERROR with: {ex}")
        pass


def display_help():
    """
    Show available commands.

    Returns: Prints available commands

    """

    print("Syntax: python {} [data dir] [command]".format(sys.argv[0]))
    print()
    print(" Commands:")
    print("    rss    Read URL and post new items to Twitter")
    print("    rtg    Search and retweet keywords from global feed")
    print("    rtl    Search and retweet keywords from list feed")
    print("    glv    Fav tweets from list or globally")
    print("    glvn   Fav tweets NOW from list or globally")
    print("    rto    Retweet last own tweet")
    print("    sch    Run scheduled jobs on infinite loop")
    print("    help   Show this help screen")


if __name__ == "__main__":
    main()

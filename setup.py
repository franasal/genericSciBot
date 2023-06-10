#!/usr/bin/python3.6
from setuptools import setup

setup(
    name="twitterscibot",
    version="1.0.0",
    description="Bot for sci-com and policy-com ",
    url="https://github.com/fanasal/genericSciBot",
    license="GNU Affero General Public License v3.0",
    packages=["twitbot4"],
    keywords=[
        "psychedelics",
        "fact-checking",
        "sci-com",
        "drug policy",
        "research",
        "science",
    ],
    entry_points={
        "console_scripts": [
            "twitbot4=twitbot4.main:main",
        ]
    },
    install_requires=[
        "beautifulsoup4==4.9.3",
        "python-dateutil==2.8.2",
        "feedparser==6.0.2",
        "oauthlib==3.2.0",
        "python-dotenv==0.15.0",
        "requests==2.27",
        "requests-oauthlib==1.3.0",
        "schedule==0.6.0",
        "telebot==0.0.4",
        "Telethon==1.18.2",
        "tweepy==4.14.0",
        "urllib3==1.26.7",
    ],
    zip_safe=False,
)

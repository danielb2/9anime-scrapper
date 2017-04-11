#!/usr/bin/env python
import logging
import json
import re
import sys
import string
import os.path

import requests
from bs4 import BeautifulSoup
from optparse import OptionParser

BASE_URL = "https://9anime.to"
GRABBER_API = BASE_URL + "/grabber-api/"
INFO_API = BASE_URL + '/ajax/episode/info'
CFG_FILE = '9anime.json'
RESOLUTIONS = {
    '360p': 0,
    '480p': 1,
    '720p': 2,
    '1080p': 3,
    0: '360p',
    1: '480p',
    2: '720p',
    3: '1080p'
}

def get_mp4(id):
    payload = {
        'id': id
    }

    details = requests.get(INFO_API, params=payload)
    details=details.json()
    payload['token'] = details['params']['token']
    logging.info("Acquired token %s when requested from id %s" % (payload['token'], payload['id']))
    data = requests.get(GRABBER_API, params=payload)
    data=data.json()['data']
    logging.info("Recieved %i different links for id %s" % (len(data), payload['id']))
    return data

def getAllEpisodes(options):
    data = {
        "episodes": [],
    }

    page = BeautifulSoup(requests.get(options.link).content,"lxml")

    servers = page.findAll("div", {"class": "server row"})

    data["title"] = page.findAll("h1", {"class": "title"})[0].text

    episodeCount = 0
    serverNo = 1

    for server in servers:
        episodes = server.findAll("a")
        if len(episodes) > episodeCount:
            episodeCount = len(episodes)
        for episode in episodes:
            data['episodes'].append({
                'id': episode['data-id'],
                'link': episode['href'],
                'number': episode['data-base'],
                'title': data['title'],
                'server': serverNo
                })
        serverNo += 1

    if not options.finish:
        options.finish = episodeCount
        print "last episode number is: %d" % episodeCount

    return data


def append_file(handle, link, episode, resolution):

    resolution = RESOLUTIONS[resolution]
    link += ".type=video/mp4"
    episodeNumber = string.rjust(episode['number'],3,"0")
    link += "&title=%s-%s-%s\n" % (episode['title'], episodeNumber, resolution)
    handle.write(link)

def get_link(options):

    resolution = RESOLUTIONS[options.resolution]
    data = getAllEpisodes(options)
    outFile = open(options.output,'w')
    last_episode = options.start - 1

    wanted = range(options.start, options.finish+1)
    for episode in data['episodes']:
        current_res = resolution
        episodeNumber = int(episode['number'])

        if not int(episode['number']) in wanted:
            continue

        links=get_mp4(episode['id'])

        while current_res > 0 and episodeNumber in wanted:
            try:
                dwnld_link=links[current_res]['file']
                append_file(outFile, dwnld_link, episode, current_res)
                wanted.remove(episodeNumber)
                last_episode = episodeNumber
            except IndexError:
                tmp_res = RESOLUTIONS[current_res]
                current_res -= 1
                print "%s is unavailable for episode %s on server %d, attempting %s" % ( tmp_res, episode['number'], episode['server'], RESOLUTIONS[current_res])
                continue

    if options.cfg:
        write_cfg({
            'link': options.link,
            'next': last_episode + 1,
            'resolution': options.resolution,
            'batchsize': options.batchsize
        })

    outFile.close()


def parse():
    usage = """usage: %prog [options] url
    url: the url of the anime (ex:http://9anime.to/watch/masamune-kun-no-revenge.pyr9)

    Additional:

    The episode paramter allows to specify a range delimited by '-'

    -e 7-  #=> downloads all episodes from episode 4 and onward
    -e -7  #=> downloads episodes 1-4
    -e 3-5 #=> downloads episodes 3-5 ( shortcut for -s 3 -f 5 )
    -e 7 #=> downloads episode 7 ( shortcut for -s 7 -f 7 )"""

    parser = OptionParser(usage)
    parser.add_option("-o", "--output",
            help="write report to FILE [default: %default]", default="dwnld_links.txt")
    parser.add_option("-s", "--start",
                    default=1,
                    type="int",
                    help="episode to begin with [default: %default]")
    parser.add_option("-f", "--finish",
            type="int",
            help="episode to finish with [default: %default]")
    parser.add_option("-e", "--episode",
            help="episode to download. Can also use a range: (ex: 4- all episodes from for on) [default: %default]")
    parser.add_option("-r", "--resolution",
            default="720p",
            choices=['360p','480p','720p','1080p'],
            help="resolution of download: 360p, 480p, 720p, 1080p [default: %default]")
    parser.add_option("-b", "--batchsize",
            default='10',
            help='number of episodes to generate next batch for when reading from 9anime.json')

    return parser.parse_args()

def main():
    (options, args) = parse()

    options.cfg = True

    if len(args) > 0:
        options.link = args[0]

    if os.path.isfile(CFG_FILE):
        with open(CFG_FILE) as json_data:
            cfg = json.load(json_data)
            options.resolution = cfg['resolution']
            options.start = int(cfg['next'])
            options.batchsize = options.batchsize or int(cfg['batchsize'])
            options.finish = options.start + options.batchsize
            options.link = cfg['link']
        if options.episode:
            options.cfg = False

    if options.episode:
        episodes = string.split(options.episode, '-')
        options.start = int(episodes.pop(0) or 1)
        options.finish = options.start
        if len(episodes) >= 1:
            if episodes[0]:
                options.finish = int(episodes.pop(0))
            else:
                options.finish = None

    if options.finish and options.start > options.finish:
        print "ERROR: Start must be smaller than finish"
        exit(-1)

    get_link(options)

def write_cfg(args, isOK):
    with open(CFG_FILE, 'w') as outfile:
        json.dump(args, outfile)


main()



import praw
import urllib.request
import requests
import os
import datetime
from bs4 import BeautifulSoup
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
from pathlib import Path
import subprocess
import re
import shutil

# uncomment to enable shutdown option
# shutdown  =  None
# while shutdown != 'y' and  shutdown  !=  'n':
#     shutdown = input("Do you wish to shutdown after script? (y/n): ").lower()
# if shutdown == 'y': 
#     print("shutting down after script")
# else:
#     print("not shutting after script")

num = ['zero', 'one',  'two',  'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

today = datetime.date.today()
yesterday = today - datetime.timedelta(1)
new_path = f'{today}_scraped_videos'
old_path = f'{yesterday}_scraped_videos'

if not os.path.exists(new_path):
    os.makedirs(new_path)
if not os.path.exists(old_path):
    os.makedirs(old_path)

tda = today - datetime.timedelta(2) # two days ago
tda_path = f'{tda}_scraped_videos'
tda_final = f"{tda}_final_video.mp4"
print("deleting files and folder created 2 days ago")
if os.path.exists(tda_path):
    shutil.rmtree(tda_path)
if os.path.exists(tda_final):
    os.remove(tda_final)
print("done")

user_agent, secret, client_id = '', '', ''
reddit = praw.Reddit(client_id=client_id, client_secret=secret, user_agent=user_agent)
cid = ''

print('started scraping LSF')
top_posts = reddit.subreddit('LivestreamFail').top(limit=15, time_filter='day')
counter = 0
f_counter = 0
title_author = {}
highest_upvotes = 0

for post in top_posts:
    url_link = post.url
    author = post.author
    clip_title  = post.title[:40]
    while not re.match(r'^\w+$', clip_title):   # remove all digits and special char in file name
        clip_title = re.sub('[^A-Za-z]+', '', clip_title)
    if post.link_flair_text and post.link_flair_text.lower() == 'cx': # first check if tag object is not None
        continue    # skip Cx clips
    try:
        slug = url_link.split('/')[3].replace('\n', '')
        if '?' in slug:
            slug = slug.split('?')[0]
        clip_info = requests.get("https://api.twitch.tv/helix/clips?id=" + slug, headers={"Client-ID": cid}).json()
        clip_url = clip_info['data'][0]['thumbnail_url'].split('-preview-')[0]
        clip_url = f'{clip_url}.mp4'
        clip_title = ''.join(e for e in clip_title if e.isalnum() or e=="_")
        file_path = f'{new_path}/{clip_title}.mp4'
        old_file_path = f'{old_path}/{clip_title}.mp4'
        if os.path.exists(old_file_path) or os.path.exists(file_path):
            print('already exists', post.title)
            idx = file_path.index('.')  # my key is set arbritarily according to file path, conincidences are unlikely but possible
            mykey = file_path[idx-5:idx] + file_path[0]
            title_author[mykey] = (post.title, post.author)
        else:
            try:
                urllib.request.urlretrieve(clip_url, file_path)
                print('downloaded', post.title)
                idx = file_path.index('.')  # my key is set arbritarily according to file path, conincidences are unlikely but possible
                mykey = file_path[idx-5:idx] + file_path[0]
                title_author[mykey] = (post.title, post.author)
                if post.ups > highest_upvotes:
                    top_clip_title = post.title
                    highest_upvotes = post.ups
                counter += 1
            except Exception as e:  # problem with clip asset
                print('failed for', post.title)
                print(e)
                print(clip_url)
                f_counter += 1
        
    except Exception as e:  # deleted twitch clip or not twitch clip
        
        print(post.title)
        print('deleted clip or not twitch clip detected, attemping to recover mirrored link')
        first_comment = post.comments[0]
        if first_comment.stickied and first_comment.author == 'livestreamfailsbot':
            body = first_comment.body
            i = body.find('https')
            body = body[i:]
            i  = body.find(')') 
            post_url = body[:i]
            resp = requests.get(post_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            tag = soup.find('video', {'class': 'clip-video'})
            clip_url = tag.find('source')['src']
            resp = requests.get(clip_url, stream=True)
            file_path = f'{new_path}/{clip_title}.mp4'
            old_file_path = f'{old_path}/{clip_title}.mp4'
            if os.path.exists(old_file_path) or os.path.exists(file_path):
                print('already exists', post.title)
                idx = file_path.index('.')  # my key is set arbritarily according to file path, conincidences are unlikely but possible
                mykey = file_path[idx-5:idx] + file_path[0]
                title_author[mykey] = (post.title, post.author)
            else:
                try:
                    with open(file_path, 'wb') as f: 
                        for chunk in resp.iter_content(chunk_size = 1024*1024): 
                            if chunk: 
                                f.write(chunk) 
                    print('recovered', post.title)
                    print('downloaded', post.title)
                    idx = file_path.index('.')  # my key is set arbritarily according to file path, conincidences are unlikely but possible
                    mykey = file_path[idx-5:idx] + file_path[0]
                    title_author[mykey] = (post.title, post.author)
                    if post.ups > highest_upvotes:
                        top_clip_title = post.title
                    counter += 1
                except Exception as e:
                    print('failed for', post.title)
                    print(e)
                    print(clip_url)
                    f_counter += 1
        else:
            print("livestreamfail bot not present :(")
            f_counter += 1

print(f'downloaded {counter} videos in total, failed for {f_counter}')
print('proceeding to compile final video')
pathlist = Path(new_path+'/').glob('**/*.mp4')
final_video = []
for path in pathlist:
    path_in_str = str(path)
    print('adding:', path_in_str)
    idx = path_in_str.index('.')  # key is set arbritarily according to file path, conincidences are unlikely but possible
    mykey = path_in_str[idx-5:idx] + path_in_str[0]
    try:
        title, author = title_author[mykey]
    except KeyError:    #  note: keyerror is perfectly legal, meaning videos in today's file are not included in the scraped videos upon runtime, ie the videos scraped earlier today are not included this time
        continue
    try:
        clip = VideoFileClip(path_in_str).resize( (1920, 1080) ) # original was width=1600 or height=1080
        final_title = ''
        x = 0
        while len(title) > 30:
            part = title[:30]
            try:
                idx = part[::-1].index(' ')
            except:
                #  there is no whitespace in the title eg: AAAAAAAAAAA but still length more than 30
                title = title[:27] + '...'
                break
            part = part[::-1][idx:][::-1]
            final_title += part+'\n'
            title = title.replace(part, '')
            x += 0.5
        final_title+=title
        txt_title = (TextClip(f"{final_title}\nclipped by u/{author}", fontsize=80,
                    font="Century-Schoolbook-Roman", color="white", bg_color='black')
                    .margin(top=15, opacity=0)
                    .set_position(("center")))
        title = CompositeVideoClip([clip.to_ImageClip(), txt_title]).fadein(.5).set_duration(3.5+x) #x is decided by how many lines, each line adds 0.5s
        edit_clip = concatenate_videoclips([title, clip])
        final_video.append(edit_clip)
    except:
        print('failed for', path_in_str)
final_clip = concatenate_videoclips(final_video)
final_clip.write_videofile(f"final_videos/{today}_final_video.mp4")

print("compiled final video")
top_clip_title = top_clip_title.replace('"', "'")
# checking video title length
if len(top_clip_title) > 59:
    top_clip_title = top_clip_title[:57]+'...'

print(f"uploading to youtube: {top_clip_title}! -Trending on LivestreamFail {today}")

details = f'--file="final_videos/{today}_final_video.mp4" --title="{top_clip_title}! -Trending on LivestreamFail {"/".join(str(today).split("-")[::-1])}" --description="All the trending videos on r/LivestreamFail. I do not own any of the materials in the video and if you wish for your clip to be taken down, kindly notify me and I will remove them." --keywords="Livestream Fail, livestreamfail, Mizkif, Nymn, m0xyy, xqc, XQC, forsen, hachubby, funny, recap, compilation, GGX, greekgodx, trainwreckstv, Fails" --category="20" --privacyStatus="public"'

with open('yt_upload.bat', 'w') as f:
    f.write(f'"D:\\Anaconda\\python.exe" "upload_video.py" {details}')

try:
    subprocess.call(['yt_upload.bat'])
    print("upload complete, all done")
except Exception as e:
    print("Error uploading")
    print(f"Error: {e}")

# if shutdown == 'y': 
#     os.system("shutdown /s /t 1") 
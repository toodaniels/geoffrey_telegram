import re
import pytube


def download_video(video_url):
    # Cree un objeto Pytube para el video
    video = pytube.YouTube(video_url)

    video_title = video.title
    video_title = re.sub(r'yo quiero que este sea el mundo que conteste+', '', video_title)
    video_title = re.sub(r'Lyrics+', '', video_title)
    video_title = re.sub(r'Letra+', '', video_title)
    # video_title = video_title.strip()\
    #         .replace('\n', ' ').replace('/', '').replace('(', '').replace(')', '')
        
    video_title = re.sub(r'[^a-zA-Z0-9._\-\s]', '', video_title)
    video_title = video_title.strip()
    # video_title = re.sub(r'_+', '_', video_title)
    
    # Filtre los flujos de audio
    audio_streams = video.streams.filter(only_audio=True)

    # Descargue el flujo de audio
    audio_streams[0].download(filename=f"downloaded/{video_title}.mp3")


video_list = [
    "https://www.youtube.com/watch?v=9mI7nt40554&list=RD9mI7nt40554&start_radio=1",
    "https://www.youtube.com/watch?v=As6pQlCkbns&list=RD9mI7nt40554&index=2",
    "https://www.youtube.com/watch?v=860ymv-cWLA&list=RD9mI7nt40554&index=3",
    "https://www.youtube.com/watch?v=63pTpAAF0HM&list=RD9mI7nt40554&index=4",
    "https://www.youtube.com/watch?v=0fStdU-CBTI&list=RD9mI7nt40554&index=5",
    "https://www.youtube.com/watch?v=BlhSvoMifVk&list=RD9mI7nt40554&index=7",
    "https://www.youtube.com/watch?v=sDMxQF18yvA&list=RD9mI7nt40554&index=8",
    "https://www.youtube.com/watch?v=J8NrkPLDi_k&list=RD9mI7nt40554&index=9",
    "https://www.youtube.com/watch?v=GfUqp8gKFuQ&list=RD9mI7nt40554&index=10",
    "https://www.youtube.com/watch?v=y9e-IJ1qY_Q&list=RD9mI7nt40554&index=12",
    "https://www.youtube.com/watch?v=Ba8ZAD7Moeg&list=RD9mI7nt40554&index=13",
    "https://www.youtube.com/watch?v=nfezTxgrcUo&list=RD9mI7nt40554&index=12",
    "https://www.youtube.com/watch?v=joh4iX1bigA&list=RD9mI7nt40554&index=14",
    "https://www.youtube.com/watch?v=VtX_9bAFIyA&list=RD9mI7nt40554&index=15",
    "https://www.youtube.com/watch?v=Fj_lZC66-hw&list=RD9mI7nt40554&index=19",
    "https://www.youtube.com/watch?v=5UpGvpqFZCA&list=RD9mI7nt40554&index=20",
    "https://www.youtube.com/watch?v=_WVorCizHZs&list=RD9mI7nt40554&index=22",
    "https://www.youtube.com/watch?v=IZjy-W5tqBI&list=RD9mI7nt40554&index=22",
    "https://www.youtube.com/watch?v=Vt5pqoa_cjY&list=RD9mI7nt40554&index=24",
    "https://www.youtube.com/watch?v=_gTsBdYntp4&list=RD9mI7nt40554&index=26",
    "https://www.youtube.com/watch?v=5TFzTmVnu18&list=RD9mI7nt40554&index=27",
    "https://www.youtube.com/watch?v=ON7H_L0K5MY&list=RD9mI7nt40554&index=23",
    "https://www.youtube.com/watch?v=ZDbCCPxwqBI&list=RD9mI7nt40554&index=28",
    "https://www.youtube.com/watch?v=ZcKKO_TAocs&list=RD9mI7nt40554&index=27",
    "https://www.youtube.com/watch?v=b82IdqplUPI",
    "https://www.youtube.com/watch?v=8G_-Jt9vezQ"
]

for video_url in video_list:
    download_video(video_url)

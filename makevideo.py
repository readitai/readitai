from moviepy.editor import *
from PIL import Image, ImageOps
import numpy as np
from glob import glob


def make_youtube_video(introfile, audiofile, cover_img, outputfn, firstchapter=False):
    """
    Generate a video of an audiobook file given following parameters.
    :param introfile: introduction video clip (ie. introduction of Readit AI)
    :param audiofile: audiobook recording (wav, mp3, etc)
    :param cover_img: cover image during the audiobook playback
    :param outputfn: output filename of the youtube video
    :param firstchapter: boolean (determines whether to place audio clip from the introfile)
    :return: None
    :side-effect: saves the generated video as defined in outputfn
    """
    intro_clip = VideoFileClip(introfile)
    audio_clip = AudioFileClip(audiofile)

    # resize & pad the cover image
    im = Image.open(cover_img)
    d_sz = intro_clip.size
    ratio = min(d_sz[0]/im.size[0], d_sz[1]/im.size[1])
    im_rsz = im.resize([int(s * ratio) for s in im.size])
    im_rsz_pad = ImageOps.pad(im_rsz, d_sz)
    cover_npimg = np.asarray(im_rsz_pad)

    if firstchapter:
        video_clip = ImageClip(cover_npimg)\
            .set_duration(audio_clip.duration)\
            .set_audio(audio_clip)\
            .set_fps(intro_clip.fps)
        video_clip_rsz = video_clip.resize(intro_clip.size)

        final_video = concatenate_videoclips([intro_clip, video_clip_rsz])
        final_video.write_videofile(outputfn)
    else:
        cover_img_duration = audio_clip.duration - intro_clip.duration
        img_clip = ImageClip(cover_npimg).set_duration(cover_img_duration)

        final_video = concatenate_videoclips([intro_clip, img_clip]).set_audio(audio_clip).set_fps(intro_clip.fps)
        final_video.write_videofile(outputfn)


if __name__ == "__main__":
    introfile = 'readitai_intro.mp4'
    audio_dir = 'outputs/Frankenstein/audiobook_gcwavenet'
    cover_img = 'inputs/Frankenstein/Frankenstein.jpg'

    output_dir = os.path.join(os.path.dirname(audio_dir), 'video')
    os.makedirs(output_dir, exist_ok=True)
    book_name = os.path.basename(os.path.dirname(audio_dir))
    audiofiles = sorted(glob(os.path.join(audio_dir, '*.wav')), key=os.path.basename)
    for i, audiofile in enumerate(audiofiles[4:5]):
        i = i+0
        outputfn = os.path.join(output_dir, 'Chapter {}.mp4'.format(i + 1))
        if not i:
            make_youtube_video(introfile, audiofile, cover_img, outputfn, firstchapter=True)
        else:
            make_youtube_video(introfile, audiofile, cover_img, outputfn)

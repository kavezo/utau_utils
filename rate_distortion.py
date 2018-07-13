# Mostly unsupervised phoneme segmentation; requires number of segments as input
# Based on this Qiao et. al. 2008 paper (http://www.gavo.t.u-tokyo.ac.jp/~qiao/publish/SegPhoneme_SP08.pdf)

import numpy as np  # for vector/matrix math
import librosa  # for calculating mel-frequency cepstrum coefficients
from scipy.io.wavfile import write  # for saving audio files

import os  # for iterating through directory

g1 = []
g2 = []

def initialize_g(X):
    global g1, g2
    g1 = [sum(X[:i]) for i in range(len(X)+1)]
    g2 = [sum([np.matmul(np.reshape(x, (len(x), 1)), np.reshape(x, (1,len(x)))) for x in X[:i]])
          for i in range(len(X)+1)]

    g1[0] = np.zeros(g1[1].shape)
    g2[0] = np.zeros(g2[1].shape)

def rdfunc(X, start, end):
    if len(g1)==0:
        initialize_g(X)

    length = end - start
    mean = (g1[end]-g1[start])/length
    covariance = (g2[end]-g2[start])/length - \
                 np.matmul(np.reshape(mean, (len(mean), 1)), np.reshape(mean, (1,len(mean))))
    rd = length*np.log(np.linalg.det(np.identity(covariance.shape[0])+covariance))

    return rd

def aggseg(X, k):
    segment_times = list(range(len(X)+1))
    while len(segment_times)>k:
        min_rd = float('inf')
        min_idx = None
        for idx in range(len(segment_times)-2):
            start = segment_times[idx]
            end = segment_times[idx+1]
            nextend = segment_times[idx+2]
            rd = rdfunc(X, start, nextend)-rdfunc(X, start, end)-rdfunc(X, end, nextend)
            if(rd<min_rd):
                min_rd = rd
                min_idx = idx
        segment_times = segment_times[:min_idx+1] + segment_times[min_idx+2:]
    return segment_times

# call this function per file -- e.g. segment('/usr/voicebank/kak.wav', 3, '/usr/voicebank/segments')
def segment(path, num_phonemes, out_path):
    print('processing ' + path)

    num_segments = num_phonemes + 3 # for start and end, and because I screwed up math
    y, sr = librosa.load(path)
    ms = sr / 1000

    length = 20 # If it's too inaccurate, decrease this number; if too slow, increase

    stft = librosa.stft(y, hop_length=int(round(length * ms)), win_length=int(round(length * ms)))
    mel = librosa.feature.melspectrogram(S=stft)
    logmel = librosa.power_to_db(mel)
    mfcc = librosa.feature.mfcc(S=logmel)

    initialize_g(np.transpose(mfcc))

    print('\t' + 'mfcc calculated...')

    S = aggseg(np.transpose(mfcc), num_segments)
    print('\t' + 'boundary estimation finished. saving...')
    S_ms = [int(round(boundary * length * ms)) for boundary in S]
    segments = []
    for start, end in zip(S_ms[:-1], S_ms[1:]):
        segments.append(y[start:end])

    for i in range(len(segments)):
        write(out_path + '/' + path.split('/')[-1][:-4] + str(i) + '.wav', sr, segments[i])

if __name__=='__main__':
    voicebank_path = '/usr/voicebank'

    if not os.path.isdir(voicebank_path + '/segments'):
        os.mkdir(voicebank_path + '/segments')

    wavs = [voicebank_path + '/' + file for file in os.listdir(voicebank_path) if file.endswith('.wav')]
    for wav in wavs:
        segment(wav, 10, voicebank_path + '/segments')

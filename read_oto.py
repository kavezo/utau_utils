# input: oto.ini; output: {filename: ([(phoneme, time)],[(pitch, time)],[(style, time)])}
# three formats - syllable on time only, phoneme on time only, triphone+basic labels

import re
import os
import romkan
import io
from hyperparams import Hyperparams as hp

import sys
reload(sys)
sys.setdefaultencoding('utf8')

scale = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
def pitch_to_midi(pitch):
    if not re.match(r'[A-Z]#?\d', pitch): return 0
    pitch = pitch.strip()
    return (int(pitch[-1])+1)*12 + scale.index(pitch[:-1])

def romanize(string):
    # control for 2, 3
    string = re.sub('\d', '', string)
    if not re.match(ur'[\u3040-\u30FF]+', string): return string
    elif len(string)==1:
        string = romkan.to_hepburn(string)
        if string == 'n': string = 'nn'
    else:
        fst = romkan.to_hepburn(string[0])
        snd = romkan.to_hepburn(string[1])

        # tex, dex, tox, dox, and also palatals
        if fst[:-1] in ['t','d','ch','j','sh','v','ts','dz'] and fst[-1]!='u':
            string = fst[:-1]+snd[-1]
        # du ._.
        elif fst=='du':
            string = 'd'+snd[-1]
        # si/zi case
        elif fst in ['su','zu'] and snd=='xi':
            string = fst[0]+'i'
        # foreign y and w
        elif fst=='i':
            string = 'y'+snd[-1]
        elif fst=='u':
            string = 'w'+snd[-1]
        # palatalized stops that end in e
        elif fst[-1]=='i':
            string = fst[:-1]+'y'+snd[-1]
        # archaic medial labial glide
        elif fst[-1]=='u' and len(fst)==2 and fst[0]!='f':
            string = fst[:-1]+'w'+snd[-1]
    return string

linepat = re.compile(r'(.+\.wav)=(.+),([\-.\d]+),([\-.\d]+),([\-.\d]+),([\-.\d]+),([\-.\d]+)')
seqpat = re.compile(r'[a-z]+ ([a-zR\u3040-\u30FF\u5438\u606F\u30FB\-])\'?([A-G]#?\d)')
conts = u'\u30FC-'
breaths = u'\u5438\u606F'
def process_lines(lines, pitch='', style='', mode='phoneme_on'):

    phonemes = []
    pitches = []
    styles = []

    kanapat = re.compile(u'([R\u3040-\u30FF]+)')
    lasttime = 0

    # remove labels that are the same except for the alias
    i = 0
    end_set = []
    while 1:
        end = lines[i][lines[i].find('='):]
        if end in end_set:
            del lines[i]
        else:
            end_set.append(end)
            i+=1
        if i >= len(lines):
            break

    for line in lines:
        line = line.decode('utf8')
        matches = linepat.match(line)
        if not matches:  # for breaths and stuff that don't match the pattern
            return []
        name = matches.group(1)
        seq = matches.group(2)
        timings = [int(float(t)) for t in matches.group(3, 4, 5, 6, 7)]  # offset, consonant, cutoff, preutterance, overlap

        # For a VCV:
        # --V1-----C-V2---------C_n
        #   of   ov p  co   cu

        syll = seq
        if ' ' in seq:
            syll = seq[seq.find(' ')+1:]

        if pitch == '' or style == '':
            if re.search(r'[A-G]#?\d', seq):
                pitch = re.search(r'[A-G]#?\d', seq).group()
        sylstart = timings[0]+timings[4]

        syll = syll.replace(pitch, '')
        if not syll in breaths:
            romaji = romanize(syll.strip())
            consonant = re.sub(r'[aiueo]|nn', '', romaji)
            vowel = re.search(r'([aiueo]|nn)', romaji)
            if not vowel: # non-n syllabic consonant?
                vowel = consonant
                consonant = ''
            else:
                vowel = vowel.groups()[0]
            if vowel=='nn': vowel = 'n'

        ## FIX THING WITH CONSONANT REFERENCE IF BREATH
            if not len(consonant)==0:
                phonemes.append((consonant, sylstart)) # "overlap"
                phonemes.append((vowel, timings[0]+timings[3])) # "preutterance"
            else:
                phonemes.append((vowel, sylstart))
        else:
            phonemes.append((syll, sylstart))

        pitches.append((pitch, sylstart))
        styles.append((style, sylstart))

        lasttime = timings[0]+abs(timings[2]) # "cutoff"

    phonemes.append(('E', lasttime))
    pitches.append(('E', lasttime))
    styles.append(('E', lasttime))

    return phonemes, pitches, styles

def event_to_samples(events, samprate=1/hp.frame_shift, maxsamp=None):
    if maxsamp is None:
        maxsamp = events[-1][1]

    samples = []
    padchar = hp.vocab.find('P')
    
    samprate /= hp.r
    if not len(events)==0:
        samples += [padchar]*int(round((events[0][1]*samprate/1000.0)))
    for currev, nextev in zip(events[:-1], events[1:]):
        duration_sec = (nextev[1]-currev[1])
        length = int(round(samprate/1000.0*duration_sec))
        samples += [currev[0]]*length

    if maxsamp is not None and maxsamp-len(samples)>0:
        samples += [padchar]*int(round(samprate/1000.0*maxsamp-len(samples)))

    return samples

def process_oto(vbpath, pitch = '', style = ''):
    if os.path.isdir(vbpath):
        vbpath = os.path.join(vbpath, 'oto.ini')
    with io.open(vbpath, 'rb') as oto:
        content = oto.read().decode('shift-jis').encode('utf-8')
        lines = [line.strip() for line in content.splitlines()]

    eventdict = {}
    for line in lines:
        try:
            name = linepat.match(line).group(1)
        except:
            continue
        currlines = [l for l in lines if name in l]
        eventdict[name] = process_lines(currlines, pitch, style, mode='phoneme_on')

    return eventdict

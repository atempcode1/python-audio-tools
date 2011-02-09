#!/usr/bin/python

#Audio Tools, a module and set of tools for manipulating audio data
#Copyright (C) 2007-2011  Brian Langenberger

#This program is free software; you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation; either version 2 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.

#You should have received a copy of the GNU General Public License
#along with this program; if not, write to the Free Software
#Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

import unittest
import audiotools
import ConfigParser
import tempfile
import os
import os.path
from hashlib import md5
import random
import decimal

parser = ConfigParser.SafeConfigParser()
parser.read("test.cfg")

def do_nothing(self):
    pass

#add a bunch of decorator metafunctions like LIB_CORE
#which can be wrapped around individual tests as needed
for section in parser.sections():
    for option in parser.options(section):
        if (parser.getboolean(section, option)):
            vars()["%s_%s" % (section.upper(),
                              option.upper())] = lambda function: function
        else:
            vars()["%s_%s" % (section.upper(),
                              option.upper())] = lambda function: do_nothing

class BLANK_PCM_Reader:
    def __init__(self, length,
                 sample_rate=44100, channels=2, bits_per_sample=16,
                 channel_mask=None):
        self.length = length
        self.sample_rate = sample_rate
        self.channels = channels
        if (channel_mask is None):
            self.channel_mask = audiotools.ChannelMask.from_channels(channels)
        else:
            self.channel_mask = channel_mask
        self.bits_per_sample = bits_per_sample

        self.total_frames = length * sample_rate

        self.single_pcm_frame = audiotools.pcm.from_list(
            [1] * channels, channels, bits_per_sample, True)

    def read(self, bytes):
        if (self.total_frames > 0):
            frame = audiotools.pcm.from_frames(
                [self.single_pcm_frame] *
                min(self.single_pcm_frame.frame_count(bytes) / self.channels,
                    self.total_frames))
            self.total_frames -= frame.frames
            return frame
        else:
            return audiotools.pcm.FrameList(
                "", self.channels, self.bits_per_sample, True, True)

    def close(self):
        pass

class RANDOM_PCM_Reader(BLANK_PCM_Reader):
    def read(self, bytes):
        if (self.total_frames > 0):
            frames_to_read = min(
                self.single_pcm_frame.frame_count(bytes) / self.channels,
                self.total_frames)
            frame = audiotools.pcm.FrameList(
                os.urandom(frames_to_read *
                           (self.bits_per_sample / 8) *
                           self.channels),
                self.channels,
                self.bits_per_sample,
                True,
                True)
            self.total_frames -= frame.frames
            return frame
        else:
            return audiotools.pcm.FrameList(
                "", self.channels, self.bits_per_sample, True, True)

class MD5_Reader:
    def __init__(self, pcmreader):
        self.pcmreader = pcmreader
        self.sample_rate = pcmreader.sample_rate
        self.channels = pcmreader.channels
        self.channel_mask = pcmreader.channel_mask
        self.bits_per_sample = pcmreader.bits_per_sample
        self.md5 = md5()

    def read(self, bytes):
        framelist = self.pcmreader.read(bytes)
        self.md5.update(framelist.to_bytes(False, True))
        return framelist

    def digest(self):
        return self.md5.digest()

    def hexdigest(self):
        return self.md5.hexdigest()

    def close(self):
        self.pcmreader.close()

class Variable_Reader:
    def __init__(self, pcmreader):
        self.pcmreader = audiotools.BufferedPCMReader(pcmreader)
        self.sample_rate = pcmreader.sample_rate
        self.channels = pcmreader.channels
        self.channel_mask = pcmreader.channel_mask
        self.bits_per_sample = pcmreader.bits_per_sample
        self.md5 = md5()
        self.range = range(self.channels * (self.bits_per_sample / 8),
                           4096)

    def read(self, bytes):
        return self.pcmreader.read(random.choice(self.range))

    def close(self):
        self.pcmreader.close()


class ERROR_PCM_Reader(audiotools.PCMReader):
    def __init__(self, error,
                 sample_rate=44100, channels=2, bits_per_sample=16,
                 channel_mask=None, failure_chance=.2, minimum_successes=0):
        if (channel_mask is None):
            channel_mask = audiotools.ChannelMask.from_channels(channels)
        audiotools.PCMReader.__init__(
            self,
            file=None,
            sample_rate=sample_rate,
            channels=channels,
            bits_per_sample=bits_per_sample,
            channel_mask=channel_mask)
        self.error = error

        #this is so we can generate some "live" PCM data
        #before erroring out due to our error
        self.failure_chance = failure_chance

        self.minimum_successes = minimum_successes

        self.frame = audiotools.pcm.from_list([0] * self.channels,
                                              self.channels,
                                              self.bits_per_sample,
                                              True)

    def read(self, bytes):
        if (self.minimum_successes > 0):
            self.minimum_successes -= 1
            return audiotools.pcm.from_frames(
                [self.frame for i in xrange(self.frame.frame_count(bytes))])
        else:
            if (random.random() <= self.failure_chance):
                raise self.error
            else:
                return audiotools.pcm.from_frames(
                    [self.frame for i in xrange(self.frame.frame_count(bytes))])

    def close(self):
        pass


class FrameCounter:
    def __init__(self, channels, bits_per_sample, sample_rate, value=0):
        self.channels = channels
        self.bits_per_sample = bits_per_sample
        self.sample_rate = sample_rate
        self.value = value

    def update(self, f):
        self.value += len(f)

    def __int__(self):
        return int(round(decimal.Decimal(self.value) /
                         (self.channels *
                          (self.bits_per_sample / 8) *
                          self.sample_rate)))


#probstat does this better, but I don't want to require that
#for something used only rarely
def Combinations(items, n):
    if (n == 0):
        yield []
    else:
        for i in xrange(len(items)):
            for combos in Combinations(items[i + 1:], n - 1):
                yield [items[i]] + combos


TEST_COVER1 = \
"""eJzt1H1M0mkcAPAH0bSXZT/R6BLpxNJOz4rMXs7UP86Xq+AcQ5BCdNMLgwQ6EU0qu9tdm4plLb0p
mG62Uf7yZWpZgEpnvmTmHBmQChiSaGZUpEmKcdTt1nb3z/XPbbf1ebbnj+/3eb7Py549jkeOx2DN
/rh9cQCBQIDvnA04jGBt7HEWEwAiEQQDADzAB45R8C1wQ7q6uiLdnJ2bm9sy91Ue7k6eK1cuXwV5
enlBnhCEWotBo7zX+0DQOv916/38NmzYgELjNuKwGzHYDdj3RRDOqe7L3Fd7eKzGekPe2E/muA0g
D8QsYhaJwAEXCIGEEI4ugAEIgAQuSPCRc4euHggXpDO7aQ0CIFxdXFyQ7w/6gTPh6rYM8vJ3R3nj
8CSf7c5h3n8lP3ofhf4ZHQGrkAjn6kgIRAML7e/5zz77z/nfxDSKWK20hYHeTUNHW5qFC/jmlvoR
Ra5sei8Lvipud4Dzy89/Ws105Vr2Dvr96NLgCRotL3e7LO4O+jCVgQ+ztY6LM1UUsmWzKAqFNTWY
05cy95dstGnPWEOlcYOcK7A5juKtqpg1pzbxtovTYZaSq89WCXGRgqzguWe2FYcX6rJKSrN1Wxl3
d9La4tEFoyNGB+gb1jdRs9UnpmsycHpSFry5RpyhTjE/IZKD9Xrt1z22oQucVzdPMM4MluSdnZLK
lEnDzZpHLyUaHkGAZkpyufGCmHcaVvWL1u6+W9HoJ6k/U/vplF2CWeK63JdWrtHQFNMVo4rt9yEl
k/CQHh+ZQHo2JLlsEoYG+Z2LvKZJN7HHi6Yqj5972hBSITbXVplrYeaffvgiJyl0NHNe6c8/u1pg
vxTkbZrHh5drLOrdwzIVM4urE+OEMKuwhRtRwtA+cP/JMEk+/Yvlhth57VncDEYTdTGIf71b0djf
o2AzFa11PcTUxKHEIQbELTpNKy//bajTVuJnbGNrMSbxyLYbOVJ5bdOuEIVOm6hOVFP4FEpuWPRw
dYrygkc9umdvwL7r3Y+eXVePKs5QKMZDMkm+JWoTJaZrQBKu3fk8gYxfICeQwsDlV0tbesvsvVZq
C+fe29D1RCoX/fixkdM4viQwdLYw+hZDKcR8fNTTmuCiNHYDMzBD86BYPRW+fkAzxv+lcC7Dwj2k
qM6dgRvl13Ke3oiZC8MnJJIJ+U1+c7rFNxf//UtCVL7u4N/f7QB7H/xYz/N8MMPhNTJaGu4pO2Ql
ieqjWF7y4pHiQ/YAmF0wDSumA4UvNMW9UTQDOcMchbwQJyqdME2F8bfMZG2zveESJdmG27JYmVSR
A0snBUmEhF8HyWOnBJFuN/Osp1EmXwwxaMsITc3bYqT1K0VsvV1EZSmyOLGp2fSChfEZIlYQG5nf
kkie8GzY2mdHB5VM8ji8WjtmlfxYc2Dd0Yc60dxxG136UOWjDc8b2mEbimL0MpocoDpb0rCv2awg
RvvpJoYf2QWF6avT6cIQWQ6/QSeJQiWUMoqYYqmut1Ro8b87IbcwGiYwkwGU+ic0eaXl4NXK0YW6
AxcvpsgrfbMNjb49FXCtqFRFGOiYLrA+0yFZ4/bBs1b6nvlw+gqFluJtHrnXoyg84Ss/WcOltxPD
VaiEWxUFhQVVygIGr38MO8MXlB9XTJvfjOLwN1R8JE6/p4xAmGfD9V3Jl+eqLOSwmFwobDE+Lxdt
ijh5aaxfXp9fXZZGm8CkdbcHMi1tEjUDlhzcCb9uF7IlgreGmjS1IJZEmDf5EeKlJj61s7dTLL/V
MUm5WDdmTJ/4/o5L25GmrOKIhwPX+MnxowTb/bd06xU4QDYPtDeVQcdOYU0BlBbDqYPrykhxjOxx
gyzdC154JZq/WsMZrigsXJq+8rDTiEJB+MguB9ikaXsX0aFOmdTxjlZYPcd5rW+Hqfgdwr2Zbcn2
k1cdYPBJUpoSvlUo4b9JrgnoCYyMWNm77Sv1q+fcZrE15Iqnl7rgGg5mPifFQgmCgShpY8rC3NhL
zMtP+eKwIVLxFFz0tKgW/qa83BIY3R1xzp76+6xvJlHaeIDRVrw1ulNq4SxqjtlNcIcoKQTWV40z
o/ez5iJPo7/8tO/0s8/+jxCO4T8AO2LoJg==""".decode('base64').decode('zlib')

TEST_COVER2 = \
"""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""".decode('base64').decode('zlib')

TEST_COVER3 = \
"""eJz7f+P/AwYBLzdPNwZGRkYGDyBk+H+bwZmBl5OLm4uDl5uLm4+Pl19YQVRYSEhYXUZOXEFP09BA\nT1NXx9jKy87YzM1cR9ch3NHNxy8oOMjILioxKiDBKzDIH2QIIx8fn7CgsJqoqJq/qa6pP8ng/wEG\nQQ6GFIYUZkZBBiZBRmZBxv9HGMTATkUGLBzsQHEJAUZGNBlmJiNHoIwImnogAIkKYoreYuBhZgRa\nxSzIYM9wpviCpICZQknDjcaLzEnsLrwdsiCuwwSfmS+4O6QFrBRyHF40bmRexHaED8R18FDz+cJ6\nBKYMSZeKsFoV0yOgsgnIuk7wdQg/ULP5wuaCTwvEoga4RUKc/baME5HdA9KVwu7CyXJ8XsMJJPdA\nLVrC0pRy3iEGyXAFMwewp5gcDZ8vMELzBZirMOPzBUkFNCdB/F75gmcCpt8VPCAemQBW1nCTEewk\nsEfk/98EALdspDk=\n""".decode('base64').decode('zlib')

#this is a very large, plain BMP encoded as bz2
HUGE_BMP = \
"""QlpoOTFBWSZTWSpJrRQACVR+SuEoCEAAQAEBEAIIAABAAAEgAAAIoABwU0yMTExApURDRoeppjv2
2uMceMt8M40qoj5nGLjFQkcuWdsL3rW+ugRSA6SFFV4lUR1/F3JFOFCQKkmtFA==""".decode('base64')


class AudioFileTest(unittest.TestCase):
    def setUp(self):
        self.audio_class = audiotools.AudioFile
        self.suffix = "." + self.audio_class.SUFFIX

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_init(self):
        self.assert_(False)

    @FORMAT_AUDIOFILE
    def test_is_type(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        valid = tempfile.NamedTemporaryFile(suffix=self.suffix)
        invalid = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            #generate a valid file and check its is_type routine
            self.audio_class.from_pcm(valid.name, BLANK_PCM_Reader(1))
            f = open(valid.name, 'rb')
            self.assertEqual(self.audio_class.is_type(f), True)
            f.close()

            #generate several invalid files and check its is_type routine
            for i in xrange(256):
                self.assertEqual(os.path.getsize(invalid.name), i)
                f = open(invalid.name, 'rb')
                self.assertEqual(self.audio_class.is_type(f), False)
                f.close()
                invalid.write(os.urandom(1))
                invalid.flush()

        finally:
            valid.close()
            invalid.close()

    @FORMAT_AUDIOFILE
    def test_bits_per_sample(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for bps in (8, 16, 24):
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, bits_per_sample=bps))
                self.assertEqual(track.bits_per_sample(), bps)
                track2 = audiotools.open(temp.name)
                self.assertEqual(track2.bits_per_sample(), bps)
        finally:
            temp.close()

    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_channels(self):
        self.assert_(False)

    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_channel_mask(self):
        self.assert_(False)

    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_sample_rate(self):
        self.assert_(False)

    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_lossless(self):
        self.assert_(False)

    @FORMAT_AUDIOFILE
    def test_metadata(self):
        import string
        import random

        #a nice sampling of Unicode characters
        chars = u"".join(map(unichr,
                             range(0x30, 0x39 + 1) +
                             range(0x41, 0x5A + 1) +
                             range(0x61, 0x7A + 1) +
                             range(0xC0, 0x17E + 1) +
                             range(0x18A, 0x1EB + 1) +
                             range(0x3041, 0x3096 + 1) +
                             range(0x30A1, 0x30FA + 1)))


        if (self.audio_class is audiotools.AudioFile):
            return

        dummy_metadata = audiotools.MetaData(**dict(
                [(field, char) for (field, char) in
                 zip(audiotools.MetaData.__FIELDS__,
                     string.ascii_letters)
                 if field not in audiotools.MetaData.__INTEGER_FIELDS__] +
                [(field, i + 1) for (i, field) in
                 enumerate(audiotools.MetaData.__INTEGER_FIELDS__)]))
        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            track = self.audio_class.from_pcm(temp.name,
                                              BLANK_PCM_Reader(1))
            track.set_metadata(dummy_metadata)
            track = audiotools.open(temp.name)
            metadata = track.get_metadata()
            if (metadata is None):
                return

            #not all formats necessarily support all metadata fields
            #we'll only test the fields that are supported
            live_fields = ([field for field in audiotools.MetaData.__FIELDS__
                            if ((field not in
                                 audiotools.MetaData.__INTEGER_FIELDS__) and
                                (len(getattr(metadata, field)) > 0))] +
                           [field for field in
                            audiotools.MetaData.__INTEGER_FIELDS__
                            if (getattr(metadata, field) > 0)])

            #check that setting the fields to random values works
            for field in live_fields:
                if (field not in audiotools.MetaData.__INTEGER_FIELDS__):
                    unicode_string = u"".join(
                        [random.choice(chars)
                         for i in xrange(random.choice(range(1, 21)))])
                    setattr(metadata, field, unicode_string)
                    track.set_metadata(metadata)
                    metadata = track.get_metadata()
                    self.assertEqual(getattr(metadata, field), unicode_string)
                else:
                    number = random.choice(range(1, 100))
                    setattr(metadata, field, number)
                    track.set_metadata(metadata)
                    metadata = track.get_metadata()
                    self.assertEqual(getattr(metadata, field), number)

            #check that blanking out the fields works
            for field in live_fields:
                if (field not in audiotools.MetaData.__INTEGER_FIELDS__):
                    setattr(metadata, field, u"")
                    track.set_metadata(metadata)
                    metadata = track.get_metadata()
                    self.assertEqual(getattr(metadata, field), u"")
                else:
                    setattr(metadata, field, 0)
                    track.set_metadata(metadata)
                    metadata = track.get_metadata()
                    self.assertEqual(getattr(metadata, field), 0)

            #re-set the fields with random values
            for field in live_fields:
                if (field not in audiotools.MetaData.__INTEGER_FIELDS__):
                    unicode_string = u"".join(
                        [random.choice(chars)
                         for i in xrange(random.choice(range(1, 21)))])
                    setattr(metadata, field, unicode_string)
                    track.set_metadata(metadata)
                    metadata = track.get_metadata()
                    self.assertEqual(getattr(metadata, field), unicode_string)
                else:
                    number = random.choice(range(1, 100))
                    setattr(metadata, field, number)
                    track.set_metadata(metadata)
                    metadata = track.get_metadata()
                    self.assertEqual(getattr(metadata, field), number)

            #check that deleting the fields works
            for field in live_fields:
                delattr(metadata, field)
                track.set_metadata(metadata)
                metadata = track.get_metadata()
                if (field not in audiotools.MetaData.__INTEGER_FIELDS__):
                    self.assertEqual(getattr(metadata, field), u"")
                else:
                    self.assertEqual(getattr(metadata, field), 0)

            #check that delete_metadata works
            nonblank_metadata = audiotools.MetaData(**dict(
                    [(field, c) for (field, c) in zip(
                            live_fields,
                            string.ascii_letters)
                     if field not in
                     audiotools.MetaData.__INTEGER_FIELDS__] +
                    [(field, i + 1) for (i, field) in enumerate(
                            live_fields)
                     if field in
                     audiotools.MetaData.__INTEGER_FIELDS__]))
            track.set_metadata(nonblank_metadata)
            self.assertEqual(track.get_metadata(), nonblank_metadata)
            track.delete_metadata()
            metadata = track.get_metadata()
            if (metadata is not None):
                for field in live_fields:
                    if (field not in audiotools.MetaData.__INTEGER_FIELDS__):
                        self.assertEqual(getattr(metadata, field), u"")
                    else:
                        self.assertEqual(getattr(metadata, field), 0)

            track.set_metadata(nonblank_metadata)
            self.assertEqual(track.get_metadata(), nonblank_metadata)

            old_mode = os.stat(track.filename).st_mode
            os.chmod(track.filename, 0400)
            try:
                #check IOError on set_metadata()
                self.assertRaises(IOError,
                                  track.set_metadata,
                                  audiotools.MetaData(track_name=u"Foo"))

                #check IOError on delete_metadata()
                self.assertRaises(IOError,
                                  track.delete_metadata)
            finally:
                os.chmod(track.filename, old_mode)

            os.chmod(track.filename, 0)
            try:
                #check IOError on get_metadata()
                self.assertRaises(IOError,
                                  track.get_metadata)
            finally:
                os.chmod(track.filename, old_mode)

            #check merge
            def field_val(field, value, int_value):
                if (field in audiotools.MetaData.__INTEGER_FIELDS__):
                    return int_value
                else:
                    return value

            for i in xrange(10):
                shuffled_fields = live_fields[:]
                random.shuffle(shuffled_fields)

                for (range_a, range_b) in [
                    ((0, len(shuffled_fields) / 3), #no overlap
                     (-(len(shuffled_fields) / 3),
                       len(shuffled_fields) + 1)),

                    ((0, len(shuffled_fields) / 2), #partial overlap
                     (len(shuffled_fields) / 4,
                      len(shuffled_fields) / 4 + len(shuffled_fields) / 2)),

                    ((0, len(shuffled_fields) / 3), #complete overlap
                     (0, len(shuffled_fields) / 3))]:
                    fields_a = shuffled_fields[range_a[0]:range_a[1]]
                    fields_b = shuffled_fields[range_b[0]:range_b[1]]

                    metadata_a = audiotools.MetaData(**dict([
                                (field, field_val(field, u"a", 1)) for field
                                in fields_a]))
                    metadata_b = audiotools.MetaData(**dict([
                                (field, field_val(field, u"b", 2)) for field
                                in fields_b]))

                    track.delete_metadata()
                    track.set_metadata(metadata_a)
                    metadata_c = track.get_metadata()
                    self.assertEqual(metadata_c, metadata_a)
                    metadata_c.merge(metadata_b)
                    track.set_metadata(metadata_c)
                    metadata_c = track.get_metadata()

                    for field in live_fields:
                        if (field in fields_a):
                            if (field in
                                audiotools.MetaData.__INTEGER_FIELDS__):
                                self.assertEqual(getattr(metadata_c, field),
                                                 1)
                            else:
                                self.assertEqual(getattr(metadata_c, field),
                                                 u"a")
                        elif (field in fields_b):
                            if (field in
                                audiotools.MetaData.__INTEGER_FIELDS__):
                                self.assertEqual(getattr(metadata_c, field),
                                                 2)
                            else:
                                self.assertEqual(getattr(metadata_c, field),
                                                 u"b")
                        else:
                            if (field in
                                audiotools.MetaData.__INTEGER_FIELDS__):
                                self.assertEqual(getattr(metadata_c, field),
                                                 0)
                            else:
                                self.assertEqual(getattr(metadata_c, field),
                                                 u"")

            #check images
            metadata = audiotools.MetaData(**dict(
                    [(field, getattr(dummy_metadata, field))
                     for field in live_fields]))
            image_1 = audiotools.Image.new(TEST_COVER1, u"", 0)
            metadata.add_image(image_1)
            track.set_metadata(metadata)
            metadata = track.get_metadata()
            if (len(metadata.images()) > 0):
                #only check if images are actually supported

                self.assertEqual(metadata.images()[0], image_1)
                self.assertEqual(metadata.front_covers()[0], image_1)

                metadata.delete_image(metadata.images()[0])
                track.set_metadata(metadata)
                metadata = track.get_metadata()
                self.assertEqual(len(metadata.images()), 0)

                image_2 = audiotools.Image.new(TEST_COVER2, u"", 0)
                metadata.add_image(image_2)
                track.set_metadata(metadata)
                metadata = track.get_metadata()
                self.assertEqual(metadata.images()[0], image_2)
                self.assertEqual(metadata.front_covers()[0], image_2)


        finally:
            temp.close()

    @FORMAT_AUDIOFILE
    def test_length(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for seconds in [1, 2, 3, 4, 5, 10, 20, 60, 120]:
                track = self.audio_class.from_pcm(temp.name,
                                                  BLANK_PCM_Reader(seconds))
                self.assertEqual(track.total_frames(), seconds * 44100)
                self.assertEqual(track.cd_frames(), seconds * 75)
                self.assertEqual(track.seconds_length(), seconds)
        finally:
            temp.close()

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_pcm(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_convert(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_track_number(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_album_number(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_track_name(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_replay_gain(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_cuesheet(self):
        self.assert_(False)

    #FIXME
    @FORMAT_AUDIOFILE_PLACEHOLDER
    def test_verify(self):
        self.assert_(False)


class LosslessFileTest(AudioFileTest):
    @FORMAT_LOSSLESS
    def test_lossless(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(1))
            self.assertEqual(track.lossless(), True)
            track = audiotools.open(temp.name)
            self.assertEqual(track.lossless(), True)
        finally:
            temp.close()

    @FORMAT_LOSSLESS
    def test_channels(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for channels in [1, 2, 3, 4, 5, 6]:
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=channels, channel_mask=0))
            self.assertEqual(track.channels(), channels)
            track = audiotools.open(temp.name)
            self.assertEqual(track.channels(), channels)
        finally:
            temp.close()

    @FORMAT_LOSSLESS
    def test_channel_mask(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for mask in [["front_center"],
                         ["front_left",
                          "front_right"],
                         ["front_left",
                          "front_right",
                          "front_center"],
                         ["front_left",
                          "front_right",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "low_frequency",
                          "back_left",
                          "back_right"]]:
                cm = audiotools.ChannelMask.from_fields(**dict(
                        [(f,True) for f in mask]))
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=len(cm), channel_mask=int(cm)))
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)
                track = audiotools.open(temp.name)
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)
        finally:
            temp.close()

    @FORMAT_LOSSLESS
    def test_sample_rate(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for rate in [8000, 16000, 22050, 44100, 48000,
                         96000, 192000]:
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, sample_rate=rate))
                self.assertEqual(track.sample_rate(), rate)
                track = audiotools.open(temp.name)
                self.assertEqual(track.sample_rate(), rate)
        finally:
            temp.close()

    @FORMAT_LOSSLESS
    def test_pcm(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        temp2 = tempfile.NamedTemporaryFile()
        temp_dir = tempfile.mkdtemp()
        try:
            for compression in (None,) + self.audio_class.COMPRESSION_MODES:
                #test silence
                reader = MD5_Reader(BLANK_PCM_Reader(1))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)
                checksum = md5()
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   checksum.update)
                self.assertEqual(reader.hexdigest(), checksum.hexdigest())

                #test random noise
                reader = MD5_Reader(RANDOM_PCM_Reader(1))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)
                checksum = md5()
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   checksum.update)
                self.assertEqual(reader.hexdigest(), checksum.hexdigest())

                #test randomly-sized chunks of silence
                reader = MD5_Reader(Variable_Reader(BLANK_PCM_Reader(10)))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)
                checksum = md5()
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   checksum.update)
                self.assertEqual(reader.hexdigest(), checksum.hexdigest())

                #test randomly-sized chunks of random noise
                reader = MD5_Reader(Variable_Reader(RANDOM_PCM_Reader(10)))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)
                checksum = md5()
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   checksum.update)
                self.assertEqual(reader.hexdigest(), checksum.hexdigest())

                #test PCMReaders that trigger a DecodingError
                self.assertRaises(ValueError,
                                  ERROR_PCM_Reader(ValueError("error"),
                                                   failure_chance=1.0).read,
                                  1)
                self.assertRaises(IOError,
                                  ERROR_PCM_Reader(IOError("error"),
                                                   failure_chance=1.0).read,
                                  1)
                self.assertRaises(audiotools.EncodingError,
                                  self.audio_class.from_pcm,
                                  os.path.join(temp_dir,
                                               "invalid" + self.suffix),
                                  ERROR_PCM_Reader(IOError("I/O Error")))

                self.assertEqual(os.path.isfile(
                        os.path.join(temp_dir,
                                     "invalid" + self.suffix)),
                                 False)

                self.assertRaises(audiotools.EncodingError,
                                  self.audio_class.from_pcm,
                                  os.path.join(temp_dir,
                                               "invalid" + self.suffix),
                                  ERROR_PCM_Reader(IOError("I/O Error")))

                self.assertEqual(os.path.isfile(
                        os.path.join(temp_dir,
                                     "invalid" + self.suffix)),
                                 False)

                #test unwritable output file
                self.assertRaises(audiotools.EncodingError,
                                  self.audio_class.from_pcm,
                                  "/dev/null/foo.%s" % (self.suffix),
                                  BLANK_PCM_Reader(1))

                #test without suffix
                reader = MD5_Reader(BLANK_PCM_Reader(1))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp2.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp2.name, reader,
                                                      compression)
                checksum = md5()
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   checksum.update)
                self.assertEqual(reader.hexdigest(), checksum.hexdigest())
        finally:
            temp.close()
            temp2.close()
            for f in os.listdir(temp_dir):
                os.unlink(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)



class LossyFileTest(AudioFileTest):
    @FORMAT_LOSSY
    def test_bits_per_sample(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for bps in (8, 16, 24):
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, bits_per_sample=bps))
                self.assertEqual(track.bits_per_sample(), 16)
                track2 = audiotools.open(temp.name)
                self.assertEqual(track2.bits_per_sample(), 16)
        finally:
            temp.close()

    @FORMAT_LOSSY
    def test_lossless(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(1))
            self.assertEqual(track.lossless(), False)
            track = audiotools.open(temp.name)
            self.assertEqual(track.lossless(), False)
        finally:
            temp.close()

    @FORMAT_LOSSY
    def test_channels(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for channels in [1, 2, 3, 4, 5, 6]:
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=channels, channel_mask=0))
            self.assertEqual(track.channels(), 2)
            track = audiotools.open(temp.name)
            self.assertEqual(track.channels(), 2)
        finally:
            temp.close()

    @FORMAT_LOSSY
    def test_channel_mask(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            cm = audiotools.ChannelMask.from_fields(
                front_left=True,
                front_right=True)
            track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                    1, channels=len(cm), channel_mask=int(cm)))
            self.assertEqual(track.channels(), len(cm))
            self.assertEqual(track.channel_mask(), cm)
            track = audiotools.open(temp.name)
            self.assertEqual(track.channels(), len(cm))
            self.assertEqual(track.channel_mask(), cm)
        finally:
            temp.close()

    @FORMAT_LOSSY
    def test_sample_rate(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                    1, sample_rate=44100))
            self.assertEqual(track.sample_rate(), 44100)
            track = audiotools.open(temp.name)
            self.assertEqual(track.sample_rate(), 44100)
        finally:
            temp.close()

    @FORMAT_LOSSY
    def test_pcm(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        temp2 = tempfile.NamedTemporaryFile()
        temp_dir = tempfile.mkdtemp()
        try:
            for compression in (None,) + self.audio_class.COMPRESSION_MODES:
                #test silence
                reader = BLANK_PCM_Reader(5)
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)
                counter = FrameCounter(2, 16, 44100)
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   counter.update)
                self.assertEqual(int(counter), 5,
                                 "mismatch encoding %s at quality %s" % \
                                     (self.audio_class.NAME,
                                      compression))

                #test random noise
                reader = RANDOM_PCM_Reader(5)
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)
                counter = FrameCounter(2, 16, 44100)
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   counter.update)
                self.assertEqual(int(counter), 5,
                                 "mismatch encoding %s at quality %s" % \
                                     (self.audio_class.NAME,
                                      compression))

                #test randomly-sized chunks of silence
                reader = Variable_Reader(BLANK_PCM_Reader(5))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)

                counter = FrameCounter(2, 16, 44100)
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   counter.update)
                self.assertEqual(int(counter), 5,
                                 "mismatch encoding %s at quality %s" % \
                                     (self.audio_class.NAME,
                                      compression))

                #test randomly-sized chunks of random noise
                reader = Variable_Reader(RANDOM_PCM_Reader(5))
                if (compression is None):
                    track = self.audio_class.from_pcm(temp.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp.name, reader,
                                                      compression)

                counter = FrameCounter(2, 16, 44100)
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   counter.update)
                self.assertEqual(int(counter), 5,
                                 "mismatch encoding %s at quality %s" % \
                                     (self.audio_class.NAME,
                                      compression))

                #test PCMReaders that trigger a DecodingError
                self.assertRaises(ValueError,
                                  ERROR_PCM_Reader(ValueError("error"),
                                                   failure_chance=1.0).read,
                                  1)
                self.assertRaises(IOError,
                                  ERROR_PCM_Reader(IOError("error"),
                                                   failure_chance=1.0).read,
                                  1)
                self.assertRaises(audiotools.EncodingError,
                                  self.audio_class.from_pcm,
                                  os.path.join(temp_dir,
                                               "invalid" + self.suffix),
                                  ERROR_PCM_Reader(IOError("I/O Error")))

                self.assertEqual(os.path.isfile(
                        os.path.join(temp_dir,
                                     "invalid" + self.suffix)),
                                 False)

                self.assertRaises(audiotools.EncodingError,
                                  self.audio_class.from_pcm,
                                  os.path.join(temp_dir,
                                               "invalid" + self.suffix),
                                  ERROR_PCM_Reader(IOError("I/O Error")))

                self.assertEqual(os.path.isfile(
                        os.path.join(temp_dir,
                                     "invalid" + self.suffix)),
                                 False)

                #test unwritable output file
                self.assertRaises(audiotools.EncodingError,
                                  self.audio_class.from_pcm,
                                  "/dev/null/foo.%s" % (self.suffix),
                                  BLANK_PCM_Reader(1))

                #test without suffix
                reader = BLANK_PCM_Reader(5)
                if (compression is None):
                    track = self.audio_class.from_pcm(temp2.name, reader)
                else:
                    track = self.audio_class.from_pcm(temp2.name, reader,
                                                      compression)
                    
                counter = FrameCounter(2, 16, 44100)
                audiotools.transfer_framelist_data(track.to_pcm(),
                                                   counter.update)
                self.assertEqual(int(counter), 5,
                                 "mismatch encoding %s at quality %s" % \
                                     (self.audio_class.NAME,
                                      compression))
        finally:
            temp.close()
            temp2.close()
            for f in os.listdir(temp_dir):
                os.unlink(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)


class AACFileTest(LossyFileTest):
    def setUp(self):
        self.audio_class = audiotools.AACAudio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_AAC
    def test_length(self):
        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for seconds in [1, 2, 3, 4, 5, 10, 20, 60, 120]:
                track = self.audio_class.from_pcm(temp.name,
                                                  BLANK_PCM_Reader(seconds))
                self.assertEqual(int(round(track.seconds_length())), seconds)
        finally:
            temp.close()


class AiffFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.AiffAudio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_AIFF
    def test_channel_mask(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        #AIFF's support channels are a little odd

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for mask in [["front_center"],
                         ["front_left",
                          "front_right"],
                         ["front_left",
                          "front_right",
                          "front_center"],
                         ["front_left",
                          "front_right",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "back_center",
                          "side_left",
                          "side_right"]]:
                cm = audiotools.ChannelMask.from_fields(**dict(
                        [(f,True) for f in mask]))
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=len(cm), channel_mask=int(cm)))
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)
                track = audiotools.open(temp.name)
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)
        finally:
            temp.close()

class ALACFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.ALACAudio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_ALAC
    def test_bits_per_sample(self):
        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for bps in (16, 24):
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, bits_per_sample=bps))
                self.assertEqual(track.bits_per_sample(), bps)
                track2 = audiotools.open(temp.name)
                self.assertEqual(track2.bits_per_sample(), bps)
        finally:
            temp.close()

    @FORMAT_ALAC
    def test_channel_mask(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for mask in [["front_center"],
                         ["front_left",
                          "front_right"]]:
                cm = audiotools.ChannelMask.from_fields(**dict(
                        [(f,True) for f in mask]))
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=len(cm), channel_mask=int(cm)))
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)
                track = audiotools.open(temp.name)
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)

            for mask in [["front_left",
                          "front_right",
                          "front_center"],
                         ["front_left",
                          "front_right",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "low_frequency",
                          "back_left",
                          "back_right"]]:
                cm = audiotools.ChannelMask.from_fields(**dict(
                        [(f,True) for f in mask]))
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=len(cm), channel_mask=int(cm)))
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), 0)
                track = audiotools.open(temp.name)
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), 0)
        finally:
            temp.close()


class AUFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.AuAudio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_AU
    def test_channel_mask(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for mask in [["front_center"],
                         ["front_left",
                          "front_right"]]:
                cm = audiotools.ChannelMask.from_fields(**dict(
                        [(f,True) for f in mask]))
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=len(cm), channel_mask=int(cm)))
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)
                track = audiotools.open(temp.name)
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), cm)

            for mask in [["front_left",
                          "front_right",
                          "front_center"],
                         ["front_left",
                          "front_right",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "back_left",
                          "back_right"],
                         ["front_left",
                          "front_right",
                          "front_center",
                          "low_frequency",
                          "back_left",
                          "back_right"]]:
                cm = audiotools.ChannelMask.from_fields(**dict(
                        [(f,True) for f in mask]))
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=len(cm), channel_mask=int(cm)))
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), 0)
                track = audiotools.open(temp.name)
                self.assertEqual(track.channels(), len(cm))
                self.assertEqual(track.channel_mask(), 0)
        finally:
            temp.close()


class FlacFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.FlacAudio
        self.suffix = "." + self.audio_class.SUFFIX


class M4AFileTest(LossyFileTest):
    def setUp(self):
        self.audio_class = audiotools.M4AAudio
        self.suffix = "." + self.audio_class.SUFFIX


class MP2FileTest(LossyFileTest):
    def setUp(self):
        self.audio_class = audiotools.MP2Audio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_MP2
    def test_length(self):
        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for seconds in [1, 2, 3, 4, 5, 10, 20, 60, 120]:
                track = self.audio_class.from_pcm(temp.name,
                                                  BLANK_PCM_Reader(seconds))
                self.assertEqual(int(round(track.seconds_length())), seconds)
        finally:
            temp.close()


class MP3FileTest(LossyFileTest):
    def setUp(self):
        self.audio_class = audiotools.MP3Audio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_MP3
    def test_length(self):
        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for seconds in [1, 2, 3, 4, 5, 10, 20, 60, 120]:
                track = self.audio_class.from_pcm(temp.name,
                                                  BLANK_PCM_Reader(seconds))
                self.assertEqual(int(round(track.seconds_length())), seconds)
        finally:
            temp.close()


class OggFlacFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.OggFlacAudio
        self.suffix = "." + self.audio_class.SUFFIX


class ShortenFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.ShortenAudio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_SHORTEN
    def test_bits_per_sample(self):
        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for bps in (8, 16):
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, bits_per_sample=bps))
                self.assertEqual(track.bits_per_sample(), bps)
                track2 = audiotools.open(temp.name)
                self.assertEqual(track2.bits_per_sample(), bps)
        finally:
            temp.close()


class SpeexFileTest(LossyFileTest):
    def setUp(self):
        self.audio_class = audiotools.SpeexAudio
        self.suffix = "." + self.audio_class.SUFFIX


class VorbisFileTest(LossyFileTest):
    def setUp(self):
        self.audio_class = audiotools.VorbisAudio
        self.suffix = "." + self.audio_class.SUFFIX

    @FORMAT_VORBIS
    def test_channels(self):
        if (self.audio_class is audiotools.AudioFile):
            return

        temp = tempfile.NamedTemporaryFile(suffix=self.suffix)
        try:
            for channels in [1, 2, 3, 4, 5, 6]:
                track = self.audio_class.from_pcm(temp.name, BLANK_PCM_Reader(
                        1, channels=channels, channel_mask=0))
            self.assertEqual(track.channels(), channels)
            track = audiotools.open(temp.name)
            self.assertEqual(track.channels(), channels)
        finally:
            temp.close()


class WaveFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.WaveAudio
        self.suffix = "." + self.audio_class.SUFFIX


class WavPackFileTest(LosslessFileTest):
    def setUp(self):
        self.audio_class = audiotools.WavPackAudio
        self.suffix = "." + self.audio_class.SUFFIX


if (__name__ == '__main__'):
    unittest.main()

# PiTiVi , Non-linear video editor
#
#       pitivi/encode.py
#
# Copyright (c) 2009, Edward Hervey <bilboed@bilboed.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

"""
Encoding-related utilities and classes
"""

import gst
from pitivi.factories.base import OperationFactory
from pitivi.factories.operation import TransformFactory

class EncoderFactory(TransformFactory):
    """
    Creates one-to-one encoding bins based on provided L{StreamEncodeSettings}.

    @cvar settings: The encoding settings.
    @type settings: L{StreamEncodeSettings}
    """
    def __init__(self, settings, *args, **kwargs):
        self.settings = settings
        TransformFactory.__init__(self, *args, **kwargs)

    def _makeBin(self, *args):
        s = self.settings
        b = gst.Bin()

        # encoder
        enc = gst.element_factory_make(s.encoder)
        for k, v in s.encodersettings.iteritems():
            enc.set_property(k, v)
        b.add(enc)

        # optional input stream
        if s.input_stream:
            infilt = gst.element_factory_make("capsfilter")
            infilt.props.caps = s.input_stream.caps
            b.add(infilt)
            infilt.link(enc)
            gsink = gst.GhostPad("sink", infilt.get_pad("sink"))
        else:
            gsink = gst.GhostPad("sink", enc.get_pad("sink"))
        gsink.set_active(True)
        b.add_pad(gsink)

        # optional output stream
        if s.output_stream:
            outfilt = gst.element_factory_make("capsfilter")
            outfilt.props.caps = s.output_stream.caps
            b.add(outfilt)
            enc.link(outfilt)
            gsrc = gst.GhostPad("src", outfilt.get_pad("src"))
        else:
            gsrc = gst.GhostPad("src", enc.get_pad("src"))
        gsrc.set_active(True)
        b.add_pad(gsrc)

        return b

class RenderFactory(OperationFactory):
    """
    Handles factories that consume streams and output one (and only one
    output stream according to the given encoding settings.

    @cvar settings: The rendering settings
    @type settings: L{RenderSettings}
    """

    def __init__(self, settings, *args, **kwargs):
        self.settings = settings
        OperationFactory.__init__(self, *args, **kwargs)

    def _makeBin(self, *args):
        s = self.settings

        b = gst.Bin()

        mux = gst.element_factory_make(s.muxer)
        for k, v in s.muxersettings.iteritems():
            mux.set_property(k, v)

        gsrc = gst.GhostPad("src", mux.get_pad("src"))
        gsrc.set_active(True)
        b.add_pad(gsrc)

        i = 0
        # add all the encoders
        for setting in s.settings:
            b2 = EncoderFactory(setting).makeBin()
            b.add(b2)

            src2 = b2.get_pad("src")

            # request a compatible pad from the muxer
            n2 = get_compatible_sink_pad(s.muxer, src2.get_caps())
            if n2 == None:
                raise Exception("can't find a compatible pad")
            # FIXME : We're assuming it's a request pad
            p2 = mux.get_request_pad(n2)
            b2.link(p2)

            # expose encoder sink pad
            gsink = gst.GhotPad("sink_%d" % i,
                                b2.get_pad("sink"))
            gsink.set_active(True)
            b.add_pad(gsink)
            i += 1

        return b

    def _requestNewInputStream(self, bin, input_stream):
        raise NotImplementedError

def get_compatible_sink_pad(factoryname, caps):
    """
    Returns the pad name of a (request) pad from factoryname which is
    compatible with the given caps.
    """
    factory = gst.registry_get_default().lookup_feature(factoryname)
    if factory == None:
        gst.warning("%s is not a valid factoryname" % factoryname)
        return None

    res = []
    sinkpads = [x for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SINK]
    for p in sinkpads:
        c = p.get_caps()
        gst.log("sinkcaps %s" % c.to_string())
        inter = caps.intersect(c)
        gst.log("intersection %s" % inter.to_string())
        if inter:
            res.append(p.get_name())
    if len(res) > 0:
        return res[0]
    return None

def get_compatible_sink_caps(factoryname, caps):
    """
    Returns the compatible caps between 'caps' and the sink pad caps of 'factoryname'
    """
    gst.log("factoryname : %s , caps : %s" % (factoryname, caps.to_string()))
    factory = gst.registry_get_default().lookup_feature(factoryname)
    if factory == None:
        gst.warning("%s is not a valid factoryname" % factoryname)
        return None

    res = []
    sinkcaps = [x.get_caps() for x in factory.get_static_pad_templates() if x.direction == gst.PAD_SINK]
    for c in sinkcaps:
        gst.log("sinkcaps %s" % c.to_string())
        inter = caps.intersect(c)
        gst.log("intersection %s" % inter.to_string())
        if inter:
            res.append(inter)

    if len(res) > 0:
        return res[0]
    return None

def list_compat(a1, b1):
    for x1 in a1:
        if not x1 in b1:
            return False
    return True

def my_can_sink_caps(muxer, ocaps):
    """ returns True if the given caps intersect with some of the muxer's
    sink pad templates' caps.
    """
    sinkcaps = [x.get_caps() for x in muxer.get_static_pad_templates() if x.direction == gst.PAD_SINK]
    for x in sinkcaps:
        if not x.intersect(ocaps).is_empty():
            return True
    return False

def available_muxers():
    """ return all available muxers """
    flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
    res = []
    for fact in flist:
        if list_compat(["Codec", "Muxer"], fact.get_klass().split('/')):
            res.append(fact)
    gst.log(str(res))
    return res

def available_video_encoders():
    """ returns all available video encoders """
    flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
    res = []
    for fact in flist:
        if list_compat(["Codec", "Encoder", "Video"], fact.get_klass().split('/')):
            res.append(fact)
        elif list_compat(["Codec", "Encoder", "Image"], fact.get_klass().split('/')):
            res.append(fact)
    gst.log(str(res))
    return res

def available_audio_encoders():
    """ returns all available audio encoders """
    flist = gst.registry_get_default().get_feature_list(gst.ElementFactory)
    res = []
    for fact in flist:
        if list_compat(["Codec", "Encoder", "Audio"], fact.get_klass().split('/')):
            res.append(fact)
    gst.log(str(res))
    return res

def encoders_muxer_compatible(encoders, muxer):
    """ returns the list of encoders compatible with the given muxer """
    res = []
    for encoder in encoders:
        for caps in [x.get_caps() for x in encoder.get_static_pad_templates() if x.direction == gst.PAD_SRC]:
            if my_can_sink_caps(muxer, caps):
                res.append(encoder)
                break
    return res

def muxer_can_sink_raw_audio(muxer):
    """ Returns True if given muxer can accept raw audio """
    return my_can_sink_caps(muxer, gst.Caps("audio/x-raw-float;audio/x-raw-int"))

def muxer_can_sink_raw_video(muxer):
    """ Returns True if given muxer can accept raw video """
    return my_can_sink_caps(muxer, gst.Caps("video/x-raw-yuv;video/x-raw-rgb"))

def available_combinations(muxers, vencoders, aencoders):
    res = []
    for mux in muxers:
        noaudio = (encoders_muxer_compatible(aencoders, mux) == []) and not muxer_can_sink_raw_audio(mux)
        novideo = (encoders_muxer_compatible(vencoders, mux) == []) and not muxer_can_sink_raw_video(mux)
        if (noaudio == False) and (novideo == False):
            res.append(mux)
    return res
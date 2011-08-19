# PiTiVi , Non-linear video editor
#
#       pitivi/timeline/timeline.py
#
# Copyright (c) 2009, Alessandro Decina <alessandro.decina@collabora.co.uk>
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
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

from gi.repository import GObject as gobject
import gst
from pitivi.factories.base import SourceFactory, ObjectFactoryError


class FixSeekStart(gst.BaseTransform):
    __gstdetails__ = (
        "Description",
        "Klass",
        "Description",
        "Author")

    sink_template = gst.PadTemplate("sink",
            gst.PAD_SINK, gst.PAD_ALWAYS,
            gst.Caps('ANY'))
    src_template = gst.PadTemplate("src",
            gst.PAD_SRC, gst.PAD_ALWAYS,
            gst.Caps('ANY'))

    __gsttemplates__ = (sink_template, src_template)

    def __init__(self, track):
        gst.BaseTransform.__init__(self)
        self.track = track
        self.caps = None

    def do_transform_caps(self, direction, caps):
        if self.caps is None:
            return caps

        return caps.intersect(self.caps)

    def do_src_event(self, event):
        if event.type == gst.EVENT_SEEK:
            rate, format, flags, cur_type, cur, stop_type, stop = \
                    event.parse_seek()
            if cur_type == gst.SEEK_TYPE_SET and cur >= self.track.duration:
                cur = self.track.duration - 1 * gst.NSECOND
                new_event = gst.event_new_seek(rate, format, flags, cur_type, cur,
                        stop_type, stop)
                event = new_event

        return gst.BaseTransform.do_src_event(self, event)

gobject.type_register(FixSeekStart)


class TimelineSourceFactory(SourceFactory):
    def __init__(self, timeline):
        SourceFactory.__init__(self, "timeline://", "timeline")
        self.bin = gst.Bin()
        self.max_bins = 1
        self.timeline = timeline
        self.pad_num = 0
        self.ghosts = {}
        self.seek_checkers = {}

        self.duration = timeline.duration

        for track in self.timeline.tracks:
            self._addTrack(track)

        self._connectTimeline()

    def clean(self):
        for track in self.timeline.tracks:
            self._removeTrack(track)

        self._disconnectTimeline()

    def _makeBin(self, output_stream=None):
        if output_stream is not None:
            raise ObjectFactoryError('not implemented yet')

        return self.bin

    def _releaseBin(self, bin):
        pass

    def _connectTimeline(self):
        self.timeline.connect('track-added', self._timelineTrackAddedCb)
        self.timeline.connect('track-removed', self._timelineTrackRemovedCb)
        self.timeline.connect('duration-changed',
                self._timelineDurationChangedCb)

    def _disconnectTimeline(self):
        self.timeline.disconnect_by_function(self._timelineTrackAddedCb)
        self.timeline.disconnect_by_function(self._timelineTrackRemovedCb)
        self.timeline.disconnect_by_function(self._timelineDurationChangedCb)

    def _addTrack(self, track):
        composition = track.composition
        composition.connect('pad-added',
                self._trackCompositionPadAddedCb, track)
        composition.connect('pad-removed',
                self._trackCompositionPadRemovedCb, track)

        self.bin.add(composition)

        self.addOutputStream(track.stream)

    def _removeTrack(self, track):
        composition = track.composition
        composition.disconnect_by_func(self._trackCompositionPadAddedCb)
        composition.disconnect_by_func(self._trackCompositionPadRemovedCb)

        self.bin.remove(composition)

        self.removeOutputStream(track.stream)

    def _newGhostPad(self, pad, track):
        pad_id = str(pad)
        if gst.get_pygst_version() < (0, 10, 14, 1):
            # in <= 0.10.14 there was a bug in basetransform (commit
            # 83f31c7194b96ec857d6695746dd8b3fcba1846a in gst-python)
            seek = gst.element_factory_make('identity')
            seek.props.silent = True
        else:
            seek = FixSeekStart(track)
        self.bin.add(seek)
        seek.sync_state_with_parent()
        pad.link_full(seek.get_pad('sink'), gst.PAD_LINK_CHECK_NOTHING)
        ghost = gst.GhostPad('src%d' % self.pad_num + str(id(pad)), seek.get_pad('src'))

        # FixSeekStart has template caps ANY. Setting seek.caps here we make it
        # so that ghost.get_caps() returns pad.get_caps()
        caps = pad.props.caps
        if caps is None:
            caps = pad.get_caps()
        seek.caps = caps
        ghost.set_active(True)
        self.ghosts[pad_id] = ghost
        self.seek_checkers[pad_id] = seek
        self.pad_num += 1

        return ghost

    def _removeGhostPad(self, pad):
        pad_id = str(pad)
        if pad_id not in self.ghosts:
            return

        ghost = self.ghosts.pop(pad_id)
        seek = self.seek_checkers.pop(pad_id)
        self.bin.remove_pad(ghost)
        ghost.set_active(False)
        self.bin.remove(seek)
        seek.set_state(gst.STATE_NULL)

    def _timelineTrackAddedCb(self, timeline, track):
        self._addTrack(track)

    def _timelineTrackRemovedCb(self, timeline, track):
        self._removeTrack(track)

    def _trackCompositionPadAddedCb(self, composition, pad, track):
        ghost = self._newGhostPad(pad, track)
        self.bin.add_pad(ghost)

    def _trackCompositionPadRemovedCb(self, composition, pad, track):
        self._removeGhostPad(pad)

    def _timelineDurationChangedCb(self, timeline, duration):
        self.duration = duration

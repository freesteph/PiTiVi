#!/usr/bin/env python
#
#       test/test_factories_operation.py
#
# Copyright (C) 2010 Thibault Saunier <tsaunier@gnome.org>
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
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.


import gst

from common import TestCase

from pitivi.factories.operation import EffectFactory
from pitivi.stream import VideoStream


class TestEffectFactory(TestCase):
    def setUp(self):
        TestCase.setUp(self)
        self.stream = VideoStream(gst.Caps("video/x-raw-rgb"))
        self.factory = EffectFactory('identity', 'identity')
        self.factory.addOutputStream(self.stream)
        self.factory.addInputStream(self.stream)

    def testMakeBin(self):
        bin = self.factory.makeBin()
        bin2 = self.factory.makeBin()
        csp = bin.elements().next()
        self.failUnless(isinstance(bin, gst.Bin))
        self.failUnless(csp)
        self.factory.releaseBin(bin)
        self.factory.releaseBin(bin2)

    def tearDown(self):
        del self.factory
        TestCase.tearDown(self)

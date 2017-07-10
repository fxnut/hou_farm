"""
Hou Farm. A Deadline submission tool for Houdini
Copyright (C) 2017 Andy Nicholas
https://github.com/fxnut/hou_farm

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see http://www.gnu.org/licenses.
"""

import re


def zero_pad_string(number, padding):
    return str(number).zfill(padding)


class IntegerSequence(object):
    def __init__(self):
        self._number_set = set()
        self._integer_ranges = None

        # This allows us to keep speed up without checking to see if we are in "range" mode
        self.add_integer = self._add_integer_to_set
        self._cached_length = None

    @staticmethod
    def from_string(string_val):
        # Expects a string like "-50, -45--35, -12, -4-3, 8-15, 17, 20-40".
        # Whitespace is optional. Overlaps and duplicates are allowed.
        inst = IntegerSequence()
        inst.add_from_string(string_val)
        return inst

    @staticmethod
    def iter_ranges_in_string(string_val):
        if isinstance(string_val, basestring) is False:
            raise TypeError("Must be passed a string")

        if string_val == "":
            return
        regex = re.compile("^\s*(-?[0-9]+)(?:\s*-\s*(-?[0-9]+))?(?:\s*:\s*(-?[0-9]+))?\s*$")
        for range_str in string_val.split(","):
            match_obj = regex.match(range_str)
            if match_obj is None:
                raise ValueError("Invalid range string: " + range_str)
            match_groups = match_obj.groups()
            val_a = match_groups[0]
            val_b = match_groups[1]
            val_c = match_groups[2]

            if val_b is None:
                val_b = val_a = int(val_a)
                yield (val_a, val_b)
            else:
                if val_c is None:
                    val_a = int(val_a)
                    val_b = int(val_b)
                    yield (val_a, val_b)
                else:
                    for num in xrange(int(val_a), int(val_b)+1, int(val_c)):
                        yield (num, num)

    def __len__(self):
        if self._number_set is not None:
            return len(self._number_set)

        if self._cached_length is not None:
            return self._cached_length

        self._cached_length = 0
        for rng in self._integer_ranges:
            self._cached_length += 1 + rng[1] - rng[0]

        return self._cached_length

    def add_from_string(self, string_val):
        # Expects a string like "-50, -45--35, -12, -4-3, 8-15, 17, 20-40, 50-100:5".
        # Whitespace is optional. Overlaps and duplicates are allowed.
        # Will not change sequence if any part of string parsing fails.
        range_list = [range_val for range_val in IntegerSequence.iter_ranges_in_string(string_val)]

        self.pack_integers()
        for range_val in range_list:
            self._add_range(*range_val)

    def iter_ranges(self):
        self.pack_integers()
        for range_val in self._integer_ranges:
            yield range_val

    def iter_integers(self):
        self.pack_integers()
        for range_val in self._integer_ranges:
            for i in xrange(range_val[0], range_val[1]+1):
                yield i

    def get_range(self):
        if len(self._integer_ranges) == 0:
            return None
        return self._integer_ranges[0][0], self._integer_ranges[-1][1]

    def _add_integer_to_set(self, integer):
        if isinstance(integer, int) is False:
            raise TypeError("Must be passed an integer" + integer.__class__.__name__)
        self._number_set.add(integer)

    def _add_integer_to_ranges(self, integer):
        if isinstance(integer, int) is False:
            raise TypeError("Must be passed an integer" + integer.__class__.__name__)

        self._cached_length = None
        for i, rng in enumerate(self._integer_ranges):
            if integer < rng[0]:
                if integer == rng[0]-1:
                    # Extend front
                    self._integer_ranges[i] = (integer, rng[1])
                else:
                    # Insert
                    self._integer_ranges.insert(i, (integer, integer))
                return
            elif integer <= rng[1]:
                return
            elif integer == rng[1]+1:
                if i+1 < len(self._integer_ranges):
                    next_rng = self._integer_ranges[i+1]
                    if integer+1 == next_rng[0]:
                        # Merge
                        self._integer_ranges[i] = (rng[0], next_rng[1])
                        del self._integer_ranges[i+1]
                        return
                    else:
                        # Extend end
                        self._integer_ranges[i] = (rng[0], integer)
                        return                        
                else:
                    # Extend end
                    self._integer_ranges[i] = (rng[0], integer)
                    return
        # Append
        self._integer_ranges.append((integer, integer))

    def _add_range(self, val_a, val_b):
        self._cached_length = None
        if val_a == val_b:
            self.add_integer(val_a)
            return

        if val_a > val_b:
            tmp = val_b
            val_b = val_a
            val_a = tmp

        range_a = None
        for i, rng in enumerate(self._integer_ranges):
            if val_a <= rng[1]+1:
                range_a = i
                break

        if range_a is None:
            self._integer_ranges.append((val_a, val_b))
            return

        range_b = None
        range_count = len(self._integer_ranges)
        for i in xrange(range_a, range_count):
            rng = self._integer_ranges[i]

            if val_b <= rng[1]+1:
                if val_b < rng[0]-1:
                    range_b = i-1
                else:
                    if i == range_count-1:
                        range_b = range_count-1
                        break
                    rng_next = self._integer_ranges[i+1]
                    if val_b >= rng_next[0]-1:
                        range_b = i+1
                    else:
                        range_b = i
                break

        if range_b is None:
            range_b = len(self._integer_ranges)-1

        if range_a > range_b:
            self._integer_ranges.insert(range_a, (val_a, val_b))
            return

        val_a = min(self._integer_ranges[range_a][0], val_a)
        val_b = max(self._integer_ranges[range_b][1], val_b)
        self._integer_ranges[range_a] = (val_a, val_b)

        for i in xrange(range_a+1, range_b+1):
            del self._integer_ranges[range_a+1]  # List shifts left as we delete

    def add_range(self, range_pair):
        self.pack_integers()
        self._add_range(*range_pair)

    def add_integers(self, integer_list):
        for integer in integer_list:
            self.add_integer(integer)

    def pack_integers(self):
        # Go from a list of numbers to a range representation
        if self._integer_ranges is not None:
            return

        self._cached_length = None

        if len(self._number_set) == 0:
            self._number_set = None
            self._integer_ranges = []
            self.add_integer = self._add_integer_to_ranges
            return

        # Remove duplicates
        number_list = list(self._number_set)
        number_list.sort()

        self._integer_ranges = []
        cur_start = number_list[0]
        cur_end = cur_start

        for integer in number_list[1:]:
            if integer == cur_end+1:
                cur_end = integer
            else:
                self._integer_ranges.append((cur_start, cur_end))
                cur_start = integer
                cur_end = integer

        if len(self._integer_ranges) == 0 or self._integer_ranges[-1][1] != cur_end:
            self._integer_ranges.append((cur_start, cur_end))

        self._number_set = None
        self.add_integer = self._add_integer_to_ranges

    def get_integer_string(self, max_str_len=0, padding=0):
        if self._integer_ranges is None:
            self.pack_integers()

        integer_str = ""
        for rng in self._integer_ranges:
            if rng[0] == rng[1]:
                integer_str += "{0},".format(zero_pad_string(rng[0], padding))
            else:
                integer_str += "{0}-{1},".format(zero_pad_string(rng[0], padding),
                                                 zero_pad_string(rng[1], padding))
        
        integer_str = integer_str[:-1]

        integer_strlen = len(integer_str)

        if 0 < max_str_len < integer_strlen and len(self._integer_ranges) > 1:
            last_comma_pos = integer_str.rfind(",")
            assert last_comma_pos != -1

            search_end = max_str_len - (integer_strlen - last_comma_pos) - 1
            if search_end > 0:
                limit_comma_pos = integer_str.rfind(",", 0, search_end)
                if limit_comma_pos != -1:
                    start_str = integer_str[:limit_comma_pos]
                    end_str = integer_str[last_comma_pos+1:]
                    integer_str = start_str + "..." + end_str
                else:
                    integer_str = "{0}...{1}".format(zero_pad_string(self._integer_ranges[0][0], padding),
                                                     zero_pad_string(self._integer_ranges[-1][1], padding))
            else:
                integer_str = "{0}...{1}".format(zero_pad_string(self._integer_ranges[0][0], padding),
                                                 zero_pad_string(self._integer_ranges[-1][1], padding))

        return integer_str

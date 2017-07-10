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

try:
    import hou
except:
    pass


class Message(object):

    Info = 0
    Warning = 1
    Error = 2

    def __init__(self, message, message_type):
        self.message = message
        self.message_type = message_type

    def get_message(self):
        message_header_dict = {Message.Info: "Info",
                               Message.Warning: "Warn",
                               Message.Error: "Error"}

        return "({0}) {1}".format(message_header_dict[self.message_type], self.message)

    def is_error(self):
        return self.message_type == ErrorMessage.Error

    def is_warning(self):
        return self.message_type == ErrorMessage.Warning


class InfoMessage(Message):
    def __init__(self, message):
        Message.__init__(self, message, Message.Info)


class WarningMessage(Message):
    def __init__(self, message):
        Message.__init__(self, message, Message.Warning)


class ErrorMessage(Message):
    def __init__(self, message):
        Message.__init__(self, message, Message.Error)


class ErrorList(object): 

    def __init__(self, parent_error_list):
        self.parent_error_list = parent_error_list
        if self.parent_error_list is not None:
            self.list = self.parent_error_list.list
        else:
            self.list = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            return False
        if self.parent_error_list is None:
            self.display()
        return True

    def display(self, message=None, options=("OK",)):
        result = 0
        if self.error_count()>0:
            if message is None:
                message = "Some errors were found. Please review below:"
            result = hou.ui.displayMessage(message, options, hou.severityType.Error,
                                           details=self.get_message(), details_expanded=True)
        elif self.warning_count()>0:
            if message is None:
                message = "Some warnings were found. Please review below:"
            result = hou.ui.displayMessage(message, options, hou.severityType.Warning,
                                           details=self.get_message(), details_expanded=True)
        elif len(self.list)>0:
            if message is None:
                message = "For your information:"
            result = hou.ui.displayMessage(message, options, hou.severityType.Message,
                                           details=self.get_message(), details_expanded=True)
        del self.list[:]
        return result

    def add(self, item):
        self.list.append(item)

    def add_to_front(self, item):
        self.list.insert(0, item)

    def get_message(self):
        msg = ""
        for item in self.list:
            msg += "  * "+item.get_message() + "\n"
        return msg

    def error_count(self):
        count = 0
        for item in self.list:
            if item.is_error():
                count += 1
        return count

    def warning_count(self):
        count = 0
        for item in self.list:
            if item.is_warning():
                count += 1
        return count


class RopMessage(Message):

    def __init__(self, rop, message, message_type):
        Message.__init__(self, message, message_type)
        self.rop = rop


class RopInfoMessage(RopMessage):
    def __init__(self, rop, message):
        RopMessage.__init__(self, rop, message, Message.Info)


class RopWarningMessage(RopMessage):
    def __init__(self, rop, message):
        RopMessage.__init__(self, rop, message, Message.Warning)


class RopErrorMessage(RopMessage):
    def __init__(self, rop, message):
        RopMessage.__init__(self, rop, message, Message.Error)



class RopErrorList(ErrorList):

    def get_message(self):
        msg = ""
        last_rop = None
        for item in self.list:
            if item.rop is not last_rop:
                msg += "\n------------------------------------------------\n"
                if item.rop is not None:
                    msg += item.rop.path() + ":\n\n"
            msg += "  * "+item.get_message() + "\n"
            last_rop = item.rop
        return msg

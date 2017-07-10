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

import hou

global kwargs

try:
    import hou_farm.tools as hou_farm_tools
    reload(hou_farm_tools)

    if hou_farm_tools.validate_environment("deadline"):
        hou_farm_tools.patch_selected_rops(kwargs,"deadline")

except Exception as err:
    import traceback
    hou.ui.displayMessage("Error in \"hou_farm.tools\" module", severity=hou.severityType.Error,
                          title="Python Error", details=traceback.format_exc())


import hou

global kwargs

try:
    import hou_farm.tools as hou_farm_tools
    reload(hou_farm_tools)

    if hou_farm_tools.validate_environment("deadline"):
        hou_farm_tools.unpatch_selected_rops(kwargs, "deadline")

except Exception as err:
    import traceback
    hou.ui.displayMessage("Error in \"hou_farm.tools\" module", severity=hou.severityType.Error,
                          title="Python Error", details=traceback.format_exc())


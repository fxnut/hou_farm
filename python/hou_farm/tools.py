import os
import re
import json

try:
    import hou
except:
    pass

from hou_farm.errors import ErrorList, InfoMessage, WarningMessage, ErrorMessage


# --------------------------------------------------------------------------
# Entry Points
# --------------------------------------------------------------------------


def create_rop(script_args, farm_name, node_type, error_list_obj=None):
    """
    Creates the required ROP type, and adds parameters for farm submission. See patch_rop() for more info.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        node_type (str): Name of the ROP type to create. E.g. "ifd"
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        hou.RopNode: The new node, or None if failed.
    """
    with ErrorList(error_list_obj) as error_list_obj:

        rop_node = create_rop_in_active_pane(node_type, error_list_obj)
        if rop_node is None:
            error_list_obj.add(ErrorMessage("Could not create '{0}' ROP".format(node_type)))
            return None

        return patch_rop(script_args, farm_name, rop_node, error_list_obj)


def patch_rop(script_args, farm_name, rop_node, error_list_obj=None):
    """
    Patches a ROP with spare parameters to allow for farm submission. Puts existing parameters underneath a
    top level folder, and patches it with the required farm parameter folder which contains parameters for submission.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        rop_node (hou.Node): A ROP node (in any context) to patch
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        Bool: True on success, otherwise False
    """
    with ErrorList(error_list_obj) as error_list_obj:

        if not is_rop_patchable(farm_name, rop_node):
            error_list_obj.add(WarningMessage("ROP nodes of type '{0}' not supported ".format(rop_node.type().name())))
            return False

        prepare_rop_for_new_parms(rop_node)
        create_rop_parameters(script_args, farm_name, rop_node, error_list_obj)
        return True


def unpatch_rop(script_args, farm_name, rop_node, error_list_obj=None):
    """
    Undos the patching operation on a ROP. Removes the custom farm folder and parameters and moves the original
    parameters back up to the top level.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        rop_node (hou.Node): A ROP node (in any context) to unpatch
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        Bool: True if successfully removed, False if not
    """
    with ErrorList(error_list_obj) as error_list_obj:

        if remove_top_level_folders(rop_node, "hf_orig_parms", [farm_name.title()]) is False:
            error_list_obj.add(WarningMessage("Failed to un-patch: {0}".format(rop_node.path())))
            return False
        return True


def patch_selected_rops(script_args, farm_name, error_list_obj=None):
    """
    Adds parameters to selected ROPs to allow for farm submission. See patch_rop() for more info.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        Bool: True if all successfully patched, False if not
    """

    with ErrorList(error_list_obj) as error_list_obj:

        rop_list = get_selected_rops_for_patching()
        new_errors = False
        for rop_node in rop_list:
            if patch_rop(script_args, farm_name, rop_node, error_list_obj):
                new_errors = True

        return new_errors 


def unpatch_selected_rops(script_args, farm_name, error_list_obj=None):
    """
    Undos the patching operation on selected ROPs. See unpatch_rop() for more info.

    Args:
        script_args (dict): The Houdini "kwargs" dictionary
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        None
    """
    with ErrorList(error_list_obj) as error_list_obj:

        rop_list = get_selected_rops_for_unpatching()
        new_errors = False
        for rop_node in rop_list:
            if unpatch_rop(script_args, farm_name, rop_node, error_list_obj):
                new_errors = True
            
        return new_errors


# --------------------------------------------------------------------------
# ROP Utilities
# --------------------------------------------------------------------------

def get_rop_context_name(rop_node):
    return rop_node.parent().childTypeCategory().name().lower()


def get_simplified_rop_type_name(rop_node):
    """
    Returns a simplified rop type name, dealing with nodes that have namespace specifiers. 
    Invalid characters are replaced by an underscore
    Args:
        rop_node (hou.RopNode): The node to return the type name for.

    Returns:
        string: Name of the rop type. E.g. a node type of "BakeTexture::3.0" gives  "BakeTexture__3_0"
    """
    rop_type_str = rop_node.type().name()
    rop_type_str = rop_type_str.replace(":", "_")
    rop_type_str = rop_type_str.replace(".", "_")
    return rop_type_str


def create_rop_in_active_pane(node_type, error_list_obj=None):
    """
    Creates the specified ROP type in the current network pane and moves it to a convenient location

    Args:
        node_type (str): Name of the node type to create. E.g. "ifd"
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        hou.RopNode: The new node, or None if failed.
    """
    with ErrorList(error_list_obj) as error_list_obj:

        network_pane = get_network_pane()
        cwd = network_pane.pwd()

        if cwd.childTypeCategory() != hou.ropNodeTypeCategory():
            error_list_obj.add(ErrorMessage("Cannot create ROP node in:\n"+cwd.path()))
            return None

        rop_node = cwd.createNode(node_type, exact_type_name=True)
        rop_node.setSelected(True, True)
        rop_node.moveToGoodPosition()
        return rop_node


def get_node_folder_type_name(rop_node):
    """
    Used to get a readable name for a ROP node. Used for the top level folder name. Currently only used on IFD
    Rops to call their top level folders "Mantra" instead of "Ifd"
    
    Args:
        rop_node (hou.Node): A ROP node (in any context) to provide the name for

    Returns:
        String: The readable name
    """
    folder_name = rop_node.type().name().title()

    regex = re.compile(r"((?P<company>[a-zA-Z.]*)::)?(?P<name>[a-zA-z_]+)(::(?P<version>[a-zA-Z0-9._]*))?")
    matches = regex.match(folder_name)
    if matches is not None:
        folder_name = matches.group("name")

    # Special cases for nodes where their type name is not a good folder label
    folder_name_dict = {"Ifd": "Mantra", 
                        "Baketexture": "Bake Texture"}
    if folder_name in folder_name_dict:
        folder_name = folder_name_dict[folder_name]

    return folder_name


def prepare_rop_for_new_parms(rop_node):
    """
    Prepares a ROP for having the extra farm parameters added to it.
    Puts all existing parameters under a new top level folder, and creates a new folder for the new parameters.

    Args:
        rop_node (hou.Node): A ROP node (in any context) to modify

    Returns:
        None
    """
    folder_name = get_node_folder_type_name(rop_node)
    make_top_level_folder(rop_node, "hf_orig_parms", folder_name)


def get_selected_rops_for_patching():
    """
    Gets a list of ROPs from the current selection that are able to be patched.

    Returns:
        List: A list of ROPs to patch
    """
    # TODO: Need to do more checks on what is selected. Maybe allow the ROP SOP Output Driver?
    rop_list = []
    sel_nodes = list(hou.selectedNodes())
    for rop_node in sel_nodes:
        network_type = rop_node.parent().childTypeCategory().name()
        if network_type == "Driver" or rop_node.type().name().startswith("rop_"):
            parm_tg = rop_node.parmTemplateGroup()
            entry = parm_tg.parmTemplates()[0]
            if entry.name() != "hf_orig_parms":
                rop_list.append(rop_node)
    return rop_list


def get_selected_rops_for_unpatching():
    """
    Gets a list of ROPs from the current selection that are able to be unpatched.

    Returns:
        List: A list of ROPs to unpatch
    """
    rop_list = []
    sel_nodes = list(hou.selectedNodes())
    for rop_node in sel_nodes:
        network_type = rop_node.parent().childTypeCategory().name()
        if network_type == "Driver" or rop_node.type().name().startswith("rop_"):
            parm_tg = rop_node.parmTemplateGroup()
            entry = parm_tg.parmTemplates()[0]
            if entry.name() == "hf_orig_parms":
                rop_list.append(rop_node)
    return rop_list


def make_top_level_folder(node, name, label):
    """
    Creates a top level folder on a node and places all existing parameters and folders underneath it.

    Args:
        node (hou.RopNode): The ROP to modify
        name (str): The parameter name of the folder
        label (str): The label of the folder

    Returns:
        None
    """
    parm_tg = node.parmTemplateGroup()
    top_folder = hou.FolderParmTemplate(name, label, parm_tg.entries())
    parm_tg.clear()
    parm_tg.addParmTemplate(top_folder)
    node.setParmTemplateGroup(parm_tg)


def remove_top_level_folders(node, parm_name, folder_list):
    """
    Removes the top level folder previously created by make_top_level_folder()

    Args:
        node (hou.RopNode): The ROP to modify
        parm_name (str): The parameter name of the folder (previously given to make_top_level_folder())
        folder_list (list): A list of strings with the names of folders to remove

    Returns:
        Bool: True of the operation was successful, otherwise False
    """
    parm_tg = node.parmTemplateGroup()
    parms = parm_tg.parmTemplates()
    if len(parms) != len(folder_list)+1:
        return False

    orig_parent_folder_name = get_node_folder_type_name(node)
    folder_list = list(folder_list)
    folder_list.append(orig_parent_folder_name)
    orig_folder = None
    for parm in parms:
        if parm.label() not in folder_list:
            continue
        if parm.name() != parm_name:
            continue
        if parm.label() == orig_parent_folder_name:
            orig_folder = parm

    if orig_folder is None:
        return False

    parm_tg.clear()
    for parm in orig_folder.parmTemplates():
        parm_tg.addParmTemplate(parm)

    node.setParmTemplateGroup(parm_tg)
    return True


def is_rop_patchable(farm_name, rop_node):
    parm_list = get_node_parameter_list(farm_name, rop_node)
    if parm_list is None:
        return False
    return True


def create_rop_parameters(script_args, farm_name, rop_node, error_list_obj=None):
    """
    Creates parameters on a specific ROP and farm

    Args:
        script_args (dict): The Houdini "kwargs" dictionary
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        rop_node (hou.Node): A ROP node (in any context)
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        Bool: True if successful, False if the parameter configuration can't be found
    """
    with ErrorList(error_list_obj) as error_list_obj:

        param_list = get_config_parameter_list(farm_name, rop_node)
        if param_list is None:
            err_msg = "Could not load '{0}' ROP {1} parameters from config".format(rop_node.type().name(), farm_name)
            error_list_obj.add(ErrorMessage(err_msg))
            return False

        parm_list = create_parameters_from_list(param_list, farm_name)
        farm_folder = hou.FolderParmTemplate("hf_{0}_folder".format(farm_name), farm_name.title(), parm_list)

        rop_parm_template_group = rop_node.parmTemplateGroup()
        rop_parm_template_group.append(farm_folder)
        rop_node.setParmTemplateGroup(rop_parm_template_group)

        return True


def create_parameters_from_list(param_list, farm_name):
    """
    Creates the ParmTemplate objects from a parameter definition list

    Args:
        param_list (list): List of parameter definition dictionaries
        farm_name (str): Lowercase name of the farm integration. Must match the name of the farm module. E.g. "deadline"

    Returns:
        List: A list of ParmTemplate objects representing the parameters
    """
    factfunc_dict = {"str": hou.StringParmTemplate, "int": hou.IntParmTemplate, "float": hou.FloatParmTemplate,
                     "bool": hou.ToggleParmTemplate, "button": hou.ButtonParmTemplate, "folder": hou.FolderParmTemplate}

    foldertype_dict = {"Collapsible": hou.folderType.Collapsible, "Simple": hou.folderType.Simple,
                       "Tabs": hou.folderType.Tabs, "RadioButtons": hou.folderType.RadioButtons,
                       "MultiparmBlock": hou.folderType.MultiparmBlock,
                       "ScrollingMultiparmBlock": hou.folderType.ScrollingMultiparmBlock,
                       "TabbedMultiparmBlock": hou.folderType.TabbedMultiparmBlock,
                       "ImportBlock": hou.folderType.ImportBlock}

    parm_templates = []

    for parm_dict in param_list:
        parm_type = parm_dict["type"]
        hou_parm_dict = parm_dict.copy()
        del hou_parm_dict["type"]

        if "item_generator_script" in hou_parm_dict:
            code = """
try:
    import hou_farm.{0}
except ImportError:
    return (kwargs["parm"].eval(), kwargs["parm"].eval())
else:
    return hou_farm.{0}.{1}(kwargs)
"""

            hou_parm_dict["item_generator_script"] = code.format(farm_name,hou_parm_dict["item_generator_script"])
            hou_parm_dict["item_generator_script_language"] = hou.scriptLanguage.Python

        if "script_callback" in hou_parm_dict:
            code  = """
try:
    import hou_farm.{0}
except ImportError:
    hou.ui.displayMessage("Cannot import houfarm.{0} module",("OK",), hou.severityType.Error)
else:
    hou_farm.{0}.{1}(kwargs)
"""

            hou_parm_dict["script_callback"] = code.format(farm_name, hou_parm_dict["script_callback"])
            hou_parm_dict["script_callback_language"] = hou.scriptLanguage.Python

        if parm_type == "folder":
            parm_child_list = hou_parm_dict["children"]
            del hou_parm_dict["children"]

            if "folder_type" in hou_parm_dict:
                hou_parm_dict["folder_type"] = foldertype_dict[hou_parm_dict["folder_type"]]
            else:
                hou_parm_dict["folder_type"] = hou.folderType.Tabs

            # Recurse to add child parameters
            hou_parm_dict["parm_templates"] = create_parameters_from_list(parm_child_list, farm_name)

        item = factfunc_dict[parm_type](**hou_parm_dict)
        parm_templates.append(item)

    return parm_templates


# --------------------------------------------------------------------------
# ROP Render Utilities
# --------------------------------------------------------------------------


def get_mantra_commandline_options(rop_node):
    """
    Extracts Mantra commandline options from an IFD node

    Args:
        rop_node (hou.RopNode): The IFD (Mantra) node to examine

    Returns:
        String: A string containing the command line options for mantra for the ROP provided
    """
    cmd_line = rop_node.parm("soho_pipecmd").eval()
    if cmd_line.startswith("mantra"):
        return cmd_line[6:].strip()
    return ""


def expand_string_for_rop(rop_node, string_value):
    """
    Expands a string that contains tokens such as $OS which depend on being evaluated with respect to a specific node
    Args:
        rop_node (hou.Node): A Houdini node to evaluate this string with respect to
        string_value (str): The string to expand

    Returns:
        String: The expanded string
    """
    cur_pwd_node = hou.pwd()
    hou.cd(rop_node.path())
    result = hou.expandString(string_value)
    hou.cd(cur_pwd_node.path())
    return result


def get_expanded_render_path(rop_node, parm_name, frame_char):
    """
    Returns an expanded string of a file path and replaces the frame number with a suitable number of
    frame_char characters to indicate padding.

    Example:
        ::

            "$JOB/render/${HIPNAME}/${OS}/${HIPNAME}_${OS}.${F4}.exr"
            -> "//jobs/my_job/render/test/BEAUTY/test_BEAUTY.####.exr"

    Args:
        rop_node (hou.RopNode): The ROP node instance that owns the parameter containing the filename
        parm_name (string): Name of the parameter that holds the filename
        frame_char (string): The character to use to act as a stand-in for the padded frame number, e.g. "#".

    Returns:
         String: The expanded filename
    """

    unexpanded_filename = rop_node.parm(parm_name).unexpandedString()
    regex = re.compile("(?P<prefix>.*)(?P<expression>\$\{?F(?P<padding>[0-9]*)\}?)(?P<suffix>.*)")
    match_obj = regex.search(unexpanded_filename)
    if match_obj is None:
        result = rop_node.parm(parm_name).evalAsString()
        return result

    padding = 1
    padding_str = match_obj.group("padding")
    if padding_str != "":
        padding = int(padding_str)

    result = expand_string_for_rop(rop_node, match_obj.group("prefix")) + \
        (padding*frame_char) + \
        expand_string_for_rop(rop_node, match_obj.group("suffix"))

    return result


def get_rop_process_list(start_rop, eval_full_tree=False):
    """
    Given an initial ROP, this returns a list of ROPs that this one is dependent on. The order returned also specifies
    the proper evaluation order.
    If eval_full_tree is set to True, then all connected ROP nodes in the tree will have their dependency evaluated.

    Args:
        start_rop (hou.RopNode): A ROP node located anywhere on the tree to find the ROP roots
        eval_full_tree (bool): If True, it will return all ROPs connected in the same tree,
            if False, only direct ancestors of start_rop.

    Returns:
        List: A list of hou.RopNode instances in the correct order for evaluation.
    """

    if eval_full_tree is False:
        return [rop_node for rop_node, framerange in start_rop.inputDependencies()]

    root_rop_list = get_all_rop_roots_connected(start_rop)

    rop_list = []
    # Use a dictionary as a fast look up to see if rop has already been added
    found_rops = {}

    for root_rop in root_rop_list:
        dependencies = [rop_node for rop_node, framerange in root_rop.inputDependencies()]
        for rop_node in dependencies:
            if rop_node.path() not in found_rops:
                rop_list.append(rop_node)
                found_rops[rop_node.path()] = True
    return rop_list


def get_all_rop_roots_connected(start_rop):
    """
    Returns a list of rop_nodes that are connected to start_rop but have no outputs.
    These are the rops which are the "end of chain" ROPs. The last ones that should get processed.

    Args:
        start_rop (hou.RopNode): A ROP node located anywhere on the tree to find the ROP roots

    Returns:
        List of hou.RopNode: All the ROPs that have no outputs.
    """

    nodes_to_check = [start_rop]
    rop_root_list = []
    new_nodes_to_check = []

    # Use dictionaries as a fast look up to see if rop has already been added
    checked_nodes = {}
    found_roots = {}

    # Use a counter to make sure we never go into an infinite loop
    count = 0

    while len(nodes_to_check) > 0 and count < 1000:
        for rop_node in nodes_to_check:
            inputs = rop_node.inputs()
            outputs = rop_node.outputs()
            path = rop_node.path()
            if len(outputs) == 0:
                if path not in found_roots:
                    found_roots[path] = True
                    rop_root_list.append(rop_node)
            else:
                for rop_output in outputs:
                    if rop_output.path() not in checked_nodes:
                        new_nodes_to_check.append(rop_output)

            for rop_input in inputs:
                if rop_input.path() not in checked_nodes:
                    new_nodes_to_check.append(rop_input)

            checked_nodes[path] = True
        nodes_to_check = new_nodes_to_check
        count += 1
    return rop_root_list


# --------------------------------------------------------------------------
# Houdini Utilities
# --------------------------------------------------------------------------


def get_network_pane(containing_path=None, child_category=None):
    """
    Returns the current network pane. Allows you to give it a hint to specify a path or a
    child node type e.g. hou.ropNodeTypeCategory(). If multiple are available, then the first one is returned.

    Args:
        containing_path (str): Optional parameter. Only returns a network pane if it points to this path
        child_category (str): Optional parameter. Only returns a network pane if is able to contain this node type

    Returns:
        hou.NetworkEditor: The first NetworkEditor panel that satisfies the input conditions
    """

    network_panes = [pane for pane in hou.ui.paneTabs() if pane.type() == hou.paneTabType.NetworkEditor and pane.isCurrentTab()]

    if len(network_panes)==0:
        return None

    if len(network_panes)==1:
        return network_panes[0]

    for pane in network_panes:
        if child_category is None or pane.pwd().childTypeCategory() == child_category:
            if containing_path is None or pane.pwd().path() == containing_path:
                return pane
    return network_panes[0]


def get_hou_major_version():
    """
    A wrapper for returning Houdini's major version

    Returns:
        String: Returns a string containing Houdini's major version number. E.g. '15'
    """
    return str(hou.applicationVersion()[0])


# --------------------------------------------------------------------------
# Environment Helpers
# --------------------------------------------------------------------------

def validate_environment(farm_name, error_list_obj=None):
    """
    Checks with the farm integration to make sure that the environment is correct.
    Displays any error messages to the user
    Args:
        farm_name (str): Lowercase name of the farm integration. Must match the name of the farm module. E.g. "deadline"
        error_list_obj (RopErrorList): An instance of RopErrorList class to store any errors or warnings

    Returns:
        List: An empty list on success, otherwise a list of strings containing error messages
    """
    with ErrorList(error_list_obj) as error_list_obj:

        exec("import hou_farm.{0}".format(farm_name))
        return hou_farm.__getattribute__(farm_name).validate_environment(error_list_obj)


def get_environ_filename(path_env, name_env, path_default_list, name_default_list,
                         parent_dir_must_exist=True, file_must_exist=True):
    """
    Returns a filename from the current environment based on two supplied environment variable names; one for the path,
    one for the filename. In case the environment variables are not present or valid, you can specify a list of default
    paths and default filenames to check. The first valid filename will be returned. You can request that the path
    must exist, or that the full filename must exist.

    Args:
        path_env (str): Name of the environment variable containing the path
        name_env (str): Name of the environment variable containing the filename
        path_default_list (list): List of strings for default path
        name_default_list (list): List of strings for default filename
        parent_dir_must_exist (bool): If True, then the function will only return a filename if the path exists
        file_must_exist (bool): If True, then the function will only return a filename if the file exists too

    Returns:
        String: Returns a string containing the filename if the conditions are met, otherwise None
    """
    path_list = []
    name_list = []

    if path_env in os.environ:
        path_list.append(os.environ[path_env])

    if name_env in os.environ:
        name_list.append(os.environ[name_env])

    path_list.extend(path_default_list)
    name_list.extend(name_default_list)

    for path in path_list:
        for name in name_list:
            # Use hou.expandString() on each part of the path individually. Otherwise it will remove \\ at start
            path = os.path.normpath("\\".join([hou.expandString(item) for item in path.split("\\")]))
            name = hou.expandString(name)
            filename = os.path.join(path, name)

            if file_must_exist and not (os.path.exists(filename) and os.path.isfile(filename)):
                continue

            if parent_dir_must_exist and not (os.path.exists(path) and os.path.isdir(path)):
                continue

            return filename
    return None


# --------------------------------------------------------------------------
# Configuration File Tools
# --------------------------------------------------------------------------


def json_load_byteified(file_handle):
    """
    Loads unicode strings to regular python strings, as Houdini can't handle unicode
    Taken from:
    http://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-ones-from-json-in-python

    Args:
        file_handle (file handle instance): An instance of an open file handle

    Returns:
        JSON data: The converted JSON data loaded from the file handle
    """
    #
    return _byteify(json.load(file_handle, object_hook=_byteify), ignore_dicts=True)


def _byteify(data, ignore_dicts=False):
    """
    A hook for loading JSON as ASCII. Converts unicode strings to regular python strings.
    This is necessary as Houdini can't handle unicode strings.
    Taken from:
    http://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-ones-from-json-in-python

    Args:
        data (various types): Input data to byteify
        ignore_dicts (bool): Whether to ignore byteifying dictionaries

    Returns:
        Various types: The converted data
    """

    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
            for key, value in data.iteritems()
        }
    # if it's anything else, return it in its original form
    return data


def load_global_config():
    """
    Loads the global JSON configuration file for configuring the parameter layout.

    Returns:
        JSON data: Returns the loaded configuration file as python objects (lists and dictionaries).
    """
    config_filename = get_environ_filename("HOUFARM_GLOBAL_CONFIG_PATH", "HOUFARM_GLOBAL_CONFIG_NAME",
                                           [], ["hou_farm_global_config.json"])
    if config_filename is None:
        raise IOError("Cannot locate global config file")

    handle = open(config_filename, "r")
    json_dict = json_load_byteified(handle)
    handle.close()
    return json_dict


def expand_json_include_blocks(nodes_dict, parm_list, include_dict):
    """
    Expands 'include' and 'instance' sections in the configuration file parameter definitions.
    For brevity and ease of reuse, blocks of parameters can be reused by using the 'include' type
    in the config file.

    Example:
        The 'section' refers to keys contained in the "include_blocks" part of the configuration file ::

            {"type": "include", "section": "HOUDINI"},

    Example:
        It is also possible to use 'instance' to reuse the entire parameter definition belonging to a node ::

            "alembic": [{"type": "instance", "node": "geometry"}],

    Args:
        nodes_dict (dict): The dictionary of nodes
        parm_list (list): The current list of parameters to expand
        include_dict (dict): The 'include_blocks" dictionary

    Returns:
        List: The expanded parameter list
    """
    expanded_parm_list = []
    for i, parm in enumerate(parm_list):
        parm_type = parm["type"]
        if parm_type == "include":
            expanded_parm_list.extend(include_dict[parm["section"]])
        elif parm_type == "instance":
            parm_list = nodes_dict[parm["context"]][parm["node"]]
            expanded_parm_list.extend(expand_json_include_blocks(nodes_dict, parm_list, include_dict))
        else:
            if parm_type == "folder":
                parm["children"] = expand_json_include_blocks(nodes_dict, parm["children"], include_dict)

            expanded_parm_list.append(parm)

    return expanded_parm_list


def set_dict_path(json_dict, path, value=None):
    """
    Creates a key (with optional value) in a hierarchy of dictionaries. Typically used for setting values in JSON data.

    Args:
        json_dict (dict): Hierarchical dictionary of values
        path (list): A list of strings indicating where to create the key.
        value (various): Optional data to set at the indicated path

    Returns:
        None
    """
    cur_dict = json_dict
    for name in path[:-1]:
        if name not in cur_dict:
            cur_dict[name] = {}
        cur_dict = cur_dict[name]
    cur_dict[path[-1]] = value


def get_farm_config_dict(farm_name):
    json_dict = load_global_config()
    return json_dict["farm"][farm_name]


def get_nodes_config_dict(farm_name):
    farm_dict = get_farm_config_dict(farm_name)
    return farm_dict["nodes"]


def get_include_config_dict(farm_name):
    farm_dict = get_farm_config_dict(farm_name)
    return farm_dict["include_blocks"]


def get_node_parameter_list(farm_name, rop_node):
    node_context = get_rop_context_name(rop_node)
    node_type = rop_node.type().name().lower()

    context_dict = get_nodes_config_dict(farm_name)

    if node_context not in context_dict:
        return None    
    nodes_dict = context_dict[node_context]
    
    if node_type not in nodes_dict:
        return None
    return nodes_dict[node_type]


def get_config_parameter_list(farm_name, rop_node):
    """
    Retrieves the parameter layout for a particular farm integration and a particular node.

    Args:
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        rop_node (hou.Node): A ROP node (in any context)

    Returns:
        List: A list of parameter definitions
    """

    parm_list = get_node_parameter_list(farm_name, rop_node)
    if parm_list is None:
        return None
    include_dict = get_include_config_dict(farm_name)
    nodes_dict = get_nodes_config_dict(farm_name)
    return expand_json_include_blocks(nodes_dict, parm_list, include_dict)


def set_config_parameter_list(farm_name, json_dict, rop_node, parameter_list):
    """
    Sets parameter data for a specified node and farm.

    Args:
        farm_name (str): Name of the farm integration. Lowercase. Must match the name of the farm module. E.g. "deadline"
        json_dict (dict): Hierarchical dictionary of values
        rop_node (hou.Node): A ROP node (in any context)
        parameter_list (list): Parameter list

    Returns:
        None
    """
    node_context = get_rop_context_name()
    node_type = rop_node.type().name()

    set_dict_path(json_dict, ["farm", farm_name, "nodes", node_context, node_type], parameter_list)
